"""Kiểm thử API lấy lịch sử chỉnh sửa audit GET /meetings/{id}/edits (BE-12).

Bao gồm:
- Lọc theo entity_type, entity_id, field.
- Phân trang theo (page, page_size) và (limit, offset).
- Sắp xếp mới nhất lên đầu.
- Phân quyền PRIV-12 (404 khi truy cập meeting của người khác).
"""

import uuid
from collections.abc import Generator
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
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
        display_name="Nguyễn Văn A",
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
        title="Cuộc họp kiểm thử audit",
        source="upload",
        status="ready",
        version=1,
    )
    test_db.add(meeting)
    test_db.commit()
    test_db.refresh(meeting)
    return meeting


@pytest.fixture
def seed_events(test_db: Session, sample_meeting: Meeting, owner_user: User) -> list[EditEvent]:
    """Tạo các sự kiện audit mẫu với thời gian khác nhau."""
    base_time = datetime.now(UTC) - timedelta(hours=5)

    ev1 = EditEvent(
        id=str(uuid.uuid4()),
        meeting_id=sample_meeting.id,
        actor_id=owner_user.id,
        entity_type="segment",
        entity_id="seg-1",
        action="update",
        field="text",
        before={"text": "Văn bản cũ 1"},
        after={"text": "Văn bản mới 1"},
        entity_version_after=2,
        request_id="req-1",
        created_at=base_time + timedelta(minutes=10),
    )
    ev2 = EditEvent(
        id=str(uuid.uuid4()),
        meeting_id=sample_meeting.id,
        actor_id=owner_user.id,
        entity_type="segment",
        entity_id="seg-1",
        action="update",
        field="speaker_id",
        before={"speaker_id": "spk-1"},
        after={"speaker_id": "spk-2"},
        entity_version_after=2,
        request_id="req-1",
        created_at=base_time + timedelta(minutes=20),
    )
    ev3 = EditEvent(
        id=str(uuid.uuid4()),
        meeting_id=sample_meeting.id,
        actor_id=owner_user.id,
        entity_type="speaker",
        entity_id="spk-1",
        action="update",
        field="display_name",
        before={"display_name": "Speaker 1"},
        after={"display_name": "Chị Hoa"},
        entity_version_after=2,
        request_id="req-2",
        created_at=base_time + timedelta(minutes=30),
    )
    ev4 = EditEvent(
        id=str(uuid.uuid4()),
        meeting_id=sample_meeting.id,
        actor_id=owner_user.id,
        entity_type="meeting",
        entity_id=sample_meeting.id,
        action="update",
        field="title",
        before={"title": "Cuộc họp kiểm thử audit"},
        after={"title": "Tiêu đề mới"},
        entity_version_after=2,
        request_id="req-3",
        created_at=base_time + timedelta(minutes=40),
    )
    events = [ev1, ev2, ev3, ev4]
    test_db.add_all(events)
    test_db.commit()
    return events


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


def test_list_edits_all_sorted_newest_first(
    client_owner: TestClient,
    sample_meeting: Meeting,
    seed_events: list[EditEvent],
    owner_user: User,
):
    """GET danh sách audit: mặc định trả về tất cả sắp xếp mới nhất lên đầu."""
    res = client_owner.get(f"/api/v1/meetings/{sample_meeting.id}/edits")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 4
    items = data["items"]
    assert len(items) == 4
    # ev4 được tạo muộn nhất nên đứng đầu
    assert items[0]["entity_type"] == "meeting"
    assert items[0]["field"] == "title"
    assert items[0]["actor"]["id"] == owner_user.id
    assert items[0]["actor"]["display_name"] == owner_user.display_name

    # ev1 được tạo sớm nhất nên đứng cuối
    assert items[3]["entity_type"] == "segment"
    assert items[3]["field"] == "text"


def test_list_edits_filter_by_entity_type(
    client_owner: TestClient,
    sample_meeting: Meeting,
    seed_events: list[EditEvent],
):
    """Lọc theo entity_type='segment'."""
    res = client_owner.get(f"/api/v1/meetings/{sample_meeting.id}/edits?entity_type=segment")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 2
    for item in data["items"]:
        assert item["entity_type"] == "segment"


def test_list_edits_filter_by_field(
    client_owner: TestClient,
    sample_meeting: Meeting,
    seed_events: list[EditEvent],
):
    """Lọc theo field='speaker_id'."""
    res = client_owner.get(f"/api/v1/meetings/{sample_meeting.id}/edits?field=speaker_id")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 1
    assert data["items"][0]["field"] == "speaker_id"


def test_list_edits_filter_by_entity_id(
    client_owner: TestClient,
    sample_meeting: Meeting,
    seed_events: list[EditEvent],
):
    """Lọc theo entity_id='spk-1'."""
    res = client_owner.get(f"/api/v1/meetings/{sample_meeting.id}/edits?entity_id=spk-1")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 1
    assert data["items"][0]["entity_type"] == "speaker"


def test_list_edits_pagination_page_page_size(
    client_owner: TestClient,
    sample_meeting: Meeting,
    seed_events: list[EditEvent],
):
    """Phân trang theo page và page_size."""
    # Trang 1 lấy 2 bản ghi
    res1 = client_owner.get(f"/api/v1/meetings/{sample_meeting.id}/edits?page=1&page_size=2")
    assert res1.status_code == 200
    d1 = res1.json()
    assert d1["total"] == 4
    assert len(d1["items"]) == 2
    first_id = d1["items"][0]["id"]

    # Trang 2 lấy 2 bản ghi tiếp theo
    res2 = client_owner.get(f"/api/v1/meetings/{sample_meeting.id}/edits?page=2&page_size=2")
    assert res2.status_code == 200
    d2 = res2.json()
    assert d2["total"] == 4
    assert len(d2["items"]) == 2
    assert d2["items"][0]["id"] != first_id


def test_list_edits_pagination_limit_offset(
    client_owner: TestClient,
    sample_meeting: Meeting,
    seed_events: list[EditEvent],
):
    """Phân trang theo limit và offset."""
    res = client_owner.get(f"/api/v1/meetings/{sample_meeting.id}/edits?limit=2&offset=1")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 4
    assert len(data["items"]) == 2


def test_list_edits_owner_scoping_404(
    client_other: TestClient,
    sample_meeting: Meeting,
    seed_events: list[EditEvent],
):
    """Truy cập meeting của người khác trả về 404 NOT_FOUND."""
    res = client_other.get(f"/api/v1/meetings/{sample_meeting.id}/edits")
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "NOT_FOUND"
