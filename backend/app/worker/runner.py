"""Bộ điều phối chạy pipeline và xử lý Job cho Worker (BE-06).

Tuân thủ nghiêm ngặt ranh giới module:
- Chỉ worker được import `meeting_pipeline`.
- Chỉ sử dụng `run_job`, `JobSpec`, `Stage`, `overall_progress`
  và các exception từ `meeting_pipeline.errors`.
- Cập nhật tiến độ `stage` và `progress` vào DB tối đa 1 lần mỗi giây (throttling).
"""

import logging
import os
import shutil
import time
from collections.abc import Callable, Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path

from meeting_pipeline.errors import (
    PermanentPipelineError,
    PipelineCancelledError,
    PipelineError,
    TransientPipelineError,
)
from meeting_pipeline.runner import Stage, overall_progress, run_job
from meeting_pipeline.schemas import JobSpec, Transcript
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models.ai_output import AIOutput
from app.db.models.job import Job
from app.db.models.meeting import Meeting
from app.db.models.transcript import Segment, Speaker
from app.services.storage import Storage
from app.worker.persister import persist_summary, persist_transcript
from app.worker.queue import (
    JobStatus,
    claim_job,
    complete_job,
    fail_job,
    schedule_retry,
    transition_job_status,
)
from app.worker.reaper import (
    DEFAULT_LEASE_SEC,
    DEFAULT_REAPER_INTERVAL_SEC,
    LeaseLostError,
    heartbeat_job,
    reap_expired_jobs,
    release_job_on_sigterm,
)
from app.worker.retry import compute_backoff_delay

logger = logging.getLogger("backend.worker")

PROGRESS_THROTTLE_SEC = 1.0


def export_transcript_override(db: Session, meeting: Meeting, workdir: Path) -> Path:
    """Xuất transcript hiện tại trong DB thành file JSON theo transcript.schema.json.

    Dùng cho stage summarize khi chạy lại từ transcript đã được người dùng chỉnh sửa.
    """
    # 1. Lấy thông tin audio, models, diarization_status từ ai_outputs của stage merge
    ai_output = (
        db.execute(
            select(AIOutput)
            .where(
                AIOutput.meeting_id == meeting.id,
                AIOutput.stage == "merge",
            )
            .order_by(AIOutput.created_at.desc())
        )
        .scalars()
        .first()
    )

    merge_payload = ai_output.payload if ai_output and isinstance(ai_output.payload, dict) else {}

    # 2. Lấy danh sách segments và speakers từ DB
    segments_db = (
        db.execute(select(Segment).where(Segment.meeting_id == meeting.id).order_by(Segment.idx))
        .scalars()
        .all()
    )

    speakers_db = (
        db.execute(select(Speaker).where(Speaker.meeting_id == meeting.id)).scalars().all()
    )
    speaker_map = {spk.id: spk for spk in speakers_db}

    # Tính duration_sec an toàn
    max_seg_end = max((seg.end_sec for seg in segments_db), default=0.0)
    base_duration = float(meeting.duration_sec or 0.0)
    duration_sec = max(base_duration, max_seg_end + 1.0, 1.0)

    audio_info = merge_payload.get("audio") or {
        "duration_sec": duration_sec,
        "sample_rate": 16000,
        "channels": 1,
    }
    if audio_info.get("duration_sec", 0.0) < max_seg_end:
        audio_info["duration_sec"] = max_seg_end + 1.0

    models_info = merge_payload.get("models") or {
        "asr": "whisper",
        "diarization": "pyannote",
    }
    diarization_status = merge_payload.get("diarization_status", "ok")
    warnings_info = merge_payload.get("warnings", [])

    # Tính first_start_sec cho mỗi speaker
    speaker_first_start: dict[str, float] = {}
    for seg in segments_db:
        if seg.speaker_id and seg.speaker_id not in speaker_first_start:
            speaker_first_start[seg.speaker_id] = seg.start_sec

    # Danh sách speakers kèm display_name
    speakers_list = []
    for spk in speakers_db:
        speakers_list.append(
            {
                "label": spk.label,
                "first_start_sec": speaker_first_start.get(spk.id, 0.0),
                "display_name": spk.display_name,
            }
        )

    # Danh sách segments kèm text và speaker đã sửa
    segments_list = []
    for seg in segments_db:
        spk_obj = speaker_map.get(seg.speaker_id) if seg.speaker_id else None
        speaker_label = spk_obj.label if spk_obj else None

        flags: list[str] = []
        if isinstance(seg.flags, dict):
            flags = list(seg.flags.get("flags", []))
        elif isinstance(seg.flags, list):
            flags = list(seg.flags)

        orig_words: list[dict] = []
        if merge_payload and "segments" in merge_payload:
            orig_segs = merge_payload["segments"]
            if 0 <= seg.idx < len(orig_segs) and isinstance(orig_segs[seg.idx], dict):
                orig_words = orig_segs[seg.idx].get("words", [])

        segments_list.append(
            {
                "index": seg.idx,
                "start_sec": seg.start_sec,
                "end_sec": seg.end_sec,
                "speaker_label": speaker_label,
                "text": seg.text,
                "confidence": seg.confidence,
                "flags": flags,
                "words": orig_words,
            }
        )

    # Gắn cờ overlap nếu có đoạn nào chồng lấn để đảm bảo bất biến của schema
    for prev, cur in zip(segments_list, segments_list[1:], strict=False):
        if cur["start_sec"] < prev["end_sec"]:
            if "overlap" not in prev["flags"]:
                prev["flags"].append("overlap")
            if "overlap" not in cur["flags"]:
                cur["flags"].append("overlap")

    transcript_dict = {
        "schema_version": "1.0",
        "audio": audio_info,
        "models": models_info,
        "diarization_status": diarization_status,
        "speakers": speakers_list,
        "segments": segments_list,
        "warnings": warnings_info,
    }

    transcript_obj = Transcript.model_validate(transcript_dict)
    override_path = workdir / "transcript_override.json"
    override_path.write_text(transcript_obj.model_dump_json(indent=2), encoding="utf-8")
    return override_path


