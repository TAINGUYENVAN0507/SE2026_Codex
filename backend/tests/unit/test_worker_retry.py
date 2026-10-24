"""Kiểm thử chính sách retry và backoff của worker (BE-08, RT-01, RT-03, RT-05).

Bao gồm:
- Tính toán backoff: 30 s -> 2' (120 s) -> 8' (480 s) ±20%.
- RT-03: Lỗi permanent (PermanentPipelineError) thì failed ngay, không retry.
- RT-01: Lỗi transient / timeout thì chuyển sang retry_scheduled kèm lịch next_run_at.
- RT-05: Khi vượt quá số lần thử tối đa (max_attempts) thì job chuyển sang failed.
"""

import uuid
from collections.abc import Generator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.models.action_item import ActionItem
from app.db.models.ai_output import AIOutput
from app.db.models.job import Job
from app.db.models.meeting import Meeting
from app.db.models.summary import Summary
from app.db.models.transcript import Segment, Speaker
from app.db.models.user import User
from app.services.storage import Storage
from app.services.storage.local import LocalStorage
from app.worker.queue import JobStatus, enqueue_job
from app.worker.retry import compute_backoff_delay
from app.worker.runner import run_worker_once


@pytest.fixture
def test_db() -> Generator[Session, None, None]:
    """Tạo database SQLite in-memory dùng cho test."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    tables = [
        User.__table__,
        Meeting.__table__,
        Job.__table__,
        AIOutput.__table__,
        Speaker.__table__,
        Segment.__table__,
        Summary.__table__,
        ActionItem.__table__,
    ]
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
def test_storage(tmp_path: Path) -> Storage:
    """Tạo LocalStorage với thư mục tạm tmp_path."""
    return LocalStorage(base_dir=tmp_path)


@pytest.fixture
def sample_user(test_db: Session) -> User:
    """Tạo user mẫu."""
    user = User(
        id=str(uuid.uuid4()),
        email="retry_user@example.com",
        display_name="Retry User",
        password_hash="hash",
    )
    test_db.add(user)
    test_db.commit()
    return user


@pytest.fixture
def sample_meeting_with_audio(
    test_db: Session,
    sample_user: User,
    test_storage: Storage,
) -> Meeting:
    """Tạo meeting mẫu có sẵn tệp âm thanh giả định."""
    meeting_id = str(uuid.uuid4())
    audio_dir = test_storage.base_dir / "audio" / meeting_id
    audio_dir.mkdir(parents=True, exist_ok=True)
    audio_file = audio_dir / "original.wav"
    audio_file.write_bytes(b"RIFFdummywavdata")

    meeting = Meeting(
        id=meeting_id,
        owner_id=sample_user.id,
        title="Cuộc họp kiểm thử retry",
        audio_path=f"audio/{meeting_id}/original.wav",
        source="upload",
        status="running",
    )
    test_db.add(meeting)
    test_db.commit()
    return meeting


def test_backoff_delay_calculation() -> None:
    """Kiểm tra thời gian chờ backoff chuẩn và có jitter ±20%."""
    # Khi không có jitter
    assert compute_backoff_delay(1, with_jitter=False) == 30.0
    assert compute_backoff_delay(2, with_jitter=False) == 120.0
    assert compute_backoff_delay(3, with_jitter=False) == 480.0
    assert compute_backoff_delay(4, with_jitter=False) == 480.0

    # Khi có jitter ±20%
    for _ in range(20):
        d1 = compute_backoff_delay(1, with_jitter=True)
        assert 24.0 <= d1 <= 36.0

        d2 = compute_backoff_delay(2, with_jitter=True)
        assert 96.0 <= d2 <= 144.0

        d3 = compute_backoff_delay(3, with_jitter=True)
        assert 384.0 <= d3 <= 576.0


def test_rt03_permanent_pipeline_error_fails_immediately(
    test_db: Session,
    sample_meeting_with_audio: Meeting,
    test_storage: Storage,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """RT-03: Lỗi permanent (PermanentPipelineError) khiến job failed ngay, không retry."""
    monkeypatch.setenv("FAKE_SCENARIO", "permanent")

    meeting = sample_meeting_with_audio
    job = enqueue_job(test_db, meeting_id=meeting.id, max_attempts=3)
    test_db.commit()

    ran = run_worker_once(
        test_db,
        storage=test_storage,
        worker_id="test-worker",
        backend="fake",
    )
    assert ran is True

    test_db.refresh(job)
    assert job.status == JobStatus.FAILED.value
    assert job.attempt == 1
    assert job.error_code == "AUDIO_INVALID"
    assert job.next_run_at is None
    assert job.locked_by is None

    test_db.refresh(meeting)
    assert meeting.status == "failed"


def test_rt01_transient_error_schedules_retry(
    test_db: Session,
    sample_meeting_with_audio: Meeting,
    test_storage: Storage,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """RT-01: Lỗi transient ở lần chạy 1 lên lịch retry_scheduled với backoff."""
    monkeypatch.setenv("FAKE_SCENARIO", "transient_once")

    meeting = sample_meeting_with_audio
    job = enqueue_job(test_db, meeting_id=meeting.id, max_attempts=3)
    test_db.commit()

    base_time = datetime(2026, 10, 24, 12, 0, 0, tzinfo=UTC)

    ran = run_worker_once(
        test_db,
        storage=test_storage,
        worker_id="test-worker",
        backend="fake",
        now=base_time,
    )
    assert ran is True

    test_db.refresh(job)
    # Job chuyển sang retry_scheduled
    assert job.status == JobStatus.RETRY_SCHEDULED.value
    assert job.attempt == 2  # schedule_retry tăng attempt lên 2
    assert job.locked_by is None
    assert job.locked_until is None
    assert job.next_run_at is not None

    # Thời gian hẹn nằm trong khoảng 30s ± 20%
    diff_sec = (job.next_run_at.replace(tzinfo=UTC) - base_time).total_seconds()
    assert 24.0 <= diff_sec <= 36.0

    # Meeting vẫn giữ trạng thái running
    test_db.refresh(meeting)
    assert meeting.status == "running"


def test_rt05_transient_error_max_attempts_exceeded(
    test_db: Session,
    sample_meeting_with_audio: Meeting,
    test_storage: Storage,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """RT-05: Lỗi transient khi đã đạt max_attempts thì job chuyển sang failed."""
    monkeypatch.setenv("FAKE_SCENARIO", "transient_once")

    meeting = sample_meeting_with_audio
    # Tạo job đã ở lượt thử cuối (attempt=3, max_attempts=3)
    job = Job(
        id=str(uuid.uuid4()),
        meeting_id=meeting.id,
        status=JobStatus.QUEUED.value,
        attempt=3,
        max_attempts=3,
    )
    test_db.add(job)
    test_db.commit()

    ran = run_worker_once(
        test_db,
        storage=test_storage,
        worker_id="test-worker",
        backend="fake",
    )
    assert ran is True

    test_db.refresh(job)
    assert job.status == JobStatus.FAILED.value
    assert job.locked_by is None

    test_db.refresh(meeting)
    assert meeting.status == "failed"
