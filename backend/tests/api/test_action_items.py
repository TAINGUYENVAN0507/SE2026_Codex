"""Kiểm thử API Action Items CRUD với xóa mềm và optimistic locking (BE-11).

Bao gồm:
- GET /meetings/{id}/action-items: không trả về item đã xóa mềm, owner-scoping (PRIV-12).
- POST /meetings/{id}/action-items: tạo item source='user', version=1, validation, ghi edit_events.
- PATCH /meetings/{id}/action-items/{id}: optimistic locking (409), no-op, giữ ai_original.
- DELETE /meetings/{id}/action-items/{id}: xóa mềm (deleted_at), version check (409), ghi audit.
"""

import uuid
from collections.abc import Generator
from datetime import UTC, datetime

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
        title="Cuộc họp lập kế hoạch Q4",
        source="upload",
        status="ready",
        version=1,
    )
    test_db.add(meeting)
    test_db.commit()
    test_db.refresh(meeting)
    return meeting


@pytest.fixture
def sample_speakers(test_db: Session, sample_meeting: Meeting) -> list[Speaker]:
    """Tạo 2 speakers thuộc sample_meeting."""
    spk1 = Speaker(
        id=str(uuid.uuid4()),
        meeting_id=sample_meeting.id,
        label="SPEAKER_00",
        default_name="Speaker 1",
        display_name="Anh Minh",
        version=1,
    )
    spk2 = Speaker(
        id=str(uuid.uuid4()),
        meeting_id=sample_meeting.id,
        label="SPEAKER_01",
        default_name="Speaker 2",
        display_name="Chị Lan",
        version=1,
    )
    test_db.add_all([spk1, spk2])
    test_db.commit()
    test_db.refresh(spk1)
    test_db.refresh(spk2)
    return [spk1, spk2]


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


# =========================================================================
# 1. GET /meetings/{id}/action-items
# =========================================================================


def test_get_action_items_empty(client_owner: TestClient, sample_meeting: Meeting):
    """GET danh sách khi chưa có action items nào."""
    res = client_owner.get(f"/api/v1/meetings/{sample_meeting.id}/action-items")
    assert res.status_code == 200
    data = res.json()
    assert data["items"] == []


def test_get_action_items_filters_soft_deleted(
    test_db: Session,
    client_owner: TestClient,
    sample_meeting: Meeting,
):
    """GET danh sách chỉ trả về item chưa bị xóa mềm."""
    now = datetime.now(UTC)
    item_active = ActionItem(
        id=str(uuid.uuid4()),
        meeting_id=sample_meeting.id,
        description="Active task",
        status="open",
        source="user",
        version=1,
        created_at=now,
        updated_at=now,
    )
    item_deleted = ActionItem(
        id=str(uuid.uuid4()),
        meeting_id=sample_meeting.id,
        description="Deleted task",
        status="open",
        source="user",
        deleted_at=now,
        version=2,
        created_at=now,
        updated_at=now,
    )
    test_db.add_all([item_active, item_deleted])
    test_db.commit()

    res = client_owner.get(f"/api/v1/meetings/{sample_meeting.id}/action-items")
    assert res.status_code == 200
    items = res.json()["items"]
    assert len(items) == 1
    assert items[0]["id"] == item_active.id
    assert items[0]["description"] == "Active task"


def test_get_action_items_owner_scoping_404(client_other: TestClient, sample_meeting: Meeting):
    """GET danh sách trả về 404 khi truy cập meeting của người khác."""
    res = client_other.get(f"/api/v1/meetings/{sample_meeting.id}/action-items")
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "NOT_FOUND"


# =========================================================================
# 2. POST /meetings/{id}/action-items
# =========================================================================


