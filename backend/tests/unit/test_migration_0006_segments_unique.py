"""Migration 0006 (VT-018): dedupe segment trùng idx rồi thêm unique (meeting_id, idx)."""

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError

from alembic import command
from tests.conftest import get_alembic_config


def _seed(conn, rows):
    conn.execute(
        text(
            "INSERT INTO users (id, email, display_name, password_hash, created_at, updated_at) "
            "VALUES ('u1','m6@example.com','M6','h',now(),now())"
        )
    )
    conn.execute(
        text(
            "INSERT INTO meetings (id, owner_id, title, source, status, created_at, updated_at) "
            "VALUES ('m1','u1','t','upload','ready',now(),now())"
        )
    )
    for sid, idx, created, body in rows:
        conn.execute(
            text(
                "INSERT INTO segments (id, meeting_id, idx, start_sec, end_sec, text, ai_text, "
                "version, created_at, updated_at) VALUES (:id,'m1',:idx,0,1,:t,:t,1,:c,:c)"
            ),
            {"id": sid, "idx": idx, "t": body, "c": created},
        )


def test_upgrade_keeps_newest_duplicate_and_blocks_new_ones(require_postgres: str) -> None:
    cfg = get_alembic_config(require_postgres)
    command.upgrade(cfg, "0005_edit_events_cascade_delete")
    engine = create_engine(require_postgres)
    try:
        with engine.begin() as conn:
            _seed(
                conn,
                [
                    ("a-old", 0, "2026-11-01T00:00:00Z", "cũ"),
                    ("a-new", 0, "2026-11-02T00:00:00Z", "mới"),
                    ("b-only", 1, "2026-11-01T00:00:00Z", "một"),
                ],
            )
        command.upgrade(cfg, "0006_segments_unique_idx")
        with engine.begin() as conn:
            kept = {r[0] for r in conn.execute(text("SELECT id FROM segments"))}
        assert kept == {"a-new", "b-only"}

        with pytest.raises(IntegrityError), engine.begin() as conn:
            _seed_dup = text(
                "INSERT INTO segments (id, meeting_id, idx, start_sec, end_sec, text, ai_text, "
                "version, created_at, updated_at) "
                "VALUES ('dup','m1',0,0,1,'x','x',1,now(),now())"
            )
            conn.execute(_seed_dup)

        command.downgrade(cfg, "0005_edit_events_cascade_delete")
    finally:
        engine.dispose()
        command.downgrade(cfg, "base")
