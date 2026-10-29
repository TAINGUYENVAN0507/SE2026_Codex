"""Triển khai hàm record_edit dùng chung cho audit logging."""

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.db.models.edit_event import EditEvent


def record_edit(
    db: Session,
    *,
    meeting_id: str,
    entity_type: str,
    entity_id: str,
    action: str,
    actor_id: str | None,
    field: str | None = None,
    before: Any = None,
    after: Any = None,
    entity_version_after: int | None = None,
    request_id: str | None = None,
    created_at: datetime | None = None,
) -> EditEvent:
    """Ghi nhận một sự kiện chỉnh sửa (audit event) vào cơ sở dữ liệu.

    Thêm đối tượng EditEvent vào session hiện tại (chưa gọi commit).
    """
    if created_at is None:
        created_at = datetime.now(UTC)

    event = EditEvent(
        id=str(uuid.uuid4()),
        meeting_id=meeting_id,
        actor_id=actor_id,
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        field=field,
        before=before,
        after=after,
        entity_version_after=entity_version_after,
        request_id=request_id,
        created_at=created_at,
    )
    db.add(event)
    return event