def test_post_action_item_happy_path(
    test_db: Session,
    client_owner: TestClient,
    sample_meeting: Meeting,
    sample_speakers: list[Speaker],
):
    """POST tạo mới action item hợp lệ với speaker và due_date."""
    spk = sample_speakers[0]
    payload = {
        "description": "Viết tài liệu API cho frontend",
        "assignee_speaker_id": spk.id,
        "due_date": "2026-10-30",
        "status": "open",
    }
    res = client_owner.post(f"/api/v1/meetings/{sample_meeting.id}/action-items", json=payload)
    assert res.status_code == 201
    data = res.json()
    assert data["description"] == "Viết tài liệu API cho frontend"
    assert data["assignee_name"] == spk.display_name
    assert data["assignee_speaker_id"] == spk.id
    assert data["due_date"] == "2026-10-30"
    assert data["status"] == "open"
    assert data["source"] == "user"
    assert data["version"] == 1
    assert data["is_edited"] is False
    assert data["ai_original"] is None

    # Kiểm tra EditEvent đã được ghi vào DB
    events = (
        test_db.execute(
            select(EditEvent).where(
                EditEvent.entity_id == data["id"],
                EditEvent.action == "create",
            )
        )
        .scalars()
        .all()
    )
    assert len(events) == 1
    ev = events[0]
    assert ev.entity_type == "action_item"
    assert ev.entity_version_after == 1
    assert ev.after["description"] == "Viết tài liệu API cho frontend"


def test_post_action_item_validation_empty_desc_422(
    client_owner: TestClient,
    sample_meeting: Meeting,
):
    """POST thất bại khi description rỗng hoặc chỉ có khoảng trắng."""
    res = client_owner.post(
        f"/api/v1/meetings/{sample_meeting.id}/action-items",
        json={"description": "   "},
    )
    assert res.status_code == 422


def test_post_action_item_validation_desc_too_long_422(
    client_owner: TestClient,
    sample_meeting: Meeting,
):
    """POST thất bại khi description dài quá 1000 ký tự."""
    res = client_owner.post(
        f"/api/v1/meetings/{sample_meeting.id}/action-items",
        json={"description": "a" * 1001},
    )
    assert res.status_code == 422


def test_post_action_item_validation_invalid_status_422(
    client_owner: TestClient,
    sample_meeting: Meeting,
):
    """POST thất bại khi status không phải 'open' hoặc 'done'."""
    res = client_owner.post(
        f"/api/v1/meetings/{sample_meeting.id}/action-items",
        json={"description": "Task", "status": "in_progress"},
    )
    assert res.status_code == 422


def test_post_action_item_speaker_not_in_meeting_422(
    test_db: Session,
    client_owner: TestClient,
    sample_meeting: Meeting,
    owner_user: User,
):
    """POST thất bại khi assignee_speaker_id thuộc meeting khác."""
    other_meeting = Meeting(
        id=str(uuid.uuid4()),
        owner_id=owner_user.id,
        title="Other Meeting",
        source="upload",
        status="ready",
    )
    test_db.add(other_meeting)
    test_db.flush()

    other_spk = Speaker(
        id=str(uuid.uuid4()),
        meeting_id=other_meeting.id,
        label="SPEAKER_00",
        default_name="Speaker X",
        display_name="Speaker X",
    )
    test_db.add(other_spk)
    test_db.commit()

    res = client_owner.post(
        f"/api/v1/meetings/{sample_meeting.id}/action-items",
        json={"description": "Task", "assignee_speaker_id": other_spk.id},
    )
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "SPEAKER_NOT_IN_MEETING"


def test_post_action_item_owner_scoping_404(
    client_other: TestClient,
    sample_meeting: Meeting,
):
    """POST thất bại 404 khi cố tạo item vào meeting của người khác."""
    res = client_other.post(
        f"/api/v1/meetings/{sample_meeting.id}/action-items",
        json={"description": "Hacking"},
    )
    assert res.status_code == 404


# =========================================================================
# 3. PATCH /meetings/{id}/action-items/{item_id}
# =========================================================================


