"""Kiểm thử API chỉnh sửa tiêu đề cuộc họp (BE-11).

Bao gồm:
- PATCH /meetings/{id} sửa title (1-200 ký tự) kèm version.
- Kiểm tra optimistic locking nguyên tử (409 VERSION_CONFLICT).
- Kiểm tra no-op không đổi version và không ghi EditEvent.
- Kiểm tra validation 422 (tiêu đề rỗng, quá 200 ký tự).
- Kiểm tra phân quyền PRIV-12 (404 khi truy cập meeting của người khác).
- Kiểm tra ghi nhận EditEvent cho trường title.
"""

import uuid
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import get_current_user
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
        Summary.__table__,
        EditEvent.__table__,
        AIOutput.__table__,
        ActionItem.__table__,
    ]
    Base.metadata.create_all(bind=engine, tables=tables)
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = session_factory()

    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def owner_user(test_db: Session) -> User:
    """Tạo người dùng chủ sở hữu cuộc họp."""
    user = User(
        id=str(uuid.uuid4()),
        email="owner@example.com",
        display_name="Chủ Cuộc Họp",
        password_hash="fakehashpassword",
    )
    test_db.add(user)
    test_db.commit()
    test_db.refresh(user)
    return user


@pytest.fixture
def other_user(test_db: Session) -> User:
    """Tạo người dùng khác để kiểm thử phân quyền PRIV-12."""
    user = User(
        id=str(uuid.uuid4()),
        email="other@example.com",
        display_name="Người Dùng Khác",
        password_hash="fakehashpassword",
    )
    test_db.add(user)
    test_db.commit()
    test_db.refresh(user)
    return user


@pytest.fixture
def sample_meeting(test_db: Session, owner_user: User) -> Meeting:
    """Tạo cuộc họp mẫu thuộc owner_user."""
    meeting = Meeting(
        id=str(uuid.uuid4()),
        owner_id=owner_user.id,
        title="Cuộc họp ban giám đốc quý 3",
        source="upload",
        status="ready",
        version=1,
    )
    test_db.add(meeting)
    test_db.commit()
    test_db.refresh(meeting)
    return meeting


@pytest.fixture
def client_owner(test_db: Session, owner_user: User) -> Generator[TestClient, None, None]:
    """Tạo client xác thực bằng owner_user."""
    app = create_app()
    app.dependency_overrides[get_db] = lambda: test_db
    app.dependency_overrides[get_current_user] = lambda: owner_user
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def client_other(test_db: Session, other_user: User) -> Generator[TestClient, None, None]:
    """Tạo client xác thực bằng other_user."""
    app = create_app()
    app.dependency_overrides[get_db] = lambda: test_db
    app.dependency_overrides[get_current_user] = lambda: other_user
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def test_patch_meeting_title_happy_path(
    test_db: Session,
    client_owner: TestClient,
    sample_meeting: Meeting,
    owner_user: User,
):
    """Sửa tiêu đề thành công, version tăng 1, ghi nhận EditEvent."""
    payload = {
        "title": "Cuộc họp ban giám đốc quý 3 - Đã cập nhật",
        "version": 1,
    }
    res = client_owner.patch(f"/api/v1/meetings/{sample_meeting.id}", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["title"] == "Cuộc họp ban giám đốc quý 3 - Đã cập nhật"
    assert data["version"] == 2

    # Kiểm tra DB
    test_db.refresh(sample_meeting)
    assert sample_meeting.title == "Cuộc họp ban giám đốc quý 3 - Đã cập nhật"
    assert sample_meeting.version == 2

    # Kiểm tra EditEvent
    events = (
        test_db.execute(
            select(EditEvent).where(
                EditEvent.meeting_id == sample_meeting.id,
                EditEvent.entity_id == sample_meeting.id,
            )
        )
        .scalars()
        .all()
    )
    assert len(events) == 1
    ev = events[0]
    assert ev.entity_type == "meeting"
    assert ev.action == "update"
    assert ev.field == "title"
    assert ev.before == {"title": "Cuộc họp ban giám đốc quý 3"}
    assert ev.after == {"title": "Cuộc họp ban giám đốc quý 3 - Đã cập nhật"}
    assert ev.entity_version_after == 2
    assert ev.actor_id == owner_user.id


def test_patch_meeting_title_no_op(
    test_db: Session,
    client_owner: TestClient,
    sample_meeting: Meeting,
):
    """Gửi cùng tiêu đề: trả về 200, version không đổi, không ghi EditEvent."""
    payload = {
        "title": "Cuộc họp ban giám đốc quý 3",
        "version": 1,
    }
    res = client_owner.patch(f"/api/v1/meetings/{sample_meeting.id}", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["version"] == 1

    events = (
        test_db.execute(
            select(EditEvent).where(
                EditEvent.meeting_id == sample_meeting.id,
                EditEvent.entity_id == sample_meeting.id,
            )
        )
        .scalars()
        .all()
    )
    assert len(events) == 0


def test_patch_meeting_title_conflict_409(
    test_db: Session,
    client_owner: TestClient,
    sample_meeting: Meeting,
):
    """Gửi sai version trả về 409 VERSION_CONFLICT."""
    payload = {
        "title": "Tiêu đề mới",
        "version": 99,
    }
    res = client_owner.patch(f"/api/v1/meetings/{sample_meeting.id}", json=payload)
    assert res.status_code == 409
    body = res.json()
    assert body["error"]["code"] == "VERSION_CONFLICT"
    assert body["error"]["details"]["current"]["version"] == 1


def test_patch_meeting_title_validation_empty_422(
    client_owner: TestClient,
    sample_meeting: Meeting,
):
    """Tiêu đề rỗng hoặc chỉ có khoảng trắng trả về 422."""
    res = client_owner.patch(
        f"/api/v1/meetings/{sample_meeting.id}",
        json={"title": "   ", "version": 1},
    )
    assert res.status_code == 422


def test_patch_meeting_title_validation_too_long_422(
    client_owner: TestClient,
    sample_meeting: Meeting,
):
    """Tiêu đề dài quá 200 ký tự trả về 422."""
    res = client_owner.patch(
        f"/api/v1/meetings/{sample_meeting.id}",
        json={"title": "a" * 201, "version": 1},
    )
    assert res.status_code == 422


def test_patch_meeting_title_owner_scoping_404(
    client_other: TestClient,
    sample_meeting: Meeting,
):
    """Sửa meeting của người khác trả về 404."""
    res = client_other.patch(
        f"/api/v1/meetings/{sample_meeting.id}",
        json={"title": "Hacked title", "version": 1},
    )
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "MEETING_NOT_FOUND"
