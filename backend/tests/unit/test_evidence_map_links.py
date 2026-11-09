"""Bản đồ bằng chứng (docs/evidence/README.md) không được trỏ tới file không tồn tại."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
INDEX = ROOT / "docs/evidence/README.md"


def referenced_paths(text: str) -> list[str]:
    """Đường dẫn trong dấu backtick, bỏ phần sau dấu hai chấm và các cụm không phải đường dẫn."""
    out = []
    for token in re.findall(r"`([^`]+)`", text):
        for part in re.split(r",\s*", token):
            if "/" in part and " " not in part and not part.startswith("http"):
                out.append(part)
    return out


def resolve(path: str) -> Path:
    # Mục trong docs/evidence được viết tương đối với thư mục đó (load-247/..., vt-018/...).
    direct = ROOT / path
    return direct if direct.exists() else INDEX.parent / path


def test_every_referenced_file_exists():
    paths = referenced_paths(INDEX.read_text(encoding="utf-8"))
    assert len(paths) >= 15, "regex không bắt được đủ đường dẫn, test vô nghĩa"
    missing = [p for p in paths if not resolve(p).exists()]
    assert not missing, f"bản đồ bằng chứng trỏ tới file không có: {missing}"


def test_negative_control_detects_a_missing_path():
    assert not resolve("docs/evidence/khong-co-file-nay.md").exists()
