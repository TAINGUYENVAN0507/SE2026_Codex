"""Dịch vụ xóa hoàn toàn cuộc họp khỏi mọi nơi lưu trữ (BE-18).

Bao gồm:
- Hủy các job đang active của cuộc họp.
- Xóa tệp âm thanh gốc và các tệp artifacts trên ổ đĩa.
- Xóa các bản ghi idempotency_keys của người dùng liên quan đến cuộc họp.
- Xóa cuộc họp và các bản ghi phụ thuộc khỏi cơ sở dữ liệu.
- Ghi log bảo mật: chỉ ghi ID, không ghi tiêu đề, tên tệp hay nội dung.
"""

import json
import logging
from datetime import UTC, datetime
from typing import Any

from fastapi import status
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.errors import APIError
from app.db.models.edit_event import EditEvent
from app.db.models.idempotency import IdempotencyKey
from app.db.models.job import Job
from app.db.models.meeting import Meeting
from app.services.storage import Storage

logger = logging.getLogger("backend.services.erasure")


def _contains_meeting_id(payload: Any, meeting_id: str) -> bool:
    """Kiểm tra xem dữ liệu JSON có chứa meeting_id hay không."""
    if not payload:
        return False
    if isinstance(payload, str):
        return meeting_id in payload
    try:
        serialized = json.dumps(payload)
        return meeting_id in serialized
    except (TypeError, ValueError):
        return meeting_id in str(payload)


def erase_meeting(
    db: Session,
    storage: Storage,
    meeting_id: str,
    current_user_id: str,
) -> None:
    """Xóa hoàn toàn cuộc họp khỏi toàn bộ các kho dữ liệu (DB, storage, idempotency).

    Raises:
        APIError: 404 MEETING_NOT_FOUND nếu cuộc họp không tồn tại hoặc không thuộc quyền sở hữu.
    """
    meeting = db.execute(select(Meeting).where(Meeting.id == meeting_id)).scalar_one_or_none()

    if not meeting or meeting.owner_id != current_user_id:
        raise APIError(
            code="MEETING_NOT_FOUND",
            message="Không tìm thấy cuộc họp được yêu cầu.",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    # 1. Chuyển trạng thái các job đang active sang cancelled
    active_jobs = (
        db.execute(
            select(Job).where(
                Job.meeting_id == meeting.id,
                Job.status.in_(["queued", "running", "retry_scheduled"]),
            )
        )
        .scalars()
        .all()
    )
    now_utc = datetime.now(UTC)
    for aj in active_jobs:
        aj.status = "cancelled"
        aj.updated_at = now_utc
    if active_jobs:
        db.commit()

    # 2. Xóa audio và artifacts trên đĩa
    storage.delete_meeting_files(meeting_id)

    # 3. Xóa các dòng idempotency_keys của owner có response_body hoặc endpoint chứa meeting_id
    user_idem_records = (
        db.execute(select(IdempotencyKey).where(IdempotencyKey.user_id == current_user_id))
        .scalars()
        .all()
    )
    keys_to_delete: list[str] = []
    for rec in user_idem_records:
        has_endpoint_match = bool(rec.endpoint and meeting_id in rec.endpoint)
        has_body_match = bool(
            rec.response_body and _contains_meeting_id(rec.response_body, meeting_id)
        )
        if has_endpoint_match or has_body_match:
            keys_to_delete.append(rec.id)

    if keys_to_delete:
        db.execute(delete(IdempotencyKey).where(IdempotencyKey.id.in_(keys_to_delete)))

    # 4. Xóa cuộc họp và các bảng liên quan khỏi DB
    db.delete(meeting)
    db.flush()
    db.execute(delete(EditEvent).where(EditEvent.meeting_id == meeting_id))
    db.commit()

    # 5. Ghi log bảo mật: chỉ ghi ID, không ghi tiêu đề, tên file, nội dung (PRIV-12, PRIV-10)
    logger.info("Đã xóa cuộc họp: meeting_id=%s", meeting_id)
