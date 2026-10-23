"""Kiểm thử API đọc danh sách và chi tiết cuộc họp từ DB (BE-05).

Bao gồm:
- Phân trang page, page_size, total
- Lọc theo status
- Tìm kiếm theo từ khóa q
- Owner scoping: chỉ thấy cuộc họp của chính mình
- Lấy chi tiết meeting kèm latest_job và speakers
- 404 khi meeting không tồn tại hoặc thuộc user khác (PRIV-12)
"""

import uuid
from collections.abc import Generator

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
from app.db.models.transcript import Speaker
from app.db.models.user import User
from app.db.session import get_db
from app.main import create_app


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
def user_a(test_db: Session) -> User:
    """Tạo User A."""
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
    """Tạo User B."""
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
def client_a(test_db: Session, user_a: User) -> Generator[TestClient, None, None]:
    """TestClient xác thực với User A."""
    app = create_app()

    def _override_get_db() -> Generator[Session, None, None]:
        yield test_db

    def _override_current_user() -> User:
        return user_a

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_current_user] = _override_current_user

    token = create_access_token(user_a.id)
    with TestClient(app, cookies={"session_token": token}) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def client_b(test_db: Session, user_b: User) -> Generator[TestClient, None, None]:
    """TestClient xác thực với User B."""
    app = create_app()

    def _override_get_db() -> Generator[Session, None, None]:
        yield test_db

    def _override_current_user() -> User:
        return user_b

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_current_user] = _override_current_user

    token = create_access_token(user_b.id)
    with TestClient(app, cookies={"session_token": token}) as c:
        yield c
    app.dependency_overrides.clear()


def test_list_meetings_pagination(client_a: TestClient, test_db: Session, user_a: User) -> None:
    """Kiểm tra phân trang danh sách cuộc họp page, page_size và total."""
    # Tạo 15 cuộc họp cho user_a
    for i in range(15):
        m = Meeting(
            id=str(uuid.uuid4()),
            owner_id=user_a.id,
            title=f"Cuộc họp số {i:02d}",
            source="upload",
            status="queued",
            version=1,
        )
        test_db.add(m)
    test_db.commit()

    # Trang 1: lấy 10 mục
    res_p1 = client_a.get("/api/v1/meetings?page=1&page_size=10")
    assert res_p1.status_code == 200
    data_p1 = res_p1.json()
    assert data_p1["page"] == 1
    assert data_p1["page_size"] == 10
    assert data_p1["total"] == 15
    assert len(data_p1["items"]) == 10

    # Trang 2: lấy 5 mục còn lại
    res_p2 = client_a.get("/api/v1/meetings?page=2&page_size=10")
    assert res_p2.status_code == 200
    data_p2 = res_p2.json()
    assert data_p2["page"] == 2
    assert data_p2["page_size"] == 10
    assert data_p2["total"] == 15
    assert len(data_p2["items"]) == 5


def test_list_meetings_filter_status_and_search(
    client_a: TestClient,
    test_db: Session,
    user_a: User,
) -> None:
    """Kiểm tra lọc theo trạng thái status và tìm kiếm từ khóa q."""
    m1 = Meeting(
        id=str(uuid.uuid4()),
        owner_id=user_a.id,
        title="Họp thảo luận kiến trúc vi dịch vụ",
        source="upload",
        status="ready",
        version=1,
    )
    m2 = Meeting(
        id=str(uuid.uuid4()),
        owner_id=user_a.id,
        title="Họp đánh giá hiệu năng pipeline",
        source="upload",
        status="processing",
        version=1,
    )
    m3 = Meeting(
        id=str(uuid.uuid4()),
        owner_id=user_a.id,
        title="Họp sprint planning kiến trúc mới",
        source="upload",
        status="queued",
        version=1,
    )
    test_db.add_all([m1, m2, m3])
    test_db.commit()

    # Lọc theo status=ready
    res_ready = client_a.get("/api/v1/meetings?status=ready")
    assert res_ready.status_code == 200
    assert res_ready.json()["total"] == 1
    assert res_ready.json()["items"][0]["id"] == m1.id

    # Tìm kiếm theo từ khóa "kiến trúc" -> khớp m1 và m3
    res_search = client_a.get("/api/v1/meetings?q=kiến trúc")
    assert res_search.status_code == 200
    assert res_search.json()["total"] == 2
    titles = [item["title"] for item in res_search.json()["items"]]
    assert "Họp thảo luận kiến trúc vi dịch vụ" in titles
    assert "Họp sprint planning kiến trúc mới" in titles


