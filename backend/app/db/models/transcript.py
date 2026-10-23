"""Model SQLAlchemy cho các bảng liên quan đến transcript: speakers và segments."""

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Speaker(Base):
    """Bảng lưu trữ thông tin người nói trong cuộc họp."""

    __tablename__ = "speakers"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        comment="UUID định danh duy nhất của người nói",
    )
    meeting_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("meetings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="ID cuộc họp liên kết",
    )
    label: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Nhãn speaker từ pipeline (vd: SPEAKER_00)",
    )
    default_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Tên mặc định ban đầu (vd: Speaker 1)",
    )
    display_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Tên hiển thị người nói có thể chỉnh sửa",
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

    meeting: Mapped["Meeting"] = relationship("Meeting", back_populates="speakers")  # noqa: F821
    segments: Mapped[list["Segment"]] = relationship(
        "Segment",
        back_populates="speaker",
        foreign_keys="Segment.speaker_id",
    )

    __table_args__ = (
        Index("uq_speakers_meeting_label", "meeting_id", "label", unique=True),
    )


class Segment(Base):
    """Bảng lưu trữ từng phân đoạn transcript lời thoại."""

    __tablename__ = "segments"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        comment="UUID định danh duy nhất của phân đoạn",
    )
    meeting_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("meetings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="ID cuộc họp liên kết",
    )
    idx: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Thứ tự xuất hiện của phân đoạn trong cuộc họp",
    )
    start_sec: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        comment="Thời điểm bắt đầu tính bằng giây",
    )
    end_sec: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        comment="Thời điểm kết thúc tính bằng giây",
    )
    speaker_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("speakers.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="ID người nói hiện tại",
    )
    ai_speaker_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("speakers.id", ondelete="SET NULL"),
        nullable=True,
        comment="ID người nói gốc từ AI (bất biến)",
    )
    text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Nội dung lời thoại hiện tại",
    )
    ai_text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Nội dung lời thoại gốc từ AI (bất biến)",
    )
    confidence: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        comment="Độ tin cậy của ASR",
    )
    flags: Mapped[dict[str, Any] | None] = mapped_column(
        JSON().with_variant(postgresql.JSONB(), "postgresql"),
        nullable=True,
        comment="Các cờ bổ trợ (overlap, low_confidence, ...)",
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

    meeting: Mapped["Meeting"] = relationship("Meeting", back_populates="segments")  # noqa: F821
    speaker: Mapped[Speaker | None] = relationship(
        "Speaker",
        foreign_keys=[speaker_id],
        back_populates="segments",
    )

    __table_args__ = (
        CheckConstraint(
            "start_sec >= 0 AND start_sec < end_sec",
            name="ck_segments_time_range",
        ),
        Index("ix_segments_meeting_time", "meeting_id", "start_sec", "end_sec"),
    )
