"""Bộ điều phối chạy pipeline và xử lý Job cho Worker (BE-06).

Tuân thủ nghiêm ngặt ranh giới module:
- Chỉ worker được import `meeting_pipeline`.
- Chỉ sử dụng `run_job`, `JobSpec`, `Stage`, `overall_progress`
  và các exception từ `meeting_pipeline.errors`.
- Cập nhật tiến độ `stage` và `progress` vào DB tối đa 1 lần mỗi giây (throttling).
"""

import logging
import os
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
from meeting_pipeline.schemas import JobSpec
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models.job import Job
from app.db.models.meeting import Meeting
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
    heartbeat_job,
    reap_expired_jobs,
    release_job_on_sigterm,
)
from app.worker.retry import compute_backoff_delay

logger = logging.getLogger("backend.worker")

PROGRESS_THROTTLE_SEC = 1.0


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

    def check_cancelled() -> bool:
        if sigterm_check and sigterm_check():
            return True
        return bool(is_cancelled and is_cancelled())

    def handle_heartbeat() -> None:
        heartbeat_job(db, job, lease_duration_sec=DEFAULT_LEASE_SEC, now=get_now())

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

    spec = JobSpec(
        meeting_id=meeting.id,
        job_id=job.id,
        audio_path=str(audio_file.resolve()),
        from_stage=from_stage_val,
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
            job.stage = stage.value
            job.progress = calc_progress

            stages = dict(job.stage_status or {})
            stages[stage.value] = "running" if value < 1.0 else "succeeded"
            job.stage_status = stages

            cur_time = get_now()
            job.heartbeat_at = cur_time
            job.locked_until = cur_time + timedelta(seconds=DEFAULT_LEASE_SEC)
            job.updated_at = cur_time
            db.commit()
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

        job.stage_status = {k.value: v for k, v in outcome.stage_status.items()}
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

    except PipelineCancelledError:
        if sigterm_check and sigterm_check():
            logger.info("Worker nhận SIGTERM: giải phóng job %s về queued", job.id)
            release_job_on_sigterm(db, job, now=get_now())
        else:
            logger.info("Job %s đã bị hủy", job.id)
            transition_job_status(job, JobStatus.CANCELLED, now=get_now())
            db.commit()

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
