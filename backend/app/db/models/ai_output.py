"""Model SQLAlchemy cho bảng ai_outputs."""

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, JSON, String
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class AIOutput(Base):
    """Bảng lưu trữ kết quả trung gian và cuối cùng bất biến từ các stage của pipeline."""

    __tablename__ = "ai_outputs"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        comment="UUID định danh duy nhất của ai_output",
    )
    meeting_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("meetings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="ID cuộc họp liên kết",
    )
    job_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="ID job sinh ra output này",
    )
    stage: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="Tên stage (preprocess, vad, asr, diarize, merge, summarize)",
    )
    payload: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(postgresql.JSONB(), "postgresql"),
        nullable=False,
        comment="Nội dung kết quả artifact bất biến dạng JSON",
    )
    model: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="Tên model AI thực thi",
    )
    model_params: Mapped[dict[str, Any] | None] = mapped_column(
        JSON().with_variant(postgresql.JSONB(), "postgresql"),
        nullable=True,
        comment="Tham số cấu hình model khi chạy",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        comment="Thời điểm lưu trữ bất biến UTC",
    )

    meeting: Mapped["Meeting"] = relationship("Meeting", back_populates="ai_outputs")  # noqa: F821
    job: Mapped["Job"] = relationship("Job")  # noqa: F821

    __table_args__ = (
        Index("uq_ai_outputs_job_stage", "job_id", "stage", unique=True),
    )
