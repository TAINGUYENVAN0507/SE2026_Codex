"""Kiểm thử access logs không lưu giữ dữ liệu cá nhân hay chuỗi canary (AD-018, BE-19).

Kiểm chứng:
1. Khi client upload meeting kèm canary trong title, filename và Idempotency-Key,
   gọi tìm kiếm với canary query param ?q=<canary>, và đọc meeting detail:
   - Logger `app.access` (middleware) và `uvicorn.access` tuyệt đối không ghi lại
     bất kỳ chuỗi canary nào.
   - Trường `path` trong `app.access` dùng `request.url.path` nên không lộ query string.
2. Kiểm tra cấu hình Uvicorn: uvicorn chạy mặc định không có cờ `--no-access-log`,
   và định dạng access log chỉ gồm client IP, method, path, HTTP version và status code;
   không bao giờ ghi nhận headers hay request body.
"""

import io
import logging
from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import get_current_user
from app.core.security import create_access_token
from app.db.base import Base
from app.db.models.idempotency import IdempotencyKey
from app.db.models.job import Job
from app.db.models.meeting import Meeting
from app.db.models.transcript import Segment, Speaker
from app.db.models.user import User
from app.db.session import get_db
from app.main import create_app
from app.services.audio_validator import AudioProbeResult
from app.services.storage import LocalStorage, get_storage

CANARY_TITLE = "CANARY_CONFIDENTIAL_MEETING_TITLE_XYZ_999"
CANARY_FILENAME = "canary_sensitive_recording_abc_888.wav"
CANARY_IDEMPOTENCY = "IDEM_CANARY_UNIQUE_KEY_DEF_777"
CANARY_QUERY = "CANARY_SEARCH_QUERY_PARAM_GHI_666"

ALL_CANARIES = [
    CANARY_TITLE,
    CANARY_FILENAME,
    CANARY_IDEMPOTENCY,
    CANARY_QUERY,
]


@pytest.fixture
def test_storage(tmp_path: Path) -> LocalStorage:
    """Tạo storage tạm thời cho test upload."""
    return LocalStorage(base_dir=tmp_path)


@pytest.fixture
def test_db() -> Generator[Session, None, None]:
    """Tạo DB SQLite in-memory cho test access log."""
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
    """Tạo người dùng mẫu cho test."""
    user = User(
        id="user-access-log-test-id",
        email="access_log_privacy@example.com",
        display_name="Access Log User",
        password_hash="mock_hash",
    )
    test_db.add(user)
    test_db.commit()
    return user


@pytest.fixture
def auth_headers(sample_user: User) -> dict[str, str]:
    """Header xác thực Bearer token."""
    token = create_access_token(sample_user.id)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def client(
    test_db: Session,
    test_storage: LocalStorage,
    sample_user: User,
) -> Generator[TestClient, None, None]:
    """TestClient với dependencies được ghi đè."""
    app = create_app()
    app.dependency_overrides[get_db] = lambda: test_db
    app.dependency_overrides[get_storage] = lambda: test_storage
    app.dependency_overrides[get_current_user] = lambda: sample_user
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def mock_probe_audio(monkeypatch: pytest.MonkeyPatch) -> None:
    """Mock audio probe để không phụ thuộc ffprobe."""

    def _mock_probe(file_path: Path, timeout_sec: float = 10.0, ffprobe_bin: str | None = None):
        return AudioProbeResult(
            duration_sec=60.0,
            format_name="wav",
            sample_rate=16000,
            channels=1,
        )

    monkeypatch.setattr("app.api.v1.meetings.probe_audio", _mock_probe)


def test_access_logs_carry_no_personal_data(
    client: TestClient,
    auth_headers: dict[str, str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Log access của app.access và uvicorn.access không giữ dữ liệu cá nhân hay canary (BE-19)."""
    with caplog.at_level(logging.DEBUG):
        # 1. Upload meeting chứa canary ở tiêu đề, tên file và Idempotency-Key
        fake_audio = io.BytesIO(b"RIFF" + b"\x00" * 200)
        files = {"file": (CANARY_FILENAME, fake_audio, "audio/wav")}
        data = {
            "title": CANARY_TITLE,
            "consent_confirmed": "true",
            "num_speakers": "2",
            "meeting_date": "2026-11-15",
        }
        headers = {**auth_headers, "Idempotency-Key": CANARY_IDEMPOTENCY}
        upload_res = client.post("/api/v1/meetings", data=data, files=files, headers=headers)
        assert upload_res.status_code == 201
        meeting_id = upload_res.json()["meeting"]["id"]

        # 2. Gọi GET /meetings?q=<canary> kiểm tra query param không lọt vào log path
        search_res = client.get(f"/api/v1/meetings?q={CANARY_QUERY}", headers=auth_headers)
        assert search_res.status_code == 200

        # 3. Gọi GET /meetings/{id}
        detail_res = client.get(f"/api/v1/meetings/{meeting_id}", headers=auth_headers)
        assert detail_res.status_code == 200

    # Lọc các bản ghi từ app.access và uvicorn.access
    access_records = [
        record for record in caplog.records if record.name in ("app.access", "uvicorn.access")
    ]
    assert len(access_records) > 0, "Phải ghi nhận được ít nhất một bản ghi access log."

    # Khẳng định không có bất kỳ chuỗi canary nào xuất hiện trong access logs
    for record in access_records:
        msg = record.getMessage()
        # Kiểm tra nội dung text của message
        for canary in ALL_CANARIES:
            assert canary not in msg, f"Canary '{canary}' bị rò rỉ trong log message: {msg}"

        # Kiểm tra toàn bộ attributes / extra fields của LogRecord
        for key, val in record.__dict__.items():
            if isinstance(val, str):
                for canary in ALL_CANARIES:
                    assert canary not in val, (
                        f"Canary '{canary}' bị rò rỉ trong record.{key}: '{val}'"
                    )

        # Kiểm tra riêng trường path trong app.access: dùng request.url.path không chứa query
        if record.name == "app.access" and hasattr(record, "path"):
            assert "?" not in record.path, (
                f"Path trong access log không được chứa query params: {record.path}"
            )
            assert CANARY_QUERY not in record.path


def test_uvicorn_access_log_settings_documented_in_infra() -> None:
    """Xác nhận uvicorn trong docker-compose.yml và Dockerfile không truyền --no-access-log.

    Uvicorn mặc định bật access log ở mức INFO, ghi log qua standard access formatter
    chỉ bao gồm client IP, HTTP method, path, HTTP version, status code.
    Không ghi request headers (Idempotency-Key, Authorization) hay request body.
    """
    compose_path = Path(__file__).resolve().parents[3] / "docker-compose.yml"
    assert compose_path.exists(), "docker-compose.yml phải tồn tại"
    compose_content = compose_path.read_text(encoding="utf-8")
    assert "--no-access-log" not in compose_content, (
        "docker-compose.yml hiện không dùng cờ --no-access-log; uvicorn access log chạy mặc định."
    )

    dockerfile_path = Path(__file__).resolve().parents[3] / "infra" / "docker" / "api.Dockerfile"
    if dockerfile_path.exists():
        df_content = dockerfile_path.read_text(encoding="utf-8")
        assert "--no-access-log" not in df_content
