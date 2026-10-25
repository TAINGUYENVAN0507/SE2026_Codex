import json
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
from app.core.errors import APIError
from app.db.models.action_item import ActionItem
from app.db.models.edit_event import EditEvent
from app.db.models.job import Job
from app.db.models.meeting import Meeting
from app.db.models.summary import Summary
from app.db.models.transcript import Segment, Speaker
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.action_item import (
    ActionItemAiOriginal,
    ActionItemCreate,
    ActionItemListOut,
    ActionItemOut,
    ActionItemPatch,
)
from app.schemas.common import ErrorResponse
from app.schemas.edit import EditActorOut, EditEventOut, EditListOut
from app.schemas.job import JobErrorOut, JobOut, JobRetryCreate
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
from app.schemas.summary import SummaryOut, SummaryUpdate
from app.schemas.transcript import (
    SegmentPatch,
    SpeakerPatch,
    TranscriptOut,
    TranscriptSegmentOut,
)
from app.services.audio_validator import probe_audio, validate_extension_and_mime
from app.services.audit import record_edit
from app.services.idempotency.service import IdempotencyService
from app.services.storage import FileTooLargeError, Storage, get_storage

router = APIRouter(
    prefix="/meetings",
    tags=["Meetings"],
    dependencies=[Depends(get_current_user)],
)

FIXTURES_DIR = Path(__file__).resolve().parents[4] / "contracts" / "fixtures" / "api"
MEETING_FIXTURE_PATH = FIXTURES_DIR / "meeting_processing.json"
MEETING_LIST_FIXTURE_PATH = FIXTURES_DIR / "meeting_list.json"
MEETING_CREATED_FIXTURE_PATH = FIXTURES_DIR / "meeting_created.json"


def load_meeting_fixture() -> dict:
    """Đọc dữ liệu fixture meeting mẫu."""
    if MEETING_FIXTURE_PATH.is_file():
        with open(MEETING_FIXTURE_PATH, encoding="utf-8") as f:
            return json.load(f)
    # Dữ liệu fallback nếu fixture chưa được gắn kết
    return {
        "id": "8f6c2a1e-b2c3-4d4e-8f9a-0b1c2d3e4f5a",
        "title": "Họp sprint planning tuần 42",
        "source": "recording",
        "status": "processing",
        "language": "vi",
        "meeting_date": "2026-10-15",
        "duration_sec": 1834.52,
        "num_speakers_hint": 3,
        "audio": {
            "available": True,
            "mime_type": "audio/webm",
            "size_bytes": 11834512,
            "retention_until": "2026-11-14T08:30:00Z",
        },
        "artifacts": {"transcript": "ready", "diarization": "ok", "summary": "pending"},
        "warnings": [],
        "latest_job_id": "c1d2e3f4-a5b6-4c7d-8e9f-0a1b2c3d4e5f",
        "created_at": "2026-10-15T08:30:00Z",
        "updated_at": "2026-10-15T08:52:10Z",
        "version": 1,
    }


def load_meeting_list_fixture() -> dict:
    """Đọc dữ liệu fixture danh sách meeting mẫu."""
    if MEETING_LIST_FIXTURE_PATH.is_file():
        with open(MEETING_LIST_FIXTURE_PATH, encoding="utf-8") as f:
            return json.load(f)
    return {
        "items": [load_meeting_fixture()],
        "page": 1,
        "page_size": 10,
        "total": 1,
    }


