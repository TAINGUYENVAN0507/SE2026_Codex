"""Middleware quản lý request_id và ghi structured log cho mỗi HTTP request."""

import logging
import time
import uuid
from typing import Any

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from app.core.logging import current_request_id

logger = logging.getLogger("app.access")


class RequestIDAndLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware trích xuất/sinh X-Request-ID và ghi log truy cập dạng JSON."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Lấy X-Request-ID từ header hoặc sinh UUID mới
        request_id = request.headers.get("X-Request-ID")
        if not request_id:
            request_id = str(uuid.uuid4())

        request.state.request_id = request_id
        token = current_request_id.set(request_id)

        start_time = time.perf_counter()

        try:
            response = await call_next(request)
        finally:
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)

            # Đảm bảo header X-Request-ID luôn có trong response
            # (nếu đã có response object)
            status_code = getattr(response, "status_code", 500) if "response" in locals() else 500

            # Ghi log kỹ thuật, chỉ ghi method, path, status, duration và request_id
            # Tuyệt đối không log body hay Authorization header (rules/privacy-security.md)
            extra_fields: dict[str, Any] = {
                "method": request.method,
                "path": request.url.path,
                "status_code": status_code,
                "duration_ms": duration_ms,
                "request_id": request_id,
            }

            logger.info("HTTP request completed", extra=extra_fields)
            current_request_id.reset(token)

        response.headers["X-Request-ID"] = request_id
        return response
