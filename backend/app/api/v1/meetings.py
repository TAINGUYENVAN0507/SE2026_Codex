import logging
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
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
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, get_current_user
from app.api.v1.action_items import (
    router as action_items_router,
)
from app.api.v1.action_items import (
    serialize_action_item,
)
from app.api.v1.export import (
    router as export_router,
)
from app.api.v1.jobs import (
    meeting_jobs_router,
)
from app.api.v1.segments import (
    router as segments_router,
)
from app.api.v1.summary import (
    router as summary_router,
)
from app.core.config import get_settings
from app.core.errors import APIError
from app.db.models.edit_event import EditEvent
from app.db.models.job import Job
from app.db.models.meeting import Meeting
from app.db.models.transcript import Segment, Speaker
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.common import ErrorResponse
from app.schemas.edit import EditActorOut, EditEventOut, EditListOut
from app.schemas.job import JobErrorOut, JobOut
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
from app.schemas.transcript import (
    SpeakerPatch,
    TranscriptOut,
    TranscriptSegmentOut,
)
from app.services.audio_validator import probe_audio, validate_extension_and_mime
from app.services.audit import record_edit
from app.services.erasure import erase_meeting
from app.services.idempotency.service import IdempotencyService
from app.services.storage import FileTooLargeError, Storage, get_storage

router = APIRouter(
    prefix="/meetings",
    tags=["Meetings"],
    dependencies=[Depends(get_current_user)],
)

logger = logging.getLogger("backend.api.meetings")

