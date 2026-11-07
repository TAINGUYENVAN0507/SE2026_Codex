"""Golden tests TXT/Markdown, fallback và an toàn tên file."""

import json
import re
from pathlib import Path

import pytest

from app.services.export import MeetingExport, filename, to_markdown, to_txt

FIXTURES = Path(__file__).parents[1] / "fixtures/export"


def source() -> MeetingExport:
    """Dữ liệu mẫu chung với JSON golden."""
    return MeetingExport.model_validate_json((FIXTURES / "source.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("variant", ["current", "ai_original"])
@pytest.mark.parametrize(("fmt", "serializer"), [("txt", to_txt), ("md", to_markdown)])
def test_export_text_golden_and_deterministic(variant, fmt, serializer) -> None:
    meeting = source()
    before = meeting.model_dump()
    output = serializer(meeting, variant)
    assert output == serializer(meeting, variant) == serializer(meeting, variant)
    assert output == (FIXTURES / f"{variant}.{fmt}").read_text(encoding="utf-8").encode()
    assert meeting.model_dump() == before


@pytest.mark.parametrize(
    ("title", "slug"),
    [("Đề án — cuộc họp", "de-an-cuoc-hop"), ("../💬***", "cuoc-hop"), ("ĐẶT TÊN", "dat-ten")],
)
def test_export_ascii_filename(title: str, slug: str) -> None:
    values = source().model_dump()
    values["meeting"]["title"] = title
    name = filename(MeetingExport.model_validate(values), "txt")
    assert name == f"{slug}-2026-10-25.txt"
    assert re.fullmatch(r"[a-z0-9-]+\.txt", name)


def test_export_filename_rejects_unknown_extension() -> None:
    with pytest.raises(ValueError):
        filename(source(), "../../exe")


def test_export_handles_empty_and_missing_data() -> None:
    values = source().model_dump()
    values.update(segments=[], summary=None, action_items=[])
    values["meeting"]["meeting_date"] = None
    meeting = MeetingExport.model_validate(values)
    assert to_txt(meeting) == b""
    assert "Chưa có tóm tắt." in to_markdown(meeting).decode()
    assert filename(meeting, "md").endswith("-khong-ro-ngay.md")


def test_export_preserves_text_without_injecting_markdown_or_extra_txt_lines() -> None:
    values = json.loads((FIXTURES / "source.json").read_text(encoding="utf-8"))
    values["segments"][0]["text"] = "<script>x</script>\n# heading | [link](https://example.com)"
    meeting = MeetingExport.model_validate(values)
    assert (
        len([line for line in to_txt(meeting).decode().splitlines() if line.startswith("[")]) == 2
    )
    markdown = to_markdown(meeting).decode()
    assert "<script>" not in markdown
    assert "\\[link\\]" in markdown
    assert "\\|" in markdown


@pytest.mark.parametrize("serializer", [to_txt, to_markdown])
@pytest.mark.parametrize("variant", ["current", "ai_original"])
def test_export_evidence_matches_variant_and_flags_missing_ids(serializer, variant) -> None:
    values = source().model_dump()
    values["summary"]["content"]["key_points"] = [
        {"text": "Ý hiện tại", "evidence_segment_ids": ["seg1", "missing"]}
    ]
    values["summary"]["ai_content"]["key_points"] = [
        {"text": "Ý gốc", "evidence_segment_ids": ["seg2"]}
    ]
    values["action_items"][0]["evidence_segment_ids"] = ["seg1"]
    values["action_items"][0]["needs_review"] = True
    values["action_items"][0]["ai_original"].update(
        evidence_segment_ids=["seg2"], needs_review=False
    )
    result = serializer(MeetingExport.model_validate(values), variant).decode()
    if variant == "current":
        assert "00:00:00 Người phụ trách" in result
        assert "Chưa có bằng chứng, cần kiểm tra" in result
        assert "Cần kiểm tra" in result
    else:
        assert "00:01:05 Speaker 1" in result
        assert "Ý gốc" in result
        assert "Người phụ trách" not in result


def test_export_evidence_fields_have_compatible_defaults() -> None:
    import json

    from app.services.export import to_json

    values = source().model_dump()
    for item in values["action_items"]:
        item.pop("evidence_segment_ids", None)
        item.pop("needs_review", None)
        if item["ai_original"]:
            item["ai_original"].pop("evidence_segment_ids", None)
            item["ai_original"].pop("needs_review", None)
    action = json.loads(to_json(MeetingExport.model_validate(values)))["action_items"][0]
    assert action["evidence_segment_ids"] == []
    assert action["needs_review"] is False
