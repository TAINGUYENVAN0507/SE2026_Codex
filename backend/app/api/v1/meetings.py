import logging
from datetime import UTC, datetime
from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    Header,
    Query,
    Request,
    Response,
    UploadFile,
    status,
)
from fastapi import Path as FastApiPath
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, get_current_user
from app.api.v1.action_items import router as action_items_router
from app.api.v1.action_items import serialize_action_item
from app.api.v1.audio import router as audio_router
from app.api.v1.edits import router as edits_router
from app.api.v1.export import router as export_router
from app.api.v1.jobs import meeting_jobs_router, serialize_job
from app.api.v1.segments import router as segments_router
from app.api.v1.speakers import router as speakers_router
from app.api.v1.summary import router as summary_router
from app.api.v1.transcript import router as transcript_router
from app.core.errors import APIError
from app.db.models.job import Job
from app.db.models.meeting import Meeting
from app.db.models.transcript import Speaker
from app.db.session import get_db
from app.schemas.common import ErrorResponse
from app.schemas.meeting import (
    MeetingCreateOut,
    MeetingDetailOut,
    MeetingListOut,
    MeetingOut,
    MeetingPatch,
    MeetingSource,
    MeetingStatus,
    SpeakerOut,
)
from app.services.audit import record_edit
from app.services.erasure import erase_meeting
from app.services.meetings.upload import handle_meeting_upload, probe_audio
from app.services.storage import Storage, get_storage

router = APIRouter(
    prefix="/meetings",
    tags=["Meetings"],
    dependencies=[Depends(get_current_user)],
)

logger = logging.getLogger("backend.api.meetings")

__all__ = ["probe_audio", "router", "serialize_action_item"]


def serialize_meeting_summary(meeting: Meeting, db: Session) -> MeetingOut:
    """Chuyển đổi một thực thể Meeting trong DB sang schema MeetingOut."""
    latest_job = (
        db.execute(select(Job).where(Job.meeting_id == meeting.id).order_by(Job.created_at.desc()))
        .scalars()
        .first()
    )

    clean_ext = (
        meeting.audio_path.rsplit(".", 1)[-1].lower()
        if meeting.audio_path and "." in meeting.audio_path
        else "wav"
    )
    mime_type = "audio/mpeg" if clean_ext == "mp3" else f"audio/{clean_ext}"

    transcript_status = "pending"
    diarization_status = "pending"
    summary_status = "pending"
    if meeting.status in ("ready", "partial"):
        transcript_status = "ready"
        diarization_status = "ok"
        summary_status = "ready"
    elif meeting.status == "failed":
        transcript_status = "failed"
        diarization_status = "failed"
        summary_status = "failed"

    return MeetingOut(
        id=meeting.id,
        title=meeting.title,
        source=meeting.source,  # type: ignore[arg-type]
        status=meeting.status,  # type: ignore[arg-type]
        language="vi",
        meeting_date=meeting.meeting_date,
        duration_sec=meeting.duration_sec,
        num_speakers_hint=meeting.num_speakers_hint,
        audio={
            "available": meeting.audio_path is not None,
            "mime_type": mime_type,
            "size_bytes": 0,
            "retention_until": meeting.retention_until,
        },
        artifacts={
            "transcript": transcript_status,
            "diarization": diarization_status,
            "summary": summary_status,
        },
        warnings=[],
        latest_job_id=latest_job.id if latest_job else None,
        created_at=meeting.created_at,
        updated_at=meeting.updated_at,
        version=meeting.version,
    )


@router.get(
    "",
    response_model=MeetingListOut,
    status_code=status.HTTP_200_OK,
    summary="Lấy danh sách cuộc họp có phân trang và lọc",
)
def list_meetings(
    current_user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
    page: Annotated[int, Query(ge=1, description="Số thứ tự trang (bắt đầu từ 1)")] = 1,
    page_size: Annotated[int, Query(ge=1, le=100, description="Số lượng mục trên mỗi trang")] = 10,
    status_filter: Annotated[
        MeetingStatus | None, Query(alias="status", description="Lọc theo trạng thái")
    ] = None,
    q: Annotated[str | None, Query(description="Tìm kiếm theo tiêu đề cuộc họp")] = None,
) -> MeetingListOut:
    """Lấy danh sách cuộc họp có phân trang và lọc theo trạng thái."""
    base_query = select(Meeting).where(Meeting.owner_id == current_user.id)
    if status_filter is not None:
        base_query = base_query.where(Meeting.status == status_filter)
    if q and q.strip():
        base_query = base_query.where(Meeting.title.ilike(f"%{q.strip()}%"))

    total = db.scalar(select(func.count()).select_from(base_query.subquery())) or 0
    offset = (page - 1) * page_size
    meetings = (
        db.execute(base_query.order_by(Meeting.created_at.desc()).offset(offset).limit(page_size))
        .scalars()
        .all()
    )

    items = [serialize_meeting_summary(m, db) for m in meetings]
    return MeetingListOut(
        items=items,
        page=page,
        page_size=page_size,
        total=total,
    )


