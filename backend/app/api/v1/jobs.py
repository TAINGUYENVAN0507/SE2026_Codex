"""Router cho resource Jobs theo hợp đồng REST API v0."""

import logging
import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    Header,
    Response,
    status,
)
from fastapi import (
    Path as FastApiPath,
)
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, get_current_user
from app.core.errors import APIError
from app.db.models.edit_event import EditEvent
from app.db.models.job import Job
from app.db.models.meeting import Meeting
from app.db.models.transcript import Segment
from app.db.session import get_db
from app.schemas.common import ErrorResponse
from app.schemas.job import JobErrorOut, JobOut, JobRetryCreate
from app.services.idempotency import IdempotencyService

logger = logging.getLogger("app.jobs")

router = APIRouter(
    prefix="/jobs",
    tags=["Jobs"],
    dependencies=[Depends(get_current_user)],
)

meeting_jobs_router = APIRouter()


def serialize_job(job: Job) -> JobOut:
    """Chuyển đổi một thực thể Job trong DB sang schema JobOut."""
    job_error = (
        JobErrorOut(
            code=job.error_code,
            message=job.error_message or "",
            retryable=job.can_retry,
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
        started_at=job.started_at,
        finished_at=job.finished_at,
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
    job = db.execute(
        select(Job)
        .join(Meeting, Meeting.id == Job.meeting_id)
        .where(Job.id == job_id, Meeting.owner_id == current_user.id)
    ).scalar_one_or_none()
    if not job:
        raise APIError(
            code="NOT_FOUND",
            message="Không tìm thấy tiến trình xử lý.",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    return serialize_job(job)


@meeting_jobs_router.post(
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
@meeting_jobs_router.post(
    "/{meeting_id}/retry",
    response_model=JobOut,
    status_code=status.HTTP_202_ACCEPTED,
    include_in_schema=False,
)
def retry_meeting_job(
    meeting_id: Annotated[str, FastApiPath(description="UUID của cuộc họp")],
    payload: JobRetryCreate,
    current_user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
    response: Response,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> JobOut:
    """Chạy lại tiến trình xử lý từ một stage nhất định (hoặc chạy lại toàn bộ)."""
    meeting = db.execute(select(Meeting).where(Meeting.id == meeting_id)).scalar_one_or_none()
    if not meeting or meeting.owner_id != current_user.id:
        raise APIError(
            code="MEETING_NOT_FOUND",
            message="Không tìm thấy cuộc họp được yêu cầu.",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    # 1. Kiểm tra tính idempotent nếu có Idempotency-Key
    idempotency_service = None
    idem_res = None
    if idempotency_key and idempotency_key.strip():
        idempotency_service = IdempotencyService()
        endpoint_str = f"/api/v1/meetings/{meeting_id}/jobs"
        idem_res = idempotency_service.check_or_start(
            session=db,
            user_id=current_user.id,
            key=idempotency_key.strip(),
            endpoint=endpoint_str,
        )
        if idem_res.is_replayed:
            response.headers["Idempotent-Replayed"] = "true"
            if idem_res.response_code:
                response.status_code = idem_res.response_code
            return JobOut.model_validate(idem_res.response_body)
        db.commit()

    # 2. Đang có job queued hoặc running (hoặc retry_scheduled) thì 409 JOB_ALREADY_ACTIVE kèm job
    active_job = db.execute(
        select(Job).where(
            Job.meeting_id == meeting.id,
            Job.status.in_(["queued", "running", "retry_scheduled"]),
        )
    ).scalar_one_or_none()
    if active_job:
        active_job_out = serialize_job(active_job)
        if idempotency_service and idem_res and idem_res.record_id:
            idempotency_service.fail(session=db, record_id=idem_res.record_id)
            db.commit()
        raise APIError(
            code="JOB_ALREADY_ACTIVE",
            message="Cuộc họp hiện đang có một tiến trình xử lý đang chạy.",
            status_code=status.HTTP_409_CONFLICT,
            details={"job": active_job_out.model_dump(mode="json")},
        )

    # 3. Job gần nhất đã thành công mà gửi lại cùng yêu cầu thì 409 JOB_ALREADY_SUCCEEDED
    latest_job = (
        db.execute(select(Job).where(Job.meeting_id == meeting.id).order_by(Job.created_at.desc()))
        .scalars()
        .first()
    )
    if (
        latest_job
        and latest_job.status == "succeeded"
        and (payload.from_stage is None or payload.from_stage == latest_job.from_stage)
    ):
        if idempotency_service and idem_res and idem_res.record_id:
            idempotency_service.fail(session=db, record_id=idem_res.record_id)
            db.commit()
        raise APIError(
            code="JOB_ALREADY_SUCCEEDED",
            message="Cuộc họp đã được xử lý thành công.",
            status_code=status.HTTP_409_CONFLICT,
        )

    # 4. Chạy lại từ asr/diarize khi người dùng đã sửa transcript -> 409 HAS_USER_EDITS
    if payload.from_stage in (None, "preprocess", "vad", "asr", "diarize", "merge"):
        has_user_edits = (
            db.execute(
                select(Segment).where(
                    Segment.meeting_id == meeting.id,
                    (Segment.text != Segment.ai_text)
                    | (Segment.speaker_id != Segment.ai_speaker_id),
                )
            ).first()
            is not None
            or db.execute(
                select(EditEvent).where(
                    EditEvent.meeting_id == meeting.id,
                    EditEvent.entity_type.in_(["segment", "speaker"]),
                )
            ).first()
            is not None
        )

        if has_user_edits:
            if idempotency_service and idem_res and idem_res.record_id:
                idempotency_service.fail(session=db, record_id=idem_res.record_id)
                db.commit()
            raise APIError(
                code="HAS_USER_EDITS",
                message="Cuộc họp đã có chỉnh sửa thủ công, không thể chạy lại từ đầu.",
                status_code=status.HTTP_409_CONFLICT,
            )

    # 5. Khởi tạo trạng thái stages và progress
    all_stages = ["preprocess", "vad", "asr", "diarize", "merge", "summarize"]
    stage_status = {stg: "queued" for stg in all_stages}
    initial_progress = 0.0
    start_stage = payload.from_stage or "preprocess"

    if payload.from_stage and payload.from_stage in all_stages:
        from_idx = all_stages.index(payload.from_stage)
        for i in range(from_idx):
            stage_status[all_stages[i]] = "succeeded"
        initial_progress = from_idx / len(all_stages)

    now = datetime.now(UTC)
    new_job = Job(
        id=str(uuid.uuid4()),
        meeting_id=meeting.id,
        status="queued",
        stage=start_stage,
        from_stage=payload.from_stage,
        stage_status=stage_status,
        progress=initial_progress,
        attempt=1,
        max_attempts=3,
        created_at=now,
        updated_at=now,
    )
    db.add(new_job)
    meeting.status = "processing"
    meeting.updated_at = now

    try:
        db.commit()
        logger.info(
            "Job %s đã được tạo lại cho cuộc họp %s",
            new_job.id,
            meeting.id,
            extra={
                "event": "job_created",
                "job_id": new_job.id,
                "meeting_id": meeting.id,
                "stage": new_job.stage,
                "attempt": new_job.attempt,
                "status": "queued",
            },
        )
    except IntegrityError as exc:
        db.rollback()
        if idempotency_service and idem_res and idem_res.record_id:
            idempotency_service.fail(session=db, record_id=idem_res.record_id)
            db.commit()
        active_job = db.execute(
            select(Job).where(
                Job.meeting_id == meeting.id,
                Job.status.in_(["queued", "running", "retry_scheduled"]),
            )
        ).scalar_one_or_none()
        raise APIError(
            code="JOB_ALREADY_ACTIVE",
            message="Cuộc họp hiện đang có một tiến trình xử lý đang chạy.",
            status_code=status.HTTP_409_CONFLICT,
            details={
                "job": serialize_job(active_job).model_dump(mode="json") if active_job else None
            },
        ) from exc

    job_out = serialize_job(new_job)

    if idempotency_service and idem_res and idem_res.record_id:
        idempotency_service.complete(
            session=db,
            record_id=idem_res.record_id,
            response_code=status.HTTP_202_ACCEPTED,
            response_body=job_out.model_dump(mode="json"),
        )
        db.commit()

    return job_out
