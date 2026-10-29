"""Triển khai dịch vụ lưu trữ trên hệ thống tệp cục bộ (Local Filesystem)."""

import contextlib
import hashlib
import os
import shutil
import uuid
from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.services.storage.base import (
    FileTooLargeError,
    Storage,
    StorageError,
    StorageUploadResult,
)

DEFAULT_CHUNK_SIZE = 1024 * 1024  # 1 MB


class LocalStorage(Storage):
    """Lưu trữ tệp tin trên ổ đĩa cục bộ hoặc volume mounted."""

    def __init__(
        self,
        base_dir: str | Path | None = None,
        max_upload_mb: int | None = None,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
    ) -> None:
        settings = get_settings()
        self.base_dir = (
            Path(base_dir).resolve()
            if base_dir is not None
            else Path(__file__).resolve().parent.parent.parent.parent / "appdata"
        )
        self.max_upload_bytes = (
            (max_upload_mb if max_upload_mb is not None else settings.MAX_UPLOAD_MB) * 1024 * 1024
        )
        self.chunk_size = chunk_size

    def _sanitize_extension(self, extension: str) -> str:
        """Chuẩn hóa phần mở rộng tệp tin (bỏ dấu chấm và chuyển chữ thường)."""
        clean = extension.strip().lstrip(".").lower()
        if not clean:
            raise StorageError("Phần mở rộng tệp tin không hợp lệ")
        return clean

    def get_audio_dir(self, meeting_id: str) -> Path:
        """Trả về thư mục lưu audio của meeting."""
        return self.base_dir / "audio" / meeting_id

    def get_audio_path(self, meeting_id: str, extension: str) -> Path:
        """Trả về đường dẫn tới tệp audio gốc của cuộc họp."""
        clean_ext = self._sanitize_extension(extension)
        return self.get_audio_dir(meeting_id) / f"original.{clean_ext}"

    def save_upload(
        self,
        meeting_id: str,
        extension: str,
        stream: Any,
    ) -> StorageUploadResult:
        """Ghi dữ liệu upload vào file tạm theo chunk 1 MB, kiểm tra dung lượng và di chuyển atomic.

        Tham số stream có thể là file-like object (có hàm .read()), Iterable[bytes],
        hoặc callable sinh chunk.
        """
        clean_ext = self._sanitize_extension(extension)
        audio_dir = self.get_audio_dir(meeting_id)
        audio_dir.mkdir(parents=True, exist_ok=True)

        target_file = audio_dir / f"original.{clean_ext}"
        temp_file = audio_dir / f"upload_{uuid.uuid4().hex}.tmp"

        hasher = hashlib.sha256()
        total_bytes = 0

        try:
            with open(temp_file, "wb") as f:
                # Xử lý trường hợp stream là file-like object
                if hasattr(stream, "read"):
                    while True:
                        chunk = stream.read(self.chunk_size)
                        if not chunk:
                            break
                        total_bytes += len(chunk)
                        if total_bytes > self.max_upload_bytes:
                            raise FileTooLargeError(
                                f"Kích thước file vượt quá giới hạn "
                                f"{self.max_upload_bytes // (1024 * 1024)} MB"
                            )
                        hasher.update(chunk)
                        f.write(chunk)

                # Xử lý trường hợp stream là Iterable các chunks bytes
                elif hasattr(stream, "__iter__") and not isinstance(stream, bytes | str):
                    for chunk in stream:
                        total_bytes += len(chunk)
                        if total_bytes > self.max_upload_bytes:
                            raise FileTooLargeError(
                                f"Kích thước file vượt quá giới hạn "
                                f"{self.max_upload_bytes // (1024 * 1024)} MB"
                            )
                        hasher.update(chunk)
                        f.write(chunk)

                # Trường hợp stream là bytes trực tiếp
                elif isinstance(stream, bytes):
                    total_bytes = len(stream)
                    if total_bytes > self.max_upload_bytes:
                        raise FileTooLargeError(
                            f"Kích thước file vượt quá giới hạn "
                            f"{self.max_upload_bytes // (1024 * 1024)} MB"
                        )
                    hasher.update(stream)
                    f.write(stream)
                else:
                    raise StorageError(f"Kiểu dữ liệu stream không được hỗ trợ: {type(stream)}")

            # Di chuyển atomic sang file đích chính thức
            os.replace(temp_file, target_file)

        except Exception:
            # Dọn sạch file tạm nếu có lỗi hoặc vượt quá dung lượng
            if temp_file.exists():
                with contextlib.suppress(Exception):
                    temp_file.unlink()
            raise

        rel_path = f"audio/{meeting_id}/original.{clean_ext}"
        return StorageUploadResult(
            path=rel_path,
            sha256=hasher.hexdigest(),
            size_bytes=total_bytes,
        )

    def delete_meeting_files(self, meeting_id: str) -> None:
        """Xóa thư mục audio và artifacts của meeting."""
        meeting_dir = self.get_audio_dir(meeting_id)
        if meeting_dir.exists():
            shutil.rmtree(meeting_dir, ignore_errors=True)
        artifacts_dir = Path(self.base_dir) / "artifacts" / meeting_id
        if artifacts_dir.exists():
            shutil.rmtree(artifacts_dir, ignore_errors=True)
