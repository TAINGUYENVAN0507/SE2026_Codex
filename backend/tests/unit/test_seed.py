"""Kiểm thử tính idempotent của lệnh seed dữ liệu demo."""

import contextlib
from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from alembic import command
from app.core.config import get_settings
from app.db.models.action_item import ActionItem
from app.db.models.meeting import Meeting
from app.db.models.summary import Summary
from app.db.models.transcript import Segment, Speaker
from app.db.models.user import User
from app.scripts.seed import run_seed


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
    """Fixture tạo DB sạch, chạy migration và cung cấp session cho test."""
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
        test_db_path = Path(__file__).resolve().parent.parent.parent / "test_seed.db"
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


def test_seed_missing_env_raises_error(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Kiểm tra nếu thiếu biến môi trường SEED_DEMO_PASSWORD thì seed báo lỗi rõ ràng."""
    monkeypatch.delenv("SEED_DEMO_PASSWORD", raising=False)
    expected_err = "Thiếu biến môi trường SEED_DEMO_PASSWORD bắt buộc để seed tài khoản demo."
    with pytest.raises(ValueError, match=expected_err):
        run_seed(db_session)


def test_seed_is_idempotent(db_session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    """Kiểm tra chạy seed 2 lần: lần 1 tạo dữ liệu, lần 2 số row không đổi."""
    monkeypatch.setenv("SEED_DEMO_PASSWORD", "demo_secret_2026")
    # Lần 1: Chạy seed
    stats_first = run_seed(db_session)
    assert stats_first["users_created"] == 1
    assert stats_first["meetings_created"] == 1
    assert stats_first["speakers_created"] == 2
    assert stats_first["segments_created"] == 3
    assert stats_first["summaries_created"] == 1
    assert stats_first["action_items_created"] == 2

    # Đếm số lượng row hiện tại
    users_count_1 = len(db_session.execute(select(User)).scalars().all())
    meetings_count_1 = len(db_session.execute(select(Meeting)).scalars().all())
    speakers_count_1 = len(db_session.execute(select(Speaker)).scalars().all())
    segments_count_1 = len(db_session.execute(select(Segment)).scalars().all())
    summaries_count_1 = len(db_session.execute(select(Summary)).scalars().all())
    action_items_count_1 = len(db_session.execute(select(ActionItem)).scalars().all())

    assert users_count_1 == 1
    assert meetings_count_1 == 1
    assert speakers_count_1 == 2
    assert segments_count_1 == 3
    assert summaries_count_1 == 1
    assert action_items_count_1 == 2

    # Kiểm tra segment có 1 segment speaker_id = null theo yêu cầu đề bài
    null_speaker_segments = (
        db_session.execute(select(Segment).where(Segment.speaker_id.is_(None))).scalars().all()
    )
    assert len(null_speaker_segments) == 1

    # Lần 2: Chạy seed lại trên cùng DB
    stats_second = run_seed(db_session)
    assert stats_second["users_created"] == 0
    assert stats_second["meetings_created"] == 0
    assert stats_second["speakers_created"] == 0
    assert stats_second["segments_created"] == 0
    assert stats_second["summaries_created"] == 0
    assert stats_second["action_items_created"] == 0

    # Đếm lại số row: phải giữ nguyên không đổi
    users_count_2 = len(db_session.execute(select(User)).scalars().all())
    meetings_count_2 = len(db_session.execute(select(Meeting)).scalars().all())
    speakers_count_2 = len(db_session.execute(select(Speaker)).scalars().all())
    segments_count_2 = len(db_session.execute(select(Segment)).scalars().all())
    summaries_count_2 = len(db_session.execute(select(Summary)).scalars().all())
    action_items_count_2 = len(db_session.execute(select(ActionItem)).scalars().all())

    assert users_count_2 == users_count_1
    assert meetings_count_2 == meetings_count_1
    assert speakers_count_2 == speakers_count_1
    assert segments_count_2 == segments_count_1
    assert summaries_count_2 == summaries_count_1
    assert action_items_count_2 == action_items_count_1
