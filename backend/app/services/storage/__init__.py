"""Package dịch vụ lưu trữ (Storage Service)."""

from functools import lru_cache

from app.services.storage.base import (
    FileTooLargeError,
    Storage,
    StorageError,
    StorageUploadResult,
)
from app.services.storage.local import LocalStorage

__all__ = [
    "Storage",
    "LocalStorage",
    "StorageError",
    "FileTooLargeError",
    "StorageUploadResult",
    "get_storage",
]


@lru_cache
def get_storage() -> Storage:
    """Trả về singleton instance của storage mặc định."""
    return LocalStorage()
