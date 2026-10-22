"""Model SQLAlchemy cho bảng idempotency_keys."""

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, Integer, JSON, String
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class IdempotencyKey(Base):
    """Bảng lưu trữ idempotency keys để chống gọi trùng các thao tác POST."""

    __tablename__ = "idempotency_keys"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        comment="UUID định danh duy nhất của idempotency record",
    )
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="ID người dùng gửi request",
    )
    key: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Khóa Idempotency-Key từ header",
    )
    endpoint: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        comment="Đường dẫn endpoint API được gọi",
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="processing",
        comment="Trạng thái xử lý: processing, completed, failed",
    )
    response_code: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="HTTP status code trả về",
    )
    response_body: Mapped[dict[str, Any] | None] = mapped_column(
        JSON().with_variant(postgresql.JSONB(), "postgresql"),
        nullable=True,
        comment="Nội dung response JSON đã cache",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        comment="Thời điểm nhận request UTC",
    )

    user: Mapped["User"] = relationship("User")  # noqa: F821

    __table_args__ = (
        Index("uq_idempotency_keys_user_key_endpoint", "user_id", "key", "endpoint", unique=True),
    )
