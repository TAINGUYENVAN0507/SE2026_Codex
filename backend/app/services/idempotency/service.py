"""Service xử lý tính idempotent cho các thao tác HTTP POST."""

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import status
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.errors import APIError
from app.db.models.idempotency import IdempotencyKey

IDEMPOTENCY_TTL = timedelta(hours=24)


@dataclass
class IdempotencyCheckResult:
    """Kết quả kiểm tra tính idempotent."""

    is_replayed: bool
    response_code: int | None = None
    response_body: dict[str, Any] | None = None
    record_id: str | None = None


class IdempotencyService:
    """Service quản lý trạng thái idempotent theo (user_id, key, endpoint)."""

    def __init__(self, clock: Callable[[], datetime] | None = None) -> None:
        self._clock = clock or (lambda: datetime.now(UTC))

    def check_or_start(
        self,
        session: Session,
        user_id: str,
        key: str,
        endpoint: str,
    ) -> IdempotencyCheckResult:
        """Kiểm tra hoặc bắt đầu một yêu cầu idempotent.

        - Chưa có hoặc hết hạn TTL: tạo record mới với status 'processing'.
        - Đang xử lý: ném APIError 409 REQUEST_IN_PROGRESS.
        - Đã hoàn thành (chưa hết hạn): trả về kết quả cũ với is_replayed=True.
        """
        now = self._clock()
        cutoff_time = now - IDEMPOTENCY_TTL

        # Tìm bản ghi theo (user_id, key, endpoint)
        record = session.execute(
            select(IdempotencyKey).where(
                IdempotencyKey.user_id == user_id,
                IdempotencyKey.key == key,
                IdempotencyKey.endpoint == endpoint,
            )
        ).scalar_one_or_none()

        if record is not None:
            # Kiểm tra hết hạn TTL
            created_at = record.created_at
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=UTC)

            if created_at < cutoff_time:
                # Đã hết hạn TTL: xóa bản ghi cũ
                session.execute(delete(IdempotencyKey).where(IdempotencyKey.id == record.id))
                session.flush()
                record = None
            elif record.status == "processing":
                raise APIError(
                    code="REQUEST_IN_PROGRESS",
                    message="Yêu cầu đang được xử lý, vui lòng chờ trong giây lát.",
                    status_code=status.HTTP_409_CONFLICT,
                )
            elif record.status == "completed":
                return IdempotencyCheckResult(
                    is_replayed=True,
                    response_code=record.response_code or 200,
                    response_body=record.response_body or {},
                    record_id=record.id,
                )
            else:
                # Trạng thái failed: xóa để cho phép thử lại
                session.execute(delete(IdempotencyKey).where(IdempotencyKey.id == record.id))
                session.flush()
                record = None

        # Tạo record mới trạng thái 'processing'
        new_record = IdempotencyKey(
            id=str(uuid.uuid4()),
            user_id=user_id,
            key=key,
            endpoint=endpoint,
            status="processing",
            created_at=now,
        )
        session.add(new_record)
        session.flush()

        return IdempotencyCheckResult(
            is_replayed=False,
            record_id=new_record.id,
        )

    def complete(
        self,
        session: Session,
        record_id: str,
        response_code: int,
        response_body: dict[str, Any],
    ) -> None:
        """Đánh dấu hoàn thành yêu cầu và lưu response body/code."""
        record = session.execute(
            select(IdempotencyKey).where(IdempotencyKey.id == record_id)
        ).scalar_one_or_none()
        if record:
            record.status = "completed"
            record.response_code = response_code
            record.response_body = response_body
            session.flush()

    def fail(self, session: Session, record_id: str) -> None:
        """Xóa hoặc đánh dấu thất bại khi xảy ra lỗi để cho phép thử lại sau."""
        record = session.execute(
            select(IdempotencyKey).where(IdempotencyKey.id == record_id)
        ).scalar_one_or_none()
        if record:
            session.delete(record)
            session.flush()
