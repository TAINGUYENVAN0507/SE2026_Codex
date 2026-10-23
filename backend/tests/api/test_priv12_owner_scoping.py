"""Kiểm thử bảo mật PRIV-12: phân quyền owner và trả về 404 thay vì 403."""

import uuid
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import create_access_token, hash_password
from app.db.base import Base
from app.db.models.job import Job
from app.db.models.meeting import Meeting
from app.db.models.user import User
from app.db.session import get_db
from app.main import create_app


@pytest.fixture
def test_db() -> Generator[Session, None, None]:
    """Tạo database in-memory cho kiểm thử PRIV-12."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine, tables=[User.__table__, Meeting.__table__, Job.__table__])
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = session_factory()

    try:
        yield session
    finally:
        session.close()
        tables = [User.__table__, Meeting.__table__, Job.__table__]
        Base.metadata.drop_all(bind=engine, tables=tables)
        engine.dispose()


@pytest.fixture
def client(test_db: Session) -> Generator[TestClient, None, None]:
    """FastAPI TestClient kết nối in-memory database."""
    app = create_app()

    def _override_get_db() -> Generator[Session, None, None]:
        yield test_db

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def test_priv12_unauthenticated_request_returns_401(client: TestClient) -> None:
    """Yêu cầu chưa xác thực tới /meetings và /jobs phải trả về 401 UNAUTHENTICATED."""
    meeting_id = str(uuid.uuid4())
    job_id = str(uuid.uuid4())

    res_meeting = client.get(f"/api/v1/meetings/{meeting_id}")
    assert res_meeting.status_code == 401
    assert res_meeting.json()["error"]["code"] == "UNAUTHENTICATED"

    res_meetings_list = client.get("/api/v1/meetings")
    assert res_meetings_list.status_code == 401
    assert res_meetings_list.json()["error"]["code"] == "UNAUTHENTICATED"

    res_job = client.get(f"/api/v1/jobs/{job_id}")
    assert res_job.status_code == 401
    assert res_job.json()["error"]["code"] == "UNAUTHENTICATED"


def test_priv12_user_b_accessing_user_a_meeting_returns_404(
    client: TestClient, test_db: Session
) -> None:
    """PRIV-12: User B truy cập cuộc họp của User A phải nhận 404 (không được trả 403)."""
    # 1. Tạo User A và User B
    user_a = User(
        id=str(uuid.uuid4()),
        email="user_a@example.com",
        display_name="User A",
        password_hash=hash_password("PassA_123!"),
    )
    user_b = User(
        id=str(uuid.uuid4()),
        email="user_b@example.com",
        display_name="User B",
        password_hash=hash_password("PassB_123!"),
    )
    test_db.add_all([user_a, user_b])
    test_db.commit()

    # 2. Tạo Meeting thuộc quyền sở hữu của User A
    meeting_a = Meeting(
        id=str(uuid.uuid4()),
        owner_id=user_a.id,
        title="Cuộc họp nội bộ của User A",
        source="upload",
        status="ready",
    )
    test_db.add(meeting_a)
    test_db.commit()

    # 3. Đăng nhập với danh nghĩa User B
    token_b = create_access_token(user_b.id)
    client.cookies.set("session_token", token_b)

    # 4. User B truy cập meeting của User A -> Phải trả 404, TUYỆT ĐỐI không trả 403
    response = client.get(f"/api/v1/meetings/{meeting_a.id}")
    assert response.status_code == 404
    assert response.status_code != 403
    assert response.json()["error"]["code"] in ("MEETING_NOT_FOUND", "NOT_FOUND")


def test_priv12_user_a_accessing_own_meeting_returns_200(
    client: TestClient, test_db: Session
) -> None:
    """User A truy cập cuộc họp của chính mình thành công (200 OK)."""
    user_a = User(
        id=str(uuid.uuid4()),
        email="owner@example.com",
        display_name="Owner User",
        password_hash=hash_password("Pass_123!"),
    )
    test_db.add(user_a)
    test_db.commit()

    meeting_a = Meeting(
        id=str(uuid.uuid4()),
        owner_id=user_a.id,
        title="Cuộc họp chính chủ",
        source="upload",
        status="ready",
    )
    test_db.add(meeting_a)
    test_db.commit()

    token_a = create_access_token(user_a.id)
    client.cookies.set("session_token", token_a)

    response = client.get(f"/api/v1/meetings/{meeting_a.id}")
    assert response.status_code == 200
    assert response.json()["id"] == meeting_a.id


def test_priv12_user_b_accessing_user_a_job_returns_404(
    client: TestClient, test_db: Session
) -> None:
    """User B truy cập Job thuộc meeting của User A phải nhận 404 (không được trả 403)."""
    user_a = User(
        id=str(uuid.uuid4()),
        email="user_a_job@example.com",
        display_name="User A Job",
        password_hash=hash_password("PassA_123!"),
    )
    user_b = User(
        id=str(uuid.uuid4()),
        email="user_b_job@example.com",
        display_name="User B Job",
        password_hash=hash_password("PassB_123!"),
    )
    test_db.add_all([user_a, user_b])
    test_db.commit()

    meeting_a = Meeting(
        id=str(uuid.uuid4()),
        owner_id=user_a.id,
        title="Cuộc họp có Job của User A",
    )
    test_db.add(meeting_a)
    test_db.commit()

    job_a = Job(
        id=str(uuid.uuid4()),
        meeting_id=meeting_a.id,
        status="running",
    )
    test_db.add(job_a)
    test_db.commit()

    # User B đăng nhập và cố truy cập job của User A
    token_b = create_access_token(user_b.id)
    client.cookies.set("session_token", token_b)

    response = client.get(f"/api/v1/jobs/{job_a.id}")
    assert response.status_code == 404
    assert response.status_code != 403
    assert response.json()["error"]["code"] == "NOT_FOUND"