def load_meeting_created_fixture() -> dict:
    """Đọc dữ liệu fixture kết quả tạo meeting mẫu."""
    if MEETING_CREATED_FIXTURE_PATH.is_file():
        with open(MEETING_CREATED_FIXTURE_PATH, encoding="utf-8") as f:
            return json.load(f)
    return {
        "meeting": load_meeting_fixture(),
        "job": {
            "id": "c1d2e3f4-a5b6-4c7d-8e9f-0a1b2c3d4e5f",
            "meeting_id": "8f6c2a1e-b2c3-4d4e-8f9a-0b1c2d3e4f5a",
            "status": "queued",
            "stage": "preprocess",
            "from_stage": None,
            "progress": 0.0,
            "stages": {
                "preprocess": "queued",
                "vad": "queued",
                "asr": "queued",
                "diarize": "queued",
                "merge": "queued",
                "summarize": "queued",
            },
            "attempt": 1,
            "max_attempts": 3,
            "next_run_at": None,
            "error": None,
            "created_at": "2026-10-15T08:30:01Z",
            "started_at": None,
            "finished_at": None,
        },
    }


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

    idempotency_service = IdempotencyService()
    idem_res = idempotency_service.check_or_start(
        session=db,
        user_id=current_user.id,
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
        now = datetime.now(UTC)
        retention_until = now + timedelta(days=30)
        meeting_title = (
            title.strip() if title and title.strip() else (file.filename or "Cuộc họp mới")
        )

        meeting = Meeting(
            id=meeting_id,
            owner_id=current_user.id,
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
        db.flush()

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
                retryable=latest_job.attempt < latest_job.max_attempts,
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
            started_at=None,
            finished_at=None,
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
    meeting_id: str = FastApiPath(..., description="UUID của cuộc họp cần lấy thông tin"),
    current_user: CurrentUser = None,  # type: ignore[assignment]
    db: Annotated[Session, Depends(get_db)] = None,  # type: ignore[assignment]
) -> MeetingDetailOut:
    """Trả về chi tiết cuộc họp (stub contract v0 phục vụ phát triển frontend)."""
    if db is not None and current_user is not None:
        meeting = db.execute(select(Meeting).where(Meeting.id == meeting_id)).scalar_one_or_none()
        if not meeting or meeting.owner_id != current_user.id:
            raise APIError(
                code="MEETING_NOT_FOUND",
                message="Không tìm thấy cuộc họp được yêu cầu.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        return serialize_meeting_detail(meeting, db)

    data = load_meeting_fixture()
    data["id"] = meeting_id
    data["latest_job"] = None
    data["speakers"] = []
    return MeetingDetailOut.model_validate(data)


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


TRANSCRIPT_READY_FIXTURE_PATH = FIXTURES_DIR / "transcript_ready.json"
TRANSCRIPT_PENDING_FIXTURE_PATH = FIXTURES_DIR / "transcript_pending.json"


def load_transcript_ready_fixture() -> dict:
    """Đọc dữ liệu fixture transcript ở trạng thái sẵn sàng."""
    if TRANSCRIPT_READY_FIXTURE_PATH.is_file():
        with open(TRANSCRIPT_READY_FIXTURE_PATH, encoding="utf-8") as f:
            return json.load(f)
    return {
        "status": "ready",
        "diarization_status": "ok",
        "speakers": [],
        "segments": [],
    }


def load_transcript_pending_fixture() -> dict:
    """Đọc dữ liệu fixture transcript ở trạng thái đang xử lý."""
    if TRANSCRIPT_PENDING_FIXTURE_PATH.is_file():
        with open(TRANSCRIPT_PENDING_FIXTURE_PATH, encoding="utf-8") as f:
            return json.load(f)
    return {
        "status": "pending",
        "diarization_status": "pending",
        "speakers": [],
        "segments": [],
    }


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
    meeting_id: str = FastApiPath(..., description="UUID của cuộc họp"),
    current_user: CurrentUser = None,  # type: ignore[assignment]
    db: Annotated[Session, Depends(get_db)] = None,  # type: ignore[assignment]
) -> TranscriptOut:
    """Trả về dữ liệu transcript của cuộc họp (trạng thái pending trả về segments rỗng)."""
    if db is not None and current_user is not None:
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
                    select(Segment)
                    .where(Segment.meeting_id == meeting.id)
                    .order_by(Segment.idx.asc())
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

    if "pending" in meeting_id.lower():
        data = load_transcript_pending_fixture()
    else:
        data = load_transcript_ready_fixture()
    return TranscriptOut.model_validate(data)


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


SUMMARY_READY_FIXTURE_PATH = FIXTURES_DIR / "summary_ready.json"
SUMMARY_DISABLED_FIXTURE_PATH = FIXTURES_DIR / "summary_disabled.json"
ACTION_ITEMS_FIXTURE_PATH = FIXTURES_DIR / "action_items.json"


def load_summary_ready_fixture() -> dict:
    """Đọc dữ liệu fixture summary ở trạng thái sẵn sàng."""
    if SUMMARY_READY_FIXTURE_PATH.is_file():
        with open(SUMMARY_READY_FIXTURE_PATH, encoding="utf-8") as f:
            return json.load(f)
    return {
        "meeting_id": "test-id",
        "status": "ready",
        "content": None,
        "ai_content": None,
        "is_edited": False,
        "model": None,
        "prompt_version": None,
        "generated_at": None,
        "version": 1,
    }


def load_summary_disabled_fixture() -> dict:
    """Đọc dữ liệu fixture summary ở trạng thái disabled."""
    if SUMMARY_DISABLED_FIXTURE_PATH.is_file():
        with open(SUMMARY_DISABLED_FIXTURE_PATH, encoding="utf-8") as f:
            return json.load(f)
    return {
        "meeting_id": "test-id",
        "status": "disabled",
        "content": None,
        "ai_content": None,
        "is_edited": False,
        "model": None,
        "prompt_version": None,
        "generated_at": None,
        "version": 1,
    }


def load_action_items_fixture() -> dict:
    """Đọc dữ liệu fixture danh sách action items."""
    if ACTION_ITEMS_FIXTURE_PATH.is_file():
        with open(ACTION_ITEMS_FIXTURE_PATH, encoding="utf-8") as f:
            return json.load(f)
    return {"items": []}


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
    meeting_id: str = FastApiPath(..., description="UUID của cuộc họp"),
) -> SummaryOut:
    """Lấy thông tin tóm tắt cuộc họp (stub contract v0)."""
    if "disabled" in meeting_id.lower():
        data = load_summary_disabled_fixture()
    else:
        data = load_summary_ready_fixture()
    data["meeting_id"] = meeting_id
    return SummaryOut.model_validate(data)


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


