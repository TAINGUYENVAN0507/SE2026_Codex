"""Router stub cho resource Meetings theo hợp đồng REST API v0."""

import json
from pathlib import Path

from fastapi import APIRouter, status
from fastapi import Path as FastApiPath

from app.schemas.common import ErrorResponse
from app.schemas.meeting import MeetingDetailOut

router = APIRouter(prefix="/meetings", tags=["Meetings"])

FIXTURE_PATH = (
    Path(__file__).resolve().parents[4]
    / "contracts"
    / "fixtures"
    / "api"
    / "meeting_processing.json"
)


def load_meeting_fixture() -> dict:
    """Đọc dữ liệu fixture meeting mẫu."""
    if FIXTURE_PATH.is_file():
        with open(FIXTURE_PATH, encoding="utf-8") as f:
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
