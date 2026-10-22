"""Cấu hình DeclarativeBase cho SQLAlchemy 2."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class cho toàn bộ database models."""

    pass
