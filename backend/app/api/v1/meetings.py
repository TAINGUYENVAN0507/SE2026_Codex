"""Router stub cho resource Meetings theo hợp đồng REST API v0."""

import json
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, File, Form, Header, Query, UploadFile, status
from fastapi import Path as FastApiPath

from app.core.errors import APIError
from app.schemas.common import ErrorResponse
from app.schemas.meeting import (
    MeetingCreateOut,
    MeetingDetailOut,
    MeetingListOut,
    MeetingSource,
    MeetingStatus,
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
