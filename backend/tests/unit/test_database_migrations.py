"""Kiểm thử migration Alembic và kết nối cơ sở dữ liệu."""

import contextlib
from pathlib import Path

from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from alembic import command
from app.core.config import get_settings
from app.core.database import DefaultDatabaseHealthChecker


def get_alembic_config(db_url: str) -> Config:
    """Tạo cấu hình Alembic trỏ tới thư mục alembic và URL DB tương ứng."""
    backend_dir = Path(__file__).resolve().parent.parent.parent
    ini_path = backend_dir / "alembic.ini"
    cfg = Config(str(ini_path))
    cfg.set_main_option("script_location", str(backend_dir / "alembic"))
    cfg.set_main_option("sqlalchemy.url", db_url)
    return cfg


def test_alembic_upgrade_and_downgrade() -> None:
    """Kiểm tra chạy alembic upgrade head rồi downgrade base không phát sinh lỗi."""
    settings = get_settings()
    postgres_available = False

    # Thử kết nối tới PostgreSQL theo cấu hình nếu có
    if settings.DATABASE_URL.startswith("postgresql"):
        try:
            connect_args = {"connect_timeout": 1} if "psycopg" in settings.DATABASE_URL else {}
            test_engine = create_engine(settings.DATABASE_URL, connect_args=connect_args)
            with test_engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            postgres_available = True
            db_url = settings.DATABASE_URL
        except Exception:
            postgres_available = False

    # Nếu không kết nối được Postgres (môi trường local không có Docker),
    # kiểm thử cú pháp DDL migration trên SQLite test engine
    if not postgres_available:
        test_db_path = Path(__file__).resolve().parent.parent.parent / "test_migration.db"
        if test_db_path.exists():
            test_db_path.unlink()
        db_url = f"sqlite:///{test_db_path.as_posix()}"

    cfg = get_alembic_config(db_url)

    try:
        # Upgrade lên head
        command.upgrade(cfg, "head")

        engine = create_engine(db_url)
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        assert "users" in tables
        assert "meetings" in tables
        assert "jobs" in tables

        # Downgrade về base
        command.downgrade(cfg, "base")

        inspector = inspect(engine)
        tables_after = inspector.get_table_names()
        assert "users" not in tables_after
        assert "meetings" not in tables_after
        assert "jobs" not in tables_after
    finally:
        with contextlib.suppress(Exception):
            engine.dispose()
        if not postgres_available:
            test_db_path = Path(__file__).resolve().parent.parent.parent / "test_migration.db"
            if test_db_path.exists():
                with contextlib.suppress(Exception):
                    test_db_path.unlink()


def test_ready_check_db_disconnected() -> None:
    """Kiểm tra DefaultDatabaseHealthChecker trả về False khi DB không kết nối được."""
    # Engine trỏ tới port không tồn tại
    invalid_engine = create_engine(
        "postgresql+psycopg://invalid_user:invalid_pass@localhost:59999/invalid_db",
        connect_args={"connect_timeout": 1},
    )
    checker = DefaultDatabaseHealthChecker(engine=invalid_engine)
    assert checker.is_healthy() is False
