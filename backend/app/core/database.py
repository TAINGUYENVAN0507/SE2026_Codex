"""Interface kiểm tra kết nối cơ sở dữ liệu để phục vụ readiness probe."""

from typing import Protocol

from sqlalchemy import text
from sqlalchemy.engine import Engine


class DatabaseHealthChecker(Protocol):
    """Interface định nghĩa phương thức kiểm tra kết nối cơ sở dữ liệu."""

    def is_healthy(self) -> bool:
        """Kiểm tra kết nối DB có sẵn sàng hay không."""
        ...


class DefaultDatabaseHealthChecker:
    """Triển khai kiểm tra kết nối DB thật qua SQLAlchemy engine."""

    def __init__(self, engine: Engine | None = None) -> None:
        self.engine = engine

    def is_healthy(self) -> bool:
        """Kiểm tra kết nối thật bằng cách thực thi lệnh ping 'SELECT 1'.

        Trả về True nếu kết nối thành công, False nếu mất kết nối hoặc DB tắt.
        """
        if self.engine is None:
            return False
        try:
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return True
        except Exception:
            return False


def get_db_health_checker() -> DatabaseHealthChecker:
    """Dependency cung cấp instance DatabaseHealthChecker."""
    from app.db.session import get_engine

    try:
        engine = get_engine()
        return DefaultDatabaseHealthChecker(engine=engine)
    except Exception:
        return DefaultDatabaseHealthChecker(engine=None)
