"""Router stub cho resource Meetings theo hợp đồng REST API v0."""

import json
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, File, Form, Header, Query, Response, UploadFile, status
from fastapi import Path as FastApiPath

from app.core.errors import APIError
from app.schemas.action_item import (
    ActionItemCreate,
    ActionItemListOut,
    ActionItemOut,
    ActionItemPatch,
)
from app.schemas.common import ErrorResponse
from app.schemas.meeting import (
    MeetingCreateOut,
    MeetingDetailOut,
    MeetingListOut,
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

router = APIRouter(prefix="/meetings", tags=["Meetings"])

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


@router.get(
    "",
    response_model=MeetingListOut,
    status_code=status.HTTP_200_OK,
    summary="Lấy danh sách cuộc họp có phân trang và lọc",
)
def list_meetings(
    page: Annotated[int, Query(ge=1, description="Số thứ tự trang (bắt đầu từ 1)")] = 1,
    page_size: Annotated[int, Query(ge=1, le=100, description="Số lượng mục trên mỗi trang")] = 10,
    status_filter: Annotated[
        MeetingStatus | None, Query(alias="status", description="Lọc theo trạng thái")
    ] = None,
    q: Annotated[str | None, Query(description="Tìm kiếm theo tiêu đề cuộc họp")] = None,
) -> MeetingListOut:
    """Lấy danh sách cuộc họp có phân trang và lọc theo trạng thái."""
    data = load_meeting_list_fixture()
    items = data.get("items", [])
    if status_filter is not None:
        items = [item for item in items if item.get("status") == status_filter]
    return MeetingListOut(
        items=items,
        page=page,
        page_size=page_size,
        total=len(items) if status_filter is not None else data.get("total", len(items)),
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

    data = load_meeting_created_fixture()
    if title:
        data["meeting"]["title"] = title
    if source:
        data["meeting"]["source"] = source
    if num_speakers is not None:
        data["meeting"]["num_speakers_hint"] = num_speakers
    if meeting_date:
        data["meeting"]["meeting_date"] = meeting_date

    return MeetingCreateOut.model_validate(data)


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
) -> MeetingDetailOut:
    """Trả về chi tiết cuộc họp (stub contract v0 phục vụ phát triển frontend)."""
    data = load_meeting_fixture()
    # Nếu client truyền ID cụ thể thì gán id tương ứng
    data["id"] = meeting_id
    data["latest_job"] = None
    data["speakers"] = []
    return MeetingDetailOut.model_validate(data)


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
) -> TranscriptOut:
    """Trả về dữ liệu transcript của cuộc họp (trạng thái pending trả về segments rỗng)."""
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
    meeting_id: str = FastApiPath(..., description="UUID của cuộc họp"),
    segment_id: str = FastApiPath(..., description="UUID của đoạn thoại cần sửa"),
    payload: SegmentPatch = ...,
) -> TranscriptSegmentOut:
    """Chỉnh sửa đoạn transcript với optimistic locking qua trường version."""
    # Kiểm tra version conflict: version kỳ vọng của fixture mẫu là 2
    if payload.version != 2:
        raise APIError(
            code="VERSION_CONFLICT",
            message="Đoạn transcript đã được cập nhật ở nơi khác. Vui lòng tải lại.",
            status_code=status.HTTP_409_CONFLICT,
            details={
                "entity": "segment",
                "current": {"id": segment_id, "version": 3},
            },
        )

    # Đọc fixture mẫu để tạo kết quả
    data = load_transcript_ready_fixture()
    matched = None
    for seg in data.get("segments", []):
        if seg.get("id") == segment_id:
            matched = seg
            break

    if not matched:
        matched = {
            "id": segment_id,
            "index": 0,
            "start_sec": 0.84,
            "end_sec": 6.2,
            "speaker_id": payload.speaker_id,
            "ai_speaker_id": "2c7a9d10-a1b2-4c3d-8e4f-5a6b7c8d9e0f",
            "text": payload.text or "Nội dung mặc định",
            "ai_text": "Nội dung gốc do AI",
            "is_edited": True,
            "confidence": 0.81,
            "flags": [],
            "version": payload.version + 1,
            "updated_at": "2026-10-15T09:15:00Z",
        }
    else:
        if payload.text is not None:
            matched["text"] = payload.text
        if payload.speaker_id is not None:
            matched["speaker_id"] = payload.speaker_id
        matched["is_edited"] = True
        matched["version"] = payload.version + 1

    return TranscriptSegmentOut.model_validate(matched)


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
    meeting_id: str = FastApiPath(..., description="UUID của cuộc họp"),
    speaker_id: str = FastApiPath(..., description="UUID của người nói cần sửa"),
    payload: SpeakerPatch = ...,
) -> SpeakerOut:
    """Cập nhật tên hiển thị người nói với kiểm tra optimistic concurrency control."""
    if payload.version not in (1, 2):
        raise APIError(
            code="VERSION_CONFLICT",
            message="Người nói đã được cập nhật ở nơi khác. Vui lòng tải lại.",
            status_code=status.HTTP_409_CONFLICT,
            details={
                "entity": "speaker",
                "current": {"id": speaker_id, "version": 2},
            },
        )

    data = load_transcript_ready_fixture()
    matched = None
    for spk in data.get("speakers", []):
        if spk.get("id") == speaker_id:
            matched = spk
            break

    if not matched:
        matched = {
            "id": speaker_id,
            "meeting_id": meeting_id,
            "label": "SPEAKER_00",
            "default_name": "Speaker 1",
            "display_name": payload.display_name,
            "is_edited": True,
            "color_index": 0,
            "segment_count": 1,
            "speaking_time_sec": 6.42,
            "version": payload.version + 1,
        }
    else:
        matched["display_name"] = payload.display_name
        matched["is_edited"] = True
        matched["version"] = payload.version + 1

    return SpeakerOut.model_validate(matched)


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
    meeting_id: str = FastApiPath(..., description="UUID của cuộc họp"),
    payload: SummaryUpdate = ...,
) -> SummaryOut:
    """Cập nhật tóm tắt cuộc họp với optimistic locking."""
    if payload.version != 2:
        raise APIError(
            code="VERSION_CONFLICT",
            message="Tóm tắt cuộc họp đã được cập nhật ở nơi khác. Vui lòng tải lại.",
            status_code=status.HTTP_409_CONFLICT,
            details={
                "entity": "summary",
                "current": {"meeting_id": meeting_id, "version": 2},
            },
        )

    data = load_summary_ready_fixture()
    data["meeting_id"] = meeting_id
    data["content"] = payload.content.model_dump()
    data["is_edited"] = True
    data["version"] = payload.version + 1
    return SummaryOut.model_validate(data)


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
    meeting_id: str = FastApiPath(..., description="UUID của cuộc họp"),
) -> ActionItemListOut:
    """Lấy danh sách các action item (công việc cần làm) của cuộc họp."""
    data = load_action_items_fixture()
    return ActionItemListOut.model_validate(data)


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
    meeting_id: str = FastApiPath(..., description="UUID của cuộc họp"),
    payload: ActionItemCreate = ...,
) -> ActionItemOut:
    """Tạo mới một action item với nguồn gốc source='user'."""
    new_item = {
        "id": "new-action-item-uuid-1",
        "meeting_id": meeting_id,
        "description": payload.description,
        "assignee_name": payload.assignee_name,
        "assignee_speaker_id": payload.assignee_speaker_id,
        "due_date": payload.due_date,
        "due_date_text": None,
        "status": payload.status,
        "source": "user",
        "is_edited": False,
        "needs_review": False,
        "evidence_segment_ids": [],
        "ai_original": None,
        "version": 1,
        "created_at": "2026-10-15T09:00:00Z",
        "updated_at": "2026-10-15T09:00:00Z",
    }
    return ActionItemOut.model_validate(new_item)


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
    meeting_id: str = FastApiPath(..., description="UUID của cuộc họp"),
    item_id: str = FastApiPath(..., description="UUID của action item"),
    payload: ActionItemPatch = ...,
) -> ActionItemOut:
    """Chỉnh sửa thông tin action item có kiểm tra optimistic locking."""
    if payload.version != 1:
        raise APIError(
            code="VERSION_CONFLICT",
            message="Action item đã được cập nhật ở nơi khác. Vui lòng tải lại.",
            status_code=status.HTTP_409_CONFLICT,
            details={
                "entity": "action_item",
                "current": {"id": item_id, "version": 2},
            },
        )

    data = load_action_items_fixture()
    matched = None
    for item in data.get("items", []):
        if item.get("id") == item_id:
            matched = dict(item)
            break

    if not matched:
        matched = {
            "id": item_id,
            "meeting_id": meeting_id,
            "description": payload.description or "Công việc cần làm",
            "assignee_name": payload.assignee_name,
            "assignee_speaker_id": payload.assignee_speaker_id,
            "due_date": payload.due_date,
            "due_date_text": None,
            "status": payload.status or "open",
            "source": "ai",
            "is_edited": True,
            "needs_review": False,
            "evidence_segment_ids": [],
            "ai_original": None,
            "version": payload.version + 1,
            "created_at": "2026-10-15T08:55:02Z",
            "updated_at": "2026-10-15T09:10:00Z",
        }
    else:
        if payload.description is not None:
            matched["description"] = payload.description
        if payload.assignee_name is not None:
            matched["assignee_name"] = payload.assignee_name
        if payload.assignee_speaker_id is not None:
            matched["assignee_speaker_id"] = payload.assignee_speaker_id
        if payload.due_date is not None:
            matched["due_date"] = payload.due_date
        if payload.status is not None:
            matched["status"] = payload.status
        matched["is_edited"] = True
        matched["version"] = payload.version + 1

    return ActionItemOut.model_validate(matched)


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
    meeting_id: str = FastApiPath(..., description="UUID của cuộc họp"),
    item_id: str = FastApiPath(..., description="UUID của action item"),
    version: Annotated[int | None, Query(description="Phiên bản của action item")] = None,
) -> Response:
    """Xóa action item (xóa mềm) có kiểm tra version nếu được cung cấp."""
    if version is not None and version != 1:
        raise APIError(
            code="VERSION_CONFLICT",
            message="Action item đã được cập nhật ở nơi khác. Vui lòng tải lại.",
            status_code=status.HTTP_409_CONFLICT,
            details={
                "entity": "action_item",
                "current": {"id": item_id, "version": 2},
            },
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
