"""Model SQLAlchemy cho bảng summaries."""

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Summary(Base):
    """Bảng lưu trữ biên bản tóm tắt cuộc họp."""

    __tablename__ = "summaries"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        comment="UUID định danh duy nhất của summary",
    )
    meeting_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("meetings.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
        comment="ID cuộc họp liên kết (mỗi cuộc họp 1 bản summary)",
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
        comment="Trạng thái: pending, ready, failed, insufficient_content, disabled",
    )
    content: Mapped[dict[str, Any] | None] = mapped_column(
        JSON().with_variant(postgresql.JSONB(), "postgresql"),
        nullable=True,
        comment="Nội dung tóm tắt hiện tại (overview, key_points, decisions)",
    )
    ai_content: Mapped[dict[str, Any] | None] = mapped_column(
        JSON().with_variant(postgresql.JSONB(), "postgresql"),
        nullable=True,
        comment="Nội dung tóm tắt gốc từ AI (bất biến)",
    )
    model: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="Model LLM sinh ra tóm tắt",
    )
    prompt_version: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Phiên bản prompt tóm tắt",
    )
    version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        comment="Phiên bản phục vụ optimistic locking",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        comment="Thời điểm tạo UTC",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
        comment="Thời điểm cập nhật gần nhất UTC",
    )

    meeting: Mapped["Meeting"] = relationship("Meeting", back_populates="summary")  # noqa: F821
