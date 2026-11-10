"""Router cho thông tin bản ghi gỡ băng (Transcript) của cuộc họp."""

from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    status,
)
from fastapi import (
    Path as FastApiPath,
)
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser
from app.core.errors import APIError
from app.db.models.meeting import Meeting
from app.db.models.transcript import Segment, Speaker
from app.db.session import get_db
from app.schemas.common import ErrorResponse
from app.schemas.transcript import (
    SpeakerOut,
    TranscriptOut,
    TranscriptSegmentOut,
)

router = APIRouter()


@router.get(
    "/{meeting_id}/transcript",
    response_model=TranscriptOut,
    status_code=status.HTTP_200_OK,
    responses={
        404: {"model": ErrorResponse, "description": "Không tìm thấy cuộc họp"},
    },
    summary="Lấy transcript của cuộc họp",
)
def get_meeting_transcript(
    meeting_id: Annotated[str, FastApiPath(description="UUID của cuộc họp")],
    current_user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
) -> TranscriptOut:
    """Trả về dữ liệu transcript của cuộc họp từ cơ sở dữ liệu."""
    meeting = db.execute(select(Meeting).where(Meeting.id == meeting_id)).scalar_one_or_none()
    if not meeting or meeting.owner_id != current_user.id:
        raise APIError(
            code="MEETING_NOT_FOUND",
            message="Không tìm thấy cuộc họp được yêu cầu.",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    if meeting.status in ("ready", "partial"):
        speakers = (
            db.execute(
                select(Speaker)
                .where(Speaker.meeting_id == meeting.id)
                .order_by(Speaker.created_at.asc())
            )
            .scalars()
            .all()
        )

        segments = (
            db.execute(
                select(Segment).where(Segment.meeting_id == meeting.id).order_by(Segment.idx.asc())
            )
            .scalars()
            .all()
        )

        if segments:
            speakers_out = [
                SpeakerOut(
                    id=spk.id,
                    meeting_id=spk.meeting_id,
                    label=spk.label,
                    default_name=spk.default_name,
                    display_name=spk.display_name,
                    is_edited=spk.display_name != spk.default_name,
                    color_index=idx % 10,
                    segment_count=0,
                    speaking_time_sec=0.0,
                    version=spk.version,
                )
                for idx, spk in enumerate(speakers)
            ]
            segments_out = [
                TranscriptSegmentOut(
                    id=seg.id,
                    index=seg.idx,
                    start_sec=seg.start_sec,
                    end_sec=seg.end_sec,
                    speaker_id=seg.speaker_id,
                    ai_speaker_id=seg.ai_speaker_id,
                    text=seg.text,
                    ai_text=seg.ai_text,
                    is_edited=seg.text != seg.ai_text or seg.speaker_id != seg.ai_speaker_id,
                    confidence=seg.confidence,
                    flags=list(seg.flags.keys())
                    if isinstance(seg.flags, dict)
                    else (list(seg.flags) if isinstance(seg.flags, list) else []),
                    version=seg.version,
                    updated_at=seg.updated_at,
                )
                for seg in segments
            ]
            return TranscriptOut(
                status="ready",
                diarization_status="ok",
                speakers=speakers_out,
                segments=segments_out,
            )

    status_val = "failed" if meeting.status == "failed" else "pending"
    return TranscriptOut(
        status=status_val,
        diarization_status=status_val,
        speakers=[],
        segments=[],
    )
