"""Interface và các kiểu dữ liệu cho dịch vụ lưu trữ file."""

from collections.abc import AsyncIterable, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Protocol


class StorageError(Exception):
    """Lỗi cơ sở cho các thao tác lưu trữ."""

    def __init__(self, message: str, code: str = "STORAGE_ERROR") -> None:
        super().__init__(message)
        self.message = message
        self.code = code


class FileTooLargeError(StorageError):
    """Lỗi kích thước file upload vượt quá giới hạn tối đa cho phép."""

    def __init__(self, message: str = "Kích thước tệp vượt quá giới hạn cho phép") -> None:
        super().__init__(message, code="FILE_TOO_LARGE")


@dataclass(frozen=True)
class StorageUploadResult:
    """Kết quả sau khi lưu trữ file upload thành công."""

    path: str
    sha256: str
    size_bytes: int


class Storage(Protocol):
    """Interface định nghĩa các thao tác lưu trữ file của hệ thống."""

    def save_upload(
        self,
        meeting_id: str,
        extension: str,
        stream: BinaryIO | Iterable[bytes] | AsyncIterable[bytes],
    ) -> StorageUploadResult:
        """Ghi stream dữ liệu vào file tạm, kiểm tra dung lượng, tính sha256 và di chuyển atomic.

        Raises:
            FileTooLargeError: Nếu dung lượng vượt quá MAX_UPLOAD_MB.
            StorageError: Nếu có lỗi I/O phát sinh.
        """
        ...

    def get_audio_path(self, meeting_id: str, extension: str) -> Path:
        """Lấy đường dẫn đầy đủ tới file audio gốc."""
        ...

    def delete_meeting_files(self, meeting_id: str) -> None:
        """Xóa toàn bộ các tệp liên quan đến cuộc họp."""
        ...
