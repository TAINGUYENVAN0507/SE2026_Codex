"""Kiểm thử máy trạng thái và hàng đợi Job của Worker (BE-06).

Bao gồm:
- Các bước chuyển đổi trạng thái hợp lệ và không hợp lệ (State Machine).
- Enqueue và claim job theo thứ tự thời gian.
- Lọc theo next_run_at cho job retry_scheduled.
- Hai worker claim đồng thời không bao giờ lấy trùng job.
- Hoàn tất (complete), thất bại (fail), lên lịch retry và nhả lock.
"""

import threading
import uuid
from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.db.models.job import Job
from app.db.models.meeting import Meeting
from app.db.models.user import User
from app.worker.queue import (
    InvalidJobStateTransitionError,
    JobStatus,
    claim_job,
    complete_job,
    enqueue_job,
    fail_job,
    release_job_lock,
    schedule_retry,
    transition_job_status,
    validate_transition,
)


@pytest.fixture
def sqlite_db_path(tmp_path: Path) -> Path:
    """Tạo file database SQLite tạm thời cho test đa luồng."""
    return tmp_path / "test_queue.db"


@pytest.fixture
def engine(sqlite_db_path: Path):
    """Engine SQLite hỗ trợ đa kết nối."""
    eng = create_engine(
        f"sqlite:///{sqlite_db_path}",
        connect_args={"check_same_thread": False, "timeout": 30.0},
    )
    Base.metadata.create_all(bind=eng, tables=[User.__table__, Meeting.__table__, Job.__table__])
    try:
        yield eng
    finally:
        eng.dispose()


@pytest.fixture
def session_factory(engine) -> sessionmaker[Session]:
    """Factory sinh Session cho từng worker/thread."""
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture
def db_session(session_factory: sessionmaker[Session]) -> Generator[Session, None, None]:
    """Session chính dùng thiết lập fixture."""
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def sample_meeting(db_session: Session) -> Meeting:
    """Tạo user và meeting mẫu để gắn job."""
    user = User(
        id=str(uuid.uuid4()),
        email="worker_user@example.com",
        display_name="Worker User",
        password_hash="hash",
    )
    db_session.add(user)
    db_session.commit()

    meeting = Meeting(
        id=str(uuid.uuid4()),
        owner_id=user.id,
        title="Cuộc họp test queue",
    )
    db_session.add(meeting)
    db_session.commit()
    return meeting


def test_valid_state_transitions() -> None:
    """Kiểm tra các bước chuyển đổi trạng thái hợp lệ."""
    # queued -> running, cancelled
    validate_transition(JobStatus.QUEUED, JobStatus.RUNNING)
    validate_transition(JobStatus.QUEUED, JobStatus.CANCELLED)

    # running -> succeeded, failed, retry_scheduled, queued, cancelled
    validate_transition(JobStatus.RUNNING, JobStatus.SUCCEEDED)
    validate_transition(JobStatus.RUNNING, JobStatus.FAILED)
    validate_transition(JobStatus.RUNNING, JobStatus.RETRY_SCHEDULED)
    validate_transition(JobStatus.RUNNING, JobStatus.QUEUED)
    validate_transition(JobStatus.RUNNING, JobStatus.CANCELLED)

    # retry_scheduled -> running, cancelled, failed
    validate_transition(JobStatus.RETRY_SCHEDULED, JobStatus.RUNNING)
    validate_transition(JobStatus.RETRY_SCHEDULED, JobStatus.CANCELLED)
    validate_transition(JobStatus.RETRY_SCHEDULED, JobStatus.FAILED)

    # failed -> queued
    validate_transition(JobStatus.FAILED, JobStatus.QUEUED)

    # cancelled -> queued
    validate_transition(JobStatus.CANCELLED, JobStatus.QUEUED)


def test_invalid_state_transitions() -> None:
    """Kiểm tra các bước chuyển đổi trạng thái sai bị từ chối."""
    # Succeeded là terminal: không thể chuyển sang running
    with pytest.raises(InvalidJobStateTransitionError) as exc_info:
        validate_transition(JobStatus.SUCCEEDED, JobStatus.RUNNING)
    assert exc_info.value.current_status == "succeeded"
    assert exc_info.value.target_status == "running"

    # Succeeded không thể chuyển sang queued
    with pytest.raises(InvalidJobStateTransitionError):
        validate_transition(JobStatus.SUCCEEDED, JobStatus.QUEUED)

    # Queued không thể nhảy cóc sang succeeded
    with pytest.raises(InvalidJobStateTransitionError):
        validate_transition(JobStatus.QUEUED, JobStatus.SUCCEEDED)

    # Queued không thể nhảy cóc sang retry_scheduled
    with pytest.raises(InvalidJobStateTransitionError):
        validate_transition(JobStatus.QUEUED, JobStatus.RETRY_SCHEDULED)


def test_transition_job_status_helper(sample_meeting: Meeting, db_session: Session) -> None:
    """Hàm transition_job_status cập nhật trường và giải phóng khóa khi kết thúc."""
    job = enqueue_job(db_session, meeting_id=sample_meeting.id)
    db_session.commit()

    # queued -> running
    transition_job_status(job, JobStatus.RUNNING)
    job.locked_by = "worker-1"
    job.locked_until = datetime.now(UTC) + timedelta(seconds=60)
    db_session.commit()
    assert job.status == "running"

    # running -> succeeded: tự động mở khóa
    transition_job_status(job, JobStatus.SUCCEEDED)
    db_session.commit()
    assert job.status == "succeeded"
    assert job.locked_by is None
    assert job.locked_until is None


