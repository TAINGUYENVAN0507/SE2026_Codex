"""Router cho các phân đoạn thoại (Transcript Segments) trong cuộc họp."""

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
from app.schemas.transcript import (
    SegmentPatch,
    TranscriptSegmentOut,
)
from app.services.audit import record_edit

router = APIRouter()


@router.patch(
    "/{meeting_id}/segments/{segment_id}",
    response_model=TranscriptSegmentOut,
    status_code=status.HTTP_200_OK,
    responses={
        404: {"model": ErrorResponse, "description": "Không tìm thấy đoạn thoại"},
        409: {
            "model": ErrorResponse,
            "description": "Xung đột phiên bản version do đã có chỉnh sửa khác",
        },
    },
    summary="Chỉnh sửa nội dung hoặc gán người nói cho đoạn transcript",
)
def patch_meeting_segment(
    meeting_id: Annotated[str, FastApiPath(description="UUID của cuộc họp")],
    segment_id: Annotated[str, FastApiPath(description="UUID của đoạn thoại cần sửa")],
    payload: SegmentPatch,
    current_user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
    request: Request,
) -> TranscriptSegmentOut:
    """Chỉnh sửa đoạn transcript với optimistic locking qua trường version."""
    meeting = db.execute(
        select(Meeting).where(Meeting.id == meeting_id, Meeting.owner_id == current_user.id)
    ).scalar_one_or_none()
    if meeting is None:
        raise APIError(
            code="NOT_FOUND",
            message="Không tìm thấy cuộc họp được yêu cầu.",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    segment = db.execute(
        select(Segment).where(Segment.id == segment_id, Segment.meeting_id == meeting.id)
    ).scalar_one_or_none()
    if segment is None:
        raise APIError(
            code="NOT_FOUND",
            message="Không tìm thấy đoạn thoại được yêu cầu.",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    if payload.version != segment.version:
        raise APIError(
            code="VERSION_CONFLICT",
            message="Đoạn transcript đã được cập nhật ở nơi khác. Vui lòng tải lại.",
            status_code=status.HTTP_409_CONFLICT,
            details={
                "entity": "segment",
                "current": {
                    "id": segment.id,
                    "version": segment.version,
                    "text": segment.text,
                    "speaker_id": segment.speaker_id,
                },
            },
        )

    fields_set = payload.model_fields_set
    new_text = segment.text
    if "text" in fields_set:
        if payload.text is None:
            raise APIError(
                code="TEXT_EMPTY",
                message="Nội dung đoạn thoại không được để trống.",
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        cleaned = payload.text.strip()
        if not cleaned:
            raise APIError(
                code="TEXT_EMPTY",
                message="Nội dung đoạn thoại không được để trống.",
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        if len(cleaned) > 5000:
            raise APIError(
                code="TEXT_TOO_LONG",
                message="Nội dung vượt quá độ dài tối đa cho phép.",
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        new_text = cleaned

    new_speaker_id = segment.speaker_id
    if "speaker_id" in fields_set:
        if payload.speaker_id is not None:
            spk = db.execute(
                select(Speaker).where(
                    Speaker.id == payload.speaker_id,
                    Speaker.meeting_id == meeting.id,
                )
            ).scalar_one_or_none()
            if spk is None:
                raise APIError(
                    code="SPEAKER_NOT_IN_MEETING",
                    message="Người nói không thuộc cuộc họp này.",
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                )
            new_speaker_id = spk.id
        else:
            new_speaker_id = None

    is_edited_now = (new_text != segment.ai_text) or (new_speaker_id != segment.ai_speaker_id)
    flags_list = []
    if segment.flags and isinstance(segment.flags, dict):
        flags_list = segment.flags.get("flags", [])

    # Nếu không có thay đổi giá trị -> trả về 200 và không tăng version
    if new_text == segment.text and new_speaker_id == segment.speaker_id:
        return TranscriptSegmentOut(
            id=segment.id,
            index=segment.idx,
            start_sec=segment.start_sec,
            end_sec=segment.end_sec,
            speaker_id=segment.speaker_id,
            ai_speaker_id=segment.ai_speaker_id,
            text=segment.text,
            ai_text=segment.ai_text,
            is_edited=is_edited_now,
            confidence=segment.confidence,
            flags=flags_list,
            version=segment.version,
            updated_at=segment.updated_at,
        )

    old_text = segment.text
    old_speaker_id = segment.speaker_id
    text_changed = new_text != old_text
    speaker_changed = new_speaker_id != old_speaker_id

    before_state = {
        "text": old_text,
        "speaker_id": old_speaker_id,
    }
    after_state = {
        "text": new_text,
        "speaker_id": new_speaker_id,
    }

    now = datetime.now(UTC)
    new_version = payload.version + 1

    # Cập nhật nguyên tử có điều kiện theo version (optimistic locking)
    stmt = (
        update(Segment)
        .where(
            Segment.id == segment.id,
            Segment.meeting_id == meeting.id,
            Segment.version == payload.version,
        )
        .values(
            text=new_text,
            speaker_id=new_speaker_id,
            version=new_version,
            updated_at=now,
        )
    )
    res = db.execute(stmt)
    if res.rowcount == 0:
        db.rollback()
        current_segment = db.execute(
            select(Segment).where(Segment.id == segment.id, Segment.meeting_id == meeting.id)
        ).scalar_one_or_none()
        curr_ver = current_segment.version if current_segment else payload.version
        curr_text = current_segment.text if current_segment else segment.text
        curr_spk = current_segment.speaker_id if current_segment else segment.speaker_id
        raise APIError(
            code="VERSION_CONFLICT",
            message="Đoạn transcript đã được cập nhật ở nơi khác. Vui lòng tải lại.",
            status_code=status.HTTP_409_CONFLICT,
            details={
                "entity": "segment",
                "current": {
                    "id": segment.id,
                    "version": curr_ver,
                    "text": curr_text,
                    "speaker_id": curr_spk,
                },
            },
        )

    req_id = getattr(getattr(request, "state", None), "request_id", None)

    if text_changed:
        record_edit(
            db,
            meeting_id=meeting.id,
            entity_type="segment",
            entity_id=segment.id,
            action="update",
            actor_id=current_user.id,
            field="text",
            before=before_state,
            after=after_state,
            entity_version_after=new_version,
            request_id=req_id,
            created_at=now,
        )

    if speaker_changed:
        record_edit(
            db,
            meeting_id=meeting.id,
            entity_type="segment",
            entity_id=segment.id,
            action="update",
            actor_id=current_user.id,
            field="speaker_id",
            before=before_state,
            after=after_state,
            entity_version_after=new_version,
            request_id=req_id,
            created_at=now,
        )

    db.commit()
    db.refresh(segment)

    return TranscriptSegmentOut(
        id=segment.id,
        index=segment.idx,
        start_sec=segment.start_sec,
        end_sec=segment.end_sec,
        speaker_id=segment.speaker_id,
        ai_speaker_id=segment.ai_speaker_id,
        text=segment.text,
        ai_text=segment.ai_text,
        is_edited=is_edited_now,
        confidence=segment.confidence,
        flags=flags_list,
        version=segment.version,
        updated_at=segment.updated_at,
    )
