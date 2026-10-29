"""prevent edit_events delete trigger

Revision ID: 0004_prevent_edit_events_delete
Revises: 0003_transcript_summary_audit
Create Date: 2026-10-25 15:30:00

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0004_prevent_edit_events_delete"
down_revision: str | Sequence[str] | None = "0003_transcript_summary_audit"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Thêm trigger chặn DELETE trên bảng edit_events (BE-12, AUD-11)."""
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
        op.execute("""
        CREATE TRIGGER trg_prevent_edit_events_delete
        BEFORE DELETE ON edit_events
        FOR EACH ROW
        EXECUTE FUNCTION prevent_edit_events_delete();
        """)
    elif bind.dialect.name == "sqlite":
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


def downgrade() -> None:
    """Xóa trigger chặn DELETE."""
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("DROP TRIGGER IF EXISTS trg_prevent_edit_events_delete ON edit_events;")
        op.execute("DROP FUNCTION IF EXISTS prevent_edit_events_delete();")
    elif bind.dialect.name == "sqlite":
        op.execute("DROP TRIGGER IF EXISTS trg_prevent_edit_events_delete;")
