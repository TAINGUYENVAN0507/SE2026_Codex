"""Kiểm thử API chỉnh sửa transcript segment (BE-11).

Bao gồm:
- PATCH /meetings/{id}/segments/{id} cập nhật text và speaker_id thành công
- Optimistic locking (409 VERSION_CONFLICT)
- Ghi nhận bản ghi edit_events trong cùng transaction
- Không tăng version và không ghi edit_events nếu payload không thay đổi giá trị (no-op)
- Kiểm tra hợp lệ dữ liệu (422 TEXT_EMPTY, TEXT_TOO_LONG, SPEAKER_NOT_IN_MEETING)
- Kiểm tra bảo mật và quyền sở hữu PRIV-12 (404 khi không phải owner hoặc không tìm thấy)
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
from app.db.models.edit_event import EditEvent
from app.db.models.idempotency import IdempotencyKey
from app.db.models.job import Job
from app.db.models.meeting import Meeting
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
        EditEvent.__table__,
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
def meeting_data(test_db: Session, users: dict[str, User]) -> dict[str, object]:
    """Tạo dữ liệu meeting, speaker, segment mẫu."""
    owner = users["owner"]
    meeting = Meeting(
        id=str(uuid.uuid4()),
        owner_id=owner.id,
        title="Cuộc họp sprint planning",
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

    segment = Segment(
        id=str(uuid.uuid4()),
        meeting_id=meeting.id,
        idx=0,
        start_sec=1.5,
        end_sec=5.0,
        speaker_id=spk1.id,
        ai_speaker_id=spk1.id,
        text="Xin chào mọi người",
        ai_text="Xin chào mọi người",
        confidence=0.95,
        flags={"flags": []},
        version=1,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    test_db.add(segment)
    test_db.commit()

    return {
        "meeting": meeting,
        "spk1": spk1,
        "spk2": spk2,
        "segment": segment,
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


def test_patch_segment_text_success(
    test_db: Session, users: dict[str, User], meeting_data: dict[str, object]
) -> None:
    """Kiểm tra sửa text thành công: version tăng 1, is_edited=True, có EditEvent."""
    owner = users["owner"]
    meeting = meeting_data["meeting"]
    segment = meeting_data["segment"]
    client = make_client_for_user(owner, test_db)

    url = f"/api/v1/meetings/{meeting.id}/segments/{segment.id}"
    res = client.patch(url, json={"text": "Xin chào các bạn đã tới buổi họp", "version": 1})

    assert res.status_code == 200
    data = res.json()
    assert data["text"] == "Xin chào các bạn đã tới buổi họp"
    assert data["version"] == 2
    assert data["is_edited"] is True

    # Kiểm tra DB đã cập nhật và có EditEvent
    test_db.refresh(segment)
    assert segment.text == "Xin chào các bạn đã tới buổi họp"
    assert segment.version == 2

    events = (
        test_db.execute(
            select(EditEvent).where(
                EditEvent.meeting_id == meeting.id, EditEvent.entity_id == segment.id
            )
        )
        .scalars()
        .all()
    )
    assert len(events) == 1
    ev = events[0]
    assert ev.entity_type == "segment"
    assert ev.action == "update"
    assert ev.field == "text"
    assert ev.before == {"text": "Xin chào mọi người", "speaker_id": segment.speaker_id}
    assert ev.after == {
        "text": "Xin chào các bạn đã tới buổi họp",
        "speaker_id": segment.speaker_id,
    }
    assert ev.entity_version_after == 2
    assert ev.actor_id == owner.id


def test_patch_segment_speaker_success(
    test_db: Session, users: dict[str, User], meeting_data: dict[str, object]
) -> None:
    """Kiểm tra sửa speaker_id thành công và ghi EditEvent."""
    owner = users["owner"]
    meeting = meeting_data["meeting"]
    spk2 = meeting_data["spk2"]
    segment = meeting_data["segment"]
    client = make_client_for_user(owner, test_db)

    url = f"/api/v1/meetings/{meeting.id}/segments/{segment.id}"
    res = client.patch(url, json={"speaker_id": spk2.id, "version": 1})

    assert res.status_code == 200
    data = res.json()
    assert data["speaker_id"] == spk2.id
    assert data["version"] == 2
    assert data["is_edited"] is True

    events = (
        test_db.execute(
            select(EditEvent).where(
                EditEvent.meeting_id == meeting.id, EditEvent.entity_id == segment.id
            )
        )
        .scalars()
        .all()
    )
    assert len(events) == 1
    assert events[0].field == "speaker_id"
    assert events[0].after["speaker_id"] == spk2.id


def test_patch_segment_both_text_and_speaker(
    test_db: Session, users: dict[str, User], meeting_data: dict[str, object]
) -> None:
    """Kiểm tra sửa cả text và speaker_id cùng lúc."""
    owner = users["owner"]
    meeting = meeting_data["meeting"]
    spk2 = meeting_data["spk2"]
    segment = meeting_data["segment"]
    client = make_client_for_user(owner, test_db)

    url = f"/api/v1/meetings/{meeting.id}/segments/{segment.id}"
    res = client.patch(
        url, json={"text": "Nội dung mới bởi người khác", "speaker_id": spk2.id, "version": 1}
    )

    assert res.status_code == 200
    data = res.json()
    assert data["text"] == "Nội dung mới bởi người khác"
    assert data["speaker_id"] == spk2.id
    assert data["version"] == 2


def test_patch_segment_no_op_does_not_bump_version(
    test_db: Session, users: dict[str, User], meeting_data: dict[str, object]
) -> None:
    """Khi gửi cùng nội dung text và speaker hiện tại:
    trả về 200, giữ nguyên version và không ghi EditEvent.
    """
    owner = users["owner"]
    meeting = meeting_data["meeting"]
    segment = meeting_data["segment"]
    client = make_client_for_user(owner, test_db)

    url = f"/api/v1/meetings/{meeting.id}/segments/{segment.id}"
    res = client.patch(
        url, json={"text": "Xin chào mọi người", "speaker_id": segment.speaker_id, "version": 1}
    )

    assert res.status_code == 200
    data = res.json()
    assert data["version"] == 1

    events = (
        test_db.execute(
            select(EditEvent).where(
                EditEvent.meeting_id == meeting.id, EditEvent.entity_id == segment.id
            )
        )
        .scalars()
        .all()
    )
    assert len(events) == 0


def test_patch_segment_version_conflict_409(
    test_db: Session, users: dict[str, User], meeting_data: dict[str, object]
) -> None:
    """Gửi lệch version trả về 409 VERSION_CONFLICT kèm thông tin version hiện tại."""
    owner = users["owner"]
    meeting = meeting_data["meeting"]
    segment = meeting_data["segment"]
    client = make_client_for_user(owner, test_db)

    url = f"/api/v1/meetings/{meeting.id}/segments/{segment.id}"
    res = client.patch(url, json={"text": "Xung đột version", "version": 99})

    assert res.status_code == 409
    body = res.json()
    assert body["error"]["code"] == "VERSION_CONFLICT"
    assert body["error"]["details"]["current"]["version"] == 1


def test_patch_segment_speaker_not_in_meeting_422(
    test_db: Session, users: dict[str, User], meeting_data: dict[str, object]
) -> None:
    """Gán speaker không thuộc meeting trả về 422 SPEAKER_NOT_IN_MEETING."""
    owner = users["owner"]
    meeting = meeting_data["meeting"]
    segment = meeting_data["segment"]
    client = make_client_for_user(owner, test_db)

    url = f"/api/v1/meetings/{meeting.id}/segments/{segment.id}"
    res = client.patch(url, json={"speaker_id": str(uuid.uuid4()), "version": 1})

    assert res.status_code == 422
    assert res.json()["error"]["code"] == "SPEAKER_NOT_IN_MEETING"


def test_patch_segment_text_empty_422(
    test_db: Session, users: dict[str, User], meeting_data: dict[str, object]
) -> None:
    """Gửi text rỗng hoặc toàn khoảng trắng trả về 422 TEXT_EMPTY."""
    owner = users["owner"]
    meeting = meeting_data["meeting"]
    segment = meeting_data["segment"]
    client = make_client_for_user(owner, test_db)

    url = f"/api/v1/meetings/{meeting.id}/segments/{segment.id}"

    # Gửi chuỗi toàn khoảng trắng
    res_spaces = client.patch(url, json={"text": "     ", "version": 1})
    assert res_spaces.status_code == 422
    assert res_spaces.json()["error"]["code"] == "TEXT_EMPTY"

    # Gửi chuỗi rỗng
    res_empty = client.patch(url, json={"text": "", "version": 1})
    assert res_empty.status_code == 422
    assert res_empty.json()["error"]["code"] == "TEXT_EMPTY"


def test_patch_segment_text_too_long_422(
    test_db: Session, users: dict[str, User], meeting_data: dict[str, object]
) -> None:
    """Gửi text vượt quá 5000 ký tự trả về 422 TEXT_TOO_LONG."""
    owner = users["owner"]
    meeting = meeting_data["meeting"]
    segment = meeting_data["segment"]
    client = make_client_for_user(owner, test_db)

    url = f"/api/v1/meetings/{meeting.id}/segments/{segment.id}"
    long_text = "A" * 5001
    res = client.patch(url, json={"text": long_text, "version": 1})

    assert res.status_code == 422
    assert res.json()["error"]["code"] == "TEXT_TOO_LONG"


def test_patch_segment_owner_scoping_404(
    test_db: Session, users: dict[str, User], meeting_data: dict[str, object]
) -> None:
    """User khác truy cập segment trả về 404 thay vì 403 (PRIV-12)."""
    other = users["other"]
    meeting = meeting_data["meeting"]
    segment = meeting_data["segment"]
    client = make_client_for_user(other, test_db)

    url = f"/api/v1/meetings/{meeting.id}/segments/{segment.id}"
    res = client.patch(url, json={"text": "Thử sửa trộm", "version": 1})

    assert res.status_code == 404
    assert res.json()["error"]["code"] in ("MEETING_NOT_FOUND", "NOT_FOUND")


def test_patch_segment_not_found_404(
    test_db: Session, users: dict[str, User], meeting_data: dict[str, object]
) -> None:
    """Segment không tồn tại trả về 404 NOT_FOUND."""
    owner = users["owner"]
    meeting = meeting_data["meeting"]
    client = make_client_for_user(owner, test_db)

    url = f"/api/v1/meetings/{meeting.id}/segments/{uuid.uuid4()}"
    res = client.patch(url, json={"text": "Không tìm thấy", "version": 1})

    assert res.status_code == 404
    assert res.json()["error"]["code"] in ("SEGMENT_NOT_FOUND", "NOT_FOUND")
