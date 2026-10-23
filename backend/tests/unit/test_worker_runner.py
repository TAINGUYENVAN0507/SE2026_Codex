"""Kiểm thử worker chạy pipeline qua run_job với backend fake (BE-06).

Bao gồm:
- Job ở trạng thái queued được claim và xử lý hoàn tất qua fake pipeline.
- File job.json và các artifact được sinh trong artifacts/{meeting_id}/{job_id}/.
- Trạng thái job chuyển thành succeeded và meeting chuyển thành ready.
- Cập nhật tiến độ progress và stage_status.
"""

import json
import uuid
from collections.abc import Generator
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.models.job import Job
from app.db.models.meeting import Meeting
from app.db.models.user import User
from app.services.storage import Storage
from app.services.storage.local import LocalStorage
from app.worker.queue import enqueue_job
from app.worker.runner import run_worker_once


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
def test_storage(tmp_path: Path) -> Storage:
    """Tạo LocalStorage với thư mục tạm tmp_path."""
    return LocalStorage(base_dir=tmp_path)


@pytest.fixture
def sample_user(test_db: Session) -> User:
    """Tạo user mẫu."""
    user = User(
        id=str(uuid.uuid4()),
        email="worker_runner@example.com",
        display_name="Worker Runner",
        password_hash="hash",
    )
    test_db.add(user)
    test_db.commit()
    return user


@pytest.fixture
def sample_meeting_with_audio(
    test_db: Session, sample_user: User, test_storage: Storage
) -> Meeting:
    """Tạo meeting mẫu có tệp âm thanh hợp lệ trong storage."""
    meeting_id = str(uuid.uuid4())
    audio_data = b"RIFF....WAVEfmt ...."  # Dữ liệu giả lập

    res = test_storage.save_upload(meeting_id=meeting_id, extension="wav", stream=audio_data)

    meeting = Meeting(
        id=meeting_id,
        owner_id=sample_user.id,
        title="Cuộc họp kiểm thử fake pipeline",
        source="upload",
        status="queued",
        duration_sec=60.0,
        audio_path=res.path,
        audio_sha256=res.sha256,
        version=1,
    )
    test_db.add(meeting)
    test_db.commit()
    return meeting


def test_worker_run_queued_job_to_succeeded(
    test_db: Session,
    sample_meeting_with_audio: Meeting,
    test_storage: Storage,
) -> None:
    """Job queued được claim và chạy hết fake pipeline thành công."""
    meeting = sample_meeting_with_audio
    job = enqueue_job(test_db, meeting_id=meeting.id)
    test_db.commit()
    job_id = job.id

    stages_done: list[str] = []

    def on_stage_done(stage, artifact_path):
        stages_done.append(stage.value)
        assert artifact_path.is_file()

    # Worker chạy 1 vòng lặp claim và xử lý
    ran = run_worker_once(
        test_db,
        storage=test_storage,
        worker_id="test-worker-1",
        backend="fake",
        on_stage_done_callback=on_stage_done,
    )
    assert ran is True

    # Kiểm tra job trong database
    test_db.refresh(job)
    assert job.status == "succeeded"
    assert job.progress == 1.0
    assert job.locked_by is None
    assert job.locked_until is None

    # Kiểm tra meeting
    test_db.refresh(meeting)
    assert meeting.status == "ready"

    # Kiểm tra các stage đã hoàn thành
    expected_stages = ["preprocess", "vad", "asr", "diarize", "merge", "summarize"]
    assert stages_done == expected_stages

    # Kiểm tra thư mục workdir và file job.json
    workdir = test_storage.base_dir / "artifacts" / meeting.id / job_id
    assert workdir.is_dir()

    job_json_file = workdir / "job.json"
    assert job_json_file.is_file()

    with open(job_json_file, encoding="utf-8") as f:
        job_data = json.load(f)
    assert job_data["meeting_id"] == meeting.id
    assert job_data["job_id"] == job_id

    # Kiểm tra các artifact JSON của từng stage đã sinh ra
    assert (workdir / "preprocess.json").is_file()
    assert (workdir / "vad.json").is_file()
    assert (workdir / "asr.json").is_file()
    assert (workdir / "diarization.json").is_file()
    assert (workdir / "transcript.json").is_file()
    assert (workdir / "summary.json").is_file()


def test_worker_run_empty_queue(
    test_db: Session,
    test_storage: Storage,
) -> None:
    """Khi hàng đợi không có job nào, run_worker_once trả về False."""
    ran = run_worker_once(
        test_db,
        storage=test_storage,
        worker_id="test-worker-1",
        backend="fake",
    )
    assert ran is False
