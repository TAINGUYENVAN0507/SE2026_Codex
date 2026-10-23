"""Quản lý hàng đợi công việc và máy trạng thái (State Machine) của Job (BE-06).

Triển khai:
- Định nghĩa các trạng thái và ma trận chuyển đổi trạng thái hợp lệ.
- Claim job sẵn sàng thực thi bằng SELECT ... FOR UPDATE SKIP LOCKED.
- Enqueue, chuyển trạng thái và cập nhật thông tin khóa lease.
"""

import uuid
from datetime import UTC, datetime, timedelta
from enum import StrEnum

from sqlalchemy import and_, or_, select, update
from sqlalchemy.orm import Session

from app.db.models.job import Job


class JobStatus(StrEnum):
    """Các trạng thái hợp lệ của Job."""

    QUEUED = "queued"
    RUNNING = "running"
    RETRY_SCHEDULED = "retry_scheduled"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class InvalidJobStateTransitionError(Exception):
    """Ngoại lệ khi chuyển đổi trạng thái Job không hợp lệ."""

    def __init__(
        self,
        current_status: str,
        target_status: str,
        job_id: str | None = None,
    ) -> None:
        ident = f"của job {job_id} " if job_id else ""
        message = (
            f"Không thể chuyển đổi trạng thái {ident}từ '{current_status}' sang '{target_status}'."
        )
        super().__init__(message)
        self.current_status = current_status
        self.target_status = target_status
        self.job_id = job_id


# Ma trận các bước chuyển đổi trạng thái hợp lệ
VALID_TRANSITIONS: dict[JobStatus, set[JobStatus]] = {
    JobStatus.QUEUED: {JobStatus.RUNNING, JobStatus.CANCELLED},
    JobStatus.RUNNING: {
        JobStatus.SUCCEEDED,
        JobStatus.FAILED,
        JobStatus.RETRY_SCHEDULED,
        JobStatus.QUEUED,  # Khi reaper thu hồi lease hết hạn
        JobStatus.CANCELLED,
    },
    JobStatus.RETRY_SCHEDULED: {
        JobStatus.RUNNING,
        JobStatus.CANCELLED,
        JobStatus.FAILED,
    },
    JobStatus.FAILED: {
        JobStatus.QUEUED,  # Khi người dùng chủ động yêu cầu retry
    },
    JobStatus.CANCELLED: {
        JobStatus.QUEUED,  # Khi người dùng chủ động yêu cầu chạy lại
    },
    # Trạng thái succeeded là terminal: không thể chuyển sang bất kỳ trạng thái nào khác
    JobStatus.SUCCEEDED: set(),
}


def validate_transition(
    current_status: str | JobStatus,
    target_status: str | JobStatus,
    job_id: str | None = None,
) -> None:
    """Kiểm tra tính hợp lệ của việc chuyển đổi trạng thái.

    Raises:
        InvalidJobStateTransitionError: Nếu bước chuyển đổi trạng thái vi phạm quy định.
    """
    try:
        curr = JobStatus(current_status)
    except ValueError:
        raise InvalidJobStateTransitionError(
            str(current_status), str(target_status), job_id
        ) from None

    try:
        tgt = JobStatus(target_status)
    except ValueError:
        raise InvalidJobStateTransitionError(
            str(current_status), str(target_status), job_id
        ) from None

    allowed = VALID_TRANSITIONS.get(curr, set())
    if tgt not in allowed:
        raise InvalidJobStateTransitionError(curr.value, tgt.value, job_id)


def transition_job_status(
    job: Job,
    target_status: str | JobStatus,
    now: datetime | None = None,
) -> None:
    """Cập nhật trạng thái của Job sau khi đã kiểm tra qua máy trạng thái."""
    validate_transition(job.status, target_status, job_id=job.id)
    tgt = JobStatus(target_status)
    current_time = now or datetime.now(UTC)

    job.status = tgt.value
    job.updated_at = current_time

    # Nếu quay về queued (từ reaper hoặc user retry), xóa lịch hẹn cũ
    if tgt == JobStatus.QUEUED:
        job.next_run_at = None
        job.locked_by = None
        job.locked_until = None

    # Nếu hoàn thành hoặc hủy bỏ thì giải phóng khóa
    if tgt in (JobStatus.SUCCEEDED, JobStatus.FAILED, JobStatus.CANCELLED):
        job.locked_by = None
        job.locked_until = None


