"""create jobs table with status check and partial unique active job index

Revision ID: 0002_jobs_table
Revises: 0001_users_meetings
Create Date: 2026-10-22 10:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002_jobs_table"
down_revision: str | Sequence[str] | None = "0001_users_meetings"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Tạo bảng jobs với check constraint status và partial unique index."""
    op.create_table(
        "jobs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("meeting_id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="queued", nullable=False),
        sa.Column("stage", sa.String(length=20), nullable=True),
        sa.Column("from_stage", sa.String(length=20), nullable=True),
        sa.Column(
            "stage_status",
            sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
            nullable=True,
        ),
        sa.Column("progress", sa.Float(), server_default="0.0", nullable=False),
        sa.Column("attempt", sa.Integer(), server_default="1", nullable=False),
        sa.Column("max_attempts", sa.Integer(), server_default="3", nullable=False),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("locked_by", sa.String(length=100), nullable=True),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_code", sa.String(length=50), nullable=True),
        sa.Column("error_message", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'retry_scheduled', "
            "'succeeded', 'failed', 'cancelled')",
            name="ck_jobs_status",
        ),
        sa.ForeignKeyConstraint(["meeting_id"], ["meetings.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_jobs_meeting_id"), "jobs", ["meeting_id"], unique=False)
    op.create_index(
        "uq_jobs_active_meeting",
        "jobs",
        ["meeting_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('queued', 'running', 'retry_scheduled')"),
        sqlite_where=sa.text("status IN ('queued', 'running', 'retry_scheduled')"),
    )


def downgrade() -> None:
    """Xóa bảng jobs."""
    op.drop_index("uq_jobs_active_meeting", table_name="jobs")
    op.drop_index(op.f("ix_jobs_meeting_id"), table_name="jobs")
    op.drop_table("jobs")
