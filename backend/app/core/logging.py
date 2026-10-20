"""Cấu hình structured JSON logging theo chuẩn của dự án."""

import json
import logging
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any

# ContextVar lưu trữ request_id của request hiện tại
current_request_id: ContextVar[str | None] = ContextVar("current_request_id", default=None)


class JSONLogFormatter(logging.Formatter):
    """Formatter chuyển log record thành định dạng JSON chuẩn.

    Chỉ log metadata kỹ thuật: method, path, status, duration, request_id.
    Cấm log body, cookie, Authorization token hay transcript người dùng (privacy-security.md).
    """

    def format(self, record: logging.LogRecord) -> str:
        log_entry: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", None) or current_request_id.get(),
        }

        # Nếu record có extra fields liên quan đến HTTP request
        for key in ("method", "path", "status_code", "duration_ms"):
            if hasattr(record, key):
                log_entry[key] = getattr(record, key)

        if record.exc_info and not record.exc_text:
            # Chỉ ghi tên loại exception, không ghi message hoặc stack trace chứa PII
            exc_type = record.exc_info[0]
            log_entry["exception_type"] = exc_type.__name__ if exc_type else "Exception"

        return json.dumps(log_entry, ensure_ascii=False)


def setup_logging(log_level: int = logging.INFO) -> None:
    """Cấu hình root logger và app logger sử dụng JSONLogFormatter."""
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Xóa các handler cũ nếu có
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(JSONLogFormatter())
    root_logger.addHandler(stream_handler)