def test_list_meetings_owner_scoping(
    client_a: TestClient,
    client_b: TestClient,
    test_db: Session,
    user_a: User,
    user_b: User,
) -> None:
    """Mỗi người dùng chỉ thấy danh sách cuộc họp do chính mình sở hữu."""
    m_a = Meeting(
        id=str(uuid.uuid4()),
        owner_id=user_a.id,
        title="Cuộc họp riêng của User A",
        source="upload",
        status="queued",
        version=1,
    )
    m_b = Meeting(
        id=str(uuid.uuid4()),
        owner_id=user_b.id,
        title="Cuộc họp riêng của User B",
        source="upload",
        status="queued",
        version=1,
    )
    test_db.add_all([m_a, m_b])
    test_db.commit()

    # User A chỉ thấy meeting của mình
    res_a = client_a.get("/api/v1/meetings")
    assert res_a.status_code == 200
    assert res_a.json()["total"] == 1
    assert res_a.json()["items"][0]["id"] == m_a.id

    # User B chỉ thấy meeting của mình
    res_b = client_b.get("/api/v1/meetings")
    assert res_b.status_code == 200
    assert res_b.json()["total"] == 1
    assert res_b.json()["items"][0]["id"] == m_b.id


def test_get_meeting_detail_with_job_and_speakers(
    client_a: TestClient,
    test_db: Session,
    user_a: User,
) -> None:
    """Lấy chi tiết cuộc họp trả về đúng latest_job và danh sách speakers."""
    meeting_id = str(uuid.uuid4())
    job_id = str(uuid.uuid4())
    speaker_id = str(uuid.uuid4())

    meeting = Meeting(
        id=meeting_id,
        owner_id=user_a.id,
        title="Họp nghiệm thu module M1",
        source="upload",
        status="ready",
        duration_sec=3600.0,
        meeting_date="2026-10-23",
        num_speakers_hint=2,
        version=1,
    )
    job = Job(
        id=job_id,
        meeting_id=meeting_id,
        status="succeeded",
        stage="summarize",
        progress=1.0,
        stage_status={
            "preprocess": "succeeded",
            "vad": "succeeded",
            "asr": "succeeded",
            "diarize": "succeeded",
            "merge": "succeeded",
            "summarize": "succeeded",
        },
        attempt=1,
        max_attempts=3,
    )
    speaker = Speaker(
        id=speaker_id,
        meeting_id=meeting_id,
        label="SPEAKER_00",
        default_name="Speaker 1",
        display_name="Trần Thị B",
        version=1,
    )
    test_db.add_all([meeting, job, speaker])
    test_db.commit()

    response = client_a.get(f"/api/v1/meetings/{meeting_id}")
    assert response.status_code == 200
    data = response.json()

    assert data["id"] == meeting_id
    assert data["title"] == "Họp nghiệm thu module M1"
    assert data["status"] == "ready"
    assert data["latest_job_id"] == job_id

    # Kiểm tra latest_job
    assert data["latest_job"] is not None
    assert data["latest_job"]["id"] == job_id
    assert data["latest_job"]["status"] == "succeeded"
    assert data["latest_job"]["progress"] == 1.0

    # Kiểm tra speakers
    assert len(data["speakers"]) == 1
    spk_out = data["speakers"][0]
    assert spk_out["id"] == speaker_id
    assert spk_out["label"] == "SPEAKER_00"
    assert spk_out["display_name"] == "Trần Thị B"
    assert spk_out["is_edited"] is True


def test_get_meeting_detail_not_found_and_scoping_404(
    client_a: TestClient,
    client_b: TestClient,
    test_db: Session,
    user_a: User,
) -> None:
    """Truy cập meeting không tồn tại hoặc của user khác phải nhận 404 (PRIV-12)."""
    # 1. ID ngẫu nhiên không tồn tại -> 404
    non_existent = str(uuid.uuid4())
    res_404 = client_a.get(f"/api/v1/meetings/{non_existent}")
    assert res_404.status_code == 404
    assert res_404.json()["error"]["code"] == "MEETING_NOT_FOUND"

    # 2. Meeting của User A nhưng User B truy cập -> 404 MEETING_NOT_FOUND (không trả 403)
    meeting_a = Meeting(
        id=str(uuid.uuid4()),
        owner_id=user_a.id,
        title="Dữ liệu nhạy cảm của User A",
        source="upload",
        status="ready",
        version=1,
    )
    test_db.add(meeting_a)
    test_db.commit()

    res_forbidden_as_404 = client_b.get(f"/api/v1/meetings/{meeting_a.id}")
    assert res_forbidden_as_404.status_code == 404
    assert res_forbidden_as_404.status_code != 403
    assert res_forbidden_as_404.json()["error"]["code"] == "MEETING_NOT_FOUND"
