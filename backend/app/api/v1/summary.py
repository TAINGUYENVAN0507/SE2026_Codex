"""Router cho tóm tắt cuộc họp (Summary & Key Points)."""

from datetime import UTC, datetime
from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    Request,
    status,
)
from fastapi import (
    Path as FastApiPath,
)
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser
from app.core.errors import APIError
from app.db.models.meeting import Meeting
from app.db.models.summary import Summary
from app.db.session import get_db
from app.schemas.common import ErrorResponse
from app.schemas.summary import (
    SummaryContentOut,
    SummaryOut,
    SummaryUpdate,
)
from app.services.audit import record_edit

router = APIRouter()


@router.get(
    "/{meeting_id}/summary",
    response_model=SummaryOut,
    status_code=status.HTTP_200_OK,
    responses={
        404: {
            "model": ErrorResponse,
            "description": "Không tìm thấy tóm tắt cuộc họp",
        },
    },
    summary="Lấy tóm tắt cuộc họp",
)
def get_meeting_summary(
    meeting_id: Annotated[str, FastApiPath(description="UUID của cuộc họp")],
    current_user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
) -> SummaryOut:
    """Lấy thông tin tóm tắt cuộc họp từ cơ sở dữ liệu."""
    meeting = db.execute(select(Meeting).where(Meeting.id == meeting_id)).scalar_one_or_none()
    if not meeting or meeting.owner_id != current_user.id:
        raise APIError(
            code="MEETING_NOT_FOUND",
            message="Không tìm thấy cuộc họp được yêu cầu.",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    summary = db.execute(
        select(Summary).where(Summary.meeting_id == meeting.id)
    ).scalar_one_or_none()

    if summary is None:
        status_val = "failed" if meeting.status == "failed" else "pending"
        return SummaryOut(
            meeting_id=meeting.id,
            status=status_val,
            content=None,
            ai_content=None,
            is_edited=False,
            model=None,
            prompt_version=None,
            generated_at=None,
            version=1,
        )

    is_edited = (
        summary.ai_content is not None
        and summary.content is not None
        and summary.content != summary.ai_content
    )

    content_out = SummaryContentOut.model_validate(summary.content) if summary.content else None
    ai_content_out = (
        SummaryContentOut.model_validate(summary.ai_content) if summary.ai_content else None
    )

    return SummaryOut(
        meeting_id=meeting.id,
        status=summary.status,
        content=content_out,
        ai_content=ai_content_out,
        is_edited=is_edited,
        model=summary.model,
        prompt_version=summary.prompt_version,
        generated_at=summary.created_at,
        version=summary.version,
    )


@router.put(
    "/{meeting_id}/summary",
    response_model=SummaryOut,
    status_code=status.HTTP_200_OK,
    responses={
        404: {
            "model": ErrorResponse,
            "description": "Không tìm thấy tóm tắt cuộc họp",
        },
        409: {
            "model": ErrorResponse,
            "description": "Xung đột phiên bản version của tóm tắt",
        },
    },
    summary="Chỉnh sửa nội dung tóm tắt cuộc họp",
)
def update_meeting_summary(
    meeting_id: Annotated[str, FastApiPath(description="UUID của cuộc họp")],
    payload: SummaryUpdate,
    current_user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
    request: Request,
) -> SummaryOut:
    """Cập nhật tóm tắt cuộc họp với optimistic locking."""
    meeting = db.execute(
        select(Meeting).where(Meeting.id == meeting_id, Meeting.owner_id == current_user.id)
    ).scalar_one_or_none()
    if meeting is None:
        raise APIError(
            code="NOT_FOUND",
            message="Không tìm thấy cuộc họp được yêu cầu.",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    summary = db.execute(
        select(Summary).where(Summary.meeting_id == meeting.id)
    ).scalar_one_or_none()
    if summary is None:
        raise APIError(
            code="NOT_FOUND",
            message="Không tìm thấy tóm tắt cuộc họp.",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    if payload.version != summary.version:
        raise APIError(
            code="VERSION_CONFLICT",
            message="Tóm tắt cuộc họp đã được cập nhật ở nơi khác. Vui lòng tải lại.",
            status_code=status.HTTP_409_CONFLICT,
            details={
                "entity": "summary",
                "current": {"meeting_id": meeting.id, "version": summary.version},
            },
        )

    new_content = payload.content.model_dump()
    is_edited_now = summary.ai_content is not None and new_content != summary.ai_content

    # No-op check: nếu nội dung gửi lên giống hệt hiện tại
    if new_content == summary.content:
        return SummaryOut(
            meeting_id=summary.meeting_id,
            status=summary.status,
            content=summary.content,
            ai_content=summary.ai_content,
            is_edited=is_edited_now,
            model=summary.model,
            prompt_version=summary.prompt_version,
            generated_at=summary.created_at,
            version=summary.version,
        )

    before_state = {"content": summary.content}
    after_state = {"content": new_content}

    now = datetime.now(UTC)
    new_version = payload.version + 1

    # Cập nhật nguyên tử có điều kiện theo version (optimistic locking)
    stmt = (
        update(Summary)
        .where(
            Summary.id == summary.id,
            Summary.meeting_id == meeting.id,
            Summary.version == payload.version,
        )
        .values(
            content=new_content,
            version=new_version,
            updated_at=now,
        )
    )
    res = db.execute(stmt)
    if res.rowcount == 0:
        db.rollback()
        current_summary = db.execute(
            select(Summary).where(Summary.meeting_id == meeting.id)
        ).scalar_one_or_none()
        curr_ver = current_summary.version if current_summary else payload.version
        raise APIError(
            code="VERSION_CONFLICT",
            message="Tóm tắt cuộc họp đã được cập nhật ở nơi khác. Vui lòng tải lại.",
            status_code=status.HTTP_409_CONFLICT,
            details={
                "entity": "summary",
                "current": {"meeting_id": meeting.id, "version": curr_ver},
            },
        )

    record_edit(
        db,
        meeting_id=meeting.id,
        entity_type="summary",
        entity_id=summary.id,
        action="update",
        actor_id=current_user.id,
        field=None,
        before=before_state,
        after=after_state,
        entity_version_after=new_version,
        request_id=getattr(getattr(request, "state", None), "request_id", None),
        created_at=now,
    )
    db.commit()
    db.refresh(summary)

    return SummaryOut(
        meeting_id=summary.meeting_id,
        status=summary.status,
        content=summary.content,
        ai_content=summary.ai_content,
        is_edited=is_edited_now,
        model=summary.model,
        prompt_version=summary.prompt_version,
        generated_at=summary.created_at,
        version=summary.version,
    )
