"""Migration 0007 (VT-018): thêm started_at, finished_at cho jobs, backfill finished_at."""

from sqlalchemy import create_engine, inspect, text

from alembic import command
from tests.conftest import get_alembic_config


def test_upgrade_backfills_finished_at_and_downgrade_removes_columns(require_postgres: str) -> None:
    cfg = get_alembic_config(require_postgres)
    command.upgrade(cfg, "0006_segments_unique_idx")
    engine = create_engine(require_postgres)
    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO users (id,email,display_name,password_hash,created_at,updated_at)"
                    " VALUES ('u7','m7@example.com','M7','h',now(),now())"
                )
            )
            conn.execute(
                text(
                    "INSERT INTO meetings (id,owner_id,title,source,status,created_at,updated_at)"
                    " VALUES ('m7','u7','t','upload','ready',now(),now())"
                )
            )
            conn.execute(
                text(
                    "INSERT INTO jobs (id,meeting_id,status,stage,stage_status,progress,attempt,"
                    "max_attempts,created_at,updated_at) VALUES "
                    "('j-done','m7','succeeded','summarize','{}',1.0,1,3,now(),'2026-11-01T10:00:00Z')"
                )
            )
        command.upgrade(cfg, "0007_jobs_started_finished")
        with engine.begin() as conn:
            row = conn.execute(
                text("SELECT started_at, finished_at, updated_at FROM jobs WHERE id='j-done'")
            ).one()
        assert row.started_at is None
        assert row.finished_at == row.updated_at

        command.downgrade(cfg, "0006_segments_unique_idx")
        cols = {c["name"] for c in inspect(engine).get_columns("jobs")}
        assert not {"started_at", "finished_at"} & cols
    finally:
        engine.dispose()
        command.downgrade(cfg, "base")
