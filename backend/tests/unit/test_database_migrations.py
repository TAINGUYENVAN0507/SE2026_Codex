"""Kiểm thử migration Alembic và kết nối cơ sở dữ liệu."""

from sqlalchemy import create_engine, inspect

from alembic import command
from app.core.database import DefaultDatabaseHealthChecker
from tests.conftest import get_alembic_config


def test_alembic_upgrade_and_downgrade(require_postgres: str) -> None:
    """Kiểm tra chạy alembic upgrade head rồi downgrade base trên Postgres không phát sinh lỗi."""
    db_url = require_postgres
    cfg = get_alembic_config(db_url)

    # Upgrade lên head
    command.upgrade(cfg, "head")

    engine = create_engine(db_url)
    try:
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        for t in [
            "users",
            "meetings",
            "jobs",
            "speakers",
            "segments",
            "ai_outputs",
            "summaries",
            "action_items",
            "edit_events",
            "idempotency_keys",
        ]:
            assert t in tables

        # Downgrade về base
        command.downgrade(cfg, "base")

        inspector = inspect(engine)
        tables_after = inspector.get_table_names()
        for t in [
            "users",
            "meetings",
            "jobs",
            "speakers",
            "segments",
            "ai_outputs",
            "summaries",
            "action_items",
            "edit_events",
            "idempotency_keys",
        ]:
            assert t not in tables_after
    finally:
        engine.dispose()


def test_ready_check_db_disconnected() -> None:
    """Kiểm tra DefaultDatabaseHealthChecker trả về False khi DB không kết nối được."""
    invalid_engine = create_engine(
        "postgresql+psycopg://invalid_user:invalid_pass@localhost:59999/invalid_db",
        connect_args={"connect_timeout": 1},
    )
    checker = DefaultDatabaseHealthChecker(engine=invalid_engine)
    assert checker.is_healthy() is False
