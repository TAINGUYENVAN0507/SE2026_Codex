"""Model SQLAlchemy cho bảng action_items."""

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ActionItem(Base):
    """Bảng lưu trữ các nhiệm vụ / hành động phát sinh từ cuộc họp."""

    __tablename__ = "action_items"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        comment="UUID định danh duy nhất của action item",
    )
    meeting_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("meetings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="ID cuộc họp liên kết",
    )
    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Mô tả công việc cần làm",
    )
    assignee_name: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="Tên người được giao",
    )
    assignee_speaker_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("speakers.id", ondelete="SET NULL"),
        nullable=True,
        comment="Speaker ID tương ứng nếu có",
    )
    due_date: Mapped[str | None] = mapped_column(
        String(10),
        nullable=True,
        comment="Hạn hoàn thành định dạng YYYY-MM-DD",
    )
    due_date_text: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="Cụm từ chỉ thời hạn gốc trong lời thoại",
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="open",
        comment="Trạng thái: open hoặc done",
    )
    source: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="ai",
        comment="Nguồn tạo: ai hoặc user",
    )
    ai_original: Mapped[dict[str, Any] | None] = mapped_column(
        JSON().with_variant(postgresql.JSONB(), "postgresql"),
        nullable=True,
        comment="Bản ghi gốc từ AI trước khi người dùng sửa",
    )
    evidence_segment_ids: Mapped[list[str] | None] = mapped_column(
        JSON().with_variant(postgresql.JSONB(), "postgresql"),
        nullable=True,
        comment="Danh sách UUID các segment làm bằng chứng",
    )
    needs_review: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Cờ báo cần người dùng kiểm tra lại do thiếu căn cứ rõ ràng",
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Thời điểm xóa mềm UTC",
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

    meeting: Mapped["Meeting"] = relationship("Meeting", back_populates="action_items")  # noqa: F821
    assignee_speaker: Mapped["Speaker"] = relationship("Speaker")  # noqa: F821