@router.post(
    "",
    response_model=MeetingCreateOut,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"model": ErrorResponse, "description": "Thiếu header Idempotency-Key"},
        422: {
            "model": ErrorResponse,
            "description": "Chưa xác nhận consent hoặc dữ liệu không hợp lệ",
        },
    },
    summary="Tải lên tệp âm thanh và tạo cuộc họp mới",
)
def create_meeting(
    file: Annotated[UploadFile, File(description="Tệp âm thanh cuộc họp")],
    response: Response,
    current_user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
    storage: Annotated[Storage, Depends(get_storage)],
    title: Annotated[str | None, Form(description="Tiêu đề cuộc họp tùy chọn")] = None,
    source: Annotated[
        MeetingSource, Form(description="Nguồn âm thanh: upload hoặc recording")
    ] = "upload",
    num_speakers: Annotated[
        int | None, Form(ge=1, le=10, description="Gợi ý số lượng người nói (1-10)")
    ] = None,
    meeting_date: Annotated[
        str | None, Form(description="Ngày diễn ra cuộc họp YYYY-MM-DD")
    ] = None,
    consent_confirmed: Annotated[
        bool, Form(description="Xác nhận người tham gia đã đồng ý ghi âm")
    ] = False,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> MeetingCreateOut:
    """Tải lên file âm thanh và khởi tạo cuộc họp kèm job xử lý."""
    if not idempotency_key or not idempotency_key.strip():
        raise APIError(
            code="IDEMPOTENCY_KEY_REQUIRED",
            message="Header Idempotency-Key là bắt buộc khi tạo cuộc họp.",
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    if not consent_confirmed:
        raise APIError(
            code="CONSENT_REQUIRED",
            message="Cần xác nhận đồng ý xử lý dữ liệu trước khi tải lên.",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    result, is_replayed, replay_code = handle_meeting_upload(
        db=db,
        storage=storage,
        file=file,
        user_id=current_user.id,
        idempotency_key=idempotency_key.strip(),
        title=title,
        source=source,
        num_speakers=num_speakers,
        meeting_date=meeting_date,
    )

    if is_replayed:
        response.headers["Idempotent-Replayed"] = "true"
        if replay_code:
            response.status_code = replay_code

    return result


def serialize_meeting_detail(meeting: Meeting, db: Session) -> MeetingDetailOut:
    """Tạo đối tượng MeetingDetailOut từ model Meeting."""
    latest_job = (
        db.execute(select(Job).where(Job.meeting_id == meeting.id).order_by(Job.created_at.desc()))
        .scalars()
        .first()
    )

    speakers = (
        db.execute(
            select(Speaker)
            .where(Speaker.meeting_id == meeting.id)
            .order_by(Speaker.created_at.asc())
        )
        .scalars()
        .all()
    )

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

    job_out = serialize_job(latest_job) if latest_job else None

    meeting_summary = serialize_meeting_summary(meeting, db)
    return MeetingDetailOut(
        **meeting_summary.model_dump(),
        latest_job=job_out,
        speakers=speakers_out,
    )


@router.get(
    "/{meeting_id}",
    response_model=MeetingDetailOut,
    status_code=status.HTTP_200_OK,
    responses={
        404: {"model": ErrorResponse, "description": "Không tìm thấy cuộc họp"},
    },
    summary="Lấy chi tiết cuộc họp",
)
def get_meeting(
    meeting_id: Annotated[str, FastApiPath(description="UUID của cuộc họp cần lấy thông tin")],
    current_user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
) -> MeetingDetailOut:
    """Trả về chi tiết cuộc họp từ cơ sở dữ liệu."""
    meeting = db.execute(select(Meeting).where(Meeting.id == meeting_id)).scalar_one_or_none()
    if not meeting or meeting.owner_id != current_user.id:
        raise APIError(
            code="MEETING_NOT_FOUND",
            message="Không tìm thấy cuộc họp được yêu cầu.",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    return serialize_meeting_detail(meeting, db)


@router.patch(
    "/{meeting_id}",
    response_model=MeetingDetailOut,
    status_code=status.HTTP_200_OK,
    responses={
        404: {"model": ErrorResponse, "description": "Không tìm thấy cuộc họp"},
        409: {
            "model": ErrorResponse,
            "description": "Xung đột phiên bản version của cuộc họp",
        },
        422: {"model": ErrorResponse, "description": "Dữ liệu không hợp lệ"},
    },
    summary="Chỉnh sửa thông tin cuộc họp (tiêu đề)",
)
def patch_meeting(
    meeting_id: Annotated[str, FastApiPath(description="UUID của cuộc họp")],
    payload: MeetingPatch,
    current_user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
    request: Request,
) -> MeetingDetailOut:
    """Chỉnh sửa tiêu đề cuộc họp có kiểm tra optimistic locking nguyên tử."""
    meeting = db.execute(
        select(Meeting).where(Meeting.id == meeting_id, Meeting.owner_id == current_user.id)
    ).scalar_one_or_none()
    if meeting is None:
        raise APIError(
            code="MEETING_NOT_FOUND",
            message="Không tìm thấy cuộc họp được yêu cầu.",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    if payload.version != meeting.version:
        raise APIError(
            code="VERSION_CONFLICT",
            message="Cuộc họp đã được cập nhật ở nơi khác. Vui lòng tải lại.",
            status_code=status.HTTP_409_CONFLICT,
            details={
                "entity": "meeting",
                "current": {"id": meeting.id, "version": meeting.version},
            },
        )

    fields_set = payload.model_fields_set
    new_title = meeting.title
    if "title" in fields_set:
        if payload.title is None:
            raise APIError(
                code="VALIDATION_ERROR",
                message="Tiêu đề cuộc họp không được để trống.",
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        cleaned_title = payload.title.strip()
        if not cleaned_title:
            raise APIError(
                code="VALIDATION_ERROR",
                message="Tiêu đề cuộc họp không được để trống.",
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        if len(cleaned_title) > 200:
            raise APIError(
                code="VALIDATION_ERROR",
                message="Tiêu đề cuộc họp không được vượt quá 200 ký tự.",
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        new_title = cleaned_title

    # Kiểm tra no-op (không đổi giá trị)
    if new_title == meeting.title:
        return serialize_meeting_detail(meeting, db)

    old_title = meeting.title
    now = datetime.now(UTC)
    new_version = payload.version + 1

    stmt = (
        update(Meeting)
        .where(
            Meeting.id == meeting.id,
            Meeting.owner_id == current_user.id,
            Meeting.version == payload.version,
        )
        .values(
            title=new_title,
            version=new_version,
            updated_at=now,
        )
    )
    res = db.execute(stmt)
    if res.rowcount == 0:
        db.rollback()
        curr_meeting = db.execute(
            select(Meeting).where(Meeting.id == meeting.id, Meeting.owner_id == current_user.id)
        ).scalar_one_or_none()
        curr_ver = curr_meeting.version if curr_meeting else payload.version
        raise APIError(
            code="VERSION_CONFLICT",
            message="Cuộc họp đã được cập nhật ở nơi khác. Vui lòng tải lại.",
            status_code=status.HTTP_409_CONFLICT,
            details={
                "entity": "meeting",
                "current": {"id": meeting.id, "version": curr_ver},
            },
        )

    record_edit(
        db,
        meeting_id=meeting.id,
        entity_type="meeting",
        entity_id=meeting.id,
        action="update",
        actor_id=current_user.id,
        field="title",
        before={"title": old_title},
        after={"title": new_title},
        entity_version_after=new_version,
        request_id=getattr(getattr(request, "state", None), "request_id", None),
        created_at=now,
    )
    db.commit()
    db.refresh(meeting)
    return serialize_meeting_detail(meeting, db)


@router.delete(
    "/{meeting_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        204: {"description": "Cuộc họp đã được xóa thành công"},
        404: {"model": ErrorResponse, "description": "Không tìm thấy cuộc họp"},
    },
    summary="Xóa cuộc họp",
)
def delete_meeting(
    meeting_id: Annotated[str, FastApiPath(description="UUID của cuộc họp cần xóa")],
    current_user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
    storage: Annotated[Storage, Depends(get_storage)],
) -> Response:
    """Xóa cuộc họp cùng file audio, artifacts và toàn bộ dữ liệu liên quan."""
    erase_meeting(
        db=db,
        storage=storage,
        meeting_id=meeting_id,
        current_user_id=current_user.id,
    )
    logger.info("Đã xóa cuộc họp: meeting_id=%s", meeting_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


router.include_router(audio_router)
router.include_router(transcript_router)
router.include_router(segments_router)
router.include_router(speakers_router)
router.include_router(summary_router)
router.include_router(action_items_router)
router.include_router(meeting_jobs_router)
router.include_router(edits_router)
router.include_router(export_router)
