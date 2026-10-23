"""Model SQLAlchemy cho bảng edit_events."""

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, Integer, JSON, String
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class EditEvent(Base):
    """Bảng ghi nhật ký chỉnh sửa (audit log), chỉ ghi thêm (append-only), chặn UPDATE."""

    __tablename__ = "edit_events"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        comment="UUID định danh duy nhất của sự kiện sửa",
    )
    meeting_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("meetings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="ID cuộc họp liên kết",
    )
    actor_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="ID người dùng thực hiện sửa",
    )
    entity_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="Loại thực thể bị sửa (segment, speaker, summary, action_item, meeting)",
    )
    entity_id: Mapped[str] = mapped_column(
        String(36),
        nullable=False,
        index=True,
        comment="ID của thực thể bị sửa",
    )
    action: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="Hành động: update, create, delete",
    )
    field: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Tên trường cụ thể bị sửa",
    )
    before: Mapped[dict[str, Any] | None] = mapped_column(
        JSON().with_variant(postgresql.JSONB(), "postgresql"),
        nullable=True,
        comment="Giá trị trước khi sửa dạng JSON",
    )
    after: Mapped[dict[str, Any] | None] = mapped_column(
        JSON().with_variant(postgresql.JSONB(), "postgresql"),
        nullable=True,
        comment="Giá trị sau khi sửa dạng JSON",
    )
    entity_version_after: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Phiên bản của entity sau khi sửa",
    )
    request_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="Request ID gắn liền với HTTP request",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        comment="Thời điểm phát sinh sự kiện sửa UTC",
    )

    meeting: Mapped["Meeting"] = relationship("Meeting", back_populates="edit_events")  # noqa: F821
    actor: Mapped["User"] = relationship("User")  # noqa: F821

    __table_args__ = (
        Index("ix_edit_events_meeting_entity", "meeting_id", "entity_type", "entity_id"),
    )
