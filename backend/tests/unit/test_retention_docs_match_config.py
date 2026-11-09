"""RE-018 (14 ngày) và AD-018 (28 ngày): tài liệu và cấu hình không được nói hai con số khác nhau.

Đã từng lệch: `rules/privacy-security.md` ghi "đề xuất 30 ngày" trong khi cấu hình là 14.
"""

import re
from pathlib import Path

import pytest

from app.core.config import Settings

ROOT = Path(__file__).resolve().parents[3]
DOCS = [
    "rules/privacy-security.md",
    "docs/privacy/data-policy.md",
    ".env.example",
    "tasks/ROADMAP.md",
]


def values_for(text: str, name: str) -> set[int]:
    """Các số đứng ngay sau `NAME` (dạng `NAME=14`, `NAME | 14`, `NAME (14 ngày)`)."""
    found = re.findall(rf"{name}\W{{1,6}}(?:đề xuất\s+|mặc định\s+)?(\d+)", text)
    return {int(v) for v in found}


@pytest.mark.parametrize("path", DOCS)
@pytest.mark.parametrize(
    ("name", "default"),
    [
        ("AUDIO_RETENTION_DAYS", Settings().AUDIO_RETENTION_DAYS),
        ("OPERATIONAL_RETENTION_DAYS", Settings().OPERATIONAL_RETENTION_DAYS),
    ],
)
def test_documented_retention_value_equals_default(path: str, name: str, default: int) -> None:
    text = (ROOT / path).read_text(encoding="utf-8")
    assert values_for(text, name) <= {default}, f"{path}: {name} khác mặc định {default}"


def test_the_rules_file_actually_mentions_the_audio_retention() -> None:
    """Chặn trường hợp test xanh vì regex không bắt được gì."""
    text = (ROOT / "rules/privacy-security.md").read_text(encoding="utf-8")
    assert values_for(text, "AUDIO_RETENTION_DAYS"), "regex không tìm thấy giá trị nào"
