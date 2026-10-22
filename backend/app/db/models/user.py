"""Model SQLAlchemy cho bảng users."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class User(Base):
    """Bảng lưu thông tin tài khoản người dùng."""

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        comment="UUID định danh duy nhất của người dùng",
    )
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=False,
        comment="Địa chỉ email đăng nhập",
    )
    display_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Tên hiển thị của người dùng",
    )
    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Hash mật khẩu (Argon2)",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        comment="Thời điểm tạo tài khoản UTC",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
        comment="Thời điểm cập nhật tài khoản gần nhất UTC",
    )

    meetings: Mapped[list["Meeting"]] = relationship(  # noqa: F821
        "Meeting",
        back_populates="owner",
        cascade="all, delete-orphan",
    )
