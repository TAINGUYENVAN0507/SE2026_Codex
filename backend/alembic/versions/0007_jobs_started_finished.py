"""jobs.started_at and jobs.finished_at

Revision ID: 0007_jobs_started_finished
Revises: 0006_segments_unique_idx
Create Date: 2026-11-07 10:00:00

API trả started_at, finished_at nhưng luôn null (VT-018). Job cũ ở trạng thái kết thúc được
gán finished_at = updated_at; started_at để null vì không có dữ liệu thật để suy ra.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0007_jobs_started_finished"
down_revision: str | Sequence[str] | None = "0006_segments_unique_idx"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("jobs", sa.Column("started_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("jobs", sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True))
    op.execute(
        "UPDATE jobs SET finished_at = updated_at "
        "WHERE status IN ('succeeded', 'failed', 'cancelled')"
    )


def downgrade() -> None:
    op.drop_column("jobs", "finished_at")
    op.drop_column("jobs", "started_at")
