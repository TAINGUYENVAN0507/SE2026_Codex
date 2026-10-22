"""Cấu hình kết nối và session database SQLAlchemy 2."""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings


def get_engine():
    """Tạo hoặc lấy SQLAlchemy engine từ DATABASE_URL trong settings."""
    settings = get_settings()
    # Cấu hình pool_pre_ping để tự động reconnect khi connection bị ngắt
    return create_engine(
        settings.DATABASE_URL,
        pool_pre_ping=True,
    )


def get_session_factory(engine=None):
    """Tạo sessionmaker gắn với engine tương ứng."""
    if engine is None:
        engine = get_engine()
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """Dependency cung cấp SQLAlchemy session cho FastAPI request."""
    session_factory = get_session_factory()
    db = session_factory()
    try:
        yield db
    finally:
        db.close()