def test_claim_job_basic(sample_meeting: Meeting, db_session: Session) -> None:
    """Claim job queued thành công và ghi nhận thông tin khóa lease."""
    job = enqueue_job(db_session, meeting_id=sample_meeting.id)
    db_session.commit()

    now = datetime(2026, 10, 24, 8, 0, 0, tzinfo=UTC)
    claimed = claim_job(db_session, worker_id="worker-node-1", lease_duration_sec=60, now=now)

    assert claimed is not None
    assert claimed.id == job.id
    assert claimed.status == "running"
    assert claimed.locked_by == "worker-node-1"

    expected_locked_until = now + timedelta(seconds=60)
    actual_locked_until = (
        claimed.locked_until.replace(tzinfo=UTC)
        if claimed.locked_until and claimed.locked_until.tzinfo is None
        else claimed.locked_until
    )
    assert actual_locked_until == expected_locked_until

    actual_heartbeat = (
        claimed.heartbeat_at.replace(tzinfo=UTC)
        if claimed.heartbeat_at and claimed.heartbeat_at.tzinfo is None
        else claimed.heartbeat_at
    )
    assert actual_heartbeat == now

    # Thử claim lại khi không còn job nào sẵn sàng -> trả về None
    claimed_again = claim_job(db_session, worker_id="worker-node-2", now=now)
    assert claimed_again is None


def test_claim_job_retry_scheduled_respects_next_run_at(
    sample_meeting: Meeting, db_session: Session
) -> None:
    """Job retry_scheduled chỉ được claim khi thời điểm hiện tại >= next_run_at."""
    schedule_time = datetime(2026, 10, 24, 10, 0, 0, tzinfo=UTC)
    job = enqueue_job(db_session, meeting_id=sample_meeting.id)
    job.status = JobStatus.RETRY_SCHEDULED.value
    job.next_run_at = schedule_time
    db_session.commit()

    # Thời điểm sớm hơn next_run_at (9:59) -> Chưa được claim
    early_now = datetime(2026, 10, 24, 9, 59, 59, tzinfo=UTC)
    res = claim_job(db_session, worker_id="worker-1", now=early_now)
    assert res is None

    # Thời điểm đúng hoặc sau next_run_at (10:00) -> Được claim
    exact_now = datetime(2026, 10, 24, 10, 0, 0, tzinfo=UTC)
    claimed = claim_job(db_session, worker_id="worker-1", now=exact_now)
    assert claimed is not None
    assert claimed.id == job.id
    assert claimed.status == "running"


def test_two_workers_claim_parallel_no_duplicate(
    sample_meeting: Meeting,
    session_factory: sessionmaker[Session],
    db_session: Session,
) -> None:
    """Hai worker claim đồng thời không bao giờ lấy trùng cùng một job."""
    # Tạo 1 job duy nhất
    job = enqueue_job(db_session, meeting_id=sample_meeting.id)
    db_session.commit()
    job_id = job.id

    claimed_ids: list[str] = []
    lock = threading.Lock()

    def worker_claim(worker_id: str) -> None:
        session = session_factory()
        try:
            res = claim_job(session, worker_id=worker_id)
            if res:
                with lock:
                    claimed_ids.append(res.id)
        finally:
            session.close()

    with ThreadPoolExecutor(max_workers=2) as executor:
        f1 = executor.submit(worker_claim, "worker-A")
        f2 = executor.submit(worker_claim, "worker-B")
        f1.result()
        f2.result()

    # Chỉ duy nhất 1 worker claim được job này
    assert len(claimed_ids) == 1
    assert claimed_ids[0] == job_id


def test_complete_and_fail_and_schedule_retry(sample_meeting: Meeting, db_session: Session) -> None:
    """Kiểm tra các hàm phụ trợ complete_job, fail_job, schedule_retry."""
    enqueue_job(db_session, meeting_id=sample_meeting.id)
    db_session.commit()

    claimed = claim_job(db_session, worker_id="w1")
    assert claimed is not None

    # Test schedule_retry
    retry_time = datetime(2026, 10, 24, 12, 0, 0, tzinfo=UTC)
    schedule_retry(
        db_session,
        claimed,
        next_run_at=retry_time,
        error_code="AUDIO_TRANSCRIPTION_FAILED",
        error_message="Lỗi tạm thời",
    )
    assert claimed.status == "retry_scheduled"
    assert claimed.attempt == 2
    assert claimed.error_code == "AUDIO_TRANSCRIPTION_FAILED"
    assert claimed.locked_by is None

    # Claim lại sau retry
    claimed_2 = claim_job(db_session, worker_id="w2", now=retry_time + timedelta(seconds=1))
    assert claimed_2 is not None

    # Test fail_job
    fail_job(
        db_session,
        claimed_2,
        error_code="PERMANENT_ERROR",
        error_message="Lỗi nghiêm trọng",
    )
    assert claimed_2.status == "failed"
    assert claimed_2.error_code == "PERMANENT_ERROR"
    assert claimed_2.locked_by is None

    # Từ failed user retry lại: chuyển sang queued
    transition_job_status(claimed_2, JobStatus.QUEUED)
    db_session.commit()

    # Claim lại và complete_job
    claimed_3 = claim_job(db_session, worker_id="w3")
    assert claimed_3 is not None
    complete_job(db_session, claimed_3)
    assert claimed_3.status == "succeeded"
    assert claimed_3.progress == 1.0
    assert claimed_3.locked_by is None


def test_release_job_lock(sample_meeting: Meeting, db_session: Session) -> None:
    """Hàm release_job_lock giải phóng locked_by và locked_until."""
    enqueue_job(db_session, meeting_id=sample_meeting.id)
    db_session.commit()

    claimed = claim_job(db_session, worker_id="w-temp")
    assert claimed is not None
    assert claimed.locked_by == "w-temp"

    release_job_lock(db_session, claimed)
    assert claimed.locked_by is None
    assert claimed.locked_until is None
