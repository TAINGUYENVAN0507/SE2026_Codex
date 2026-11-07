"""Cấu hình kết nối và session database SQLAlchemy 2."""

from collections.abc import Generator
from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings


@lru_cache
def _engine_for(url: str):
    # Một engine (một pool) cho mỗi URL trong suốt vòng đời process. Trước đây mỗi request tạo
    # engine mới và không đóng, nên 40 request đồng thời cạn max_connections của Postgres.
    # pool_pre_ping để tự reconnect khi connection bị ngắt.
    return create_engine(url, pool_pre_ping=True)


def get_engine():
    """Lấy SQLAlchemy engine dùng chung theo DATABASE_URL trong settings."""
    return _engine_for(get_settings().DATABASE_URL)


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
