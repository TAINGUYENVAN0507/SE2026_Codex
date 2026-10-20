"""Router stub cho resource Jobs theo hợp đồng REST API v0."""

import json
from pathlib import Path

from fastapi import APIRouter, status
from fastapi import Path as FastApiPath

from app.schemas.common import ErrorResponse
from app.schemas.job import JobOut

router = APIRouter(prefix="/jobs", tags=["Jobs"])

FIXTURE_PATH = (
    Path(__file__).resolve().parents[4]
    / "contracts"
    / "fixtures"
    / "api"
    / "job_retry_scheduled.json"
)


def load_job_fixture() -> dict:
    """Đọc dữ liệu fixture job mẫu."""
    if FIXTURE_PATH.is_file():
        with open(FIXTURE_PATH, encoding="utf-8") as f:
            return json.load(f)
    # Dữ liệu fallback
    return {
        "id": "c1d2e3f4-a5b6-4c7d-8e9f-0a1b2c3d4e5f",
        "meeting_id": "8f6c2a1e-b2c3-4d4e-8f9a-0b1c2d3e4f5a",
        "status": "retry_scheduled",
        "stage": "summarize",
        "from_stage": None,
        "progress": 0.9,
        "stages": {
            "preprocess": "succeeded",
            "vad": "succeeded",
            "asr": "succeeded",
            "diarize": "succeeded",
            "merge": "succeeded",
            "summarize": "retry_scheduled",
        },
        "attempt": 2,
        "max_attempts": 3,
        "next_run_at": "2026-10-15T08:54:10Z",
        "error": {
            "code": "LLM_UNAVAILABLE",
            "message": "Dịch vụ tóm tắt tạm thời không phản hồi. Hệ thống sẽ tự thử lại.",
            "retryable": True,
            "stage": "summarize",
        },
        "created_at": "2026-10-15T08:30:01Z",
        "started_at": "2026-10-15T08:30:05Z",
        "finished_at": None,
    }


@router.get(
    "/{job_id}",
    response_model=JobOut,
    status_code=status.HTTP_200_OK,
    responses={
        404: {"model": ErrorResponse, "description": "Không tìm thấy job"},
    },
    summary="Lấy trạng thái tiến trình xử lý",
)
def get_job(
    job_id: str = FastApiPath(..., description="UUID của job cần lấy trạng thái"),
) -> JobOut:
    """Trả về trạng thái tiến trình job (stub contract v0)."""
    data = load_job_fixture()
    data["id"] = job_id
    return JobOut.model_validate(data)
