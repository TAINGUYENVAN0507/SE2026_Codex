"""Kiểm thử API đọc tóm tắt cuộc họp từ database (BE-05, BE-07).

Bao gồm:
- GET /meetings/{id}/summary cho từng trạng thái:
  ready, pending, failed, insufficient_content, disabled
- Trả về đúng evidence_segment_ids, version, is_edited
- Phản hồi khi meeting chưa có bản ghi summary trong DB
- PRIV-12: Trả về 404 khi truy cập meeting của người khác
- Trả về 404 khi meeting không tồn tại
- Trả về 401 khi chưa đăng nhập
"""

import uuid
from collections.abc import Generator
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import create_access_token
from app.db.base import Base
from app.db.models.meeting import Meeting
from app.db.models.summary import Summary
from app.db.models.transcript import Segment
from app.db.models.user import User
from app.db.session import get_db
from app.main import create_app
from app.schemas.summary import SummaryOut


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
        Segment.__table__,
        Summary.__table__,
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
def app_with_db(test_db: Session):
    """Tạo FastAPI application gắn kèm database test."""
    app = create_app()

    def _override_get_db() -> Generator[Session, None, None]:
        yield test_db

    app.dependency_overrides[get_db] = _override_get_db
    return app


@pytest.fixture
def users(test_db: Session) -> dict[str, User]:
    """Tạo user A (owner) và user B."""
    user_a = User(
        id=str(uuid.uuid4()),
        email="user_a@example.com",
        display_name="User A",
        password_hash="mock_hash_a",
    )
    user_b = User(
        id=str(uuid.uuid4()),
        email="user_b@example.com",
        display_name="User B",
        password_hash="mock_hash_b",
    )
    test_db.add_all([user_a, user_b])
    test_db.commit()
    return {"a": user_a, "b": user_b}


def create_auth_client(app, user: User | None) -> TestClient:
    """Tạo client kèm cookie xác thực nếu user được cung cấp."""
    client = TestClient(app)
    if user:
        token = create_access_token(user.id)
        client.cookies.set("session_token", token)
    return client


