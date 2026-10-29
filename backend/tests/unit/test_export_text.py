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
    assert output == serializer(meeting, variant)
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
    assert len(to_txt(meeting).decode().splitlines()) == 2
    markdown = to_markdown(meeting).decode()
    assert "<script>" not in markdown
    assert "\\[link\\]" in markdown
    assert "\\|" in markdown
