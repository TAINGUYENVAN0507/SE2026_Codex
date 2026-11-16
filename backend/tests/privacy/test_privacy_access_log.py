"""Kiểm thử access logs không lưu giữ dữ liệu cá nhân hay chuỗi canary (AD-018, BE-19).

Kiểm chứng:
1. Khi client upload meeting kèm canary trong title, filename và Idempotency-Key,
   gọi tìm kiếm với canary query param ?q=<canary>, và đọc meeting detail:
   - Logger `app.access` (middleware) tuyệt đối không ghi lại bất kỳ chuỗi canary nào.
   - Trường `path` trong `app.access` dùng `request.url.path` nên không lộ query string.
2. Kiểm tra cấu hình Uvicorn: uvicorn chạy với cờ `--no-access-log` để không ghi log
   protocol HTTP chứa query string trên stdout/stderr (AD-018, BE-19).
   Mọi log access cần thiết cho vận hành đã được middleware `app.access` ghi nhận an toàn.
"""

import io
import logging
import socket
import subprocess
import sys
import time
from collections.abc import Generator
from pathlib import Path

import httpx
import pytest
import yaml
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


def _get_free_port() -> int:
    """Lấy một port TCP ngẫu nhiên đang rảnh trên loopback."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def _wait_for_server(port: int, timeout: float = 10.0) -> None:
    """Chờ tiến trình uvicorn khởi động và phản hồi /api/v1/health."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            res = httpx.get(f"http://127.0.0.1:{port}/api/v1/health", timeout=1.0)
            if res.status_code == 200:
                return
        except Exception:
            pass
        time.sleep(0.2)
    raise TimeoutError(f"Server tại port {port} không khởi động kịp sau {timeout}s")


def _extract_uvicorn_flags_from_infra() -> list[str]:
    """Trích xuất cờ truyền cho uvicorn từ docker-compose.yml và api.Dockerfile."""
    compose_path = Path(__file__).resolve().parents[3] / "docker-compose.yml"
    assert compose_path.exists(), f"Không tìm thấy {compose_path}"
    with compose_path.open("r", encoding="utf-8") as f:
        compose_data = yaml.safe_load(f)
    api_cmd = compose_data.get("services", {}).get("api", {}).get("command", "")

    dockerfile_path = Path(__file__).resolve().parents[3] / "infra" / "docker" / "api.Dockerfile"
    assert dockerfile_path.exists(), f"Không tìm thấy {dockerfile_path}"
    df_content = dockerfile_path.read_text(encoding="utf-8")

    flags: list[str] = []
    if "--no-access-log" in api_cmd:
        flags.append("--no-access-log")

    # Đảm bảo docker-compose.yml và api.Dockerfile nhất quán về cờ --no-access-log
    assert ("--no-access-log" in api_cmd) == ("--no-access-log" in df_content), (
        "docker-compose.yml và api.Dockerfile phải đồng bộ về cấu hình --no-access-log"
    )
    return flags


def test_real_uvicorn_access_log_no_canary_in_query() -> None:
    """Chạy uvicorn thật bằng subprocess với đúng cờ từ compose và Dockerfile.

    Kiểm tra query string ?q=<canary> và tiêu đề canary không xuất hiện trong stdout/stderr.
    (AD-018, BE-19).
    """
    flags = _extract_uvicorn_flags_from_infra()
    port = _get_free_port()
    backend_dir = Path(__file__).resolve().parents[2]

    cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "app.main:create_app",
        "--factory",
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
    ] + flags

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        cwd=backend_dir,
    )
    try:
        _wait_for_server(port)
        with httpx.Client(base_url=f"http://127.0.0.1:{port}", timeout=5.0) as client:
            client.get(f"/api/v1/meetings?q={CANARY_QUERY}")
            fake_wav = io.BytesIO(b"RIFF" + b"\x00" * 100)
            client.post(
                "/api/v1/meetings",
                data={"title": CANARY_TITLE, "consent_confirmed": "true"},
                files={"file": (CANARY_FILENAME, fake_wav, "audio/wav")},
            )
    finally:
        proc.terminate()
        stdout, stderr = proc.communicate(timeout=5)

    combined = stdout + stderr
    assert CANARY_QUERY not in combined, (
        f"Uvicorn access log làm rò rỉ query string canary '{CANARY_QUERY}' trong log: {combined}"
    )
    assert CANARY_TITLE not in combined, (
        f"Uvicorn access log làm rò rỉ title canary '{CANARY_TITLE}' trong log: {combined}"
    )


def test_real_uvicorn_control_case_leaks_query_without_flag() -> None:
    """Ca đối chứng: khi uvicorn KHÔNG có --no-access-log, canary trong query string phải xuất hiện.

    Chứng minh test bắt được lỗi và bác bỏ giả thuyết test xanh ảo.
    """
    control_canary = "CANARY_CONTROL_LEAK_PROOF_999"
    port = _get_free_port()
    backend_dir = Path(__file__).resolve().parents[2]

    cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "app.main:create_app",
        "--factory",
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
    ]
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        cwd=backend_dir,
    )
    try:
        _wait_for_server(port)
        with httpx.Client(base_url=f"http://127.0.0.1:{port}", timeout=5.0) as client:
            client.get(f"/api/v1/meetings?q={control_canary}")
    finally:
        proc.terminate()
        stdout, stderr = proc.communicate(timeout=5)

    combined = stdout + stderr
    assert control_canary in combined, (
        f"Ca đối chứng thất bại: '{control_canary}' không xuất hiện trong log uvicorn mặc định!"
    )


def test_uvicorn_access_log_settings_documented_in_infra() -> None:
    """Xác nhận uvicorn trong compose và Dockerfile có cờ --no-access-log (AD-018, BE-19).

    Uvicorn mặc định ghi cả query string (?q=...) vào access log. Vì vậy cờ --no-access-log
    được thiết lập trên cả compose stack và Dockerfile image để bảo vệ dữ liệu cá nhân.
    Mọi thông tin access phục vụ vận hành được ghi bởi middleware app.access.
    """
    compose_path = Path(__file__).resolve().parents[3] / "docker-compose.yml"
    assert compose_path.exists(), "docker-compose.yml phải tồn tại"
    compose_content = compose_path.read_text(encoding="utf-8")
    assert "--no-access-log" in compose_content, (
        "docker-compose.yml phải chứa cờ --no-access-log cho service api"
    )

    dockerfile_path = Path(__file__).resolve().parents[3] / "infra" / "docker" / "api.Dockerfile"
    assert dockerfile_path.exists(), "api.Dockerfile phải tồn tại"
    df_content = dockerfile_path.read_text(encoding="utf-8")
    assert "--no-access-log" in df_content, (
        "api.Dockerfile phải chứa cờ --no-access-log cho lệnh uvicorn"
    )
