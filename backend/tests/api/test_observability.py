"""Kiểm thử tính năng quan sát (observability) và logging JSON có cấu trúc (BE-19).

Bao gồm:
- PRIV-10 / Canary test: Tiêu đề cuộc họp CANARY_TITLE_... không bao giờ xuất hiện trong log.
- Trace test: Chuỗi sự kiện job_created -> job_claimed -> job_failed được ghi nhận đầy đủ
  với job_id, stage, attempt và error_code khi pipeline gặp lỗi permanent.
- Trace test cho job_retry_scheduled và job_succeeded.
"""

import io
import json
import logging
import uuid
from collections.abc import Generator
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import get_current_user
from app.core.logging import JSONLogFormatter
from app.core.security import create_access_token
from app.db.base import Base
from app.db.models.action_item import ActionItem
from app.db.models.ai_output import AIOutput
from app.db.models.edit_event import EditEvent
from app.db.models.idempotency import IdempotencyKey
from app.db.models.job import Job
from app.db.models.meeting import Meeting
from app.db.models.summary import Summary
from app.db.models.transcript import Segment, Speaker
from app.db.models.user import User
from app.db.session import get_db
from app.main import create_app
from app.services.audio_validator import AudioProbeResult
from app.services.storage import Storage, get_storage
from app.services.storage.local import LocalStorage
from app.worker.runner import run_worker_once


@pytest.fixture
def test_storage(tmp_path: Path) -> Storage:
    """Tạo storage tạm thời cho test."""
    return LocalStorage(base_dir=tmp_path)


@pytest.fixture
def test_db() -> Generator[Session, None, None]:
    """Tạo database SQLite in-memory dùng chung cho test."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    tables = [
        User.__table__,
        Meeting.__table__,
        Job.__table__,
        IdempotencyKey.__table__,
        Speaker.__table__,
        Segment.__table__,
        AIOutput.__table__,
        Summary.__table__,
        ActionItem.__table__,
        EditEvent.__table__,
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
def sample_user(test_db: Session) -> User:
    """Tạo user kiểm thử."""
    user = User(
        id=str(uuid.uuid4()),
        email="test_obs@example.com",
        display_name="Observability Tester",
        password_hash="fakehash",
    )
    test_db.add(user)
    test_db.commit()
    return user


@pytest.fixture
def auth_headers(sample_user: User) -> dict[str, str]:
    """Tạo auth header cho user kiểm thử."""
    token = create_access_token(sample_user.id)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def client(
    test_db: Session,
    test_storage: Storage,
    sample_user: User,
) -> Generator[TestClient, None, None]:
    """Khởi tạo TestClient với database và storage giả định."""
    app = create_app()
    app.dependency_overrides[get_db] = lambda: test_db
    app.dependency_overrides[get_storage] = lambda: test_storage
    app.dependency_overrides[get_current_user] = lambda: sample_user
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def log_capture() -> Generator[io.StringIO, None, None]:
    """Fixture cấu hình capture log với JSONLogFormatter trên root logger."""
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JSONLogFormatter())
    root_logger = logging.getLogger()
    original_level = root_logger.level
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(handler)
    try:
        yield stream
    finally:
        root_logger.removeHandler(handler)
        root_logger.setLevel(original_level)


def test_obs_canary_title_not_in_logs(
    client: TestClient,
    auth_headers: dict[str, str],
    log_capture: io.StringIO,
) -> None:
    """Test Canary: Tiêu đề cuộc họp chứa chuỗi canary không bao giờ xuất hiện trong log."""
    canary_title = "CANARY_TITLE_TOP_SECRET_REDACTION_987654"

    with patch("app.api.v1.meetings.probe_audio") as mock_probe:
        mock_probe.return_value = AudioProbeResult(
            duration_sec=30.0,
            sample_rate=16000,
            channels=1,
            format_name="wav",
        )
        fake_wav = b"RIFF" + b"\x00" * 100
        response = client.post(
            "/api/v1/meetings",
            files={"file": ("meeting.wav", fake_wav, "audio/wav")},
            data={"title": canary_title, "consent_confirmed": "true"},
            headers={**auth_headers, "Idempotency-Key": str(uuid.uuid4())},
        )
        assert response.status_code == 201

    log_contents = log_capture.getvalue()
    assert canary_title not in log_contents, "Canary title không được xuất hiện trong log!"


def test_obs_failed_job_traceable(
    client: TestClient,
    test_db: Session,
    test_storage: Storage,
    auth_headers: dict[str, str],
    log_capture: io.StringIO,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Trace test: Pipeline lỗi permanent ghi chuỗi job_created -> job_claimed -> job_failed."""
    monkeypatch.setenv("FAKE_SCENARIO", "permanent")

    with patch("app.api.v1.meetings.probe_audio") as mock_probe:
        mock_probe.return_value = AudioProbeResult(
            duration_sec=30.0,
            sample_rate=16000,
            channels=1,
            format_name="wav",
        )
        fake_wav = b"RIFF" + b"\x00" * 100
        res = client.post(
            "/api/v1/meetings",
            files={"file": ("meeting.wav", fake_wav, "audio/wav")},
            data={"title": "Họp lỗi", "consent_confirmed": "true"},
            headers={**auth_headers, "Idempotency-Key": str(uuid.uuid4())},
        )
        assert res.status_code == 201
        data = res.json()
        job_id = data["job"]["id"]
        meeting_id = data["meeting"]["id"]

    # Chạy worker xử lý job
    ran = run_worker_once(
        test_db,
        storage=test_storage,
        worker_id="worker-obs-test",
        backend="fake",
    )
    assert ran is True

    # Parse log entries dạng JSON
    raw_logs = log_capture.getvalue().strip().split("\n")
    events = []
    for line in raw_logs:
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
            if entry.get("job_id") == job_id:
                events.append(entry)
        except json.JSONDecodeError:
            continue

    event_names = [e.get("event") for e in events]
    assert "job_created" in event_names, f"Thiếu sự kiện job_created trong log: {event_names}"
    assert "job_claimed" in event_names, f"Thiếu sự kiện job_claimed trong log: {event_names}"
    assert "job_failed" in event_names, f"Thiếu sự kiện job_failed trong log: {event_names}"

    # Kiểm tra chi tiết từng event
    created_evt = next(e for e in events if e.get("event") == "job_created")
    assert created_evt["job_id"] == job_id
    assert created_evt["meeting_id"] == meeting_id
    assert created_evt["status"] == "queued"

    claimed_evt = next(e for e in events if e.get("event") == "job_claimed")
    assert claimed_evt["job_id"] == job_id
    assert claimed_evt["worker_id"] == "worker-obs-test"
    assert claimed_evt["status"] == "running"

    failed_evt = next(e for e in events if e.get("event") == "job_failed")
    assert failed_evt["job_id"] == job_id
    assert failed_evt["worker_id"] == "worker-obs-test"
    assert failed_evt["status"] == "failed"
    assert failed_evt["stage"] == "preprocess"
    assert failed_evt["error_code"] == "AUDIO_INVALID"


