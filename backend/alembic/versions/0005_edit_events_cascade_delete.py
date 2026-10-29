"""allow edit_events delete on meeting cascade

Revision ID: 0005_edit_events_cascade_delete
Revises: 0004_prevent_edit_events_delete
Create Date: 2026-10-29 21:00:00

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0005_edit_events_cascade_delete"
down_revision: str | Sequence[str] | None = "0004_prevent_edit_events_delete"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Cập nhật trigger chặn DELETE edit_events cho phép xóa khi meeting bị xóa (BE-14)."""
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("""
        CREATE OR REPLACE FUNCTION prevent_edit_events_delete()
        RETURNS TRIGGER AS $$
        BEGIN
            IF pg_trigger_depth() > 1 THEN
                RETURN OLD;
            END IF;
            RAISE EXCEPTION
                'edit_events table is append-only and does not allow DELETE operations.';
        END;
        $$ LANGUAGE plpgsql;
        """)
    elif bind.dialect.name == "sqlite":
        op.execute("DROP TRIGGER IF EXISTS trg_prevent_edit_events_delete;")
        op.execute("""
        CREATE TRIGGER trg_prevent_edit_events_delete
        BEFORE DELETE ON edit_events
        WHEN EXISTS (SELECT 1 FROM meetings WHERE id = OLD.meeting_id)
        BEGIN
            SELECT RAISE(
                ABORT,
                'edit_events table is append-only and does not allow DELETE operations.'
            );
        END;
        """)


def downgrade() -> None:
    """Khôi phục trigger chặn mọi DELETE trên edit_events."""
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("""
        CREATE OR REPLACE FUNCTION prevent_edit_events_delete()
        RETURNS TRIGGER AS $$
        BEGIN
            RAISE EXCEPTION
                'edit_events table is append-only and does not allow DELETE operations.';
        END;
        $$ LANGUAGE plpgsql;
        """)
    elif bind.dialect.name == "sqlite":
        op.execute("DROP TRIGGER IF EXISTS trg_prevent_edit_events_delete;")
        op.execute("""
        CREATE TRIGGER trg_prevent_edit_events_delete
        BEFORE DELETE ON edit_events
        BEGIN
            SELECT RAISE(
                ABORT,
                'edit_events table is append-only and does not allow DELETE operations.'
            );
        END;
        """)
