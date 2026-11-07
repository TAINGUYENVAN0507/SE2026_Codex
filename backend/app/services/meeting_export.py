"""Dịch vụ tập hợp dữ liệu cuộc họp từ cơ sở dữ liệu thành DTO MeetingExport."""

from datetime import date
from typing import Any

from fastapi import status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import APIError
from app.db.models.action_item import ActionItem
from app.db.models.meeting import Meeting
from app.db.models.summary import Summary
from app.db.models.transcript import Segment, Speaker
from app.services.export.models import (
    ActionItem as ExportActionItem,
)
from app.services.export.models import (
    ActionOriginal as ExportActionOriginal,
)
from app.services.export.models import (
    MeetingExport,
    MeetingInfo,
    SummaryContent,
    SummaryPoint,
)
from app.services.export.models import (
    Segment as ExportSegment,
)
from app.services.export.models import (
    Speaker as ExportSpeaker,
)
from app.services.export.models import (
    Summary as ExportSummary,
)


def _parse_iso_date(value: str | None) -> date | None:
    """Chuyển đổi chuỗi YYYY-MM-DD sang date object, trả về None nếu lỗi hoặc rỗng."""
    if not value or not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value.strip())
    except ValueError:
        return None


def _to_summary_point(item: Any) -> SummaryPoint:
    """Chuyển đổi một phần tử ý chính hoặc quyết định sang SummaryPoint."""
    if isinstance(item, dict):
        text = str(item.get("text", "")).strip()
        raw_evidence = item.get("evidence_segment_ids")
        evidence_ids = (
            [str(eid) for eid in raw_evidence if eid] if isinstance(raw_evidence, list) else []
        )
        return SummaryPoint(text=text, evidence_segment_ids=evidence_ids)
    return SummaryPoint(text=str(item).strip(), evidence_segment_ids=[])


def _parse_summary_content(content_dict: dict[str, Any] | None) -> SummaryContent | None:
    """Chuyển đổi dict lưu trữ JSON của summary sang SummaryContent DTO."""
    if not content_dict or not isinstance(content_dict, dict):
        return None
    overview = str(content_dict.get("overview") or "").strip()
    raw_kp = content_dict.get("key_points") or []
    raw_dec = content_dict.get("decisions") or []

    key_points = [_to_summary_point(kp) for kp in raw_kp] if isinstance(raw_kp, list) else []
    decisions = [_to_summary_point(dec) for dec in raw_dec] if isinstance(raw_dec, list) else []

    return SummaryContent(
        overview=overview,
        key_points=key_points,
        decisions=decisions,
    )


def build_meeting_export(
    db: Session,
    meeting_id: str,
    current_user_id: str,
) -> MeetingExport:
    """Tập hợp thông tin cuộc họp từ DB thành MeetingExport DTO thuần túy.

    Kiểm tra quyền sở hữu của người dùng (nếu không khớp trả về 404 để tránh dò quét).
    Kiểm tra trạng thái transcript sẵn sàng (nếu chưa ready/partial trả về 409).
    """
    meeting = db.execute(select(Meeting).where(Meeting.id == meeting_id)).scalar_one_or_none()

    if meeting is None or meeting.owner_id != current_user_id:
        raise APIError(
            code="MEETING_NOT_FOUND",
            message="Không tìm thấy cuộc họp được yêu cầu.",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    if meeting.status not in ("ready", "partial"):
        raise APIError(
            code="TRANSCRIPT_NOT_READY",
            message="Transcript chưa sẵn sàng để xuất dữ liệu.",
            status_code=status.HTTP_409_CONFLICT,
        )

    # 1. Tập hợp danh sách người nói
    speakers_db = (
        db.execute(
            select(Speaker)
            .where(Speaker.meeting_id == meeting.id)
            .order_by(Speaker.created_at.asc())
        )
        .scalars()
        .all()
    )
    speakers = [
        ExportSpeaker(
            id=s.id,
            display_name=s.display_name,
            default_name=s.default_name,
        )
        for s in speakers_db
    ]

    # 2. Tập hợp danh sách phân đoạn transcript
    segments_db = (
        db.execute(
            select(Segment)
            .where(Segment.meeting_id == meeting.id)
            .order_by(Segment.start_sec.asc(), Segment.end_sec.asc(), Segment.idx.asc())
        )
        .scalars()
        .all()
    )
    segments: list[ExportSegment] = []
    for seg in segments_db:
        start_sec = max(0.0, float(seg.start_sec))
        end_sec = float(seg.end_sec)
        if end_sec <= start_sec:
            end_sec = start_sec + 0.001
        segments.append(
            ExportSegment(
                id=seg.id,
                start_sec=start_sec,
                end_sec=end_sec,
                text=seg.text,
                speaker_id=seg.speaker_id,
                ai_text=seg.ai_text,
                ai_speaker_id=seg.ai_speaker_id,
            )
        )

    # 3. Tập hợp thông tin tóm tắt (summary)
    summary_db = db.execute(
        select(Summary).where(Summary.meeting_id == meeting.id)
    ).scalar_one_or_none()

    summary_dto: ExportSummary | None = None
    if summary_db is not None:
        content_dto = _parse_summary_content(summary_db.content)
        ai_content_dto = _parse_summary_content(summary_db.ai_content)
        if content_dto is not None or ai_content_dto is not None:
            summary_dto = ExportSummary(
                content=content_dto,
                ai_content=ai_content_dto,
            )

    # 4. Tập hợp danh sách công việc (action items)
    actions_db = (
        db.execute(
            select(ActionItem)
            .where(
                ActionItem.meeting_id == meeting.id,
                ActionItem.deleted_at.is_(None),
            )
            .order_by(ActionItem.created_at.asc())
        )
        .scalars()
        .all()
    )

    action_items: list[ExportActionItem] = []
    for item in actions_db:
        due_d = _parse_iso_date(item.due_date)

        ai_orig_dto: ExportActionOriginal | None = None
        if item.ai_original and isinstance(item.ai_original, dict):
            orig_due_date = _parse_iso_date(item.ai_original.get("due_date"))
            ai_orig_dto = ExportActionOriginal(
                description=str(item.ai_original.get("description", "")),
                assignee_name=item.ai_original.get("assignee_name"),
                due_date=orig_due_date,
                due_date_text=item.ai_original.get("due_date_text"),
            )

        act_status = item.status if item.status in ("open", "done", "cancelled") else "open"
        act_source = item.source if item.source in ("ai", "user") else "ai"

        evidence_ids = (
            [str(eid) for eid in item.evidence_segment_ids if eid]
            if isinstance(item.evidence_segment_ids, list)
            else []
        )

        action_items.append(
            ExportActionItem(
                id=item.id,
                description=item.description,
                assignee_name=item.assignee_name,
                due_date=due_d,
                due_date_text=item.due_date_text,
                status=act_status,
                source=act_source,
                ai_original=ai_orig_dto,
                evidence_segment_ids=evidence_ids,
                needs_review=bool(item.needs_review),
            )
        )

    # 5. Metadata cuộc họp
    meeting_date_obj = _parse_iso_date(meeting.meeting_date)
    duration = float(meeting.duration_sec) if meeting.duration_sec is not None else None
    if duration is not None and duration < 0:
        duration = 0.0

    meeting_info = MeetingInfo(
        id=meeting.id,
        title=meeting.title,
        meeting_date=meeting_date_obj,
        duration_sec=duration,
    )

    return MeetingExport(
        meeting=meeting_info,
        speakers=speakers,
        segments=segments,
        summary=summary_dto,
        action_items=action_items,
    )
