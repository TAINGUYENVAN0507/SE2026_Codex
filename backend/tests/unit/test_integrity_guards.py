"""Kiểm thử các ràng buộc toàn vẹn cơ sở dữ liệu và trigger AUD-10 chặn UPDATE edit_events."""

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import exc, text, update
from sqlalchemy.orm import Session

from app.db.models.action_item import ActionItem
from app.db.models.ai_output import AIOutput
from app.db.models.edit_event import EditEvent
from app.db.models.job import Job
from app.db.models.meeting import Meeting
from app.db.models.transcript import Segment
from app.db.models.user import User


def _create_sample_meeting(session: Session) -> tuple[User, Meeting]:
    """Hàm trợ giúp tạo User và Meeting mẫu cho các test case."""
    user = User(
        id=str(uuid.uuid4()),
        email=f"user_{uuid.uuid4().hex[:8]}@example.com",
        display_name="Test User",
        password_hash="hashed_pw",
    )
    session.add(user)
    session.commit()

    meeting = Meeting(
        id=str(uuid.uuid4()),
        owner_id=user.id,
        title="Sample Meeting",
    )
    session.add(meeting)
    session.commit()
    return user, meeting


def test_aud10_edit_events_update_prevented_by_trigger(db_session: Session) -> None:
    """AUD-10: Chứng minh bảng edit_events là append-only và mọi UPDATE bị từ chối."""
    user, meeting = _create_sample_meeting(db_session)

    event = EditEvent(
        id=str(uuid.uuid4()),
        meeting_id=meeting.id,
        actor_id=user.id,
        entity_type="segment",
        entity_id=str(uuid.uuid4()),
        action="update",
        field="text",
        before={"text": "Chào các bạn"},
        after={"text": "Chào mọi người"},
        entity_version_after=2,
        request_id="req-test-aud10",
    )
    db_session.add(event)
    db_session.commit()

    # Thử UPDATE bản ghi edit_event -> Trigger phải chặn và ném exception
    with pytest.raises(exc.DBAPIError) as exc_info:
        db_session.execute(
            text("UPDATE edit_events SET action = 'tampered' WHERE id = :event_id"),
            {"event_id": event.id},
        )
        db_session.commit()

    assert "append-only" in str(exc_info.value).lower() or "abort" in str(exc_info.value).lower()
    db_session.rollback()


def test_aud11_edit_events_delete_prevented_by_trigger(db_session: Session) -> None:
    """AUD-11: Chứng minh bảng edit_events là append-only và mọi DELETE bị từ chối."""
    user, meeting = _create_sample_meeting(db_session)

    event = EditEvent(
        id=str(uuid.uuid4()),
        meeting_id=meeting.id,
        actor_id=user.id,
        entity_type="segment",
        entity_id=str(uuid.uuid4()),
        action="update",
        field="text",
        before={"text": "Chào các bạn"},
        after={"text": "Chào mọi người"},
        entity_version_after=2,
        request_id="req-test-aud11",
    )
    db_session.add(event)
    db_session.commit()

    # Thử DELETE bản ghi edit_event -> Trigger phải chặn và ném exception
    with pytest.raises(exc.DBAPIError) as exc_info:
        db_session.execute(
            text("DELETE FROM edit_events WHERE id = :event_id"),
            {"event_id": event.id},
        )
        db_session.commit()

    assert "append-only" in str(exc_info.value).lower() or "abort" in str(exc_info.value).lower()
    db_session.rollback()


def test_segments_time_range_check_constraint(db_session: Session) -> None:
    """Kiểm tra ràng buộc CHECK 0 <= start_sec < end_sec của bảng segments."""
    _, meeting = _create_sample_meeting(db_session)

    # 1. start_sec >= end_sec -> Bị từ chối
    invalid_segment_reverse = Segment(
        id=str(uuid.uuid4()),
        meeting_id=meeting.id,
        idx=0,
        start_sec=10.5,
        end_sec=5.0,
        text="Đoạn văn ngược thời gian",
        ai_text="Đoạn văn ngược thời gian",
    )
    db_session.add(invalid_segment_reverse)
    with pytest.raises(exc.IntegrityError):
        db_session.commit()
    db_session.rollback()

    # 2. start_sec < 0 -> Bị từ chối
    invalid_segment_negative = Segment(
        id=str(uuid.uuid4()),
        meeting_id=meeting.id,
        idx=0,
        start_sec=-1.0,
        end_sec=5.0,
        text="Đoạn văn âm thời gian",
        ai_text="Đoạn văn âm thời gian",
    )
    db_session.add(invalid_segment_negative)
    with pytest.raises(exc.IntegrityError):
        db_session.commit()
    db_session.rollback()

    # 3. 0 <= start_sec < end_sec -> Thành công
    valid_segment = Segment(
        id=str(uuid.uuid4()),
        meeting_id=meeting.id,
        idx=0,
        start_sec=0.0,
        end_sec=2.5,
        text="Đoạn văn hợp lệ",
        ai_text="Đoạn văn hợp lệ",
    )
    db_session.add(valid_segment)
    db_session.commit()
    assert valid_segment.id is not None


