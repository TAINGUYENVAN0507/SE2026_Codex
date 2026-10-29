"""Model SQLAlchemy cho bảng meetings."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Meeting(Base):
    """Bảng lưu thông tin cuộc họp và trạng thái xử lý."""

    __tablename__ = "meetings"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        comment="UUID định danh duy nhất của cuộc họp",
    )
    owner_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="ID người sở hữu cuộc họp",
    )
    title: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        comment="Tiêu đề cuộc họp",
    )
    source: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="upload",
        comment="Nguồn audio: upload hoặc recording",
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="queued",
        comment="Trạng thái xử lý: queued, processing, ready, partial, failed",
    )
    duration_sec: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        comment="Thời lượng audio tính bằng giây",
    )
    audio_path: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="Đường dẫn lưu file audio trên volume",
    )
    audio_sha256: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        comment="Mã hash SHA-256 của file audio gốc",
    )
    num_speakers_hint: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Gợi ý số lượng người nói từ người dùng",
    )
    meeting_date: Mapped[str | None] = mapped_column(
        String(10),
        nullable=True,
        comment="Ngày họp định dạng YYYY-MM-DD",
    )
    consent_confirmed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Thời điểm xác nhận consent UTC",
    )
    retention_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Thời điểm hết hạn lưu giữ audio UTC",
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
        comment="Thời điểm tạo cuộc họp UTC",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
        comment="Thời điểm cập nhật gần nhất UTC",
    )

    owner: Mapped["User"] = relationship("User", back_populates="meetings")  # noqa: F821
    jobs: Mapped[list["Job"]] = relationship(  # noqa: F821
        "Job",
        back_populates="meeting",
        cascade="all, delete-orphan",
    )
    speakers: Mapped[list["Speaker"]] = relationship(  # noqa: F821
        "Speaker",
        back_populates="meeting",
        cascade="all, delete-orphan",
    )
    segments: Mapped[list["Segment"]] = relationship(  # noqa: F821
        "Segment",
        back_populates="meeting",
        cascade="all, delete-orphan",
    )
    ai_outputs: Mapped[list["AIOutput"]] = relationship(  # noqa: F821
        "AIOutput",
        back_populates="meeting",
        cascade="all, delete-orphan",
    )
    summary: Mapped["Summary | None"] = relationship(  # noqa: F821
        "Summary",
        back_populates="meeting",
        uselist=False,
        cascade="all, delete-orphan",
    )
    action_items: Mapped[list["ActionItem"]] = relationship(  # noqa: F821
        "ActionItem",
        back_populates="meeting",
        cascade="all, delete-orphan",
    )
    edit_events: Mapped[list["EditEvent"]] = relationship(  # noqa: F821
        "EditEvent",
        back_populates="meeting",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
