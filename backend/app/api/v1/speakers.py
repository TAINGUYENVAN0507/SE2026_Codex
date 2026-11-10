"""Router quản lý người nói (Speakers) trong cuộc họp (BE-12)."""

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
from app.db.models.transcript import Segment, Speaker
from app.db.session import get_db
from app.schemas.common import ErrorResponse
from app.schemas.meeting import SpeakerOut
from app.schemas.transcript import SpeakerPatch
from app.services.audit import record_edit

router = APIRouter()


def serialize_speaker(spk: Speaker, db: Session, meeting_id: str) -> SpeakerOut:
    """Chuyển đổi Speaker model sang SpeakerOut schema đầy đủ thông tin hiển thị."""
    all_speakers = (
        db.execute(
            select(Speaker)
            .where(Speaker.meeting_id == meeting_id)
            .order_by(Speaker.created_at.asc(), Speaker.id.asc())
        )
        .scalars()
        .all()
    )
    color_index = 0
    for idx, s in enumerate(all_speakers):
        if s.id == spk.id:
            color_index = idx % 10
            break

    segments = (
        db.execute(
            select(Segment).where(Segment.meeting_id == meeting_id, Segment.speaker_id == spk.id)
        )
        .scalars()
        .all()
    )
    segment_count = len(segments)
    speaking_time_sec = round(
        sum(max(0.0, (seg.end_sec or 0.0) - (seg.start_sec or 0.0)) for seg in segments), 2
    )
    is_edited = spk.display_name != spk.default_name

    return SpeakerOut(
        id=spk.id,
        meeting_id=spk.meeting_id,
        label=spk.label,
        default_name=spk.default_name,
        display_name=spk.display_name,
        is_edited=is_edited,
        color_index=color_index,
        segment_count=segment_count,
        speaking_time_sec=speaking_time_sec,
        version=spk.version,
    )


@router.patch(
    "/{meeting_id}/speakers/{speaker_id}",
    response_model=SpeakerOut,
    status_code=status.HTTP_200_OK,
    responses={
        404: {"model": ErrorResponse, "description": "Không tìm thấy người nói"},
        409: {
            "model": ErrorResponse,
            "description": "Xung đột phiên bản version của người nói",
        },
    },
    summary="Đổi tên hiển thị của người nói",
)
def patch_meeting_speaker(
    meeting_id: Annotated[str, FastApiPath(description="UUID của cuộc họp")],
    speaker_id: Annotated[str, FastApiPath(description="UUID của người nói cần sửa")],
    payload: SpeakerPatch,
    current_user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
    request: Request,
) -> SpeakerOut:
    """Cập nhật tên hiển thị người nói với kiểm tra optimistic concurrency control."""
    meeting = db.execute(
        select(Meeting).where(Meeting.id == meeting_id, Meeting.owner_id == current_user.id)
    ).scalar_one_or_none()
    if meeting is None:
        raise APIError(
            code="NOT_FOUND",
            message="Không tìm thấy cuộc họp được yêu cầu.",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    speaker = db.execute(
        select(Speaker).where(Speaker.id == speaker_id, Speaker.meeting_id == meeting.id)
    ).scalar_one_or_none()
    if speaker is None:
        raise APIError(
            code="NOT_FOUND",
            message="Không tìm thấy người nói được yêu cầu.",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    if payload.version != speaker.version:
        raise APIError(
            code="VERSION_CONFLICT",
            message="Người nói đã được cập nhật ở nơi khác. Vui lòng tải lại.",
            status_code=status.HTTP_409_CONFLICT,
            details={
                "entity": "speaker",
                "current": {"id": speaker.id, "version": speaker.version},
            },
        )

    cleaned_name = payload.display_name.strip()
    if not cleaned_name:
        raise APIError(
            code="VALIDATION_ERROR",
            message="Tên người nói không được để trống.",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    # Nếu cùng tên hiển thị -> No-op update: không tăng version, không ghi edit_events
    if cleaned_name == speaker.display_name:
        return serialize_speaker(speaker, db, meeting.id)

    # Kiểm tra trùng tên trong cùng meeting (so sánh case-insensitive, trừ chính speaker này)
    other_speakers = (
        db.execute(
            select(Speaker).where(Speaker.meeting_id == meeting.id, Speaker.id != speaker.id)
        )
        .scalars()
        .all()
    )
    for other in other_speakers:
        if other.display_name.strip().lower() == cleaned_name.lower():
            raise APIError(
                code="SPEAKER_NAME_DUPLICATE",
                message="Tên người nói bị trùng với người nói khác trong cuộc họp.",
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

    before_state = {"display_name": speaker.display_name}
    after_state = {"display_name": cleaned_name}

    now = datetime.now(UTC)
    new_version = payload.version + 1

    # Cập nhật nguyên tử có điều kiện theo version (optimistic locking)
    stmt = (
        update(Speaker)
        .where(
            Speaker.id == speaker.id,
            Speaker.meeting_id == meeting.id,
            Speaker.version == payload.version,
        )
        .values(
            display_name=cleaned_name,
            version=new_version,
            updated_at=now,
        )
    )
    res = db.execute(stmt)
    if res.rowcount == 0:
        db.rollback()
        current_speaker = db.execute(
            select(Speaker).where(Speaker.id == speaker.id, Speaker.meeting_id == meeting.id)
        ).scalar_one_or_none()
        curr_ver = current_speaker.version if current_speaker else payload.version
        raise APIError(
            code="VERSION_CONFLICT",
            message="Người nói đã được cập nhật ở nơi khác. Vui lòng tải lại.",
            status_code=status.HTTP_409_CONFLICT,
            details={
                "entity": "speaker",
                "current": {"id": speaker.id, "version": curr_ver},
            },
        )

    record_edit(
        db,
        meeting_id=meeting.id,
        entity_type="speaker",
        entity_id=speaker.id,
        action="update",
        actor_id=current_user.id,
        field="display_name",
        before=before_state,
        after=after_state,
        entity_version_after=new_version,
        request_id=getattr(getattr(request, "state", None), "request_id", None),
        created_at=now,
    )
    db.commit()
    db.refresh(speaker)

    return serialize_speaker(speaker, db, meeting.id)
