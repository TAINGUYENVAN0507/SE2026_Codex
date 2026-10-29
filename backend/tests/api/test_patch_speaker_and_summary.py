"""Kiểm thử API đổi tên speaker và cập nhật summary (BE-11).

Bao gồm:
- PATCH /meetings/{id}/speakers/{id} đổi display_name, chống trùng tên (422 SPEAKER_NAME_DUPLICATE),
  optimistic locking (409 VERSION_CONFLICT), no-op update, ghi edit_events, owner scoping (PRIV-12).
- PUT /meetings/{id}/summary cập nhật overview/key_points/decisions, optimistic locking,
  giữ nguyên ai_content, no-op update, ghi edit_events, owner scoping (PRIV-12).
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
def users(test_db: Session) -> dict[str, User]:
    """Tạo 2 user để kiểm thử phân quyền và bảo mật."""
    u1 = User(
        id=str(uuid.uuid4()),
        email="owner@example.com",
        password_hash="mock_hash",
        display_name="Owner User",
    )
    u2 = User(
        id=str(uuid.uuid4()),
        email="other@example.com",
        password_hash="mock_hash",
        display_name="Other User",
    )
    test_db.add_all([u1, u2])
    test_db.commit()
    test_db.refresh(u1)
    test_db.refresh(u2)
    return {"owner": u1, "other": u2}


@pytest.fixture
def sample_data(test_db: Session, users: dict[str, User]) -> dict[str, object]:
    """Tạo dữ liệu meeting, speakers, summary mẫu."""
    owner = users["owner"]
    meeting = Meeting(
        id=str(uuid.uuid4()),
        owner_id=owner.id,
        title="Cuộc họp quý 4",
        status="ready",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    test_db.add(meeting)
    test_db.flush()

    spk1 = Speaker(
        id=str(uuid.uuid4()),
        meeting_id=meeting.id,
        label="SPEAKER_00",
        default_name="Speaker 1",
        display_name="Nguyễn Văn A",
        version=1,
    )
    spk2 = Speaker(
        id=str(uuid.uuid4()),
        meeting_id=meeting.id,
        label="SPEAKER_01",
        default_name="Speaker 2",
        display_name="Trần Thị B",
        version=1,
    )
    test_db.add_all([spk1, spk2])
    test_db.flush()

    initial_content = {
        "overview": "Tổng quan ban đầu từ AI",
        "key_points": [{"text": "Điểm 1", "evidence_segment_ids": []}],
        "decisions": [{"text": "Quyết định 1", "evidence_segment_ids": []}],
    }
    summary = Summary(
        id=str(uuid.uuid4()),
        meeting_id=meeting.id,
        status="ready",
        content=initial_content,
        ai_content=initial_content,
        model="gpt-4o",
        prompt_version="v1.0",
        version=1,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    test_db.add(summary)
    test_db.commit()

    return {
        "meeting": meeting,
        "spk1": spk1,
        "spk2": spk2,
        "summary": summary,
    }


def make_client_for_user(user: User, test_db: Session) -> TestClient:
    """Tạo TestClient đã mock current_user."""
    app = create_app()

    def _override_get_db() -> Generator[Session, None, None]:
        yield test_db

    def _override_get_current_user() -> User:
        return user

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_current_user] = _override_get_current_user
    return TestClient(app)


# ==============================================================================
# Tests for PATCH /meetings/{id}/speakers/{speaker_id}
# ==============================================================================


def test_patch_speaker_success(
    test_db: Session, users: dict[str, User], sample_data: dict[str, object]
) -> None:
    """Đổi tên speaker thành công: version tăng 1, is_edited=True, ghi EditEvent."""
    owner = users["owner"]
    meeting = sample_data["meeting"]
    spk1 = sample_data["spk1"]
    client = make_client_for_user(owner, test_db)

    url = f"/api/v1/meetings/{meeting.id}/speakers/{spk1.id}"
    res = client.patch(url, json={"display_name": "Phạm Văn C", "version": 1})

    assert res.status_code == 200
    data = res.json()
    assert data["display_name"] == "Phạm Văn C"
    assert data["version"] == 2
    assert data["is_edited"] is True

    test_db.refresh(spk1)
    assert spk1.display_name == "Phạm Văn C"
    assert spk1.version == 2

    events = (
        test_db.execute(
            select(EditEvent).where(
                EditEvent.meeting_id == meeting.id, EditEvent.entity_id == spk1.id
            )
        )
        .scalars()
        .all()
    )
    assert len(events) == 1
    ev = events[0]
    assert ev.entity_type == "speaker"
    assert ev.action == "update"
    assert ev.field == "display_name"
    assert ev.before == {"display_name": "Nguyễn Văn A"}
    assert ev.after == {"display_name": "Phạm Văn C"}
    assert ev.entity_version_after == 2


def test_patch_speaker_no_op_does_not_bump_version(
    test_db: Session, users: dict[str, User], sample_data: dict[str, object]
) -> None:
    """Đổi cùng tên hiển thị: trả về 200, version không đổi, không ghi EditEvent."""
    owner = users["owner"]
    meeting = sample_data["meeting"]
    spk1 = sample_data["spk1"]
    client = make_client_for_user(owner, test_db)

    url = f"/api/v1/meetings/{meeting.id}/speakers/{spk1.id}"
    res = client.patch(url, json={"display_name": "Nguyễn Văn A", "version": 1})

    assert res.status_code == 200
    data = res.json()
    assert data["display_name"] == "Nguyễn Văn A"
    assert data["version"] == 1

    events = (
        test_db.execute(
            select(EditEvent).where(
                EditEvent.meeting_id == meeting.id, EditEvent.entity_id == spk1.id
            )
        )
        .scalars()
        .all()
    )
    assert len(events) == 0


def test_patch_speaker_duplicate_name_422(
    test_db: Session, users: dict[str, User], sample_data: dict[str, object]
) -> None:
    """Đổi tên trùng với speaker khác trong meeting trả về 422 SPEAKER_NAME_DUPLICATE."""
    owner = users["owner"]
    meeting = sample_data["meeting"]
    spk1 = sample_data["spk1"]
    spk2 = sample_data["spk2"]
    client = make_client_for_user(owner, test_db)

    url = f"/api/v1/meetings/{meeting.id}/speakers/{spk1.id}"
    # Thử đổi tên spk1 thành tên của spk2 (viết hoa/thường khác nhau)
    res = client.patch(url, json={"display_name": spk2.display_name.lower(), "version": 1})

    assert res.status_code == 422
    assert res.json()["error"]["code"] == "SPEAKER_NAME_DUPLICATE"


def test_patch_speaker_case_insensitive_same_speaker_is_allowed(
    test_db: Session, users: dict[str, User], sample_data: dict[str, object]
) -> None:
    """Đổi hoa thường của chính speaker đó không bị xem là trùng tên với speaker khác."""
    owner = users["owner"]
    meeting = sample_data["meeting"]
    spk1 = sample_data["spk1"]
    client = make_client_for_user(owner, test_db)

    url = f"/api/v1/meetings/{meeting.id}/speakers/{spk1.id}"
    res = client.patch(url, json={"display_name": "nguyễn văn a", "version": 1})

    assert res.status_code == 200
    assert res.json()["display_name"] == "nguyễn văn a"
    assert res.json()["version"] == 2


def test_patch_speaker_empty_name_422(
    test_db: Session, users: dict[str, User], sample_data: dict[str, object]
) -> None:
    """Tên rỗng hoặc toàn khoảng trắng trả về 422."""
    owner = users["owner"]
    meeting = sample_data["meeting"]
    spk1 = sample_data["spk1"]
    client = make_client_for_user(owner, test_db)

    url = f"/api/v1/meetings/{meeting.id}/speakers/{spk1.id}"
    res_spaces = client.patch(url, json={"display_name": "     ", "version": 1})
    assert res_spaces.status_code == 422

    res_empty = client.patch(url, json={"display_name": "", "version": 1})
    assert res_empty.status_code == 422


def test_patch_speaker_name_too_long_422(
    test_db: Session, users: dict[str, User], sample_data: dict[str, object]
) -> None:
    """Tên vượt quá 50 ký tự trả về 422."""
    owner = users["owner"]
    meeting = sample_data["meeting"]
    spk1 = sample_data["spk1"]
    client = make_client_for_user(owner, test_db)

    url = f"/api/v1/meetings/{meeting.id}/speakers/{spk1.id}"
    res = client.patch(url, json={"display_name": "A" * 51, "version": 1})
    assert res.status_code == 422


def test_patch_speaker_version_conflict_409(
    test_db: Session, users: dict[str, User], sample_data: dict[str, object]
) -> None:
    """Lệch version trả về 409 VERSION_CONFLICT kèm current version."""
    owner = users["owner"]
    meeting = sample_data["meeting"]
    spk1 = sample_data["spk1"]
    client = make_client_for_user(owner, test_db)

    url = f"/api/v1/meetings/{meeting.id}/speakers/{spk1.id}"
    res = client.patch(url, json={"display_name": "Tên mới", "version": 99})

    assert res.status_code == 409
    assert res.json()["error"]["code"] == "VERSION_CONFLICT"
    assert res.json()["error"]["details"]["current"]["version"] == 1


def test_patch_speaker_owner_scoping_404(
    test_db: Session, users: dict[str, User], sample_data: dict[str, object]
) -> None:
    """User khác cố sửa speaker trong meeting trả về 404 thay vì 403 (PRIV-12)."""
    other = users["other"]
    meeting = sample_data["meeting"]
    spk1 = sample_data["spk1"]
    client = make_client_for_user(other, test_db)

    url = f"/api/v1/meetings/{meeting.id}/speakers/{spk1.id}"
    res = client.patch(url, json={"display_name": "Tên trộm", "version": 1})

    assert res.status_code == 404
    assert res.json()["error"]["code"] in ("MEETING_NOT_FOUND", "NOT_FOUND")


def test_patch_speaker_not_found_404(
    test_db: Session, users: dict[str, User], sample_data: dict[str, object]
) -> None:
    """Speaker ID không tồn tại trả về 404."""
    owner = users["owner"]
    meeting = sample_data["meeting"]
    client = make_client_for_user(owner, test_db)

    url = f"/api/v1/meetings/{meeting.id}/speakers/{uuid.uuid4()}"
    res = client.patch(url, json={"display_name": "Không tồn tại", "version": 1})

    assert res.status_code == 404
    assert res.json()["error"]["code"] in ("SPEAKER_NOT_FOUND", "NOT_FOUND")


# ==============================================================================
# Tests for PUT /meetings/{id}/summary
# ==============================================================================


def test_put_summary_success(
    test_db: Session, users: dict[str, User], sample_data: dict[str, object]
) -> None:
    """Cập nhật summary thành công: version tăng 1, is_edited=True, ghi EditEvent."""
    owner = users["owner"]
    meeting = sample_data["meeting"]
    summary = sample_data["summary"]
    client = make_client_for_user(owner, test_db)

    new_content = {
        "overview": "Tổng quan cuộc họp đã được chỉnh sửa bởi người dùng",
        "key_points": [{"text": "Đã thống nhất kiến trúc backend", "evidence_segment_ids": []}],
        "decisions": [
            {
                "text": "Triển khai optimistic locking cho edit",
                "evidence_segment_ids": [],
            }
        ],
    }

    url = f"/api/v1/meetings/{meeting.id}/summary"
    res = client.put(url, json={"content": new_content, "version": 1})

    assert res.status_code == 200
    data = res.json()
    assert data["content"]["overview"] == "Tổng quan cuộc họp đã được chỉnh sửa bởi người dùng"
    assert data["version"] == 2
    assert data["is_edited"] is True
    # Đảm bảo ai_content ban đầu được bảo toàn
    assert data["ai_content"]["overview"] == "Tổng quan ban đầu từ AI"

    test_db.refresh(summary)
    assert summary.content["overview"] == "Tổng quan cuộc họp đã được chỉnh sửa bởi người dùng"
    assert summary.version == 2

    events = (
        test_db.execute(
            select(EditEvent).where(
                EditEvent.meeting_id == meeting.id, EditEvent.entity_id == summary.id
            )
        )
        .scalars()
        .all()
    )
    assert len(events) == 1
    ev = events[0]
    assert ev.entity_type == "summary"
    assert ev.action == "update"
    assert ev.entity_version_after == 2


def test_put_summary_no_op_does_not_bump_version(
    test_db: Session, users: dict[str, User], sample_data: dict[str, object]
) -> None:
    """Gửi cùng nội dung summary: trả về 200, version không đổi, không ghi EditEvent."""
    owner = users["owner"]
    meeting = sample_data["meeting"]
    summary = sample_data["summary"]
    client = make_client_for_user(owner, test_db)

    url = f"/api/v1/meetings/{meeting.id}/summary"
    res = client.put(url, json={"content": summary.content, "version": 1})

    assert res.status_code == 200
    data = res.json()
    assert data["version"] == 1

    events = (
        test_db.execute(
            select(EditEvent).where(
                EditEvent.meeting_id == meeting.id, EditEvent.entity_id == summary.id
            )
        )
        .scalars()
        .all()
    )
    assert len(events) == 0


def test_put_summary_version_conflict_409(
    test_db: Session, users: dict[str, User], sample_data: dict[str, object]
) -> None:
    """Lệch version summary trả về 409 VERSION_CONFLICT."""
    owner = users["owner"]
    meeting = sample_data["meeting"]
    summary = sample_data["summary"]
    client = make_client_for_user(owner, test_db)

    url = f"/api/v1/meetings/{meeting.id}/summary"
    res = client.put(url, json={"content": summary.content, "version": 99})

    assert res.status_code == 409
    assert res.json()["error"]["code"] == "VERSION_CONFLICT"
    assert res.json()["error"]["details"]["current"]["version"] == 1


def test_put_summary_owner_scoping_404(
    test_db: Session, users: dict[str, User], sample_data: dict[str, object]
) -> None:
    """User khác cố sửa summary trả về 404 (PRIV-12)."""
    other = users["other"]
    meeting = sample_data["meeting"]
    summary = sample_data["summary"]
    client = make_client_for_user(other, test_db)

    url = f"/api/v1/meetings/{meeting.id}/summary"
    res = client.put(url, json={"content": summary.content, "version": 1})

    assert res.status_code == 404
    assert res.json()["error"]["code"] in ("MEETING_NOT_FOUND", "NOT_FOUND")


def test_put_summary_not_found_404(
    test_db: Session, users: dict[str, User], sample_data: dict[str, object]
) -> None:
    """Meeting không tồn tại trả về 404."""
    owner = users["owner"]
    summary = sample_data["summary"]
    client = make_client_for_user(owner, test_db)

    url = f"/api/v1/meetings/{uuid.uuid4()}/summary"
    res = client.put(url, json={"content": summary.content, "version": 1})

    assert res.status_code == 404
    assert res.json()["error"]["code"] in ("MEETING_NOT_FOUND", "NOT_FOUND")


def test_atomic_optimistic_locking_speaker_concurrent(
    test_db: Session, users: dict[str, User], sample_data: dict[str, object]
) -> None:
    """Hai request sửa speaker đồng thời với cùng version=1:
    - 1 request thành công 200, version=2
    - 1 request thất bại 409, current version=2
    - Chỉ có 1 edit event được ghi
    """
    owner = users["owner"]
    meeting = sample_data["meeting"]
    spk1 = sample_data["spk1"]
    client = make_client_for_user(owner, test_db)
    url = f"/api/v1/meetings/{meeting.id}/speakers/{spk1.id}"

    res1 = client.patch(url, json={"display_name": "Tên Mới 1", "version": 1})
    assert res1.status_code == 200
    assert res1.json()["version"] == 2

    res2 = client.patch(url, json={"display_name": "Tên Mới 2", "version": 1})
    assert res2.status_code == 409
    assert res2.json()["error"]["code"] == "VERSION_CONFLICT"
    assert res2.json()["error"]["details"]["current"]["version"] == 2

    events = (
        test_db.execute(
            select(EditEvent).where(
                EditEvent.meeting_id == meeting.id,
                EditEvent.entity_type == "speaker",
                EditEvent.entity_id == spk1.id,
            )
        )
        .scalars()
        .all()
    )
    assert len(events) == 1
    assert events[0].entity_version_after == 2


def test_atomic_optimistic_locking_summary_concurrent(
    test_db: Session, users: dict[str, User], sample_data: dict[str, object]
) -> None:
    """Hai request sửa summary đồng thời với cùng version=1:
    - 1 request thành công 200, version=2
    - 1 request thất bại 409, current version=2
    - Chỉ có 1 edit event được ghi
    """
    owner = users["owner"]
    meeting = sample_data["meeting"]
    summary = sample_data["summary"]
    client = make_client_for_user(owner, test_db)
    url = f"/api/v1/meetings/{meeting.id}/summary"

    c1 = {
        "overview": "Tóm tắt lần 1",
        "key_points": [{"text": "Ý 1", "evidence_segment_ids": []}],
        "decisions": [{"text": "Quyết định 1", "evidence_segment_ids": []}],
    }
    c2 = {
        "overview": "Tóm tắt lần 2",
        "key_points": [{"text": "Ý 2", "evidence_segment_ids": []}],
        "decisions": [{"text": "Quyết định 2", "evidence_segment_ids": []}],
    }

    res1 = client.put(url, json={"content": c1, "version": 1})
    assert res1.status_code == 200
    assert res1.json()["version"] == 2

    res2 = client.put(url, json={"content": c2, "version": 1})
    assert res2.status_code == 409
    assert res2.json()["error"]["code"] == "VERSION_CONFLICT"
    assert res2.json()["error"]["details"]["current"]["version"] == 2

    events = (
        test_db.execute(
            select(EditEvent).where(
                EditEvent.meeting_id == meeting.id,
                EditEvent.entity_type == "summary",
                EditEvent.entity_id == summary.id,
            )
        )
        .scalars()
        .all()
    )
    assert len(events) == 1
    assert events[0].entity_version_after == 2
