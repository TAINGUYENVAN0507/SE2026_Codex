"""Các phép biến đổi thuần từ MeetingExport sang dữ liệu tải xuống."""

import json

from .models import (
    ExportAction,
    ExportDocument,
    ExportSegment,
    ExportSpeaker,
    MeetingExport,
    Variant,
)


def document(meeting: MeetingExport, variant: Variant = "current") -> ExportDocument:
    """Chọn đúng bản gốc, không lấy nội dung đã sửa để lấp bản gốc bị thiếu."""
    if variant not in ("current", "ai_original"):
        raise ValueError("Biến thể export không hợp lệ")
    original = variant == "ai_original"
    actions = []
    for item in sorted(meeting.action_items, key=lambda item: item.id):
        if original:
            if item.source != "ai" or item.ai_original is None:
                continue
            values = item.ai_original.model_dump()
        else:
            values = item.model_dump(
                include={"description", "assignee_name", "due_date", "due_date_text"}
            )
        actions.append(
            ExportAction(
                **values,
                id=item.id,
                status="open" if original else item.status,
                source=item.source,
            )
        )
    return ExportDocument(
        variant=variant,
        meeting=meeting.meeting,
        speakers=[
            ExportSpeaker(id=s.id, name=s.default_name if original else s.display_name)
            for s in sorted(meeting.speakers, key=lambda s: s.id)
        ],
        segments=[
            ExportSegment(
                id=s.id,
                start_sec=round(s.start_sec, 3),
                end_sec=round(s.end_sec, 3),
                speaker_id=s.ai_speaker_id if original else s.speaker_id,
                text=s.ai_text if original else s.text,
            )
            for s in sorted(meeting.segments, key=lambda s: (s.start_sec, s.end_sec, s.id))
        ],
        summary=(meeting.summary.ai_content if original else meeting.summary.content)
        if meeting.summary
        else None,
        action_items=actions,
    )


def to_json(meeting: MeetingExport, variant: Variant = "current") -> bytes:
    """Sinh UTF-8 deterministic, giữ nguyên tiếng Việt và không thêm thời điểm xuất."""
    content = document(meeting, variant).model_dump(mode="json")
    return (json.dumps(content, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode(
        "utf-8"
    )


def export_schema() -> dict:
    """Sinh schema từ model đầu ra thay vì duy trì bản schema bằng tay."""
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        **ExportDocument.model_json_schema(),
    }
