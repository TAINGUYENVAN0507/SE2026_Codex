"""Model SQLAlchemy cho bảng jobs."""

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
    text,
)
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Job(Base):
    """Bảng quản lý tiến trình và trạng thái các job xử lý audio của cuộc họp."""

    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        comment="UUID định danh duy nhất của job",
    )
    meeting_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("meetings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="ID cuộc họp liên kết",
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="queued",
        comment="Trạng thái job: queued, running, retry_scheduled, succeeded, failed, cancelled",
    )
    stage: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        comment="Stage hiện tại đang thực thi trong pipeline",
    )
    from_stage: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        comment="Stage bắt đầu chạy lại khi retry hoặc resumed",
    )
    stage_status: Mapped[dict[str, Any] | None] = mapped_column(
        JSON().with_variant(postgresql.JSONB(), "postgresql"),
        nullable=True,
        comment="Chi tiết trạng thái từng stage dạng JSON",
    )
    progress: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
        comment="Tiến độ tổng thể từ 0.0 đến 1.0",
    )
    attempt: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        comment="Số lần thử hiện tại",
    )
    max_attempts: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=3,
        comment="Số lần thử tối đa",
    )
    next_run_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Thời điểm lên lịch chạy tiếp theo UTC",
    )
    locked_by: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="Worker instance ID đang giữ khóa lease",
    )
    locked_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Thời điểm hết hạn khóa lease UTC",
    )
    heartbeat_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Thời điểm gửi heartbeat gần nhất UTC",
    )
    error_code: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Mã lỗi chuẩn hóa",
    )
    error_message: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="Mô tả lỗi kỹ thuật",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        comment="Thời điểm tạo job UTC",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
        comment="Thời điểm cập nhật job gần nhất UTC",
    )

    meeting: Mapped["Meeting"] = relationship("Meeting", back_populates="jobs")  # noqa: F821

    __table_args__ = (
        CheckConstraint(
            "status IN ('queued', 'running', 'retry_scheduled', "
            "'succeeded', 'failed', 'cancelled')",
            name="ck_jobs_status",
        ),
        Index(
            "uq_jobs_active_meeting",
            "meeting_id",
            unique=True,
            postgresql_where=text("status IN ('queued', 'running', 'retry_scheduled')"),
            sqlite_where=text("status IN ('queued', 'running', 'retry_scheduled')"),
        ),
    )
