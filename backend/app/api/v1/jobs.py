"""Router cho resource Jobs theo hợp đồng REST API v0."""

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
    job_id: Annotated[str, FastApiPath(description="UUID của job cần lấy trạng thái")],
    current_user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
) -> JobOut:
    """Trả về trạng thái tiến trình job từ cơ sở dữ liệu."""
    job = db.execute(select(Job).where(Job.id == job_id)).scalar_one_or_none()
    if not job:
        raise APIError(
            code="NOT_FOUND",
            message="Không tìm thấy tiến trình xử lý.",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    meeting = db.execute(select(Meeting).where(Meeting.id == job.meeting_id)).scalar_one_or_none()
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