def enqueue_job(
    db: Session,
    meeting_id: str,
    from_stage: str | None = None,
    max_attempts: int = 3,
    now: datetime | None = None,
) -> Job:
    """Đưa một Job mới vào hàng đợi ở trạng thái queued."""
    current_time = now or datetime.now(UTC)
    job = Job(
        id=str(uuid.uuid4()),
        meeting_id=meeting_id,
        status=JobStatus.QUEUED.value,
        from_stage=from_stage,
        stage=from_stage or "preprocess",
        progress=0.0,
        attempt=1,
        max_attempts=max_attempts,
        created_at=current_time,
        updated_at=current_time,
    )
    db.add(job)
    return job


def claim_job(
    db: Session,
    worker_id: str,
    lease_duration_sec: int = 60,
    now: datetime | None = None,
) -> Job | None:
    """Tìm và claim một job sẵn sàng thực thi bằng SELECT ... FOR UPDATE SKIP LOCKED.

    Tiêu chí chọn:
    1. Trạng thái 'queued' và (next_run_at IS NULL hoặc next_run_at <= now).
    2. HOẶC trạng thái 'retry_scheduled' và next_run_at <= now.
    3. Sắp xếp theo created_at tăng dần.
    """
    current_time = now or datetime.now(UTC)

    stmt = (
        select(Job)
        .where(
            or_(
                and_(
                    Job.status == JobStatus.QUEUED.value,
                    or_(Job.next_run_at.is_(None), Job.next_run_at <= current_time),
                ),
                and_(
                    Job.status == JobStatus.RETRY_SCHEDULED.value,
                    Job.next_run_at <= current_time,
                ),
            )
        )
        .order_by(Job.created_at.asc())
        .limit(1)
        .with_for_update(skip_locked=True)
    )

    candidate = db.execute(stmt).scalar_one_or_none()
    if candidate is None:
        return None

    validate_transition(candidate.status, JobStatus.RUNNING, job_id=candidate.id)

    # Thực hiện atomic update có điều kiện để bảo vệ chống race-condition
    res = db.execute(
        update(Job)
        .where(
            Job.id == candidate.id,
            Job.status == candidate.status,
        )
        .values(
            status=JobStatus.RUNNING.value,
            locked_by=worker_id,
            locked_until=current_time + timedelta(seconds=lease_duration_sec),
            heartbeat_at=current_time,
            updated_at=current_time,
        )
    )
    if res.rowcount == 0:
        db.rollback()
        return None

    db.commit()
    db.refresh(candidate)
    return candidate


def complete_job(
    db: Session,
    job: Job,
    now: datetime | None = None,
) -> None:
    """Đánh dấu job đã hoàn thành thành công và mở khóa."""
    transition_job_status(job, JobStatus.SUCCEEDED, now=now)
    job.progress = 1.0
    job.locked_by = None
    job.locked_until = None
    db.commit()


def fail_job(
    db: Session,
    job: Job,
    error_code: str,
    error_message: str,
    now: datetime | None = None,
) -> None:
    """Đánh dấu job thất bại và mở khóa."""
    transition_job_status(job, JobStatus.FAILED, now=now)
    job.error_code = error_code
    job.error_message = error_message
    job.locked_by = None
    job.locked_until = None
    db.commit()


def schedule_retry(
    db: Session,
    job: Job,
    next_run_at: datetime,
    error_code: str | None = None,
    error_message: str | None = None,
    now: datetime | None = None,
) -> None:
    """Lên lịch chạy lại (retry) cho job với thời điểm next_run_at."""
    transition_job_status(job, JobStatus.RETRY_SCHEDULED, now=now)
    job.next_run_at = next_run_at
    job.attempt += 1
    job.error_code = error_code
    job.error_message = error_message
    job.locked_by = None
    job.locked_until = None
    db.commit()


def release_job_lock(
    db: Session,
    job: Job,
    now: datetime | None = None,
) -> None:
    """Giải phóng khóa lease của job khi worker tắt máy hoặc hủy xử lý."""
    current_time = now or datetime.now(UTC)
    job.locked_by = None
    job.locked_until = None
    job.updated_at = current_time
    db.commit()
