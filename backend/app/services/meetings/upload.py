"""Nghiệp vụ tải lên tệp âm thanh và khởi tạo cuộc họp (AD-018, BE-12)."""

import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import Literal

from fastapi import UploadFile, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import APIError
from app.db.models.job import Job
from app.db.models.meeting import Meeting
from app.schemas.meeting import MeetingCreateOut
from app.services.audio_validator import probe_audio, validate_extension_and_mime
from app.services.idempotency import IdempotencyService
from app.services.storage import Storage
from app.services.storage.base import FileTooLargeError

logger = logging.getLogger(__name__)

MeetingSource = Literal["upload", "recording"]


def _get_probe_fn():
    """Hỗ trợ kiểm thử khi monkeypatch ở app.api.v1.meetings hoặc app.services.meetings.upload."""
    try:
        import app.api.v1.meetings as m

        if hasattr(m, "probe_audio"):
            return m.probe_audio
    except Exception:
        pass
    return probe_audio


def handle_meeting_upload(
    db: Session,
    storage: Storage,
    file: UploadFile,
    user_id: str,
    idempotency_key: str,
    title: str | None = None,
    source: MeetingSource = "upload",
    num_speakers: int | None = None,
    meeting_date: str | None = None,
) -> tuple[MeetingCreateOut, bool, int | None]:
    """Xử lý toàn bộ quy trình tải lên âm thanh và khởi tạo cuộc họp:

    1. Kiểm tra idempotency key để tránh tạo trùng bản ghi.
    2. Xác thực định dạng MIME và phần mở rộng tệp.
    3. Lưu tệp âm thanh vào Storage.
    4. Trích xuất metadata thời lượng qua ffprobe.
    5. Tạo bản ghi Meeting và Job trong cơ sở dữ liệu.
    6. Hoàn tất idempotency key và trả về kết quả tạo cuộc họp.
    """
    clean_ext = validate_extension_and_mime(file.filename or "", file.content_type)

    idempotency_service = IdempotencyService()
    idem_res = idempotency_service.check_or_start(
        session=db,
        user_id=user_id,
        key=idempotency_key,
        endpoint="/api/v1/meetings",
    )

    if idem_res.is_replayed:
        return (
            MeetingCreateOut.model_validate(idem_res.response_body),
            True,
            idem_res.response_code,
        )

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
    probe_fn = _get_probe_fn()
    try:
        probe_result = probe_fn(file_path=audio_file_path)
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
            owner_id=user_id,
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
                    "retention_until": (
                        meeting.retention_until.isoformat() if meeting.retention_until else None
                    ),
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

    return MeetingCreateOut.model_validate(response_data), False, None