def process_job(
    db: Session,
    job: Job,
    storage: Storage,
    backend: str | None = None,
    on_stage_done_callback: Callable[[Stage, Path], None] | None = None,
    is_cancelled: Callable[[], bool] | None = None,
    sigterm_check: Callable[[], bool] | None = None,
    heartbeat_sec: float = 15.0,
    clock: Callable[[], datetime] | None = None,
    now: datetime | None = None,
    env: Mapping[str, str] | None = None,
) -> Job:
    """Thực thi pipeline cho một Job đã được claim."""

    def get_now() -> datetime:
        if clock is not None:
            return clock()
        if now is not None:
            return now
        return datetime.now(UTC)

    last_cancel_db_check = 0.0
    cached_db_cancelled = False

    def check_cancelled() -> bool:
        nonlocal last_cancel_db_check, cached_db_cancelled
        if cached_db_cancelled:
            return True
        if sigterm_check and sigterm_check():
            return True
        if is_cancelled and is_cancelled():
            return True

        now_m = time.monotonic()
        if now_m - last_cancel_db_check >= 1.0:
            last_cancel_db_check = now_m
            try:
                cur_status = db.execute(
                    select(Job.status).where(Job.id == job.id)
                ).scalar_one_or_none()
                if cur_status is None or cur_status == JobStatus.CANCELLED.value:
                    cached_db_cancelled = True
                    return True
            except Exception:
                pass
        return False

    current_worker_id = job.locked_by

    def handle_heartbeat() -> None:
        heartbeat_job(
            db,
            job,
            lease_duration_sec=DEFAULT_LEASE_SEC,
            now=get_now(),
            worker_id=current_worker_id,
        )

    meeting = db.get(Meeting, job.meeting_id)
    if meeting is None:
        fail_job(
            db,
            job,
            error_code="MEETING_NOT_FOUND",
            error_message="Không tìm thấy cuộc họp",
            now=get_now(),
        )
        return job

    pipeline_backend = backend if backend is not None else os.getenv("PIPELINE_BACKEND")

    # Xác định đường dẫn audio gốc
    clean_ext = (
        meeting.audio_path.rsplit(".", 1)[-1].lower()
        if meeting.audio_path and "." in meeting.audio_path
        else "wav"
    )
    audio_file = storage.get_audio_path(meeting.id, clean_ext)
    if not audio_file.is_file() and hasattr(storage, "base_dir") and meeting.audio_path:
        fallback = Path(storage.base_dir) / meeting.audio_path
        if fallback.is_file():
            audio_file = fallback

    # Thư mục workdir chứa artifacts
    base_storage_dir = getattr(storage, "base_dir", Path("appdata"))
    workdir = Path(base_storage_dir) / "artifacts" / meeting.id / job.id
    workdir.mkdir(parents=True, exist_ok=True)

    from_stage_val: Stage | None = None
    if job.from_stage:
        try:
            from_stage_val = Stage(job.from_stage)
        except ValueError:
            from_stage_val = None

    transcript_override_path: str | None = None
    if from_stage_val is Stage.SUMMARIZE:
        override_file = export_transcript_override(db, meeting, workdir)
        transcript_override_path = str(override_file.resolve())

    spec = JobSpec(
        meeting_id=meeting.id,
        job_id=job.id,
        audio_path=str(audio_file.resolve()),
        from_stage=from_stage_val,
        transcript_override_path=transcript_override_path,
        num_speakers_hint=meeting.num_speakers_hint,
        meeting_date=meeting.meeting_date,
        language="vi",
        attempt=job.attempt,
        max_attempts=job.max_attempts,
    )

    settings = get_settings()
    pipeline_env = dict(env or {})
    if "PIPELINE_MAX_DURATION_SEC" not in pipeline_env:
        pipeline_env["PIPELINE_MAX_DURATION_SEC"] = str(settings.MAX_DURATION_SEC)

    last_db_update = 0.0

    def handle_progress(stage: Stage, value: float) -> None:
        nonlocal last_db_update
        now_ts = time.monotonic()
        # Throttling: chỉ ghi DB tối đa 1 lần mỗi giây hoặc khi stage hoàn thành (value=1.0)
        if (now_ts - last_db_update >= PROGRESS_THROTTLE_SEC) or value >= 1.0:
            calc_progress = overall_progress(stage, value)
            stages = dict(job.stage_status or {})
            stages[stage.value] = "running" if value < 1.0 else "succeeded"

            cur_time = get_now()
            res = db.execute(
                update(Job)
                .where(
                    Job.id == job.id,
                    Job.status == JobStatus.RUNNING.value,
                    Job.locked_by == current_worker_id,
                )
                .values(
                    stage=stage.value,
                    progress=calc_progress,
                    stage_status=stages,
                    heartbeat_at=cur_time,
                    locked_until=cur_time + timedelta(seconds=DEFAULT_LEASE_SEC),
                    updated_at=cur_time,
                )
            )
            if res.rowcount == 0:
                db.rollback()
                logger.warning(
                    "Job %s đã mất lease khi cập nhật tiến độ (worker=%s). Dừng job.",
                    job.id,
                    current_worker_id,
                )
                raise LeaseLostError(f"Lease for job {job.id} was lost during progress update")

            db.commit()
            job.stage = stage.value
            job.progress = calc_progress
            job.stage_status = stages
            job.heartbeat_at = cur_time
            job.locked_until = cur_time + timedelta(seconds=DEFAULT_LEASE_SEC)
            job.updated_at = cur_time
            last_db_update = now_ts

    def handle_stage_done(stage: Stage, artifact_file: Path) -> None:
        if stage == Stage.MERGE:
            persist_transcript(
                db,
                meeting_id=meeting.id,
                job_id=job.id,
                artifact_path=artifact_file,
            )
        elif stage == Stage.SUMMARIZE:
            persist_summary(
                db,
                meeting_id=meeting.id,
                job_id=job.id,
                artifact_path=artifact_file,
            )
        if on_stage_done_callback:
            on_stage_done_callback(stage, artifact_file)

    try:
        outcome = run_job(
            spec,
            workdir=workdir,
            on_progress=handle_progress,
            on_stage_done=handle_stage_done,
            is_cancelled=check_cancelled,
            on_heartbeat=handle_heartbeat,
            heartbeat_sec=heartbeat_sec,
            backend=pipeline_backend,
            env=pipeline_env,
        )

        merged_stages = dict(job.stage_status or {})
        for k, v in outcome.stage_status.items():
            merged_stages[k.value] = v
        job.stage_status = merged_stages
        complete_job(db, job, now=get_now())
        meeting.status = "ready"
        meeting.updated_at = get_now()
        db.commit()

    except PermanentPipelineError as err:
        logger.error("Job %s gặp lỗi vĩnh viễn: %s", job.id, err)
        fail_job(db, job, error_code=err.code.value, error_message=err.message, now=get_now())
        if err.stage == Stage.SUMMARIZE:
            meeting.status = "partial"
        else:
            meeting.status = "failed"
        meeting.updated_at = get_now()
        db.commit()

    except TransientPipelineError as err:
        logger.warning(
            "Job %s gặp lỗi tạm thời: %s (attempt=%d/%d)",
            job.id,
            err,
            job.attempt,
            job.max_attempts,
        )
        current_time = get_now()
        if job.attempt < job.max_attempts:
            delay_sec = compute_backoff_delay(job.attempt)
            next_run = current_time + timedelta(seconds=delay_sec)
            schedule_retry(
                db,
                job,
                next_run_at=next_run,
                error_code=err.code.value,
                error_message=err.message,
                now=current_time,
            )
        else:
            fail_job(
                db,
                job,
                error_code=err.code.value,
                error_message=err.message,
                now=current_time,
            )
            if err.stage == Stage.SUMMARIZE:
                meeting.status = "partial"
            else:
                meeting.status = "failed"
            meeting.updated_at = current_time
            db.commit()

    except LeaseLostError as err:
        logger.warning(
            "Worker đã mất lease cho job %s (worker=%s): %s. "
            "Dừng xử lý mà không ghi kết quả hay đổi trạng thái.",
            job.id,
            current_worker_id,
            err,
        )
        return job

    except PipelineCancelledError:
        if sigterm_check and sigterm_check():
            logger.info("Worker nhận SIGTERM: giải phóng job %s về queued", job.id)
            release_job_on_sigterm(db, job, now=get_now())
        else:
            logger.info("Job %s đã bị hủy", job.id)
            existing_job = db.execute(select(Job).where(Job.id == job.id)).scalar_one_or_none()
            if existing_job is not None:
                transition_job_status(existing_job, JobStatus.CANCELLED, now=get_now())
                db.commit()
            job.status = JobStatus.CANCELLED.value
            if workdir.exists():
                shutil.rmtree(workdir, ignore_errors=True)

    except PipelineError as err:
        logger.error("Job %s gặp lỗi pipeline: %s", job.id, err)
        fail_job(db, job, error_code=err.code.value, error_message=err.message, now=get_now())
        meeting.status = "failed"
        meeting.updated_at = get_now()
        db.commit()

    return job


