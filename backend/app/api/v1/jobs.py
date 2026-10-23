"""Router cho resource Jobs theo hợp đồng REST API v0."""

import json
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi import Path as FastApiPath
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, get_current_user
from app.core.errors import APIError
from app.db.models.job import Job
from app.db.models.meeting import Meeting
from app.db.session import get_db
from app.schemas.common import ErrorResponse
from app.schemas.job import JobErrorOut, JobOut

router = APIRouter(
    prefix="/jobs",
    tags=["Jobs"],
    dependencies=[Depends(get_current_user)],
)

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
    current_user: CurrentUser = None,  # type: ignore[assignment]
    db: Annotated[Session, Depends(get_db)] = None,  # type: ignore[assignment]
) -> JobOut:
    """Trả về trạng thái tiến trình job (stub contract v0)."""
    if db is not None and current_user is not None:
        job = db.execute(select(Job).where(Job.id == job_id)).scalar_one_or_none()
        if not job:
            raise APIError(
                code="NOT_FOUND",
                message="Không tìm thấy tiến trình xử lý.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        meeting = db.execute(
            select(Meeting).where(Meeting.id == job.meeting_id)
        ).scalar_one_or_none()
        if not meeting or meeting.owner_id != current_user.id:
            raise APIError(
                code="NOT_FOUND",
                message="Không tìm thấy tiến trình xử lý.",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        job_error = (
            JobErrorOut(
                code=job.error_code,
                message=job.error_message or "",
                retryable=job.attempt < job.max_attempts,
                stage=job.stage,
            )
            if job.error_code
            else None
        )
        return JobOut(
            id=job.id,
            meeting_id=job.meeting_id,
            status=job.status,  # type: ignore[arg-type]
            stage=job.stage,  # type: ignore[arg-type]
            from_stage=job.from_stage,  # type: ignore[arg-type]
            progress=job.progress,
            stages=job.stage_status or {},
            attempt=job.attempt,
            max_attempts=job.max_attempts,
            next_run_at=job.next_run_at,
            error=job_error,
            created_at=job.created_at,
            started_at=None,
            finished_at=None,
        )

    data = load_job_fixture()
    data["id"] = job_id
    return JobOut.model_validate(data)
