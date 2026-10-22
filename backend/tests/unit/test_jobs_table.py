"""Kiểm thử ràng buộc toàn vẹn của bảng jobs."""

import contextlib
import uuid
from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import create_engine, exc
from sqlalchemy.orm import Session

from alembic import command
from app.core.config import get_settings
from app.db.models.job import Job
from app.db.models.meeting import Meeting
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
    """Fixture khởi tạo database sạch, áp dụng migration và cung cấp session."""
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
        test_db_path = Path(__file__).resolve().parent.parent.parent / "test_jobs.db"
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


def test_one_active_job_per_meeting_constraint(db_session: Session) -> None:
    """Kiểm tra chỉ 1 job ở trạng thái active (queued/running/retry_scheduled) cho mỗi meeting."""
    user = User(
        id=str(uuid.uuid4()),
        email="test_job_user@example.com",
        display_name="Job User",
        password_hash="hash",
    )
    db_session.add(user)
    db_session.commit()

    meeting = Meeting(
        id=str(uuid.uuid4()),
        owner_id=user.id,
        title="Job Test Meeting",
    )
    db_session.add(meeting)
    db_session.commit()

    # Insert job 1: status running (active) -> Thành công
    job1 = Job(
        id=str(uuid.uuid4()),
        meeting_id=meeting.id,
        status="running",
    )
    db_session.add(job1)
    db_session.commit()

    # Insert job 2 cho cùng meeting: status queued (active) -> Bị partial unique index từ chối
    job2 = Job(
        id=str(uuid.uuid4()),
        meeting_id=meeting.id,
        status="queued",
    )
    db_session.add(job2)
    with pytest.raises(exc.IntegrityError):
        db_session.commit()
    db_session.rollback()

    # Cập nhật job 1 thành 'succeeded' (không còn active)
    job1.status = "succeeded"
    db_session.commit()

    # Bây giờ tạo job 2 (queued) cho cùng meeting -> Thành công không bị chặn
    job2_retry = Job(
        id=str(uuid.uuid4()),
        meeting_id=meeting.id,
        status="queued",
    )
    db_session.add(job2_retry)
    db_session.commit()
    assert job2_retry.id is not None


def test_job_status_check_constraint(db_session: Session) -> None:
    """Kiểm tra ràng buộc CHECK ck_jobs_status từ chối các status không hợp lệ."""
    user = User(
        id=str(uuid.uuid4()),
        email="test_check_user@example.com",
        display_name="Check User",
        password_hash="hash",
    )
    db_session.add(user)
    db_session.commit()

    meeting = Meeting(
        id=str(uuid.uuid4()),
        owner_id=user.id,
        title="Check Test Meeting",
    )
    db_session.add(meeting)
    db_session.commit()

    invalid_job = Job(
        id=str(uuid.uuid4()),
        meeting_id=meeting.id,
        status="unknown_status",
    )
    db_session.add(invalid_job)
    with pytest.raises(exc.IntegrityError):
        db_session.commit()
    db_session.rollback()
