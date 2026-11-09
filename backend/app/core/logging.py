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

    Chỉ log metadata kỹ thuật theo ROADMAP: event, job_id, meeting_id, request_id,
    worker_id, stage, attempt, error_code, duration_sec, status, method, path...
    Cấm log body, cookie, Authorization token hay transcript người dùng (privacy-security.md).
    """

    ALLOWED_FIELDS = (
        "event",
        "job_id",
        "meeting_id",
        "request_id",
        "worker_id",
        "stage",
        "attempt",
        "error_code",
        "duration_sec",
        "status",
        "method",
        "path",
        "status_code",
        "duration_ms",
    )

    def format(self, record: logging.LogRecord) -> str:
        log_entry: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", None) or current_request_id.get(),
        }

        # Bổ sung các field cấu trúc được phép (ROADMAP & HTTP request)
        for key in self.ALLOWED_FIELDS:
            val = getattr(record, key, None)
            if val is not None:
                log_entry[key] = val

        if record.exc_info and not record.exc_text:
            # Chỉ ghi tên loại exception, không ghi message hoặc stack trace chứa PII
            exc_type = record.exc_info[0]
            log_entry["exception_type"] = exc_type.__name__ if exc_type else "Exception"

        return json.dumps(log_entry, ensure_ascii=False)


def setup_logging(log_level: int = logging.INFO) -> None:
    """Cấu hình root logger và app logger sử dụng JSONLogFormatter."""
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.disabled = False

    # Đảm bảo các logger ứng dụng không bị vô hiệu hóa bởi fileConfig bên ngoài
    for logger in logging.root.manager.loggerDict.values():
        if isinstance(logger, logging.Logger):
            logger.disabled = False

    # Không xóa handler phục vụ kiểm thử (như pytest LogCaptureHandler)
    has_json_handler = False
    for handler in list(root_logger.handlers):
        if "LogCapture" in type(handler).__name__:
            continue
        if isinstance(handler, logging.StreamHandler) and isinstance(
            handler.formatter, JSONLogFormatter
        ):
            has_json_handler = True
            continue
        root_logger.removeHandler(handler)

    if not has_json_handler:
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(JSONLogFormatter())
        root_logger.addHandler(stream_handler)
