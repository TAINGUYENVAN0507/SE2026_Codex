"""Kiểm thử xử lý lỗi một phần: diarization fallback và summary lỗi (BE-08, BE-10, RT-02, RT-04).

Bao gồm:
- RT-02: Khi diarize fallback, meeting vẫn ready và job thành công với diarize='fallback'.
- RT-04: Khi summarize gặp lỗi permanent, meeting chuyển sang 'partial', transcript vẫn đọc được.
"""

import uuid
from collections.abc import Generator
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select
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
        email="partial_user@example.com",
        display_name="Partial User",
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
        title="Cuộc họp kiểm thử partial results",
        audio_path=f"audio/{meeting_id}/original.wav",
        source="upload",
        status="running",
    )
    test_db.add(meeting)
    test_db.commit()
    return meeting


def test_rt02_diarization_fallback_meeting_ready(
    test_db: Session,
    sample_meeting_with_audio: Meeting,
    test_storage: Storage,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """RT-02: diarize lỗi ở lượt cuối thì fallback 1 speaker, meeting ready và job succeeded."""
    monkeypatch.setenv("FAKE_SCENARIO", "diarize_fail")

    meeting = sample_meeting_with_audio
    # Tạo job ở lượt cuối (attempt=3, max_attempts=3) để kích hoạt fallback
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
    assert job.status == JobStatus.SUCCEEDED.value
    assert job.stage_status is not None
    assert job.stage_status.get("diarize") == "fallback"

    test_db.refresh(meeting)
    assert meeting.status == "ready"

    # Transcript vẫn được persist đầy đủ
    segments = (
        test_db.execute(select(Segment).where(Segment.meeting_id == meeting.id)).scalars().all()
    )
    assert len(segments) > 0


def test_rt04_summary_fail_meeting_partial_transcript_readable(
    test_db: Session,
    sample_meeting_with_audio: Meeting,
    test_storage: Storage,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """RT-04: summarize lỗi permanent thì meeting chuyển sang 'partial', transcript vẫn đọc được."""
    monkeypatch.setenv("FAKE_SCENARIO", "summary_fail")

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
    assert job.error_code == "LLM_REQUEST_INVALID"

    test_db.refresh(meeting)
    # Cuộc họp có trạng thái partial vì transcript đã hoàn tất trước khi summarize lỗi
    assert meeting.status == "partial"

    # Transcript vẫn đọc được từ cơ sở dữ liệu
    segments = (
        test_db.execute(select(Segment).where(Segment.meeting_id == meeting.id)).scalars().all()
    )
    assert len(segments) > 0
    speakers = (
        test_db.execute(select(Speaker).where(Speaker.meeting_id == meeting.id)).scalars().all()
    )
    assert len(speakers) > 0
