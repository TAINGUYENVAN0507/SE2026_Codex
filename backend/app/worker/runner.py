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
from collections.abc import Callable
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
from app.worker.retry import compute_backoff_delay

logger = logging.getLogger("backend.worker")

PROGRESS_THROTTLE_SEC = 1.0


def process_job(
    db: Session,
    job: Job,
    storage: Storage,
    backend: str | None = None,
    on_stage_done_callback: Callable[[Stage, Path], None] | None = None,
    now: datetime | None = None,
) -> Job:
    """Thực thi pipeline cho một Job đã được claim."""
    meeting = db.get(Meeting, job.meeting_id)
    if meeting is None:
        fail_job(db, job, error_code="MEETING_NOT_FOUND", error_message="Không tìm thấy cuộc họp")
        return job

    pipeline_backend = backend or os.getenv("PIPELINE_BACKEND", "fake")

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

    last_db_update = 0.0

    def handle_progress(stage: Stage, value: float) -> None:
        nonlocal last_db_update
        now = time.monotonic()
        # Throttling: chỉ ghi DB tối đa 1 lần mỗi giây hoặc khi stage hoàn thành (value=1.0)
        if (now - last_db_update >= PROGRESS_THROTTLE_SEC) or value >= 1.0:
            calc_progress = overall_progress(stage, value)
            job.stage = stage.value
            job.progress = calc_progress

            stages = dict(job.stage_status or {})
            stages[stage.value] = "running" if value < 1.0 else "succeeded"
            job.stage_status = stages

            job.heartbeat_at = datetime.now(UTC)
            job.updated_at = datetime.now(UTC)
            db.commit()
            last_db_update = now

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
            backend=pipeline_backend,
        )

        job.stage_status = {k.value: v for k, v in outcome.stage_status.items()}
        complete_job(db, job)
        meeting.status = "ready"
        meeting.updated_at = datetime.now(UTC)
        db.commit()

    except PermanentPipelineError as err:
        logger.error("Job %s gặp lỗi vĩnh viễn: %s", job.id, err)
        fail_job(db, job, error_code=err.code.value, error_message=err.message)
        if err.stage == Stage.SUMMARIZE:
            meeting.status = "partial"
        else:
            meeting.status = "failed"
        meeting.updated_at = datetime.now(UTC)
        db.commit()

    except TransientPipelineError as err:
        logger.warning(
            "Job %s gặp lỗi tạm thời: %s (attempt=%d/%d)",
            job.id,
            err,
            job.attempt,
            job.max_attempts,
        )
        current_time = now or datetime.now(UTC)
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
        logger.info("Job %s đã bị hủy", job.id)
        transition_job_status(job, JobStatus.CANCELLED)
        db.commit()

    except PipelineError as err:
        logger.error("Job %s gặp lỗi pipeline: %s", job.id, err)
        fail_job(db, job, error_code=err.code.value, error_message=err.message)
        meeting.status = "failed"
        meeting.updated_at = datetime.now(UTC)
        db.commit()

    return job


def run_worker_once(
    db: Session,
    storage: Storage,
    worker_id: str = "worker-default",
    backend: str | None = None,
    on_stage_done_callback: Callable[[Stage, Path], None] | None = None,
    now: datetime | None = None,
) -> bool:
    """Claim một job từ hàng đợi và thực thi tiến trình xử lý.

    Returns:
        True nếu đã claim và xử lý 1 job; False nếu hàng đợi rỗng.
    """
    job = claim_job(db, worker_id=worker_id, now=now)
    if job is None:
        return False

    process_job(
        db,
        job,
        storage=storage,
        backend=backend,
        on_stage_done_callback=on_stage_done_callback,
        now=now,
    )
    return True
