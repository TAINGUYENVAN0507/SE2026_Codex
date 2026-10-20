"""Interface kiểm tra kết nối cơ sở dữ liệu để phục vụ readiness probe."""

from typing import Protocol


class DatabaseHealthChecker(Protocol):
    """Interface định nghĩa phương thức kiểm tra kết nối cơ sở dữ liệu."""

    def is_healthy(self) -> bool:
        """Kiểm tra kết nối DB có sẵn sàng hay không."""
        ...


class DefaultDatabaseHealthChecker:
    """Triển khai kiểm tra kết nối DB mặc định."""

    def __init__(self, database_url: str | None = None) -> None:
        self.database_url = database_url

    def is_healthy(self) -> bool:
        """Kiểm tra kết nối đến cơ sở dữ liệu.

        Ở giai đoạn hiện tại (chưa có SQLAlchemy engine / migrations), nếu có DATABASE_URL
        hợp lệ thì trả về True. Sẽ được tích hợp SQLAlchemy ping khi sang BE-03.
        """
        return bool(self.database_url)


def get_db_health_checker() -> DatabaseHealthChecker:
    """Dependency cung cấp instance DatabaseHealthChecker."""
    from app.core.config import get_settings

    settings = get_settings()
    return DefaultDatabaseHealthChecker(database_url=settings.DATABASE_URL)