__all__ = ["router", "serialize_action_item"]


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

    clean_ext = validate_extension_and_mime(file.filename or "", file.content_type)
    current_user_id = current_user.id

    idempotency_service = IdempotencyService()
    idem_res = idempotency_service.check_or_start(
        session=db,
        user_id=current_user_id,
        key=idempotency_key.strip(),
        endpoint="/api/v1/meetings",
    )

    if idem_res.is_replayed:
        response.headers["Idempotent-Replayed"] = "true"
        if idem_res.response_code:
            response.status_code = idem_res.response_code
        return MeetingCreateOut.model_validate(idem_res.response_body)

    db.commit()

    meeting_id = str(uuid.uuid4())
    job_id = str(uuid.uuid4())

    try:
        upload_result = storage.save_upload(
            meeting_id=meeting_id,
            extension=clean_ext,
            stream=file.file,
        )
    except FileTooLargeError as exc:
        if idem_res.record_id:
            idempotency_service.fail(session=db, record_id=idem_res.record_id)
            db.commit()
        raise APIError(
            code="FILE_TOO_LARGE",
            message="Dung lượng tệp âm thanh vượt quá giới hạn cho phép.",
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
        ) from exc
    except Exception:
        if idem_res.record_id:
            idempotency_service.fail(session=db, record_id=idem_res.record_id)
            db.commit()
        raise

    audio_file_path = storage.get_audio_path(meeting_id=meeting_id, extension=clean_ext)
    try:
        probe_result = probe_audio(file_path=audio_file_path)
    except APIError:
        storage.delete_meeting_files(meeting_id)
        if idem_res.record_id:
            idempotency_service.fail(session=db, record_id=idem_res.record_id)
            db.commit()
        raise
    except Exception as exc:
        storage.delete_meeting_files(meeting_id)
        if idem_res.record_id:
            idempotency_service.fail(session=db, record_id=idem_res.record_id)
            db.commit()
        raise APIError(
            code="AUDIO_INVALID",
            message="Tệp âm thanh bị lỗi hoặc định dạng không được hỗ trợ.",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        ) from exc

    try:
        settings = get_settings()
        now = datetime.now(UTC)
        retention_until = now + timedelta(days=settings.AUDIO_RETENTION_DAYS)
        meeting_title = (
            title.strip() if title and title.strip() else (file.filename or "Cuộc họp mới")
        )

        meeting = Meeting(
            id=meeting_id,
            owner_id=current_user_id,
            title=meeting_title,
            source=source,
            status="queued",
            duration_sec=probe_result.duration_sec,
            audio_path=upload_result.path,
            audio_sha256=upload_result.sha256,
            num_speakers_hint=num_speakers,
            meeting_date=meeting_date,
            consent_confirmed_at=now,
            retention_until=retention_until,
            version=1,
            created_at=now,
            updated_at=now,
        )
        job = Job(
            id=job_id,
            meeting_id=meeting_id,
            status="queued",
            stage="preprocess",
            progress=0.0,
            stage_status={
                "preprocess": "queued",
                "vad": "queued",
                "asr": "queued",
                "diarize": "queued",
                "merge": "queued",
                "summarize": "queued",
            },
            attempt=1,
            max_attempts=3,
            created_at=now,
        )
        db.add(meeting)
        db.add(job)

        response_data = {
            "meeting": {
                "id": meeting.id,
                "title": meeting.title,
                "source": meeting.source,
                "status": meeting.status,
                "language": "vi",
                "meeting_date": meeting.meeting_date,
                "duration_sec": meeting.duration_sec,
                "num_speakers_hint": meeting.num_speakers_hint,
                "audio": {
                    "available": True,
                    "mime_type": file.content_type or f"audio/{clean_ext}",
                    "size_bytes": upload_result.size_bytes,
                    "retention_until": meeting.retention_until.isoformat()
                    if meeting.retention_until
                    else None,
                },
                "artifacts": {
                    "transcript": "pending",
                    "diarization": "pending",
                    "summary": "pending",
                },
                "warnings": [],
                "latest_job_id": job.id,
                "created_at": meeting.created_at.isoformat(),
                "updated_at": meeting.updated_at.isoformat(),
                "version": meeting.version,
            },
            "job": {
                "id": job.id,
                "meeting_id": job.meeting_id,
                "status": job.status,
                "stage": job.stage,
                "from_stage": job.from_stage,
                "progress": job.progress,
                "stages": job.stage_status or {},
                "attempt": job.attempt,
                "max_attempts": job.max_attempts,
                "next_run_at": None,
                "error": None,
                "created_at": job.created_at.isoformat(),
                "started_at": None,
                "finished_at": None,
            },
        }

        if idem_res.record_id:
            idempotency_service.complete(
                session=db,
                record_id=idem_res.record_id,
                response_code=status.HTTP_201_CREATED,
                response_body=response_data,
            )
        db.commit()
        logger.info(
            "Job %s đã được tạo cho cuộc họp %s",
            job_id,
            meeting_id,
            extra={
                "event": "job_created",
                "job_id": job_id,
                "meeting_id": meeting_id,
                "stage": "preprocess",
                "attempt": 1,
                "status": "queued",
            },
        )
    except Exception:
        db.rollback()
        storage.delete_meeting_files(meeting_id)
        if idem_res.record_id:
            idempotency_service.fail(session=db, record_id=idem_res.record_id)
            db.commit()
        raise

    return MeetingCreateOut.model_validate(response_data)


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

    job_out = None
    if latest_job:
        job_error = (
            JobErrorOut(
                code=latest_job.error_code,
                message=latest_job.error_message or "",
                retryable=latest_job.can_retry,
                stage=latest_job.stage,
            )
            if latest_job.error_code
            else None
        )
        job_out = JobOut(
            id=latest_job.id,
            meeting_id=latest_job.meeting_id,
            status=latest_job.status,  # type: ignore[arg-type]
            stage=latest_job.stage,  # type: ignore[arg-type]
            from_stage=latest_job.from_stage,  # type: ignore[arg-type]
            progress=latest_job.progress,
            stages=latest_job.stage_status or {},
            attempt=latest_job.attempt,
            max_attempts=latest_job.max_attempts,
            next_run_at=latest_job.next_run_at,
            error=job_error,
            created_at=latest_job.created_at,
            started_at=latest_job.started_at,
            finished_at=latest_job.finished_at,
        )

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


