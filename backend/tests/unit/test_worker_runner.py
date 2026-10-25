"""Kiểm thử worker chạy pipeline qua run_job với backend fake (BE-06).

Bao gồm:
- Job ở trạng thái queued được claim và xử lý hoàn tất qua fake pipeline.
- File job.json và các artifact được sinh trong artifacts/{meeting_id}/{job_id}/.
- Trạng thái job chuyển thành succeeded và meeting chuyển thành ready.
- Cập nhật tiến độ progress và stage_status.
"""

import json
import os
import uuid
from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock

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
from app.worker.queue import claim_job, enqueue_job
from app.worker.reaper import reap_expired_jobs
from app.worker.runner import process_job, run_job, run_worker_loop, run_worker_once


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

    # Kiểm tra summary và action items đã được persist vào cơ sở dữ liệu
    summary_record = test_db.execute(
        select(Summary).where(Summary.meeting_id == meeting.id)
    ).scalar_one_or_none()
    assert summary_record is not None
    assert summary_record.status == "ready"

    action_items = (
        test_db.execute(select(ActionItem).where(ActionItem.meeting_id == meeting.id))
        .scalars()
        .all()
    )
    assert len(action_items) > 0


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


def test_worker_job_extends_lease_with_heartbeat_over_3_minutes(
    test_db: Session,
    sample_meeting_with_audio: Meeting,
    test_storage: Storage,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Job chạy với thời gian mô phỏng 3 phút (vượt quá lease 60s) vẫn giữ lease nhờ heartbeat."""
    base_time = datetime(2026, 10, 24, 10, 0, 0, tzinfo=UTC)
    current_fake_time = [base_time]

    def fake_clock() -> datetime:
        return current_fake_time[0]

    enqueue_job(test_db, meeting_id=sample_meeting_with_audio.id, now=base_time)
    test_db.commit()

    claimed = claim_job(test_db, worker_id="test-worker", now=base_time)
    assert claimed is not None

    heartbeat_count = [0]

    def on_stage_done_hook(stage, path):
        test_db.refresh(claimed)
        assert claimed.locked_until is not None
        assert claimed.locked_until.replace(tzinfo=UTC) > current_fake_time[0]

    original_run_job = run_job

    def intercept_run_job(*args, **kwargs):
        user_heartbeat = kwargs.get("on_heartbeat")

        def wrapped_heartbeat():
            heartbeat_count[0] += 1
            current_fake_time[0] += timedelta(seconds=30)
            if user_heartbeat:
                user_heartbeat()

        kwargs["on_heartbeat"] = wrapped_heartbeat
        kwargs["heartbeat_sec"] = 0.01
        return original_run_job(*args, **kwargs)

    monkeypatch.setattr("app.worker.runner.run_job", intercept_run_job)

    process_job(
        test_db,
        claimed,
        storage=test_storage,
        backend="fake",
        on_stage_done_callback=on_stage_done_hook,
        clock=fake_clock,
    )

    test_db.refresh(claimed)
    assert claimed.status == "succeeded"
    assert heartbeat_count[0] >= 6
    assert (current_fake_time[0] - base_time).total_seconds() >= 180


def test_worker_crashes_and_reaper_requeues(
    test_db: Session,
    sample_meeting_with_audio: Meeting,
) -> None:
    """Worker chết không gửi heartbeat thì reaper thu hồi job và tăng attempt."""
    base_time = datetime(2026, 10, 24, 10, 0, 0, tzinfo=UTC)
    enqueue_job(test_db, meeting_id=sample_meeting_with_audio.id, now=base_time)
    test_db.commit()

    claimed = claim_job(test_db, worker_id="crashed-worker", now=base_time)
    assert claimed is not None
    assert claimed.attempt == 1
    assert claimed.locked_until.replace(tzinfo=UTC) == base_time + timedelta(seconds=60)

    # Worker chết, không có heartbeat nào. Thời gian trôi qua 65s (hết lease 60s)
    later = base_time + timedelta(seconds=65)
    reaped = reap_expired_jobs(test_db, now=later)
    assert len(reaped) == 1
    assert reaped[0].id == claimed.id

    test_db.refresh(claimed)
    assert claimed.status == "queued"
    assert claimed.attempt == 2
    assert claimed.locked_by is None
    assert claimed.locked_until is None


def test_worker_sigterm_releases_job_to_queued_without_incrementing_attempt(
    test_db: Session,
    sample_meeting_with_audio: Meeting,
    test_storage: Storage,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """RT-09: Khi worker nhận SIGTERM giữa chừng, stage dừng và job về queued."""
    base_time = datetime(2026, 10, 24, 10, 0, 0, tzinfo=UTC)
    enqueue_job(test_db, meeting_id=sample_meeting_with_audio.id, now=base_time)
    test_db.commit()

    claimed = claim_job(test_db, worker_id="sigterm-worker", now=base_time)
    assert claimed is not None
    assert claimed.attempt == 1

    sigterm_triggered = [False]

    def fake_sigterm_check() -> bool:
        return sigterm_triggered[0]

    def on_stage_done_hook(stage, path):
        if stage.value == "preprocess":
            sigterm_triggered[0] = True

    monkeypatch.setenv("FAKE_STAGE_SLEEP_SEC", "1")

    process_job(
        test_db,
        claimed,
        storage=test_storage,
        backend="fake",
        on_stage_done_callback=on_stage_done_hook,
        sigterm_check=fake_sigterm_check,
        now=base_time,
    )

    test_db.refresh(claimed)
    assert claimed.status == "queued"
    assert claimed.attempt == 1
    assert claimed.locked_by is None
    assert claimed.locked_until is None


def test_run_worker_loop_calls_reaper(monkeypatch: pytest.MonkeyPatch) -> None:
    """run_worker_loop định kỳ gọi reap_expired_jobs mỗi 30s."""
    reap_called = [0]

    def mock_reap(db, now=None):
        reap_called[0] += 1
        return []

    monkeypatch.setattr("app.worker.runner.reap_expired_jobs", mock_reap)
    monkeypatch.setattr("app.worker.runner.run_worker_once", lambda *args, **kwargs: False)

    loop_count = 0

    class FakeSessionLocal:
        def __enter__(self):
            return MagicMock()

        def __exit__(self, exc_type, exc_val, exc_tb):
            pass

    monkeypatch.setattr("app.db.session.get_session_factory", lambda: FakeSessionLocal)

    def mock_sleep(sec):
        nonlocal loop_count
        loop_count += 1
        if loop_count >= 2:
            raise KeyboardInterrupt()

    monkeypatch.setattr("time.sleep", mock_sleep)

    with pytest.raises(KeyboardInterrupt):
        run_worker_loop(poll_interval_sec=0.01, reaper_interval_sec=0.0)

    assert reap_called[0] >= 1


def test_process_job_stops_when_lease_lost_without_writing_results(
    test_db: Session,
    sample_meeting_with_audio: Meeting,
    test_storage: Storage,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """BE-08: Reaper requeue và worker khác claim giữa chừng:
    worker cũ dừng trong 1 lần heartbeat và không ghi gì vào DB.
    """
    if not hasattr(os, "killpg"):
        monkeypatch.setattr("meeting_pipeline.runner._kill_group", lambda proc: proc.kill())

    base_time = datetime(2026, 10, 24, 10, 0, 0, tzinfo=UTC)
    enqueue_job(test_db, meeting_id=sample_meeting_with_audio.id, now=base_time)
    test_db.commit()

    claimed = claim_job(test_db, worker_id="worker-old", now=base_time)
    assert claimed is not None

    def on_stage_done_hook(stage, path):
        if stage.value == "preprocess":
            # Giả lập lease hết hạn, reaper thu hồi và worker-new claim
            reaped = reap_expired_jobs(test_db, now=base_time + timedelta(seconds=70))
            assert len(reaped) == 1
            claimed_new = claim_job(
                test_db, worker_id="worker-new", now=base_time + timedelta(seconds=70)
            )
            assert claimed_new is not None
            assert claimed_new.locked_by == "worker-new"

    process_job(
        test_db,
        claimed,
        storage=test_storage,
        backend="fake",
        on_stage_done_callback=on_stage_done_hook,
        now=base_time,
    )

    # Worker cũ dừng lại và không ghi đè gì vào DB
    test_db.refresh(claimed)
    assert claimed.locked_by == "worker-new"
    # Meeting không chuyển sang ready hay failed bởi worker-old
    test_db.refresh(sample_meeting_with_audio)
    assert sample_meeting_with_audio.status != "ready"