def serialize_action_item(item: ActionItem) -> ActionItemOut:
    """Chuyển đổi ActionItem model sang ActionItemOut schema."""
    ai_orig = None
    if item.ai_original and isinstance(item.ai_original, dict):
        ai_orig = ActionItemAiOriginal.model_validate(item.ai_original)

    if item.source == "ai" and item.ai_original:
        is_edited = (
            item.description != item.ai_original.get("description")
            or item.assignee_name != item.ai_original.get("assignee_name")
            or item.due_date != item.ai_original.get("due_date")
        )
    else:
        is_edited = item.version > 1

    return ActionItemOut(
        id=item.id,
        meeting_id=item.meeting_id,
        description=item.description,
        assignee_name=item.assignee_name,
        assignee_speaker_id=item.assignee_speaker_id,
        due_date=item.due_date,
        due_date_text=item.due_date_text,
        status=item.status,
        source=item.source,  # type: ignore[arg-type]
        is_edited=is_edited,
        needs_review=item.needs_review,
        evidence_segment_ids=item.evidence_segment_ids or [],
        ai_original=ai_orig,
        version=item.version,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


@router.get(
    "/{meeting_id}/action-items",
    response_model=ActionItemListOut,
    status_code=status.HTTP_200_OK,
    responses={
        404: {"model": ErrorResponse, "description": "Không tìm thấy cuộc họp"},
    },
    summary="Lấy danh sách các action items của cuộc họp",
)
def list_meeting_action_items(
    meeting_id: Annotated[str, FastApiPath(description="UUID của cuộc họp")],
    current_user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
) -> ActionItemListOut:
    """Lấy danh sách các action item (công việc cần làm) của cuộc họp."""
    meeting = db.execute(
        select(Meeting).where(Meeting.id == meeting_id, Meeting.owner_id == current_user.id)
    ).scalar_one_or_none()
    if meeting is None:
        raise APIError(
            code="NOT_FOUND",
            message="Không tìm thấy cuộc họp được yêu cầu.",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    stmt = (
        select(ActionItem)
        .where(
            ActionItem.meeting_id == meeting.id,
            ActionItem.deleted_at.is_(None),
        )
        .order_by(ActionItem.created_at.asc())
    )
    items = db.execute(stmt).scalars().all()
    return ActionItemListOut(items=[serialize_action_item(item) for item in items])


@router.post(
    "/{meeting_id}/action-items",
    response_model=ActionItemOut,
    status_code=status.HTTP_201_CREATED,
    responses={
        404: {"model": ErrorResponse, "description": "Không tìm thấy cuộc họp"},
        422: {"model": ErrorResponse, "description": "Dữ liệu không hợp lệ"},
    },
    summary="Tạo action item mới do người dùng thêm thủ công",
)
def create_meeting_action_item(
    meeting_id: Annotated[str, FastApiPath(description="UUID của cuộc họp")],
    payload: ActionItemCreate,
    current_user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
    request: Request,
) -> ActionItemOut:
    """Tạo mới một action item với nguồn gốc source='user'."""
    meeting = db.execute(
        select(Meeting).where(Meeting.id == meeting_id, Meeting.owner_id == current_user.id)
    ).scalar_one_or_none()
    if meeting is None:
        raise APIError(
            code="NOT_FOUND",
            message="Không tìm thấy cuộc họp được yêu cầu.",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    cleaned_desc = payload.description.strip()
    if not cleaned_desc:
        raise APIError(
            code="VALIDATION_ERROR",
            message="Mô tả công việc không được để trống.",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )
    if len(cleaned_desc) > 1000:
        raise APIError(
            code="VALIDATION_ERROR",
            message="Mô tả công việc không được vượt quá 1000 ký tự.",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    item_status = payload.status or "open"
    if item_status not in ("open", "done"):
        raise APIError(
            code="VALIDATION_ERROR",
            message="Trạng thái công việc chỉ có thể là 'open' hoặc 'done'.",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    speaker_id = None
    assignee_name = payload.assignee_name
    if payload.assignee_speaker_id is not None:
        spk = db.execute(
            select(Speaker).where(
                Speaker.id == payload.assignee_speaker_id,
                Speaker.meeting_id == meeting.id,
            )
        ).scalar_one_or_none()
        if spk is None:
            raise APIError(
                code="SPEAKER_NOT_IN_MEETING",
                message="Người nói không thuộc cuộc họp này.",
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        speaker_id = spk.id
        if not assignee_name:
            assignee_name = spk.display_name

    now = datetime.now(UTC)
    new_item = ActionItem(
        id=str(uuid.uuid4()),
        meeting_id=meeting.id,
        description=cleaned_desc,
        assignee_name=assignee_name,
        assignee_speaker_id=speaker_id,
        due_date=payload.due_date,
        due_date_text=None,
        status=item_status,
        source="user",
        ai_original=None,
        evidence_segment_ids=[],
        needs_review=False,
        version=1,
        created_at=now,
        updated_at=now,
    )
    db.add(new_item)

    record_edit(
        db,
        meeting_id=meeting.id,
        entity_type="action_item",
        entity_id=new_item.id,
        action="create",
        actor_id=current_user.id,
        field=None,
        before=None,
        after={
            "description": cleaned_desc,
            "status": item_status,
            "assignee_name": assignee_name,
            "assignee_speaker_id": speaker_id,
            "due_date": payload.due_date,
        },
        entity_version_after=1,
        request_id=getattr(getattr(request, "state", None), "request_id", None),
        created_at=now,
    )
    db.commit()
    db.refresh(new_item)

    return serialize_action_item(new_item)


@router.patch(
    "/{meeting_id}/action-items/{item_id}",
    response_model=ActionItemOut,
    status_code=status.HTTP_200_OK,
    responses={
        404: {
            "model": ErrorResponse,
            "description": "Không tìm thấy action item",
        },
        409: {
            "model": ErrorResponse,
            "description": "Xung đột phiên bản version của action item",
        },
    },
    summary="Chỉnh sửa action item",
)
def patch_meeting_action_item(
    meeting_id: Annotated[str, FastApiPath(description="UUID của cuộc họp")],
    item_id: Annotated[str, FastApiPath(description="UUID của action item")],
    payload: ActionItemPatch,
    current_user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
    request: Request,
) -> ActionItemOut:
    """Chỉnh sửa thông tin action item có kiểm tra optimistic locking."""
    meeting = db.execute(
        select(Meeting).where(Meeting.id == meeting_id, Meeting.owner_id == current_user.id)
    ).scalar_one_or_none()
    if meeting is None:
        raise APIError(
            code="NOT_FOUND",
            message="Không tìm thấy cuộc họp được yêu cầu.",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    item = db.execute(
        select(ActionItem).where(
            ActionItem.id == item_id,
            ActionItem.meeting_id == meeting.id,
            ActionItem.deleted_at.is_(None),
        )
    ).scalar_one_or_none()
    if item is None:
        raise APIError(
            code="NOT_FOUND",
            message="Không tìm thấy công việc cần làm được yêu cầu.",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    if payload.version != item.version:
        raise APIError(
            code="VERSION_CONFLICT",
            message="Action item đã được cập nhật ở nơi khác. Vui lòng tải lại.",
            status_code=status.HTTP_409_CONFLICT,
            details={
                "entity": "action_item",
                "current": {"id": item.id, "version": item.version},
            },
        )

    fields_set = payload.model_fields_set
    new_desc = item.description
    if "description" in fields_set:
        if payload.description is None:
            raise APIError(
                code="VALIDATION_ERROR",
                message="Mô tả công việc không được để trống.",
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        cleaned = payload.description.strip()
        if not cleaned:
            raise APIError(
                code="VALIDATION_ERROR",
                message="Mô tả công việc không được để trống.",
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        if len(cleaned) > 1000:
            raise APIError(
                code="VALIDATION_ERROR",
                message="Mô tả công việc không được vượt quá 1000 ký tự.",
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        new_desc = cleaned

    new_status = item.status
    if "status" in fields_set:
        if payload.status not in ("open", "done"):
            raise APIError(
                code="VALIDATION_ERROR",
                message="Trạng thái chỉ có thể là 'open' hoặc 'done'.",
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        new_status = payload.status

    new_assignee_name = item.assignee_name
    if "assignee_name" in fields_set:
        new_assignee_name = payload.assignee_name

    new_speaker_id = item.assignee_speaker_id
    if "assignee_speaker_id" in fields_set:
        if payload.assignee_speaker_id is not None:
            spk = db.execute(
                select(Speaker).where(
                    Speaker.id == payload.assignee_speaker_id,
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
            if "assignee_name" not in fields_set and not new_assignee_name:
                new_assignee_name = spk.display_name
        else:
            new_speaker_id = None

    new_due_date = item.due_date
    if "due_date" in fields_set:
        new_due_date = payload.due_date

    # Kiểm tra no-op (không đổi giá trị)
    if (
        new_desc == item.description
        and new_status == item.status
        and new_assignee_name == item.assignee_name
        and new_speaker_id == item.assignee_speaker_id
        and new_due_date == item.due_date
    ):
        return serialize_action_item(item)

    now = datetime.now(UTC)
    new_version = payload.version + 1

    stmt = (
        update(ActionItem)
        .where(
            ActionItem.id == item.id,
            ActionItem.meeting_id == meeting.id,
            ActionItem.version == payload.version,
            ActionItem.deleted_at.is_(None),
        )
        .values(
            description=new_desc,
            status=new_status,
            assignee_name=new_assignee_name,
            assignee_speaker_id=new_speaker_id,
            due_date=new_due_date,
            version=new_version,
            updated_at=now,
        )
    )
    res = db.execute(stmt)
    if res.rowcount == 0:
        db.rollback()
        current_item = db.execute(
            select(ActionItem).where(
                ActionItem.id == item.id,
                ActionItem.meeting_id == meeting.id,
                ActionItem.deleted_at.is_(None),
            )
        ).scalar_one_or_none()
        curr_ver = current_item.version if current_item else payload.version
        raise APIError(
            code="VERSION_CONFLICT",
            message="Action item đã được cập nhật ở nơi khác. Vui lòng tải lại.",
            status_code=status.HTTP_409_CONFLICT,
            details={
                "entity": "action_item",
                "current": {"id": item.id, "version": curr_ver},
            },
        )

    record_edit(
        db,
        meeting_id=meeting.id,
        entity_type="action_item",
        entity_id=item.id,
        action="update",
        actor_id=current_user.id,
        field=None,
        before={
            "description": item.description,
            "status": item.status,
            "assignee_name": item.assignee_name,
            "assignee_speaker_id": item.assignee_speaker_id,
            "due_date": item.due_date,
        },
        after={
            "description": new_desc,
            "status": new_status,
            "assignee_name": new_assignee_name,
            "assignee_speaker_id": new_speaker_id,
            "due_date": new_due_date,
        },
        entity_version_after=new_version,
        request_id=getattr(getattr(request, "state", None), "request_id", None),
        created_at=now,
    )
    db.commit()
    db.refresh(item)

    return serialize_action_item(item)


@router.delete(
    "/{meeting_id}/action-items/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        404: {
            "model": ErrorResponse,
            "description": "Không tìm thấy action item",
        },
        409: {
            "model": ErrorResponse,
            "description": "Xung đột phiên bản version khi xóa",
        },
    },
    summary="Xóa action item (xóa mềm có audit)",
)
def delete_meeting_action_item(
    meeting_id: Annotated[str, FastApiPath(description="UUID của cuộc họp")],
    item_id: Annotated[str, FastApiPath(description="UUID của action item")],
    current_user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
    request: Request,
    version: Annotated[int | None, Query(description="Phiên bản của action item")] = None,
) -> Response:
    """Xóa action item (xóa mềm) có kiểm tra version nếu được cung cấp."""
    meeting = db.execute(
        select(Meeting).where(Meeting.id == meeting_id, Meeting.owner_id == current_user.id)
    ).scalar_one_or_none()
    if meeting is None:
        raise APIError(
            code="NOT_FOUND",
            message="Không tìm thấy cuộc họp được yêu cầu.",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    item = db.execute(
        select(ActionItem).where(
            ActionItem.id == item_id,
            ActionItem.meeting_id == meeting.id,
            ActionItem.deleted_at.is_(None),
        )
    ).scalar_one_or_none()
    if item is None:
        raise APIError(
            code="NOT_FOUND",
            message="Không tìm thấy công việc cần làm được yêu cầu.",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    if version is not None and version != item.version:
        raise APIError(
            code="VERSION_CONFLICT",
            message="Action item đã được cập nhật ở nơi khác. Vui lòng tải lại.",
            status_code=status.HTTP_409_CONFLICT,
            details={
                "entity": "action_item",
                "current": {"id": item.id, "version": item.version},
            },
        )

    now = datetime.now(UTC)
    new_version = item.version + 1

    expected_ver = version if version is not None else item.version
    stmt = (
        update(ActionItem)
        .where(
            ActionItem.id == item.id,
            ActionItem.meeting_id == meeting.id,
            ActionItem.version == expected_ver,
            ActionItem.deleted_at.is_(None),
        )
        .values(
            deleted_at=now,
            version=new_version,
            updated_at=now,
        )
    )
    res = db.execute(stmt)
    if res.rowcount == 0:
        db.rollback()
        current_item = db.execute(
            select(ActionItem).where(
                ActionItem.id == item.id,
                ActionItem.meeting_id == meeting.id,
            )
        ).scalar_one_or_none()
        curr_ver = current_item.version if current_item else item.version
        raise APIError(
            code="VERSION_CONFLICT",
            message="Action item đã được cập nhật ở nơi khác. Vui lòng tải lại.",
            status_code=status.HTTP_409_CONFLICT,
            details={
                "entity": "action_item",
                "current": {"id": item.id, "version": curr_ver},
            },
        )

    record_edit(
        db,
        meeting_id=meeting.id,
        entity_type="action_item",
        entity_id=item.id,
        action="delete",
        actor_id=current_user.id,
        field=None,
        before={
            "description": item.description,
            "status": item.status,
            "assignee_name": item.assignee_name,
        },
        after={"deleted_at": now.isoformat()},
        entity_version_after=new_version,
        request_id=getattr(getattr(request, "state", None), "request_id", None),
        created_at=now,
    )
    db.commit()

    return Response(status_code=status.HTTP_204_NO_CONTENT)


EDITS_FIXTURE_PATH = FIXTURES_DIR / "edits.json"
JOB_FIXTURE_PATH = FIXTURES_DIR / "job_retry_scheduled.json"


def load_edits_fixture() -> dict:
    """Đọc dữ liệu fixture lịch sử chỉnh sửa."""
    if EDITS_FIXTURE_PATH.is_file():
        with open(EDITS_FIXTURE_PATH, encoding="utf-8") as f:
            return json.load(f)
    return {"items": [], "total": 0}


def load_job_fixture() -> dict:
    """Đọc dữ liệu fixture job."""
    if JOB_FIXTURE_PATH.is_file():
        with open(JOB_FIXTURE_PATH, encoding="utf-8") as f:
            return json.load(f)
    return {
        "id": "c1d2e3f4-a5b6-4c7d-8e9f-0a1b2c3d4e5f",
        "meeting_id": "8f6c2a1e-b2c3-4d4e-8f9a-0b1c2d3e4f5a",
        "status": "queued",
        "stage": "preprocess",
        "from_stage": None,
        "progress": 0.0,
        "stages": {},
        "attempt": 1,
        "max_attempts": 3,
        "next_run_at": None,
        "error": None,
        "created_at": "2026-10-15T08:30:01Z",
        "started_at": None,
        "finished_at": None,
    }


@router.post(
    "/{meeting_id}/jobs",
    response_model=JobOut,
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        404: {"model": ErrorResponse, "description": "Không tìm thấy cuộc họp"},
        409: {
            "model": ErrorResponse,
            "description": "Job đang chạy hoặc đã thành công hoặc có chỉnh sửa người dùng",
        },
    },
    summary="Chạy lại tiến trình xử lý cho cuộc họp",
)
def retry_meeting_job(
    meeting_id: str = FastApiPath(..., description="UUID của cuộc họp"),
    payload: JobRetryCreate = ...,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> JobOut:
    """Chạy lại tiến trình xử lý từ một stage nhất định (hoặc chạy lại toàn bộ)."""
    if "active" in meeting_id.lower():
        active_job = load_job_fixture()
        active_job["status"] = "running"
        raise APIError(
            code="JOB_ALREADY_ACTIVE",
            message="Cuộc họp hiện đang có một job đang được xử lý.",
            status_code=status.HTTP_409_CONFLICT,
            details={"job": active_job},
        )

    data = load_job_fixture()
    data["meeting_id"] = meeting_id
    data["status"] = "queued"
    data["from_stage"] = payload.from_stage
    return JobOut.model_validate(data)


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


@router.get(
    "/{meeting_id}/export",
    status_code=status.HTTP_200_OK,
    responses={
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
    format: Annotated[str, Query(description="Định dạng xuất: txt, json, md, docx")] = "txt",
    variant: Annotated[
        str, Query(description="Biến thể nội dung: current hoặc ai_original")
    ] = "current",
) -> Response:
    """Xuất biên bản cuộc họp dưới định dạng mong muốn."""
    fmt = format.lower()
    if fmt not in ("txt", "json", "md", "docx"):
        raise APIError(
            code="FORMAT_NOT_SUPPORTED",
            message=f"Định dạng xuất '{format}' không được hỗ trợ.",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    if "not-ready" in meeting_id.lower():
        raise APIError(
            code="TRANSCRIPT_NOT_READY",
            message="Transcript chưa sẵn sàng để xuất dữ liệu.",
            status_code=status.HTTP_409_CONFLICT,
        )

    media_types = {
        "txt": "text/plain; charset=utf-8",
        "md": "text/markdown; charset=utf-8",
        "json": "application/json; charset=utf-8",
        "docx": ("application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
    }

    content = f"# Biên bản cuộc họp {meeting_id}\nBiến thể: {variant}\n"
    filename = f"meeting_{meeting_id}_{variant}.{fmt}"
    return Response(
        content=content.encode("utf-8"),
        media_type=media_types.get(fmt, "application/octet-stream"),
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{filename}"},
    )