def test_ai_outputs_unique_job_stage(db_session: Session) -> None:
    """Kiểm tra ràng buộc duy nhất (job_id, stage) trên bảng ai_outputs."""
    _, meeting = _create_sample_meeting(db_session)

    job = Job(
        id=str(uuid.uuid4()),
        meeting_id=meeting.id,
        status="running",
    )
    db_session.add(job)
    db_session.commit()

    output1 = AIOutput(
        id=str(uuid.uuid4()),
        meeting_id=meeting.id,
        job_id=job.id,
        stage="asr",
        payload={"text": "kết quả ASR"},
    )
    db_session.add(output1)
    db_session.commit()

    # Ghi trùng cùng (job_id, stage) -> Bị unique index từ chối
    output2 = AIOutput(
        id=str(uuid.uuid4()),
        meeting_id=meeting.id,
        job_id=job.id,
        stage="asr",
        payload={"text": "kết quả trùng"},
    )
    db_session.add(output2)
    with pytest.raises(exc.IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_action_items_soft_delete(db_session: Session) -> None:
    """Kiểm tra thao tác xóa mềm deleted_at trên action_items."""
    _, meeting = _create_sample_meeting(db_session)

    item = ActionItem(
        id=str(uuid.uuid4()),
        meeting_id=meeting.id,
        description="Nhiệm vụ kiểm tra xóa mềm",
        status="open",
        source="ai",
    )
    db_session.add(item)
    db_session.commit()

    assert item.deleted_at is None

    # Thực hiện xóa mềm
    now_utc = datetime.now(UTC)
    item.deleted_at = now_utc
    db_session.commit()

    db_session.refresh(item)
    assert item.deleted_at is not None


def test_be11_optimistic_locking_conditional_update_postgres(db_session: Session) -> None:
    """BE-11: Kiểm tra conditional update với optimistic locking trên cơ sở dữ liệu.
    Hai phiên cùng UPDATE cùng version ban đầu:
    - Phiên 1 thành công (rowcount == 1, version -> 2)
    - Phiên 2 chạy sau với version cũ thì rowcount == 0 (bị chặn)
    """
    _, meeting = _create_sample_meeting(db_session)

    segment = Segment(
        id=str(uuid.uuid4()),
        meeting_id=meeting.id,
        idx=0,
        start_sec=0.0,
        end_sec=5.0,
        text="Văn bản gốc",
        ai_text="Văn bản gốc",
        version=1,
    )
    db_session.add(segment)
    db_session.commit()

    # Phiên 1: UPDATE có điều kiện WHERE version = 1 thành công
    res1 = db_session.execute(
        update(Segment)
        .where(
            Segment.id == segment.id,
            Segment.meeting_id == meeting.id,
            Segment.version == 1,
        )
        .values(
            text="Văn bản cập nhật bởi phiên 1",
            version=2,
        )
    )
    db_session.commit()
    assert res1.rowcount == 1

    # Phiên 2: Giả lập phiên khác cũng gửi với version = 1 (chưa đọc bản mới) -> rowcount == 0
    res2 = db_session.execute(
        update(Segment)
        .where(
            Segment.id == segment.id,
            Segment.meeting_id == meeting.id,
            Segment.version == 1,
        )
        .values(
            text="Văn bản cập nhật bởi phiên 2 (ghi đè hụt)",
            version=2,
        )
    )
    db_session.commit()
    assert res2.rowcount == 0

    # Kiểm tra DB giữ nguyên bản sửa của phiên 1
    db_session.refresh(segment)
    assert segment.version == 2
    assert segment.text == "Văn bản cập nhật bởi phiên 1"