def test_patch_action_item_happy_path_and_preserves_ai_original(
    test_db: Session,
    client_owner: TestClient,
    sample_meeting: Meeting,
):
    """PATCH cập nhật thành công, tăng version, giữ nguyên ai_original nếu là item từ AI."""
    now = datetime.now(UTC)
    ai_orig = {
        "description": "Bản mô tả gốc từ AI",
        "assignee_name": "Nam",
        "due_date": "2026-10-20",
        "due_date_text": "thứ Ba",
    }
    item = ActionItem(
        id=str(uuid.uuid4()),
        meeting_id=sample_meeting.id,
        description="Bản mô tả gốc từ AI",
        assignee_name="Nam",
        status="open",
        source="ai",
        ai_original=ai_orig,
        version=1,
        created_at=now,
        updated_at=now,
    )
    test_db.add(item)
    test_db.commit()

    payload = {
        "description": "Bản mô tả đã được người dùng chỉnh sửa",
        "status": "done",
        "version": 1,
    }
    res = client_owner.patch(
        f"/api/v1/meetings/{sample_meeting.id}/action-items/{item.id}",
        json=payload,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["version"] == 2
    assert data["description"] == "Bản mô tả đã được người dùng chỉnh sửa"
    assert data["status"] == "done"
    assert data["is_edited"] is True
    assert data["ai_original"]["description"] == "Bản mô tả gốc từ AI"

    # Kiểm tra EditEvent
    events = (
        test_db.execute(
            select(EditEvent).where(
                EditEvent.entity_id == item.id,
                EditEvent.action == "update",
            )
        )
        .scalars()
        .all()
    )
    assert len(events) == 1
    assert events[0].entity_version_after == 2


def test_patch_action_item_no_op(
    test_db: Session,
    client_owner: TestClient,
    sample_meeting: Meeting,
):
    """PATCH với giá trị không đổi thì trả về 200, không tăng version và không sinh EditEvent."""
    now = datetime.now(UTC)
    item = ActionItem(
        id=str(uuid.uuid4()),
        meeting_id=sample_meeting.id,
        description="Không đổi",
        status="open",
        source="user",
        version=3,
        created_at=now,
        updated_at=now,
    )
    test_db.add(item)
    test_db.commit()

    payload = {
        "description": "Không đổi",
        "status": "open",
        "version": 3,
    }
    res = client_owner.patch(
        f"/api/v1/meetings/{sample_meeting.id}/action-items/{item.id}",
        json=payload,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["version"] == 3

    events = (
        test_db.execute(select(EditEvent).where(EditEvent.entity_id == item.id)).scalars().all()
    )
    assert len(events) == 0


def test_patch_action_item_optimistic_locking_conflict_409(
    test_db: Session,
    client_owner: TestClient,
    sample_meeting: Meeting,
):
    """PATCH với version không khớp trả về 409 VERSION_CONFLICT."""
    now = datetime.now(UTC)
    item = ActionItem(
        id=str(uuid.uuid4()),
        meeting_id=sample_meeting.id,
        description="Task hiện tại",
        status="open",
        source="user",
        version=2,
        created_at=now,
        updated_at=now,
    )
    test_db.add(item)
    test_db.commit()

    payload = {
        "description": "Sửa trên version cũ",
        "version": 1,
    }
    res = client_owner.patch(
        f"/api/v1/meetings/{sample_meeting.id}/action-items/{item.id}",
        json=payload,
    )
    assert res.status_code == 409
    body = res.json()
    assert body["error"]["code"] == "VERSION_CONFLICT"
    assert body["error"]["details"]["current"]["version"] == 2


def test_patch_action_item_validation_422(
    test_db: Session,
    client_owner: TestClient,
    sample_meeting: Meeting,
):
    """PATCH kiểm tra validation mô tả và trạng thái."""
    now = datetime.now(UTC)
    item = ActionItem(
        id=str(uuid.uuid4()),
        meeting_id=sample_meeting.id,
        description="Valid task",
        status="open",
        source="user",
        version=1,
        created_at=now,
        updated_at=now,
    )
    test_db.add(item)
    test_db.commit()

    # Rỗng
    res = client_owner.patch(
        f"/api/v1/meetings/{sample_meeting.id}/action-items/{item.id}",
        json={"description": "   ", "version": 1},
    )
    assert res.status_code == 422

    # Status sai
    res = client_owner.patch(
        f"/api/v1/meetings/{sample_meeting.id}/action-items/{item.id}",
        json={"status": "invalid_status", "version": 1},
    )
    assert res.status_code == 422


def test_patch_action_item_owner_scoping_404(
    test_db: Session,
    client_other: TestClient,
    sample_meeting: Meeting,
):
    """PATCH trả về 404 khi truy cập meeting của người khác."""
    now = datetime.now(UTC)
    item = ActionItem(
        id=str(uuid.uuid4()),
        meeting_id=sample_meeting.id,
        description="Owner task",
        status="open",
        source="user",
        version=1,
        created_at=now,
        updated_at=now,
    )
    test_db.add(item)
    test_db.commit()

    res = client_other.patch(
        f"/api/v1/meetings/{sample_meeting.id}/action-items/{item.id}",
        json={"description": "Hacked", "version": 1},
    )
    assert res.status_code == 404


# =========================================================================
# 4. DELETE /meetings/{id}/action-items/{item_id}
# =========================================================================


def test_delete_action_item_happy_path(
    test_db: Session,
    client_owner: TestClient,
    sample_meeting: Meeting,
):
    """DELETE xóa mềm item, trả về 204, ghi EditEvent, không còn trong GET."""
    now = datetime.now(UTC)
    item = ActionItem(
        id=str(uuid.uuid4()),
        meeting_id=sample_meeting.id,
        description="Task to delete",
        status="open",
        source="user",
        version=1,
        created_at=now,
        updated_at=now,
    )
    test_db.add(item)
    test_db.commit()

    # Xóa có kèm version=1
    res = client_owner.delete(
        f"/api/v1/meetings/{sample_meeting.id}/action-items/{item.id}?version=1"
    )
    assert res.status_code == 204

    # GET lại không còn item
    get_res = client_owner.get(f"/api/v1/meetings/{sample_meeting.id}/action-items")
    assert get_res.status_code == 200
    assert len(get_res.json()["items"]) == 0

    # DB vẫn còn nhưng deleted_at != None
    deleted_item = test_db.execute(select(ActionItem).where(ActionItem.id == item.id)).scalar_one()
    assert deleted_item.deleted_at is not None
    assert deleted_item.version == 2

    # EditEvent delete được ghi lại
    events = (
        test_db.execute(
            select(EditEvent).where(
                EditEvent.entity_id == item.id,
                EditEvent.action == "delete",
            )
        )
        .scalars()
        .all()
    )
    assert len(events) == 1
    assert events[0].entity_version_after == 2

    # Xóa lần 2 trả về 404
    res2 = client_owner.delete(f"/api/v1/meetings/{sample_meeting.id}/action-items/{item.id}")
    assert res2.status_code == 404


def test_delete_action_item_conflict_409(
    test_db: Session,
    client_owner: TestClient,
    sample_meeting: Meeting,
):
    """DELETE với version không khớp trả về 409 VERSION_CONFLICT."""
    now = datetime.now(UTC)
    item = ActionItem(
        id=str(uuid.uuid4()),
        meeting_id=sample_meeting.id,
        description="Task to delete",
        status="open",
        source="user",
        version=3,
        created_at=now,
        updated_at=now,
    )
    test_db.add(item)
    test_db.commit()

    res = client_owner.delete(
        f"/api/v1/meetings/{sample_meeting.id}/action-items/{item.id}?version=2"
    )
    assert res.status_code == 409
    assert res.json()["error"]["code"] == "VERSION_CONFLICT"


def test_delete_action_item_owner_scoping_404(
    test_db: Session,
    client_other: TestClient,
    sample_meeting: Meeting,
):
    """DELETE trả về 404 khi truy cập meeting của người khác."""
    now = datetime.now(UTC)
    item = ActionItem(
        id=str(uuid.uuid4()),
        meeting_id=sample_meeting.id,
        description="Task to delete",
        status="open",
        source="user",
        version=1,
        created_at=now,
        updated_at=now,
    )
    test_db.add(item)
    test_db.commit()

    res = client_other.delete(f"/api/v1/meetings/{sample_meeting.id}/action-items/{item.id}")
    assert res.status_code == 404
