"""Kiểm thử API tải lên cuộc họp POST /meetings (BE-04)."""

import io
import uuid
from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
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
from app.services.storage.base import FileTooLargeError


@pytest.fixture
def test_storage(tmp_path: Path) -> LocalStorage:
    """Tạo storage cục bộ trong thư mục tạm."""
    return LocalStorage(base_dir=tmp_path)


@pytest.fixture
def test_db() -> Generator[Session, None, None]:
    """Tạo database in-memory cho kiểm thử upload meeting."""
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
def auth_user(test_db: Session) -> User:
    """Tạo người dùng mẫu trong DB."""
    user = User(
        id=str(uuid.uuid4()),
        email="test_upload@example.com",
        display_name="Người Upload",
        password_hash="argon2_fake_hash",
    )
    test_db.add(user)
    test_db.commit()
    return user


@pytest.fixture
def client(
    test_db: Session,
    test_storage: LocalStorage,
    auth_user: User,
) -> Generator[TestClient, None, None]:
    """FastAPI TestClient với user đăng nhập và storage tạm."""
    app = create_app()

    def _override_get_db() -> Generator[Session, None, None]:
        yield test_db

    def _override_get_storage() -> LocalStorage:
        return test_storage

    def _override_current_user() -> User:
        return auth_user

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_storage] = _override_get_storage
    app.dependency_overrides[get_current_user] = _override_current_user

    token = create_access_token(auth_user.id)
    with TestClient(app, cookies={"session_token": token}) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def mock_probe_audio(monkeypatch: pytest.MonkeyPatch) -> None:
    """Luôn mock probe_audio: test kiểm xử lý upload; ffprobe thật ở test_ffprobe_real.py."""

    def _mock_probe(file_path, timeout_sec=10.0, ffprobe_bin=None):
        return AudioProbeResult(
            duration_sec=120.5,
            format_name="wav",
            sample_rate=16000,
            channels=1,
        )

    monkeypatch.setattr("app.api.v1.meetings.probe_audio", _mock_probe)


def test_upload_meeting_success(
    client: TestClient,
    test_db: Session,
    test_storage: LocalStorage,
    auth_user: User,
) -> None:
    """Tải lên meeting thành công tạo Meeting + Job trong 1 transaction và lưu file."""
    fake_audio = io.BytesIO(b"RIFF" + b"\x00" * 100)
    files = {"file": ("sprint_meeting.wav", fake_audio, "audio/wav")}
    data = {
        "title": "Họp Sprint Tuần 42",
        "consent_confirmed": "true",
        "num_speakers": "3",
        "meeting_date": "2026-10-23",
    }
    idem_key = str(uuid.uuid4())
    headers = {"Idempotency-Key": idem_key}

    response = client.post("/api/v1/meetings", data=data, files=files, headers=headers)
    assert response.status_code == 201, response.text
    res_data = response.json()

    # Kiểm tra cấu trúc response
    assert "meeting" in res_data
    assert "job" in res_data
    meeting_info = res_data["meeting"]
    job_info = res_data["job"]

    assert meeting_info["title"] == "Họp Sprint Tuần 42"
    assert meeting_info["status"] == "queued"
    assert meeting_info["audio"]["available"] is True
    assert job_info["status"] == "queued"
    assert job_info["meeting_id"] == meeting_info["id"]

    # Kiểm tra DB
    meeting_db = test_db.execute(
        select(Meeting).where(Meeting.id == meeting_info["id"])
    ).scalar_one_or_none()
    assert meeting_db is not None
    assert meeting_db.owner_id == auth_user.id
    assert meeting_db.duration_sec == 120.5

    job_db = test_db.execute(
        select(Job).where(Job.meeting_id == meeting_info["id"])
    ).scalar_one_or_none()
    assert job_db is not None
    assert job_db.id == job_info["id"]

    # Kiểm tra file trên đĩa
    audio_path = test_storage.get_audio_path(meeting_info["id"], "wav")
    assert audio_path.is_file()


def test_upload_meeting_missing_idempotency_key_400(client: TestClient) -> None:
    """Thiếu header Idempotency-Key phải trả về 400 IDEMPOTENCY_KEY_REQUIRED."""
    fake_audio = io.BytesIO(b"RIFF" + b"\x00" * 100)
    files = {"file": ("test.wav", fake_audio, "audio/wav")}
    data = {"consent_confirmed": "true"}

    response = client.post("/api/v1/meetings", data=data, files=files)
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "IDEMPOTENCY_KEY_REQUIRED"


def test_upload_meeting_without_consent_422(client: TestClient) -> None:
    """Chưa xác nhận consent_confirmed phải trả về 422 CONSENT_REQUIRED."""
    fake_audio = io.BytesIO(b"RIFF" + b"\x00" * 100)
    files = {"file": ("test.wav", fake_audio, "audio/wav")}
    data = {"consent_confirmed": "false"}
    headers = {"Idempotency-Key": str(uuid.uuid4())}

    response = client.post("/api/v1/meetings", data=data, files=files, headers=headers)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "CONSENT_REQUIRED"


