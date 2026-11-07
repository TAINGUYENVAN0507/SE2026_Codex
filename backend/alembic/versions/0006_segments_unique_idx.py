"""unique (meeting_id, idx) on segments

Revision ID: 0006_segments_unique_idx
Revises: 0005_edit_events_cascade_delete
Create Date: 2026-11-07 09:00:00

Lỗi VT-018: job mới của cùng meeting ghi thêm một bộ segment, nên có dòng trùng idx.
Upgrade giữ bộ mới nhất theo created_at rồi mới thêm ràng buộc.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0006_segments_unique_idx"
down_revision: str | Sequence[str] | None = "0005_edit_events_cascade_delete"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Giữ dòng mới nhất cho mỗi (meeting_id, idx); id làm tie-break để kết quả xác định.
    op.execute(
        sa.text(
            """
            DELETE FROM segments WHERE id IN (
                SELECT id FROM (
                    SELECT id, ROW_NUMBER() OVER (
                        PARTITION BY meeting_id, idx ORDER BY created_at DESC, id DESC
                    ) AS rn FROM segments
                ) ranked WHERE rn > 1
            )
            """
        )
    )
    op.create_index("uq_segments_meeting_idx", "segments", ["meeting_id", "idx"], unique=True)


def downgrade() -> None:
    op.drop_index("uq_segments_meeting_idx", table_name="segments")
