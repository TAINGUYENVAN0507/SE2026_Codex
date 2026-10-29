"""Kiểm thử lease, heartbeat và reaper (BE-08, RT-08, RT-09).

Bao gồm:
- RT-08: Worker chết giữa chừng thì reaper đưa job hết hạn lease về queued và tăng attempt.
- Khi vượt quá max_attempts thì reaper chuyển job sang failed với LEASE_TIMEOUT.
- RT-09: Worker nhận SIGTERM thì trả lease về queued mà không tăng attempt.
- Heartbeat định kỳ gia hạn thời gian locked_until.
"""

import uuid
from collections.abc import Generator
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.models.job import Job
from app.db.models.meeting import Meeting
from app.db.models.user import User
from app.worker.queue import JobStatus
from app.worker.reaper import (
    DEFAULT_LEASE_SEC,
    LeaseLostError,
    heartbeat_job,
    reap_expired_jobs,
    release_job_on_sigterm,
)


@pytest.fixture
def test_db() -> Generator[Session, None, None]:
    """Tạo database SQLite in-memory dùng cho test."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    tables = [User.__table__, Meeting.__table__, Job.__table__]
    Base.metadata.create_all(bind=engine, tables=tables)
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = session_factory()

    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine, tables=tables)
        engine.dispose()


@pytest.fixture
def sample_user(test_db: Session) -> User:
    """Tạo user mẫu."""
    user = User(
        id=str(uuid.uuid4()),
        email="reaper_user@example.com",
        display_name="Reaper User",
        password_hash="hash",
    )
    test_db.add(user)
    test_db.commit()
    return user


@pytest.fixture
def sample_meeting(test_db: Session, sample_user: User) -> Meeting:
    """Tạo meeting mẫu."""
    meeting = Meeting(
        id=str(uuid.uuid4()),
        owner_id=sample_user.id,
        title="Cuộc họp kiểm thử reaper",
        source="upload",
        status="running",
    )
    test_db.add(meeting)
    test_db.commit()
    return meeting


def test_rt08_worker_crashes_and_reaper_requeues_job(
    test_db: Session,
    sample_meeting: Meeting,
) -> None:
    """RT-08: Worker chết giữa chừng thì job hết lease được requeue và tăng attempt."""
    base_time = datetime(2026, 10, 24, 10, 0, 0, tzinfo=UTC)

    # Job đang chạy với locked_until là base_time + 60s
    job = Job(
        id=str(uuid.uuid4()),
        meeting_id=sample_meeting.id,
        status=JobStatus.RUNNING.value,
        attempt=1,
        max_attempts=3,
        locked_by="crashed-worker",
        locked_until=base_time + timedelta(seconds=60),
        heartbeat_at=base_time,
        created_at=base_time,
        updated_at=base_time,
    )
    test_db.add(job)
    test_db.commit()

    # 1. Lúc chưa hết hạn lease (base_time + 30s): reaper không làm gì
    clock_30s = base_time + timedelta(seconds=30)
    reaped = reap_expired_jobs(test_db, now=clock_30s)
    assert len(reaped) == 0

    test_db.refresh(job)
    assert job.status == JobStatus.RUNNING.value
    assert job.attempt == 1

    # 2. Worker chết, quá hạn lease (base_time + 65s): reaper thu hồi
    clock_65s = base_time + timedelta(seconds=65)
    reaped = reap_expired_jobs(test_db, now=clock_65s)
    assert len(reaped) == 1
    assert reaped[0].id == job.id

    test_db.refresh(job)
    assert job.status == JobStatus.QUEUED.value
    assert job.attempt == 2
    assert job.locked_by is None
    assert job.locked_until is None


def test_reaper_fails_job_when_max_attempts_exceeded(
    test_db: Session,
    sample_meeting: Meeting,
) -> None:
    """Khi job đã thử hết số lần cho phép (attempt=3/3) thì reaper đánh dấu failed."""
    base_time = datetime(2026, 10, 24, 10, 0, 0, tzinfo=UTC)

    job = Job(
        id=str(uuid.uuid4()),
        meeting_id=sample_meeting.id,
        status=JobStatus.RUNNING.value,
        attempt=3,
        max_attempts=3,
        locked_by="crashed-worker-3",
        locked_until=base_time + timedelta(seconds=60),
        heartbeat_at=base_time,
        created_at=base_time,
        updated_at=base_time,
    )
    test_db.add(job)
    test_db.commit()

    clock_after = base_time + timedelta(seconds=70)
    reaped = reap_expired_jobs(test_db, now=clock_after)
    assert len(reaped) == 1

    test_db.refresh(job)
    assert job.status == JobStatus.FAILED.value
    assert job.error_code == "LEASE_TIMEOUT"
    assert "vượt quá thời gian lease" in job.error_message
    assert job.locked_by is None
    assert job.locked_until is None


def test_rt09_sigterm_releases_lease_without_incrementing_attempt(
    test_db: Session,
    sample_meeting: Meeting,
) -> None:
    """RT-09: Khi worker nhận SIGTERM, job được trả về queued và KHÔNG tăng attempt."""
    base_time = datetime(2026, 10, 24, 10, 0, 0, tzinfo=UTC)

    job = Job(
        id=str(uuid.uuid4()),
        meeting_id=sample_meeting.id,
        status=JobStatus.RUNNING.value,
        attempt=1,
        max_attempts=3,
        locked_by="graceful-worker",
        locked_until=base_time + timedelta(seconds=DEFAULT_LEASE_SEC),
        heartbeat_at=base_time,
        created_at=base_time,
        updated_at=base_time,
    )
    test_db.add(job)
    test_db.commit()

    # Nhận SIGTERM
    release_job_on_sigterm(test_db, job, now=base_time + timedelta(seconds=10))

    test_db.refresh(job)
    assert job.status == JobStatus.QUEUED.value
    assert job.attempt == 1  # Không tăng attempt
    assert job.locked_by is None
    assert job.locked_until is None


def test_heartbeat_extends_lease(
    test_db: Session,
    sample_meeting: Meeting,
) -> None:
    """Heartbeat cập nhật heartbeat_at và gia hạn locked_until thêm 60 giây."""
    base_time = datetime(2026, 10, 24, 10, 0, 0, tzinfo=UTC)

    job = Job(
        id=str(uuid.uuid4()),
        meeting_id=sample_meeting.id,
        status=JobStatus.RUNNING.value,
        attempt=1,
        max_attempts=3,
        locked_by="active-worker",
        locked_until=base_time + timedelta(seconds=DEFAULT_LEASE_SEC),
        heartbeat_at=base_time,
        created_at=base_time,
        updated_at=base_time,
    )
    test_db.add(job)
    test_db.commit()

    # Sau 15s, gửi heartbeat
    hb_time = base_time + timedelta(seconds=15)
    heartbeat_job(test_db, job, lease_duration_sec=DEFAULT_LEASE_SEC, now=hb_time)

    test_db.refresh(job)
    assert job.heartbeat_at.replace(tzinfo=UTC) == hb_time
    assert job.locked_until.replace(tzinfo=UTC) == hb_time + timedelta(seconds=DEFAULT_LEASE_SEC)


def test_heartbeat_raises_lease_lost_when_reaped_to_queued(
    test_db: Session,
    sample_meeting: Meeting,
) -> None:
    """BE-08: Khi reaper đã thu hồi job về queued, heartbeat ném LeaseLostError."""
    base_time = datetime(2026, 10, 24, 10, 0, 0, tzinfo=UTC)

    job = Job(
        id=str(uuid.uuid4()),
        meeting_id=sample_meeting.id,
        status=JobStatus.RUNNING.value,
        attempt=1,
        max_attempts=3,
        locked_by="worker-1",
        locked_until=base_time + timedelta(seconds=DEFAULT_LEASE_SEC),
        heartbeat_at=base_time,
        created_at=base_time,
        updated_at=base_time,
    )
    test_db.add(job)
    test_db.commit()

    # Reaper thu hồi job về queued vì hết lease
    clock_expired = base_time + timedelta(seconds=65)
    reaped = reap_expired_jobs(test_db, now=clock_expired)
    assert len(reaped) == 1

    # Worker-1 kết nối lại và cố gửi heartbeat -> ném LeaseLostError
    with pytest.raises(LeaseLostError, match="lease was lost"):
        heartbeat_job(test_db, job, now=clock_expired + timedelta(seconds=5), worker_id="worker-1")

    # Đảm bảo DB không bị ghi đè: job vẫn ở trạng thái queued và locked_by=None
    test_db.refresh(job)
    assert job.status == JobStatus.QUEUED.value
    assert job.locked_by is None
    assert job.locked_until is None


def test_heartbeat_raises_lease_lost_when_claimed_by_another_worker(
    test_db: Session,
    sample_meeting: Meeting,
) -> None:
    """BE-08: Khi worker khác đã claim job, heartbeat của worker cũ ném LeaseLostError."""
    base_time = datetime(2026, 10, 24, 10, 0, 0, tzinfo=UTC)

    job = Job(
        id=str(uuid.uuid4()),
        meeting_id=sample_meeting.id,
        status=JobStatus.RUNNING.value,
        attempt=1,
        max_attempts=3,
        locked_by="worker-1",
        locked_until=base_time + timedelta(seconds=DEFAULT_LEASE_SEC),
        heartbeat_at=base_time,
        created_at=base_time,
        updated_at=base_time,
    )
    test_db.add(job)
    test_db.commit()

    # Reaper thu hồi job về queued
    reap_expired_jobs(test_db, now=base_time + timedelta(seconds=65))

    # Worker-2 claim job này
    job.status = JobStatus.RUNNING.value
    job.locked_by = "worker-2"
    job.locked_until = base_time + timedelta(seconds=125)
    test_db.commit()

    # Worker-1 gửi heartbeat với danh tính worker-1 -> ném LeaseLostError
    with pytest.raises(LeaseLostError, match="lease was lost"):
        heartbeat_job(test_db, job, now=base_time + timedelta(seconds=70), worker_id="worker-1")

    # Đảm bảo khóa của worker-2 không bị worker-1 ghi đè
    test_db.refresh(job)
    assert job.locked_by == "worker-2"
    assert job.locked_until.replace(tzinfo=UTC) == base_time + timedelta(seconds=125)
