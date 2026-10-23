"""Kiểm thử các ràng buộc toàn vẹn cơ sở dữ liệu và trigger AUD-10 chặn UPDATE edit_events."""

import contextlib
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import create_engine, exc, text
from sqlalchemy.orm import Session

from alembic import command
from app.core.config import get_settings
from app.db.models.action_item import ActionItem
from app.db.models.ai_output import AIOutput
from app.db.models.edit_event import EditEvent
from app.db.models.job import Job
from app.db.models.meeting import Meeting
from app.db.models.transcript import Segment
from app.db.models.user import User


def get_alembic_config(db_url: str) -> Config:
    """Tạo cấu hình Alembic cho database kiểm thử."""
    backend_dir = Path(__file__).resolve().parent.parent.parent
    ini_path = backend_dir / "alembic.ini"
    cfg = Config(str(ini_path))
    cfg.set_main_option("script_location", str(backend_dir / "alembic"))
    cfg.set_main_option("sqlalchemy.url", db_url)
    return cfg


@pytest.fixture
def db_session():
    """Fixture khởi tạo database sạch, chạy migration lên head và cấp Session."""
    settings = get_settings()
    postgres_available = False

    if settings.DATABASE_URL.startswith("postgresql"):
        try:
            connect_args = {"connect_timeout": 1} if "psycopg" in settings.DATABASE_URL else {}
            test_engine = create_engine(settings.DATABASE_URL, connect_args=connect_args)
            with test_engine.connect():
                pass
            postgres_available = True
            db_url = settings.DATABASE_URL
        except Exception:
            postgres_available = False

    test_db_path = None
    if not postgres_available:
        test_db_path = Path(__file__).resolve().parent.parent.parent / "test_integrity.db"
        if test_db_path.exists():
            test_db_path.unlink()
        db_url = f"sqlite:///{test_db_path.as_posix()}"

    cfg = get_alembic_config(db_url)
    command.upgrade(cfg, "head")

    engine = create_engine(db_url)
    session = Session(engine)

    try:
        yield session
    finally:
        session.close()
        command.downgrade(cfg, "base")
        engine.dispose()
        if not postgres_available and test_db_path and test_db_path.exists():
            with contextlib.suppress(Exception):
                test_db_path.unlink()


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
