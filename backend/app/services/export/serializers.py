"""Các phép biến đổi thuần từ MeetingExport sang dữ liệu tải xuống."""

import html
import json
import re
import unicodedata

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


def timestamp(seconds: float) -> str:
    """Định dạng mốc audio, không dùng giờ địa phương hoặc ngày hiện tại."""
    value = int(seconds)
    return f"{value // 3600:02d}:{value // 60 % 60:02d}:{value % 60:02d}"


def _line(value: str) -> str:
    return " ".join(value.split())


def _markdown(value: str) -> str:
    # Dữ liệu được giữ ở dạng text, không biến thành HTML hoặc link Markdown.
    return re.sub(r"([\\`*_\[\]#|])", r"\\\1", html.escape(_line(value), quote=False))


def to_txt(meeting: MeetingExport, variant: Variant = "current") -> bytes:
    """Xuất mỗi segment đúng một dòng, kể cả text đầu vào có xuống dòng."""
    data = document(meeting, variant)
    names = {speaker.id: speaker.name for speaker in data.speakers}
    lines = [
        f"[{timestamp(s.start_sec)}] {_line(names.get(s.speaker_id, 'Chưa xác định'))}: "
        f"{_line(s.text)}"
        for s in data.segments
    ]
    return ("\n".join(lines) + ("\n" if lines else "")).encode("utf-8")


def to_markdown(meeting: MeetingExport, variant: Variant = "current") -> bytes:
    """Biên bản Markdown gồm tóm tắt, quyết định, công việc và transcript."""
    data = document(meeting, variant)
    names = {speaker.id: speaker.name for speaker in data.speakers}
    lines = [
        f"# {_markdown(data.meeting.title)}",
        "",
        f"Ngày họp: {data.meeting.meeting_date or 'Chưa có ngày'}",
        "",
        "## Tóm tắt",
        "",
        _markdown(data.summary.overview) if data.summary else "Chưa có tóm tắt.",
        "",
        "## Ý chính",
        "",
    ]
    lines += (
        [f"- {_markdown(p.text)}" for p in data.summary.key_points]
        if data.summary and data.summary.key_points
        else ["Chưa có ý chính."]
    )
    lines += ["", "## Quyết định", ""]
    lines += (
        [f"- {_markdown(p.text)}" for p in data.summary.decisions]
        if data.summary and data.summary.decisions
        else ["Chưa có quyết định."]
    )
    lines += [
        "",
        "## Công việc",
        "",
        "| Nội dung | Người nhận | Hạn | Trạng thái |",
        "| --- | --- | --- | --- |",
    ]
    status_names = {"open": "Chưa hoàn thành", "done": "Hoàn thành", "cancelled": "Đã hủy"}
    for item in data.action_items:
        lines.append(
            f"| {_markdown(item.description)} | {_markdown(item.assignee_name or 'Chưa giao')} "
            f"| {item.due_date or 'Chưa có hạn'} | {status_names[item.status]} |"
        )
    lines += ["", "## Transcript", ""]
    lines += [
        f"- [{timestamp(s.start_sec)}] {_markdown(names.get(s.speaker_id, 'Chưa xác định'))}: "
        f"{_markdown(s.text)}"
        for s in data.segments
    ]
    return ("\n".join(lines) + "\n").encode("utf-8")


def filename(meeting: MeetingExport, fmt: str) -> str:
    """Tên tải xuống chỉ dùng slug ASCII và ngày họp, không nhận đường dẫn."""
    if fmt not in ("txt", "json", "md"):
        raise ValueError("Định dạng export không hợp lệ")
    title = unicodedata.normalize("NFKD", meeting.meeting.title.lower().replace("đ", "d"))
    ascii_title = title.encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_title).strip("-")[:80].rstrip("-") or "cuoc-hop"
    return f"{slug}-{meeting.meeting.meeting_date or 'khong-ro-ngay'}.{fmt}"
