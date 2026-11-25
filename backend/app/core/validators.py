"""Các hàm kiểm tra và chuẩn hóa dữ liệu đầu vào dùng chung cho API backend."""

import re
from datetime import date

from fastapi import status

from app.core.errors import APIError

MEETING_TITLE_MAX_LEN = 200
IDEMPOTENCY_KEY_MAX_LEN = 100
_ISO_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def validate_meeting_title(raw_title: str | None) -> str:
    """Chuẩn hóa và kiểm tra tiêu đề cuộc họp (1 đến 200 ký tự sau khi strip)."""
    if raw_title is None:
        raise APIError(
            code="VALIDATION_ERROR",
            message="Tiêu đề cuộc họp không được để trống.",
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        )
    cleaned = raw_title.strip()
    if not cleaned:
        raise APIError(
            code="VALIDATION_ERROR",
            message="Tiêu đề cuộc họp không được để trống.",
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        )
    if len(cleaned) > MEETING_TITLE_MAX_LEN:
        raise APIError(
            code="VALIDATION_ERROR",
            message=f"Tiêu đề cuộc họp không được vượt quá {MEETING_TITLE_MAX_LEN} ký tự.",
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        )
    return cleaned


def parse_iso_date(value: str | None) -> str | None:
    """Kiểm tra chuỗi ngày đúng định dạng YYYY-MM-DD và là ngày hợp lệ trên lịch."""
    if value is None:
        return None
    if not _ISO_DATE_PATTERN.fullmatch(value):
        raise ValueError("Ngày phải đúng định dạng YYYY-MM-DD.")
    date.fromisoformat(value)
    return value


def validate_iso_date(value: str | None, field_label: str = "Ngày") -> str | None:
    """Xác thực chuỗi ngày YYYY-MM-DD và ném APIError 422 nếu sai."""
    try:
        return parse_iso_date(value)
    except ValueError as exc:
        raise APIError(
            code="VALIDATION_ERROR",
            message=f"{field_label} phải đúng định dạng YYYY-MM-DD hợp lệ.",
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        ) from exc


def validate_idempotency_key(raw_key: str | None, *, required: bool = True) -> str | None:
    """Kiểm tra header Idempotency-Key hợp lệ (không rỗng khi bắt buộc, tối đa 100 ký tự)."""
    cleaned = raw_key.strip() if raw_key else ""
    if not cleaned:
        if required:
            raise APIError(
                code="IDEMPOTENCY_KEY_REQUIRED",
                message="Header Idempotency-Key là bắt buộc khi tạo cuộc họp.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        return None
    if len(cleaned) > IDEMPOTENCY_KEY_MAX_LEN:
        raise APIError(
            code="IDEMPOTENCY_KEY_TOO_LONG",
            message=f"Header Idempotency-Key không được vượt quá {IDEMPOTENCY_KEY_MAX_LEN} ký tự.",
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        )
    return cleaned
