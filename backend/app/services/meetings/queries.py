"""Truy vấn và chuyển đổi dữ liệu đọc cho Meeting (tách khỏi controller, BE-05, BE-12)."""

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.db.models.job import Job
from app.db.models.meeting import Meeting
from app.db.models.transcript import Segment, Speaker
from app.schemas.meeting import MeetingDetailOut, MeetingOut, SpeakerOut

_UNSET_JOB = object()


def escape_like_wildcards(text: str) -> str:
    """Escape các ký tự đặc biệt của LIKE/ILIKE: \\, %, _."""
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def load_latest_jobs_by_meeting(db: Session, meeting_ids: list[str]) -> dict[str, Job]:
    """Lấy job mới nhất của tất cả cuộc họp trong danh sách bằng một truy vấn duy nhất."""
    if not meeting_ids:
        return {}

    ranked_jobs = (
        select(
            Job.id.label("job_id"),
            func.row_number()
            .over(
                partition_by=Job.meeting_id,
                order_by=(Job.created_at.desc(), Job.id.desc()),
            )
            .label("rn"),
        )
        .where(Job.meeting_id.in_(meeting_ids))
        .subquery()
    )
    latest_jobs = (
        db.execute(
            select(Job)
            .join(ranked_jobs, Job.id == ranked_jobs.c.job_id)
            .where(ranked_jobs.c.rn == 1)
        )
        .scalars()
        .all()
    )
    return {job.meeting_id: job for job in latest_jobs}


def serialize_meeting_summary(
    meeting: Meeting, db: Session, latest_job: Job | None | object = _UNSET_JOB
) -> MeetingOut:
    """Chuyển đổi một thực thể Meeting trong DB sang schema MeetingOut."""
    resolved_job: Job | None
    if latest_job is _UNSET_JOB:
        resolved_job = (
            db.execute(
                select(Job).where(Job.meeting_id == meeting.id).order_by(Job.created_at.desc())
            )
            .scalars()
            .first()
        )
    else:
        resolved_job = latest_job if isinstance(latest_job, Job) else None

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
        summary_status = "failed" if meeting.status == "partial" else "ready"
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
        latest_job_id=resolved_job.id if resolved_job else None,
        created_at=meeting.created_at,
        updated_at=meeting.updated_at,
        version=meeting.version,
    )


def serialize_meeting_detail(meeting: Meeting, db: Session) -> MeetingDetailOut:
    """Tạo đối tượng MeetingDetailOut từ model Meeting."""
    from app.api.v1.jobs import serialize_job

    latest_job = (
        db.execute(select(Job).where(Job.meeting_id == meeting.id).order_by(Job.created_at.desc()))
        .scalars()
        .first()
    )

    duration_expr = case(
        (Segment.end_sec > Segment.start_sec, Segment.end_sec - Segment.start_sec),
        else_=0.0,
    )
    speaker_rows = db.execute(
        select(
            Speaker,
            func.count(Segment.id).label("segment_count"),
            func.coalesce(func.sum(duration_expr), 0.0).label("speaking_time"),
        )
        .outerjoin(Segment, Segment.speaker_id == Speaker.id)
        .where(Speaker.meeting_id == meeting.id)
        .group_by(Speaker.id, Speaker.created_at)
        .order_by(Speaker.created_at.asc())
    ).all()

    speakers_out = [
        SpeakerOut(
            id=spk.id,
            meeting_id=spk.meeting_id,
            label=spk.label,
            default_name=spk.default_name,
            display_name=spk.display_name,
            is_edited=spk.display_name != spk.default_name,
            color_index=idx % 10,
            segment_count=int(seg_count),
            speaking_time_sec=round(float(spk_time), 2),
            version=spk.version,
        )
        for idx, (spk, seg_count, spk_time) in enumerate(speaker_rows)
    ]

    job_out = serialize_job(latest_job) if latest_job else None
    meeting_summary = serialize_meeting_summary(meeting, db, latest_job=latest_job)
    return MeetingDetailOut(
        **meeting_summary.model_dump(),
        latest_job=job_out,
        speakers=speakers_out,
    )