def run_worker_once(
    db: Session,
    storage: Storage,
    worker_id: str = "worker-default",
    backend: str | None = None,
    on_stage_done_callback: Callable[[Stage, Path], None] | None = None,
    is_cancelled: Callable[[], bool] | None = None,
    sigterm_check: Callable[[], bool] | None = None,
    heartbeat_sec: float = 15.0,
    clock: Callable[[], datetime] | None = None,
    now: datetime | None = None,
    env: Mapping[str, str] | None = None,
) -> bool:
    """Claim một job từ hàng đợi và thực thi tiến trình xử lý.

    Returns:
        True nếu đã claim và xử lý 1 job; False nếu hàng đợi rỗng.
    """
    job = claim_job(db, worker_id=worker_id, now=now or (clock() if clock else None))
    if job is None:
        return False

    process_job(
        db,
        job,
        storage=storage,
        backend=backend,
        on_stage_done_callback=on_stage_done_callback,
        is_cancelled=is_cancelled,
        sigterm_check=sigterm_check,
        heartbeat_sec=heartbeat_sec,
        clock=clock,
        now=now,
        env=env,
    )
    return True


def run_worker_loop(
    poll_interval_sec: float = 2.0,
    worker_id: str | None = None,
    backend: str | None = None,
    reaper_interval_sec: float = DEFAULT_REAPER_INTERVAL_SEC,
) -> None:
    """Vòng lặp thực thi của Worker: định kỳ claim job, chạy pipeline và quét reaper."""
    import signal

    from app.db.session import get_session_factory
    from app.services.storage import get_storage

    w_id = worker_id or f"worker-{os.getpid()}"
    storage = get_storage()
    session_factory = get_session_factory()
    configured_backend = backend or os.getenv("PIPELINE_BACKEND") or "real"
    logger.info(
        "Khởi động worker loop %s (poll_interval=%ss, backend=%s)",
        w_id,
        poll_interval_sec,
        configured_backend,
    )

    running = True
    sigterm_received = False

    def _handle_signal(sig, frame):
        nonlocal running, sigterm_received
        logger.info("Worker %s nhận tín hiệu dừng (%s), đang tắt...", w_id, sig)
        running = False
        sigterm_received = True

    signal.signal(signal.SIGINT, _handle_signal)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, _handle_signal)

    last_reaper_run = 0.0

    while running:
        with session_factory() as db:
            now_mono = time.monotonic()
            if now_mono - last_reaper_run >= reaper_interval_sec:
                try:
                    reaped = reap_expired_jobs(db)
                    if reaped:
                        logger.info("Reaper đã thu hồi %d job hết hạn", len(reaped))
                except Exception as e:
                    logger.error("Lỗi khi chạy reaper trong worker: %s", e)
                last_reaper_run = now_mono

            try:
                processed = run_worker_once(
                    db,
                    storage=storage,
                    worker_id=w_id,
                    backend=backend,
                    sigterm_check=lambda: sigterm_received,
                )
                if not processed and running:
                    time.sleep(poll_interval_sec)
            except Exception as e:
                logger.error("Lỗi không mong muốn trong worker loop: %s", e)
                if running:
                    time.sleep(poll_interval_sec)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_worker_loop()
