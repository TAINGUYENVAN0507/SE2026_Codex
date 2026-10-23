"""create transcript, summary, and audit tables with integrity guards

Revision ID: 0003_transcript_summary_audit
Revises: 0002_jobs_table
Create Date: 2026-10-22 14:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0003_transcript_summary_audit"
down_revision: str | Sequence[str] | None = "0002_jobs_table"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Tạo các bảng transcript, summary, action_items, audit và idempotency."""
    # 1. Bảng speakers
    op.create_table(
        "speakers",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("meeting_id", sa.String(length=36), nullable=False),
        sa.Column("label", sa.String(length=50), nullable=False),
        sa.Column("default_name", sa.String(length=100), nullable=False),
        sa.Column("display_name", sa.String(length=100), nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["meeting_id"], ["meetings.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_speakers_meeting_id"), "speakers", ["meeting_id"], unique=False)
    op.create_index(
        "uq_speakers_meeting_label",
        "speakers",
        ["meeting_id", "label"],
        unique=True,
    )

    # 2. Bảng segments
    op.create_table(
        "segments",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("meeting_id", sa.String(length=36), nullable=False),
        sa.Column("idx", sa.Integer(), nullable=False),
        sa.Column("start_sec", sa.Float(), nullable=False),
        sa.Column("end_sec", sa.Float(), nullable=False),
        sa.Column("speaker_id", sa.String(length=36), nullable=True),
        sa.Column("ai_speaker_id", sa.String(length=36), nullable=True),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("ai_text", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column(
            "flags",
            sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
            nullable=True,
        ),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "start_sec >= 0 AND start_sec < end_sec",
            name="ck_segments_time_range",
        ),
        sa.ForeignKeyConstraint(["meeting_id"], ["meetings.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["speaker_id"], ["speakers.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["ai_speaker_id"], ["speakers.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_segments_meeting_id"), "segments", ["meeting_id"], unique=False)
    op.create_index(op.f("ix_segments_speaker_id"), "segments", ["speaker_id"], unique=False)
    op.create_index(
        "ix_segments_meeting_time",
        "segments",
        ["meeting_id", "start_sec", "end_sec"],
        unique=False,
    )

    # 3. Bảng ai_outputs
    op.create_table(
        "ai_outputs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("meeting_id", sa.String(length=36), nullable=False),
        sa.Column("job_id", sa.String(length=36), nullable=False),
        sa.Column("stage", sa.String(length=20), nullable=False),
        sa.Column(
            "payload",
            sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
            nullable=False,
        ),
        sa.Column("model", sa.String(length=100), nullable=True),
        sa.Column(
            "model_params",
            sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["meeting_id"], ["meetings.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_ai_outputs_job_id"), "ai_outputs", ["job_id"], unique=False)
    op.create_index(op.f("ix_ai_outputs_meeting_id"), "ai_outputs", ["meeting_id"], unique=False)
    op.create_index(
        "uq_ai_outputs_job_stage",
        "ai_outputs",
        ["job_id", "stage"],
        unique=True,
    )

    # 4. Bảng summaries
    op.create_table(
        "summaries",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("meeting_id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="pending", nullable=False),
        sa.Column(
            "content",
            sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
            nullable=True,
        ),
        sa.Column(
            "ai_content",
            sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
            nullable=True,
        ),
        sa.Column("model", sa.String(length=100), nullable=True),
        sa.Column("prompt_version", sa.String(length=50), nullable=True),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["meeting_id"], ["meetings.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("meeting_id"),
    )
    op.create_index(op.f("ix_summaries_meeting_id"), "summaries", ["meeting_id"], unique=True)

    # 5. Bảng action_items
    op.create_table(
        "action_items",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("meeting_id", sa.String(length=36), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("assignee_name", sa.String(length=100), nullable=True),
        sa.Column("assignee_speaker_id", sa.String(length=36), nullable=True),
        sa.Column("due_date", sa.String(length=10), nullable=True),
        sa.Column("due_date_text", sa.String(length=100), nullable=True),
        sa.Column("status", sa.String(length=20), server_default="open", nullable=False),
        sa.Column("source", sa.String(length=20), server_default="ai", nullable=False),
        sa.Column(
            "ai_original",
            sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
            nullable=True,
        ),
        sa.Column(
            "evidence_segment_ids",
            sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
            nullable=True,
        ),
        sa.Column("needs_review", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["assignee_speaker_id"], ["speakers.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["meeting_id"], ["meetings.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_action_items_meeting_id"), "action_items", ["meeting_id"], unique=False
    )

    # 6. Bảng edit_events
    op.create_table(
        "edit_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("meeting_id", sa.String(length=36), nullable=False),
        sa.Column("actor_id", sa.String(length=36), nullable=True),
        sa.Column("entity_type", sa.String(length=50), nullable=False),
        sa.Column("entity_id", sa.String(length=36), nullable=False),
        sa.Column("action", sa.String(length=20), nullable=False),
        sa.Column("field", sa.String(length=50), nullable=True),
        sa.Column(
            "before",
            sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
            nullable=True,
        ),
        sa.Column(
            "after",
            sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
            nullable=True,
        ),
        sa.Column("entity_version_after", sa.Integer(), nullable=True),
        sa.Column("request_id", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["meeting_id"], ["meetings.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_edit_events_actor_id"),
        "edit_events",
        ["actor_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_edit_events_meeting_id"),
        "edit_events",
        ["meeting_id"],
        unique=False,
    )
    op.create_index(
        "ix_edit_events_meeting_entity",
        "edit_events",
        ["meeting_id", "entity_type", "entity_id"],
        unique=False,
    )

    # Trigger ngăn UPDATE trên bảng edit_events (AUD-10)
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("""
        CREATE OR REPLACE FUNCTION prevent_edit_events_update()
        RETURNS TRIGGER AS $$
        BEGIN
            RAISE EXCEPTION
                'edit_events table is append-only and does not allow UPDATE operations.';
        END;
        $$ LANGUAGE plpgsql;
        """)
        op.execute("""
        CREATE TRIGGER trg_prevent_edit_events_update
        BEFORE UPDATE ON edit_events
        FOR EACH ROW
        EXECUTE FUNCTION prevent_edit_events_update();
        """)
    elif bind.dialect.name == "sqlite":
        op.execute("""
        CREATE TRIGGER trg_prevent_edit_events_update
        BEFORE UPDATE ON edit_events
        BEGIN
            SELECT RAISE(
                ABORT,
                'edit_events table is append-only and does not allow UPDATE operations.'
            );
        END;
        """)

    # 7. Bảng idempotency_keys
    op.create_table(
        "idempotency_keys",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column("endpoint", sa.String(length=200), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="processing", nullable=False),
        sa.Column("response_code", sa.Integer(), nullable=True),
        sa.Column(
            "response_body",
            sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_idempotency_keys_user_key_endpoint",
        "idempotency_keys",
        ["user_id", "key", "endpoint"],
        unique=True,
    )


def downgrade() -> None:
    """Xóa các bảng và trigger."""
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("DROP TRIGGER IF EXISTS trg_prevent_edit_events_update ON edit_events;")
        op.execute("DROP FUNCTION IF EXISTS prevent_edit_events_update();")
    elif bind.dialect.name == "sqlite":
        op.execute("DROP TRIGGER IF EXISTS trg_prevent_edit_events_update;")

    op.drop_table("idempotency_keys")
    op.drop_table("edit_events")
    op.drop_table("action_items")
    op.drop_table("summaries")
    op.drop_table("ai_outputs")
    op.drop_table("segments")
    op.drop_table("speakers")
