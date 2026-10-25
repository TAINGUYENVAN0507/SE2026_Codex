"""Kiểm thử các giá trị mặc định an toàn (BE-09, BE-10).

Bao gồm:
1. Worker truyền backend=None khi không đặt PIPELINE_BACKEND, để pipeline tự chọn real.
2. MAX_DURATION_SEC mặc định 3600; worker truyền sang pipeline qua env.
3. ENVIRONMENT=production mà JWT_SECRET không an toàn thì app không khởi động.
"""

import uuid
from collections.abc import Generator
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import DEFAULT_DEV_JWT_SECRET, Settings
from app.db.base import Base
from app.db.models.job import Job
from app.db.models.meeting import Meeting
from app.db.models.user import User
from app.main import create_app
from app.services.storage import Storage
from app.services.storage.local import LocalStorage
from app.worker.queue import claim_job, enqueue_job
from app.worker.runner import process_job


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
    return LocalStorage(base_dir=tmp_path)


@pytest.fixture
def sample_user(test_db: Session) -> User:
    user = User(
        id=str(uuid.uuid4()),
        email="test_safe@example.com",
        display_name="Safe Defaults User",
        password_hash="hash",
    )
    test_db.add(user)
    test_db.commit()
    return user


@pytest.fixture
def sample_meeting_with_audio(
    test_db: Session, sample_user: User, test_storage: Storage
) -> Meeting:
    meeting_id = str(uuid.uuid4())
    res = test_storage.save_upload(
        meeting_id=meeting_id, extension="wav", stream=b"RIFF....WAVEfmt ...."
    )
    meeting = Meeting(
        id=meeting_id,
        owner_id=sample_user.id,
        title="Cuộc họp an toàn",
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


def test_production_jwt_secret_rejects_insecure_defaults(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ENVIRONMENT=production từ chối JWT_SECRET mặc định hoặc ngắn hơn 32 ký tự."""
    # 1. Mặc định ở development thì hợp lệ
    dev_settings = Settings(ENVIRONMENT="development", JWT_SECRET=DEFAULT_DEV_JWT_SECRET)
    assert dev_settings.JWT_SECRET == DEFAULT_DEV_JWT_SECRET

    # 2. Production dùng secret mặc định -> Báo lỗi rõ ràng
    with pytest.raises(ValidationError) as exc_info:
        Settings(ENVIRONMENT="production", JWT_SECRET=DEFAULT_DEV_JWT_SECRET)
    assert "JWT_SECRET không an toàn cho môi trường production" in str(exc_info.value)

    # 3. Production dùng secret ngắn hơn 32 ký tự -> Báo lỗi
    with pytest.raises(ValidationError) as exc_info:
        Settings(ENVIRONMENT="production", JWT_SECRET="too-short-secret-key-1234")
    assert "tối thiểu 32 ký tự" in str(exc_info.value)

    # 4. Production dùng secret hợp lệ (>= 32 ký tự, khác mặc định) -> Thành công
    secure_secret = "a" * 32
    prod_settings = Settings(ENVIRONMENT="production", JWT_SECRET=secure_secret)
    assert secure_secret == prod_settings.JWT_SECRET


def test_app_startup_fails_in_production_with_insecure_jwt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """create_app() không khởi động được nếu ENVIRONMENT=production và JWT không an toàn."""
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("JWT_SECRET", DEFAULT_DEV_JWT_SECRET)

    # Xóa cache get_settings để đọc cấu hình mới
    from app.core import config

    config.get_settings.cache_clear()
    try:
        with pytest.raises(ValidationError) as exc_info:
            create_app()
        assert "JWT_SECRET không an toàn cho môi trường production" in str(exc_info.value)
    finally:
        config.get_settings.cache_clear()


def test_max_duration_sec_defaults_to_3600() -> None:
    """MAX_DURATION_SEC mặc định là 3600 (P0: 60 phút)."""
    settings = Settings()
    assert settings.MAX_DURATION_SEC == 3600


def test_worker_defaults_to_none_backend_and_passes_max_duration(
    test_db: Session,
    sample_meeting_with_audio: Meeting,
    test_storage: Storage,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Worker truyền backend=None khi không đặt PIPELINE_BACKEND và truyền max duration qua env."""
    monkeypatch.delenv("PIPELINE_BACKEND", raising=False)

    base_time = datetime(2026, 10, 24, 10, 0, 0, tzinfo=UTC)
    enqueue_job(test_db, meeting_id=sample_meeting_with_audio.id, now=base_time)
    test_db.commit()

    claimed = claim_job(test_db, worker_id="test-worker", now=base_time)
    assert claimed is not None

    captured_kwargs: dict = {}

    def mock_run_job(*args, **kwargs):
        captured_kwargs.update(kwargs)
        outcome = MagicMock()
        outcome.stage_status = {}
        return outcome

    monkeypatch.setattr("app.worker.runner.run_job", mock_run_job)

    process_job(
        test_db,
        claimed,
        storage=test_storage,
        now=base_time,
    )

    # 1. backend truyền vào run_job phải là None để pipeline tự chọn 'real'
    assert captured_kwargs.get("backend") is None

    # 2. env truyền sang pipeline phải chứa PIPELINE_MAX_DURATION_SEC = "3600"
    passed_env = captured_kwargs.get("env")
    assert passed_env is not None
    assert passed_env.get("PIPELINE_MAX_DURATION_SEC") == "3600"
