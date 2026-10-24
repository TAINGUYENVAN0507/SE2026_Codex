"""Quản lý lease, heartbeat và reaper thu hồi job bị treo hoặc quá hạn lease (BE-08).

Quy ước:
- lease_duration: 60 s
- heartbeat_interval: 15 s
- reaper_interval: 30 s
- Khi reaper phát hiện job RUNNING có locked_until < now (hết lease):
  - Nếu attempt < max_attempts: đưa về 'queued', tăng attempt thêm 1, giải phóng khóa.
  - Nếu attempt >= max_attempts: chuyển sang 'failed' với mã lỗi 'LEASE_TIMEOUT'.
- Khi worker nhận SIGTERM (graceful shutdown):
  - Trả lease đưa job về 'queued', KHÔNG tăng attempt.
- Mọi hàm đều hỗ trợ tham số clock `now` để dễ dàng kiểm thử với clock giả.
"""

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.job import Job
from app.worker.queue import JobStatus, fail_job, transition_job_status

logger = logging.getLogger("backend.worker.reaper")

DEFAULT_LEASE_SEC = 60
DEFAULT_HEARTBEAT_SEC = 15
DEFAULT_REAPER_INTERVAL_SEC = 30


def heartbeat_job(
    db: Session,
    job: Job,
    lease_duration_sec: int = DEFAULT_LEASE_SEC,
    now: datetime | None = None,
) -> None:
    """Cập nhật heartbeat cho job đang chạy và gia hạn thời hạn lease."""
    current_time = now or datetime.now(UTC)
    job.heartbeat_at = current_time
    job.locked_until = current_time + timedelta(seconds=lease_duration_sec)
    job.updated_at = current_time
    db.commit()


def reap_expired_jobs(
    db: Session,
    now: datetime | None = None,
) -> list[Job]:
    """Tìm và xử lý các job đang chạy nhưng đã hết hạn lease (worker chết giữa chừng).

    Trả về danh sách các job đã được thu hồi và cập nhật.
    """
    current_time = now or datetime.now(UTC)

    stmt = select(Job).where(
        Job.status == JobStatus.RUNNING.value,
        Job.locked_until.is_not(None),
        Job.locked_until < current_time,
    )
    expired_jobs = db.execute(stmt).scalars().all()
    reaped: list[Job] = []

    for job in expired_jobs:
        if job.attempt < job.max_attempts:
            logger.warning(
                "Job %s hết hạn lease (locked_until=%s), đưa về queued và tăng attempt %d -> %d",
                job.id,
                job.locked_until,
                job.attempt,
                job.attempt + 1,
            )
            job.attempt += 1
            transition_job_status(job, JobStatus.QUEUED, now=current_time)
            reaped.append(job)
        else:
            logger.error(
                "Job %s hết hạn lease và đã đạt số lần thử tối đa (%d/%d), chuyển sang failed",
                job.id,
                job.attempt,
                job.max_attempts,
            )
            fail_job(
                db,
                job,
                error_code="LEASE_TIMEOUT",
                error_message=(
                    f"Job vượt quá thời gian lease ({DEFAULT_LEASE_SEC}s) và đã thử tối đa "
                    f"{job.max_attempts} lần"
                ),
                now=current_time,
            )
            reaped.append(job)

    if reaped:
        db.commit()

    return reaped


def release_job_on_sigterm(
    db: Session,
    job: Job,
    now: datetime | None = None,
) -> None:
    """Xử lý khi worker nhận SIGTERM: đưa job về queued mà KHÔNG tăng attempt."""
    current_time = now or datetime.now(UTC)
    logger.info("Worker nhận SIGTERM: giải phóng job %s về queued mà không tăng attempt", job.id)
    transition_job_status(job, JobStatus.QUEUED, now=current_time)
    db.commit()