def test_upload_meeting_unsupported_media_type_415(client: TestClient) -> None:
    """Tải lên đuôi file không hợp lệ phải trả về 415 UNSUPPORTED_MEDIA_TYPE."""
    fake_doc = io.BytesIO(b"%PDF-1.4...")
    files = {"file": ("notes.pdf", fake_doc, "application/pdf")}
    data = {"consent_confirmed": "true"}
    headers = {"Idempotency-Key": str(uuid.uuid4())}

    response = client.post("/api/v1/meetings", data=data, files=files, headers=headers)
    assert response.status_code == 415
    assert response.json()["error"]["code"] == "UNSUPPORTED_MEDIA_TYPE"


def test_upload_meeting_file_too_large_413(
    client: TestClient,
    test_storage: LocalStorage,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vượt quá dung lượng cho phép phải trả về 413 FILE_TOO_LARGE."""

    def mock_save_upload(*args, **kwargs):
        raise FileTooLargeError("File vượt quá giới hạn")

    monkeypatch.setattr(test_storage, "save_upload", mock_save_upload)

    fake_audio = io.BytesIO(b"RIFF" + b"\x00" * 100)
    files = {"file": ("large.wav", fake_audio, "audio/wav")}
    data = {"consent_confirmed": "true"}
    headers = {"Idempotency-Key": str(uuid.uuid4())}

    response = client.post("/api/v1/meetings", data=data, files=files, headers=headers)
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "FILE_TOO_LARGE"


def test_upload_meeting_audio_invalid_cleans_file(
    client: TestClient,
    test_db: Session,
    test_storage: LocalStorage,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Tệp audio hỏng qua ffprobe phải trả về 422 AUDIO_INVALID và dọn dẹp file rác."""
    from app.core.errors import APIError

    def mock_probe_error(*args, **kwargs):
        raise APIError(
            code="AUDIO_INVALID",
            message="Tệp không chứa luồng audio",
            status_code=422,
        )

    monkeypatch.setattr("app.api.v1.meetings.probe_audio", mock_probe_error)

    fake_audio = io.BytesIO(b"CORRUPTED_DATA")
    files = {"file": ("corrupted.wav", fake_audio, "audio/wav")}
    data = {"consent_confirmed": "true"}
    headers = {"Idempotency-Key": str(uuid.uuid4())}

    response = client.post("/api/v1/meetings", data=data, files=files, headers=headers)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "AUDIO_INVALID"

    # Kiểm tra không có meeting nào trong DB
    meetings = test_db.execute(select(Meeting)).scalars().all()
    assert len(meetings) == 0

    # Kiểm tra thư mục audio không còn file rác nào
    audio_dir = test_storage.base_dir / "audio"
    if audio_dir.exists():
        assert len(list(audio_dir.iterdir())) == 0


def test_upload_meeting_db_error_rolls_back_and_cleans_file(
    client: TestClient,
    test_db: Session,
    test_storage: LocalStorage,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Lỗi DB khi insert Meeting/Job phải rollback và xóa file âm thanh trên đĩa."""
    # Mock db.flush để ném Exception
    orig_flush = test_db.flush

    def broken_flush(*args, **kwargs):
        raise RuntimeError("Database connection lost during insert")

    monkeypatch.setattr(test_db, "flush", broken_flush)

    fake_audio = io.BytesIO(b"RIFF" + b"\x00" * 100)
    files = {"file": ("rollback.wav", fake_audio, "audio/wav")}
    data = {"consent_confirmed": "true"}
    headers = {"Idempotency-Key": str(uuid.uuid4())}

    with pytest.raises(RuntimeError, match="Database connection lost"):
        client.post("/api/v1/meetings", data=data, files=files, headers=headers)

    # Khôi phục flush để query DB
    monkeypatch.setattr(test_db, "flush", orig_flush)

    # Đảm bảo không có meeting nào lưu lại
    meetings = test_db.execute(select(Meeting)).scalars().all()
    assert len(meetings) == 0

    # Đảm bảo không còn file rác trên storage
    audio_dir = test_storage.base_dir / "audio"
    if audio_dir.exists():
        assert len(list(audio_dir.iterdir())) == 0


def test_upload_meeting_query_count_budget(
    client: TestClient,
    test_db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """POST /meetings không được vượt quá 6 truy vấn SQL (loại bỏ query thừa và lazy load)."""
    from sqlalchemy import event

    mock_probe = AudioProbeResult(
        duration_sec=10.0,
        sample_rate=16000,
        channels=1,
        format_name="wav",
    )
    monkeypatch.setattr("app.api.v1.meetings.probe_audio", lambda **_: mock_probe)

    query_count = 0
    engine = test_db.bind

    def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        nonlocal query_count
        query_count += 1

    event.listen(engine, "before_cursor_execute", before_cursor_execute)
    try:
        fake_audio = io.BytesIO(b"RIFF" + b"\x00" * 100)
        files = {"file": ("budget.wav", fake_audio, "audio/wav")}
        data = {"consent_confirmed": "true", "title": "Budget Meeting"}
        headers = {"Idempotency-Key": str(uuid.uuid4())}

        response = client.post("/api/v1/meetings", data=data, files=files, headers=headers)
        assert response.status_code == 201

        # Ngân sách: tối đa 6 câu lệnh SQL (1 auth, 1 idempotency select, 1 idempotency insert,
        # 1 insert meeting, 1 insert job, 1 update idempotency). Không được có lazy load sau commit.
        assert query_count <= 6, f"Số lượng truy vấn thực tế là {query_count}, vượt ngưỡng 6"
    finally:
        event.remove(engine, "before_cursor_execute", before_cursor_execute)


def test_meeting_audio_reports_real_size_and_null_when_removed(
    client: TestClient,
    test_db: Session,
    test_storage: LocalStorage,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """GET /meetings/{id} và /meetings trả size_bytes thật, hoặc null + available=False khi mất."""
    from datetime import UTC, datetime, timedelta

    from app.services.retention import run_retention_cleanup

    payload_bytes = b"RIFF" + b"\x01" * 1230
    expected_size = len(payload_bytes)
    files = {"file": ("size_check.wav", io.BytesIO(payload_bytes), "audio/wav")}
    data = {"consent_confirmed": "true", "title": "Kiểm tra size_bytes"}
    headers = {"Idempotency-Key": str(uuid.uuid4())}

    create_res = client.post("/api/v1/meetings", data=data, files=files, headers=headers)
    assert create_res.status_code == 201
    meeting_id = create_res.json()["meeting"]["id"]
    assert create_res.json()["meeting"]["audio"]["size_bytes"] == expected_size

    # Kiểm tra lấy kích thước qua storage mà không mở file
    def _fail_open(*_args, **_kwargs):
        raise AssertionError("Không được mở tệp audio để tính size_bytes")

    with monkeypatch.context() as mp:
        mp.setattr("builtins.open", _fail_open)

        detail_res = client.get(f"/api/v1/meetings/{meeting_id}")
        assert detail_res.status_code == 200
        assert detail_res.json()["audio"]["available"] is True
        assert detail_res.json()["audio"]["size_bytes"] == expected_size

        list_res = client.get("/api/v1/meetings?page=1&page_size=10")
        assert list_res.status_code == 200
        assert list_res.json()["items"][0]["audio"]["available"] is True
        assert list_res.json()["items"][0]["audio"]["size_bytes"] == expected_size

    # Sau khi hết hạn lưu và dọn dẹp: audio.available=False và audio.size_bytes=None
    meeting_row = test_db.get(Meeting, meeting_id)
    assert meeting_row is not None
    job_row = test_db.execute(select(Job).where(Job.meeting_id == meeting_id)).scalar_one()
    job_row.status = "succeeded"
    meeting_row.retention_until = datetime.now(UTC) - timedelta(days=1)
    test_db.commit()

    run_retention_cleanup(test_db, storage=test_storage, now=datetime.now(UTC))

    after_res = client.get(f"/api/v1/meetings/{meeting_id}")
    assert after_res.status_code == 200
    assert after_res.json()["audio"]["available"] is False
    assert after_res.json()["audio"]["size_bytes"] is None


def test_audio_missing_without_retention_is_unavailable(
    client: TestClient, test_db: Session, test_storage: LocalStorage
) -> None:
    """File bị mất ngoài retention phải được báo giống nhau trên detail, list và player."""
    response = client.post(
        "/api/v1/meetings",
        data={"consent_confirmed": "true"},
        files={"file": ("missing.wav", b"RIFF" + b"\x01" * 1230, "audio/wav")},
        headers={"Idempotency-Key": str(uuid.uuid4())},
    )
    assert response.status_code == 201
    meeting_id = response.json()["meeting"]["id"]
    test_storage.get_audio_path(meeting_id, "wav").unlink()
    assert test_db.get(Meeting, meeting_id).audio_path is not None

    detail = client.get(f"/api/v1/meetings/{meeting_id}")
    listing = client.get("/api/v1/meetings")
    assert detail.status_code == listing.status_code == 200
    for audio in (detail.json()["audio"], listing.json()["items"][0]["audio"]):
        assert audio["available"] is False
        assert audio["size_bytes"] is None
    assert client.get(f"/api/v1/meetings/{meeting_id}/audio").status_code == 404
