"""Router phục vụ stream dữ liệu âm thanh cuộc họp kèm hỗ trợ HTTP Range (RFC 7233)."""

from collections.abc import Generator
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    Header,
    Response,
    status,
)
from fastapi import (
    Path as FastApiPath,
)
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.responses import StreamingResponse

from app.api.deps import CurrentUser
from app.core.errors import APIError
from app.db.models.meeting import Meeting
from app.db.session import get_db
from app.schemas.common import ErrorResponse
from app.services.storage import Storage, get_storage

AUDIO_MIME_TYPES: dict[str, str] = {
    "mp3": "audio/mpeg",
    "wav": "audio/wav",
    "m4a": "audio/mp4",
    "webm": "audio/webm",
    "ogg": "audio/ogg",
    "flac": "audio/flac",
    "aac": "audio/aac",
}


def stream_file_range(
    file_path: Path, start: int, length: int, chunk_size: int = 64 * 1024
) -> Generator[bytes, None, None]:
    """Đọc và yield các chunk nhị phân từ file theo khoảng byte xác định."""
    bytes_remaining = length
    with open(file_path, "rb") as f:
        f.seek(start)
        while bytes_remaining > 0:
            bytes_to_read = min(chunk_size, bytes_remaining)
            data = f.read(bytes_to_read)
            if not data:
                break
            bytes_remaining -= len(data)
            yield data


router = APIRouter()


@router.get(
    "/{meeting_id}/audio",
    status_code=status.HTTP_200_OK,
    responses={
        200: {"description": "Toàn bộ luồng tệp âm thanh"},
        206: {"description": "Một phần tệp âm thanh theo HTTP Range"},
        404: {"model": ErrorResponse, "description": "Không tìm thấy cuộc họp hoặc tệp âm thanh"},
        410: {"model": ErrorResponse, "description": "Tệp âm thanh đã hết hạn lưu trữ"},
        416: {"model": ErrorResponse, "description": "Khoảng dữ liệu Range không hợp lệ"},
    },
    summary="Phát luồng dữ liệu âm thanh cuộc họp hỗ trợ HTTP Range",
)
def get_meeting_audio(
    meeting_id: str = FastApiPath(..., description="UUID của cuộc họp"),
    range_header: Annotated[str | None, Header(alias="Range")] = None,
    current_user: CurrentUser = None,  # type: ignore[assignment]
    db: Annotated[Session, Depends(get_db)] = None,  # type: ignore[assignment]
    storage: Annotated[Storage, Depends(get_storage)] = None,  # type: ignore[assignment]
) -> Response:
    """Stream tệp âm thanh của cuộc họp hỗ trợ HTTP Range (RFC 7233)."""
    if db is None or current_user is None or storage is None:
        raise APIError(
            code="NOT_FOUND",
            message="Không tìm thấy cuộc họp.",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    meeting = db.execute(select(Meeting).where(Meeting.id == meeting_id)).scalar_one_or_none()
    if meeting is None or meeting.owner_id != current_user.id:
        raise APIError(
            code="NOT_FOUND",
            message="Không tìm thấy cuộc họp.",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    now_utc = datetime.now(UTC)
    retention_ts = meeting.retention_until
    if retention_ts is not None and retention_ts.tzinfo is None:
        retention_ts = retention_ts.replace(tzinfo=UTC)

    if retention_ts is not None and now_utc >= retention_ts:
        raise APIError(
            code="AUDIO_EXPIRED",
            message="Tệp âm thanh đã hết hạn lưu trữ và đã được dọn dẹp.",
            status_code=status.HTTP_410_GONE,
        )

    if not meeting.audio_path:
        raise APIError(
            code="NOT_FOUND",
            message="Cuộc họp không có tệp âm thanh.",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    clean_ext = (
        meeting.audio_path.rsplit(".", 1)[-1].lower() if "." in meeting.audio_path else "wav"
    )
    audio_path = storage.get_audio_path(meeting_id=meeting.id, extension=clean_ext)
    if not audio_path.is_file() and hasattr(storage, "base_dir"):
        fallback_path = Path(storage.base_dir) / meeting.audio_path
        if fallback_path.is_file():
            audio_path = fallback_path

    if not audio_path.is_file():
        if retention_ts is not None and now_utc >= retention_ts:
            raise APIError(
                code="AUDIO_EXPIRED",
                message="Tệp âm thanh đã hết hạn lưu trữ và đã được dọn dẹp.",
                status_code=status.HTTP_410_GONE,
            )
        raise APIError(
            code="NOT_FOUND",
            message="Không tìm thấy tệp âm thanh trên hệ thống lưu trữ.",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    file_size = audio_path.stat().st_size
    mime_type = AUDIO_MIME_TYPES.get(clean_ext, "application/octet-stream")

    if range_header:
        if not range_header.startswith("bytes="):
            raise APIError(
                code="RANGE_NOT_SATISFIABLE",
                message="Khoảng dữ liệu Range không hợp lệ.",
                status_code=status.HTTP_416_RANGE_NOT_SATISFIABLE,
                headers={"Content-Range": f"bytes */{file_size}"},
            )

        range_val = range_header[6:].strip()
        if "," in range_val:
            range_val = range_val.split(",", 1)[0].strip()

        parts = range_val.split("-", 1)
        if len(parts) != 2:
            raise APIError(
                code="RANGE_NOT_SATISFIABLE",
                message="Khoảng dữ liệu Range không hợp lệ.",
                status_code=status.HTTP_416_RANGE_NOT_SATISFIABLE,
                headers={"Content-Range": f"bytes */{file_size}"},
            )

        start_str, end_str = parts[0].strip(), parts[1].strip()

        try:
            if not start_str and end_str:
                suffix_len = int(end_str)
                if suffix_len <= 0:
                    raise ValueError
                start = 0 if suffix_len >= file_size else file_size - suffix_len
                end = file_size - 1
            elif start_str and not end_str:
                start = int(start_str)
                if start < 0 or start >= file_size:
                    raise ValueError
                end = file_size - 1
            elif start_str and end_str:
                start = int(start_str)
                end = int(end_str)
                if start < 0 or start > end or start >= file_size:
                    raise ValueError
                if end >= file_size:
                    end = file_size - 1
            else:
                raise ValueError
        except ValueError:
            raise APIError(
                code="RANGE_NOT_SATISFIABLE",
                message="Khoảng dữ liệu Range không hợp lệ.",
                status_code=status.HTTP_416_RANGE_NOT_SATISFIABLE,
                headers={"Content-Range": f"bytes */{file_size}"},
            ) from None

        content_length = end - start + 1
        return StreamingResponse(
            stream_file_range(audio_path, start, content_length),
            status_code=status.HTTP_206_PARTIAL_CONTENT,
            headers={
                "Content-Range": f"bytes {start}-{end}/{file_size}",
                "Accept-Ranges": "bytes",
                "Content-Length": str(content_length),
                "Content-Type": mime_type,
            },
        )

    return StreamingResponse(
        stream_file_range(audio_path, 0, file_size),
        status_code=status.HTTP_200_OK,
        headers={
            "Accept-Ranges": "bytes",
            "Content-Length": str(file_size),
            "Content-Type": mime_type,
        },
    )