def test_obs_retry_and_succeeded_traceable(
    client: TestClient,
    test_db: Session,
    test_storage: Storage,
    auth_headers: dict[str, str],
    log_capture: io.StringIO,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Trace test: Kiểm tra log job_retry_scheduled và job_succeeded mang đủ context."""
    # 1. Job retry scheduled
    monkeypatch.setenv("FAKE_SCENARIO", "transient_once")
    with patch("app.api.v1.meetings.probe_audio") as mock_probe:
        mock_probe.return_value = AudioProbeResult(
            duration_sec=30.0,
            sample_rate=16000,
            channels=1,
            format_name="wav",
        )
        fake_wav = b"RIFF" + b"\x00" * 100
        res = client.post(
            "/api/v1/meetings",
            files={"file": ("meeting.wav", fake_wav, "audio/wav")},
            data={"title": "Họp retry", "consent_confirmed": "true"},
            headers={**auth_headers, "Idempotency-Key": str(uuid.uuid4())},
        )
        assert res.status_code == 201
        job_id_transient = res.json()["job"]["id"]

    run_worker_once(
        test_db,
        storage=test_storage,
        worker_id="worker-retry-test",
        backend="fake",
    )

    raw_logs = log_capture.getvalue().strip().split("\n")
    retry_events = [
        json.loads(line)
        for line in raw_logs
        if line.strip() and f'"job_id": "{job_id_transient}"' in line
    ]
    retry_event = next(e for e in retry_events if e.get("event") == "job_retry_scheduled")
    assert retry_event["status"] == "retry_scheduled"
    assert retry_event["attempt"] == 1
    assert "error_code" in retry_event

    # 2. Job succeeded
    monkeypatch.delenv("FAKE_SCENARIO", raising=False)
    with patch("app.api.v1.meetings.probe_audio") as mock_probe:
        mock_probe.return_value = AudioProbeResult(
            duration_sec=30.0,
            sample_rate=16000,
            channels=1,
            format_name="wav",
        )
        fake_wav = b"RIFF" + b"\x00" * 100
        res2 = client.post(
            "/api/v1/meetings",
            files={"file": ("meeting2.wav", fake_wav, "audio/wav")},
            data={"title": "Họp thành công", "consent_confirmed": "true"},
            headers={**auth_headers, "Idempotency-Key": str(uuid.uuid4())},
        )
        assert res2.status_code == 201
        job_id_success = res2.json()["job"]["id"]

    run_worker_once(
        test_db,
        storage=test_storage,
        worker_id="worker-success-test",
        backend="fake",
    )

    raw_logs_2 = log_capture.getvalue().strip().split("\n")
    success_events = [
        json.loads(line)
        for line in raw_logs_2
        if line.strip() and f'"job_id": "{job_id_success}"' in line
    ]
    succ_event = next(e for e in success_events if e.get("event") == "job_succeeded")
    assert succ_event["status"] == "succeeded"
    assert succ_event["job_id"] == job_id_success
