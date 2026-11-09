"""Router cho chức năng xuất dữ liệu (Export) cuộc họp."""

from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    Query,
    Response,
    status,
)
from fastapi import (
    Path as FastApiPath,
)
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser
from app.core.errors import APIError
from app.db.session import get_db
from app.schemas.common import ErrorResponse
from app.services.export import filename as export_filename
from app.services.export import to_json, to_markdown, to_txt
from app.services.meeting_export import build_meeting_export

router = APIRouter()


@router.get(
    "/{meeting_id}/export",
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_200_OK: {
            "description": "Nội dung biên bản cuộc họp",
            "content": {
                "text/plain": {"schema": {"type": "string"}},
                "text/markdown": {"schema": {"type": "string"}},
                "application/json": {"schema": {"type": "string"}},
            },
        },
        404: {"model": ErrorResponse, "description": "Không tìm thấy cuộc họp"},
        409: {
            "model": ErrorResponse,
            "description": "Transcript chưa sẵn sàng để xuất",
        },
        422: {
            "model": ErrorResponse,
            "description": "Định dạng export không được hỗ trợ",
        },
    },
    summary="Xuất nội dung cuộc họp theo định dạng yêu cầu",
)
def export_meeting(
    meeting_id: str = FastApiPath(..., description="UUID của cuộc họp"),
    format: Annotated[str, Query(description="Định dạng xuất: txt, json, md")] = "txt",
    variant: Annotated[
        str, Query(description="Biến thể nội dung: current hoặc ai_original")
    ] = "current",
    current_user: CurrentUser = None,
    db: Annotated[Session, Depends(get_db)] = None,
) -> Response:
    """Xuất biên bản cuộc họp dưới định dạng mong muốn."""
    fmt = format.lower()
    if fmt not in ("txt", "json", "md"):
        raise APIError(
            code="FORMAT_NOT_SUPPORTED",
            message=f"Định dạng xuất '{format}' không được hỗ trợ.",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    var = variant.lower()
    if var not in ("current", "ai_original"):
        raise APIError(
            code="FORMAT_NOT_SUPPORTED",
            message=f"Biến thể nội dung '{variant}' không được hỗ trợ.",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    meeting_export = build_meeting_export(db, meeting_id, current_user.id)

    media_types = {
        "txt": "text/plain; charset=utf-8",
        "md": "text/markdown; charset=utf-8",
        "json": "application/json; charset=utf-8",
    }

    if fmt == "txt":
        content_bytes = to_txt(meeting_export, variant=var)
    elif fmt == "md":
        content_bytes = to_markdown(meeting_export, variant=var)
    else:
        content_bytes = to_json(meeting_export, variant=var)

    download_name = export_filename(meeting_export, fmt)
    return Response(
        content=content_bytes,
        media_type=media_types[fmt],
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{download_name}"},
    )