AUDIO_MIME_TYPES: dict[str, str] = {
    "mp3": "audio/mpeg",
    "wav": "audio/wav",
    "m4a": "audio/mp4",
    "webm": "audio/webm",
    "ogg": "audio/ogg",
    "flac": "audio/flac",
    "aac": "audio/aac",
}


def stream_file_range(file_path: Path, start: int, length: int, chunk_size: int = 64 * 1024):
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


router.include_router(segments_router)


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


router.include_router(summary_router)


router.include_router(action_items_router)


router.include_router(meeting_jobs_router)


@router.get(
    "/{meeting_id}/edits",
    response_model=EditListOut,
    status_code=status.HTTP_200_OK,
    responses={
        404: {"model": ErrorResponse, "description": "Không tìm thấy cuộc họp"},
    },
    summary="Lấy lịch sử chỉnh sửa audit của cuộc họp",
)
def list_meeting_edits(
    meeting_id: Annotated[str, FastApiPath(description="UUID của cuộc họp")],
    current_user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
    entity_type: Annotated[str | None, Query(description="Lọc theo loại entity")] = None,
    entity_id: Annotated[str | None, Query(description="Lọc theo ID entity")] = None,
    field: Annotated[str | None, Query(description="Lọc theo trường sửa")] = None,
    page: Annotated[int, Query(ge=1, description="Số trang")] = 1,
    page_size: Annotated[int, Query(ge=1, le=100, description="Kích thước trang")] = 10,
    limit: Annotated[int | None, Query(ge=1, le=100, description="Số bản ghi tối đa")] = None,
    offset: Annotated[int | None, Query(ge=0, description="Vị trí bắt đầu")] = None,
) -> EditListOut:
    """Lấy danh sách các sự kiện chỉnh sửa audit của cuộc họp."""
    meeting = db.execute(
        select(Meeting).where(Meeting.id == meeting_id, Meeting.owner_id == current_user.id)
    ).scalar_one_or_none()
    if meeting is None:
        raise APIError(
            code="NOT_FOUND",
            message="Không tìm thấy cuộc họp được yêu cầu.",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    stmt = select(EditEvent).where(EditEvent.meeting_id == meeting.id)

    if entity_type:
        stmt = stmt.where(EditEvent.entity_type == entity_type)
    if entity_id:
        stmt = stmt.where(EditEvent.entity_id == entity_id)
    if field:
        stmt = stmt.where(EditEvent.field == field)

    total_count = db.execute(select(func.count()).select_from(stmt.subquery())).scalar() or 0

    take = limit if limit is not None else page_size
    skip = offset if offset is not None else (page - 1) * page_size

    stmt = stmt.order_by(EditEvent.created_at.desc(), EditEvent.id.desc()).offset(skip).limit(take)
    events = db.execute(stmt).scalars().all()

    actor_ids = {ev.actor_id for ev in events if ev.actor_id}
    users_by_id: dict[str, User] = {}
    if actor_ids:
        users = db.execute(select(User).where(User.id.in_(actor_ids))).scalars().all()
        users_by_id = {u.id: u for u in users}

    items_out = []
    for ev in events:
        actor_name = "Unknown"
        actor_id_val = ev.actor_id or "system"
        if ev.actor_id and ev.actor_id in users_by_id:
            actor_name = users_by_id[ev.actor_id].display_name
        elif ev.actor_id == current_user.id:
            actor_name = current_user.display_name

        items_out.append(
            EditEventOut(
                id=ev.id,
                meeting_id=ev.meeting_id,
                entity_type=ev.entity_type,
                entity_id=ev.entity_id,
                action=ev.action,
                field=ev.field,
                before=ev.before,
                after=ev.after,
                actor=EditActorOut(id=actor_id_val, display_name=actor_name),
                entity_version_after=ev.entity_version_after or 1,
                request_id=ev.request_id,
                created_at=ev.created_at,
            )
        )

    return EditListOut(items=items_out, total=total_count)


router.include_router(export_router)
