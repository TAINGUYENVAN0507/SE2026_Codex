"""Kiểm thử stream tệp âm thanh hỗ trợ HTTP Range (BE-05).

Bao gồm:
- Toàn bộ file không có Range header (200 OK + Accept-Ranges: bytes)
- Range đầu, giữa, cuối (206 Partial Content + Content-Range)
- Range mở (bytes=start-) và Range suffix (bytes=-suffix)
- Range không hợp lệ và vượt kích thước (416 Range Not Satisfiable + Content-Range: bytes */total)
- PRIV-12: User khác gọi meeting audio trả về 404 Not Found
- Cuộc họp không tồn tại trả về 404 Not Found
"""

import uuid
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
from app.db.models.meeting import Meeting
from app.db.models.user import User
from app.db.session import get_db
from app.main import create_app
from app.services.storage import Storage, get_storage
from app.services.storage.local import LocalStorage


@pytest.fixture
def test_db() -> Generator[Session, None, None]:
    """Tạo database SQLite in-memory dùng cho test."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    tables = [User.__table__, Meeting.__table__]
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
def mock_storage(tmp_path: Path) -> Storage:
    """Tạo LocalStorage trỏ vào tmp_path cho test."""
    return LocalStorage(base_dir=tmp_path)


@pytest.fixture
def user_a(test_db: Session) -> User:
    """Tạo User A (chủ sở hữu)."""
    user = User(
        id=str(uuid.uuid4()),
        email="user_a@example.com",
        display_name="User A",
        password_hash="mock_hash_a",
    )
    test_db.add(user)
    test_db.commit()
    return user


@pytest.fixture
def user_b(test_db: Session) -> User:
    """Tạo User B (người ngoài)."""
    user = User(
        id=str(uuid.uuid4()),
        email="user_b@example.com",
        display_name="User B",
        password_hash="mock_hash_b",
    )
    test_db.add(user)
    test_db.commit()
    return user


@pytest.fixture
def dummy_audio_meeting(
    test_db: Session, user_a: User, mock_storage: Storage
) -> tuple[Meeting, bytes]:
    """Tạo một meeting kèm file audio nhị phân 1000 bytes trên storage."""
    meeting_id = str(uuid.uuid4())
    # Tạo 1000 bytes dữ liệu mẫu có thể kiểm chứng chính xác từng byte
    audio_data = bytes([i % 256 for i in range(1000)])

    res = mock_storage.save_upload(meeting_id=meeting_id, extension="wav", stream=audio_data)

    meeting = Meeting(
        id=meeting_id,
        owner_id=user_a.id,
        title="Cuộc họp stream audio",
        source="upload",
        status="ready",
        duration_sec=10.0,
        audio_path=res.path,
        audio_sha256=res.sha256,
        version=1,
    )
    test_db.add(meeting)
    test_db.commit()
    return meeting, audio_data


@pytest.fixture
def client_a(
    test_db: Session, user_a: User, mock_storage: Storage
) -> Generator[TestClient, None, None]:
    """TestClient xác thực với User A."""
    app = create_app()

    def _override_get_db() -> Generator[Session, None, None]:
        yield test_db

    def _override_current_user() -> User:
        return user_a

    def _override_get_storage() -> Storage:
        return mock_storage

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_current_user] = _override_current_user
    app.dependency_overrides[get_storage] = _override_get_storage

    token = create_access_token(user_a.id)
    with TestClient(app, cookies={"session_token": token}) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def client_b(
    test_db: Session, user_b: User, mock_storage: Storage
) -> Generator[TestClient, None, None]:
    """TestClient xác thực với User B."""
    app = create_app()

    def _override_get_db() -> Generator[Session, None, None]:
        yield test_db

    def _override_current_user() -> User:
        return user_b

    def _override_get_storage() -> Storage:
        return mock_storage

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_current_user] = _override_current_user
    app.dependency_overrides[get_storage] = _override_get_storage

    token = create_access_token(user_b.id)
    with TestClient(app, cookies={"session_token": token}) as c:
        yield c
    app.dependency_overrides.clear()


def test_stream_audio_full_content_no_range(
    client_a: TestClient, dummy_audio_meeting: tuple[Meeting, bytes]
) -> None:
    """Yêu cầu không có Range header trả về HTTP 200 và toàn bộ file."""
    meeting, original_bytes = dummy_audio_meeting
    resp = client_a.get(f"/api/v1/meetings/{meeting.id}/audio")

    assert resp.status_code == 200
    assert resp.headers["Accept-Ranges"] == "bytes"
    assert resp.headers["Content-Length"] == str(len(original_bytes))
    assert resp.content == original_bytes


def test_stream_audio_range_beginning(
    client_a: TestClient, dummy_audio_meeting: tuple[Meeting, bytes]
) -> None:
    """Yêu cầu Range đoạn đầu file (0-99) trả về 206 Partial Content."""
    meeting, original_bytes = dummy_audio_meeting
    resp = client_a.get(
        f"/api/v1/meetings/{meeting.id}/audio",
        headers={"Range": "bytes=0-99"},
    )

    assert resp.status_code == 206
    assert resp.headers["Accept-Ranges"] == "bytes"
    assert resp.headers["Content-Range"] == "bytes 0-99/1000"
    assert resp.headers["Content-Length"] == "100"
    assert resp.content == original_bytes[0:100]


def test_stream_audio_range_middle(
    client_a: TestClient, dummy_audio_meeting: tuple[Meeting, bytes]
) -> None:
    """Yêu cầu Range đoạn giữa file (200-499) trả về 206 Partial Content."""
    meeting, original_bytes = dummy_audio_meeting
    resp = client_a.get(
        f"/api/v1/meetings/{meeting.id}/audio",
        headers={"Range": "bytes=200-499"},
    )

    assert resp.status_code == 206
    assert resp.headers["Content-Range"] == "bytes 200-499/1000"
    assert resp.headers["Content-Length"] == "300"
    assert resp.content == original_bytes[200:500]


def test_stream_audio_range_suffix_end(
    client_a: TestClient, dummy_audio_meeting: tuple[Meeting, bytes]
) -> None:
    """Yêu cầu Range đuôi file (bytes=-50) trả về 50 bytes cuối cùng."""
    meeting, original_bytes = dummy_audio_meeting
    resp = client_a.get(
        f"/api/v1/meetings/{meeting.id}/audio",
        headers={"Range": "bytes=-50"},
    )

    assert resp.status_code == 206
    assert resp.headers["Content-Range"] == "bytes 950-999/1000"
    assert resp.headers["Content-Length"] == "50"
    assert resp.content == original_bytes[950:]


def test_stream_audio_range_open_ended(
    client_a: TestClient, dummy_audio_meeting: tuple[Meeting, bytes]
) -> None:
    """Yêu cầu Range mở (bytes=800-) trả về từ byte 800 tới byte cuối cùng."""
    meeting, original_bytes = dummy_audio_meeting
    resp = client_a.get(
        f"/api/v1/meetings/{meeting.id}/audio",
        headers={"Range": "bytes=800-"},
    )

    assert resp.status_code == 206
    assert resp.headers["Content-Range"] == "bytes 800-999/1000"
    assert resp.headers["Content-Length"] == "200"
    assert resp.content == original_bytes[800:]


def test_stream_audio_invalid_range_syntax(
    client_a: TestClient, dummy_audio_meeting: tuple[Meeting, bytes]
) -> None:
    """Cú pháp Range không hợp lệ trả về HTTP 416 RANGE_NOT_SATISFIABLE."""
    meeting, _ = dummy_audio_meeting

    invalid_ranges = [
        "invalid",
        "bytes=",
        "bytes=-",
        "bytes=abc-def",
        "bytes=500-200",  # start > end
    ]

    for rng in invalid_ranges:
        resp = client_a.get(
            f"/api/v1/meetings/{meeting.id}/audio",
            headers={"Range": rng},
        )
        assert resp.status_code == 416, f"Failed on range: {rng}"
        assert resp.headers["Content-Range"] == "bytes */1000"
        body = resp.json()
        assert body["error"]["code"] == "RANGE_NOT_SATISFIABLE"


def test_stream_audio_range_out_of_bounds(
    client_a: TestClient, dummy_audio_meeting: tuple[Meeting, bytes]
) -> None:
    """Khoảng Range vượt quá kích thước file trả về HTTP 416 RANGE_NOT_SATISFIABLE."""
    meeting, _ = dummy_audio_meeting
    resp = client_a.get(
        f"/api/v1/meetings/{meeting.id}/audio",
        headers={"Range": "bytes=1500-2000"},
    )

    assert resp.status_code == 416
    assert resp.headers["Content-Range"] == "bytes */1000"
    body = resp.json()
    assert body["error"]["code"] == "RANGE_NOT_SATISFIABLE"


def test_stream_audio_other_user_meeting_404(
    client_b: TestClient, dummy_audio_meeting: tuple[Meeting, bytes]
) -> None:
    """User B truy cập audio của User A phải nhận 404 (PRIV-12)."""
    meeting, _ = dummy_audio_meeting
    resp = client_b.get(f"/api/v1/meetings/{meeting.id}/audio")

    assert resp.status_code == 404
    body = resp.json()
    assert body["error"]["code"] == "NOT_FOUND"


def test_stream_audio_non_existent_meeting_404(client_a: TestClient) -> None:
    """Meeting không tồn tại trả về 404."""
    random_id = str(uuid.uuid4())
    resp = client_a.get(f"/api/v1/meetings/{random_id}/audio")

    assert resp.status_code == 404
    body = resp.json()
    assert body["error"]["code"] == "NOT_FOUND"