def test_get_summary_ready(app_with_db, test_db: Session, users: dict[str, User]) -> None:
    """Kiểm tra GET /summary ở trạng thái ready có đầy đủ evidence, version, is_edited."""
    owner = users["a"]
    meeting = Meeting(
        id=str(uuid.uuid4()),
        owner_id=owner.id,
        title="Cuộc họp sprint planning",
        source="upload",
        status="ready",
        version=1,
    )
    test_db.add(meeting)
    test_db.flush()

    seg_id = str(uuid.uuid4())
    content = {
        "overview": "Tổng quan nội dung cuộc họp",
        "key_points": [{"text": "Hoàn thiện upload audio", "evidence_segment_ids": [seg_id]}],
        "decisions": [{"text": "Lùi export DOCX", "evidence_segment_ids": []}],
    }

    summary = Summary(
        id=str(uuid.uuid4()),
        meeting_id=meeting.id,
        status="ready",
        content=content,
        ai_content=content,
        model="claude-opus-5-5",
        prompt_version="summary-v1",
        version=1,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    test_db.add(summary)
    test_db.commit()

    client = create_auth_client(app_with_db, owner)
    response = client.get(f"/api/v1/meetings/{meeting.id}/summary")
    assert response.status_code == 200

    data = response.json()
    result = SummaryOut.model_validate(data)
    assert result.status == "ready"
    assert result.is_edited is False
    assert result.version == 1
    assert result.model == "claude-opus-5-5"
    assert result.prompt_version == "summary-v1"
    assert result.content is not None
    assert len(result.content.key_points) == 1
    assert result.content.key_points[0].evidence_segment_ids == [seg_id]


def test_get_summary_edited(app_with_db, test_db: Session, users: dict[str, User]) -> None:
    """Kiểm tra is_edited=True khi content khác ai_content."""
    owner = users["a"]
    meeting = Meeting(
        id=str(uuid.uuid4()),
        owner_id=owner.id,
        title="Cuộc họp đã sửa summary",
        source="upload",
        status="ready",
        version=1,
    )
    test_db.add(meeting)
    test_db.flush()

    ai_content = {
        "overview": "Tổng quan ban đầu từ AI",
        "key_points": [{"text": "Điểm AI", "evidence_segment_ids": []}],
        "decisions": [],
    }
    user_content = {
        "overview": "Tổng quan đã được người dùng chỉnh sửa",
        "key_points": [{"text": "Điểm đã sửa", "evidence_segment_ids": []}],
        "decisions": [],
    }

    summary = Summary(
        id=str(uuid.uuid4()),
        meeting_id=meeting.id,
        status="ready",
        content=user_content,
        ai_content=ai_content,
        model="claude-opus-5-5",
        prompt_version="summary-v1",
        version=2,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    test_db.add(summary)
    test_db.commit()

    client = create_auth_client(app_with_db, owner)
    response = client.get(f"/api/v1/meetings/{meeting.id}/summary")
    assert response.status_code == 200

    data = response.json()
    result = SummaryOut.model_validate(data)
    assert result.status == "ready"
    assert result.is_edited is True
    assert result.version == 2
    assert result.content.overview == "Tổng quan đã được người dùng chỉnh sửa"
    assert result.ai_content.overview == "Tổng quan ban đầu từ AI"


@pytest.mark.parametrize("status_val", ["pending", "failed", "insufficient_content", "disabled"])
def test_get_summary_other_statuses(
    app_with_db, test_db: Session, users: dict[str, User], status_val: str
) -> None:
    """Kiểm tra các trạng thái khác: pending, failed, insufficient_content, disabled."""
    owner = users["a"]
    meeting = Meeting(
        id=str(uuid.uuid4()),
        owner_id=owner.id,
        title=f"Cuộc họp {status_val}",
        source="upload",
        status="ready" if status_val != "failed" else "failed",
        version=1,
    )
    test_db.add(meeting)
    test_db.flush()

    summary = Summary(
        id=str(uuid.uuid4()),
        meeting_id=meeting.id,
        status=status_val,
        content=None,
        ai_content=None,
        version=1,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    test_db.add(summary)
    test_db.commit()

    client = create_auth_client(app_with_db, owner)
    response = client.get(f"/api/v1/meetings/{meeting.id}/summary")
    assert response.status_code == 200

    result = SummaryOut.model_validate(response.json())
    assert result.status == status_val
    assert result.content is None
    assert result.is_edited is False


def test_get_summary_when_row_not_exists_yet(
    app_with_db, test_db: Session, users: dict[str, User]
) -> None:
    """Khi meeting mới tạo đang processing chưa có dòng summary trong DB -> pending."""
    owner = users["a"]
    meeting = Meeting(
        id=str(uuid.uuid4()),
        owner_id=owner.id,
        title="Cuộc họp đang xử lý",
        source="upload",
        status="processing",
        version=1,
    )
    test_db.add(meeting)
    test_db.commit()

    client = create_auth_client(app_with_db, owner)
    response = client.get(f"/api/v1/meetings/{meeting.id}/summary")
    assert response.status_code == 200

    result = SummaryOut.model_validate(response.json())
    assert result.status == "pending"
    assert result.content is None


def test_get_summary_priv12_other_user_404(
    app_with_db, test_db: Session, users: dict[str, User]
) -> None:
    """PRIV-12: User B truy cập summary của User A phải nhận 404 (không lộ 403)."""
    user_a = users["a"]
    user_b = users["b"]

    meeting = Meeting(
        id=str(uuid.uuid4()),
        owner_id=user_a.id,
        title="Cuộc họp bí mật của User A",
        source="upload",
        status="ready",
        version=1,
    )
    test_db.add(meeting)
    test_db.commit()

    client = create_auth_client(app_with_db, user_b)
    response = client.get(f"/api/v1/meetings/{meeting.id}/summary")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "MEETING_NOT_FOUND"


def test_get_summary_non_existent_meeting_404(app_with_db, users: dict[str, User]) -> None:
    """Truy cập summary của meeting không tồn tại trả về 404."""
    owner = users["a"]
    client = create_auth_client(app_with_db, owner)
    response = client.get(f"/api/v1/meetings/{uuid.uuid4()}/summary")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "MEETING_NOT_FOUND"


def test_get_summary_unauthenticated_401(app_with_db) -> None:
    """Chưa xác thực trả về 401 UNAUTHENTICATED."""
    client = TestClient(app_with_db)
    response = client.get(f"/api/v1/meetings/{uuid.uuid4()}/summary")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHENTICATED"
