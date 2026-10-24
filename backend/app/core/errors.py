"""Quy định error envelope và exception handlers chuẩn hóa theo contracts."""

import uuid
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class APIError(Exception):
    """Exception cơ sở cho các lỗi nghiệp vụ trong API."""

    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        details: Any = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details
        self.headers = headers


def build_error_envelope(
    code: str,
    message: str,
    details: Any = None,
    request_id: str | None = None,
) -> dict[str, Any]:
    """Tạo dictionary chuẩn error envelope theo quy định contracts."""
    return {
        "error": {
            "code": code,
            "message": message,
            "details": details,
            "request_id": request_id,
        }
    }


def get_request_id(request: Request) -> str:
    """Lấy request_id từ request.state hoặc header X-Request-ID, nếu chưa có thì sinh mới."""
    if hasattr(request.state, "request_id") and request.state.request_id:
        return str(request.state.request_id)
    header_request_id = request.headers.get("X-Request-ID")
    if header_request_id:
        return header_request_id
    return str(uuid.uuid4())


async def api_error_handler(request: Request, exc: APIError) -> JSONResponse:
    """Xử lý lỗi APIError nghiệp vụ."""
    request_id = get_request_id(request)
    body = build_error_envelope(
        code=exc.code,
        message=exc.message,
        details=exc.details,
        request_id=request_id,
    )
    return JSONResponse(status_code=exc.status_code, content=body, headers=exc.headers)


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """Xử lý HTTPException chuẩn của Starlette/FastAPI (ví dụ 404, 403, 401)."""
    request_id = get_request_id(request)

    status_code = exc.status_code
    code_map = {
        400: "BAD_REQUEST",
        401: "UNAUTHENTICATED",
        403: "FORBIDDEN",
        404: "NOT_FOUND",
        405: "METHOD_NOT_ALLOWED",
        409: "CONFLICT",
        413: "FILE_TOO_LARGE",
        415: "UNSUPPORTED_MEDIA_TYPE",
        422: "UNPROCESSABLE_ENTITY",
        503: "SERVICE_UNAVAILABLE",
    }
    code = code_map.get(status_code, "HTTP_ERROR")

    # Nếu detail là chuỗi ký tự
    message = str(exc.detail) if exc.detail else "Yêu cầu không hợp lệ."
    if status_code == 404 and exc.detail == "Not Found":
        message = "Không tìm thấy tài nguyên được yêu cầu."

    body = build_error_envelope(
        code=code,
        message=message,
        details=None,
        request_id=request_id,
    )
    return JSONResponse(status_code=status_code, content=body)


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Xử lý lỗi 422 validation của FastAPI."""
    request_id = get_request_id(request)
    # Lọc danh sách lỗi để an toàn và nhất quán
    details = exc.errors()

    code = "VALIDATION_ERROR"
    message = "Dữ liệu yêu cầu không hợp lệ."

    for err in details:
        loc = err.get("loc", ())
        err_type = str(err.get("type", ""))
        if "text" in loc:
            if "too_short" in err_type or "empty" in err_type or "missing" in err_type:
                code = "TEXT_EMPTY"
                message = "Nội dung đoạn thoại không được để trống."
                break
            if "too_long" in err_type:
                code = "TEXT_TOO_LONG"
                message = "Nội dung vượt quá độ dài tối đa cho phép."
                break

    body = build_error_envelope(
        code=code,
        message=message,
        details=details,
        request_id=request_id,
    )
    return JSONResponse(status_code=422, content=body)


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Xử lý lỗi 500 không lường trước.

    Tuyệt đối không để lộ thông tin nhạy cảm, message của exception hoặc stack trace
    theo đúng quy định an toàn bảo mật (privacy-security.md).
    """
    request_id = get_request_id(request)
    body = build_error_envelope(
        code="INTERNAL_SERVER_ERROR",
        message="Đã xảy ra lỗi nội bộ hệ thống. Vui lòng thử lại sau.",
        details=None,
        request_id=request_id,
    )
    return JSONResponse(
        status_code=500,
        content=body,
    )


def setup_exception_handlers(application: FastAPI) -> None:
    """Đăng ký toàn bộ exception handlers cho ứng dụng FastAPI."""
    application.add_exception_handler(APIError, api_error_handler)  # type: ignore[arg-type]
    application.add_exception_handler(StarletteHTTPException, http_exception_handler)  # type: ignore[arg-type]
    application.add_exception_handler(RequestValidationError, validation_exception_handler)  # type: ignore[arg-type]
    application.add_exception_handler(Exception, unhandled_exception_handler)
