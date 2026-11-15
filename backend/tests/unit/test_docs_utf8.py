"""File văn bản trong `docs/` và `tasks/` phải là UTF-8 (G0).

PowerShell `>` ghi UTF-16 LE có BOM. GitHub hiện file đó là nhị phân, nên người đọc bằng chứng
không mở được log trên trình duyệt. Đã xảy ra hai lần:
`docs/evidence/ad-018/deletion-2026-11-12.log` (#54) và
`docs/evidence/final/summary-partial-red-2026-11-13.log` (#56).

BOM UTF-8 được chấp nhận: Windows PowerShell 5.1 `Out-File -Encoding utf8` ghi BOM, và GitHub vẫn
hiện file đó là văn bản.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DIRS = ("docs", "tasks")
TEXT_SUFFIXES = {".md", ".log", ".txt", ".csv", ".json", ".stdout", ".sh", ".py", ".yml", ".yaml"}


def encoding_problem(data: bytes) -> str | None:
    """Trả lý do nếu `data` không phải UTF-8 (có hoặc không BOM), ngược lại trả None."""
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        return "BOM UTF-16"
    if b"\x00" in data:
        return "có byte NUL (UTF-16 không BOM?)"
    try:
        data.decode("utf-8")
    except UnicodeDecodeError as e:
        return f"không phải UTF-8 (byte {e.start})"
    return None


def text_files() -> list[Path]:
    return sorted(
        p
        for d in DIRS
        for p in (ROOT / d).rglob("*")
        if p.is_file() and p.suffix.lower() in TEXT_SUFFIXES
    )


def test_every_text_file_in_docs_and_tasks_is_utf8() -> None:
    files = text_files()
    assert len(files) >= 300, "không tìm thấy đủ file, test vô nghĩa"
    bad = {
        str(p.relative_to(ROOT)): why
        for p in files
        if (why := encoding_problem(p.read_bytes())) is not None
    }
    assert not bad, (
        f"file không phải UTF-8: {bad}. Trên Windows ghi log bằng "
        "`... 2>&1 | Out-File -Encoding utf8 <file>`, không dùng `>`."
    )


def test_negative_control_flags_powershell_output() -> None:
    text = "Kiểm tra 1 passed\r\n"
    assert encoding_problem(b"\xff\xfe" + text.encode("utf-16-le")) == "BOM UTF-16"
    assert encoding_problem("1 passed".encode("utf-16-le")) == "có byte NUL (UTF-16 không BOM?)"
    assert encoding_problem(b"\xef\xbb\xbf" + text.encode("utf-8")) is None
    assert encoding_problem("café".encode("latin-1")) == "không phải UTF-8 (byte 3)"
    assert encoding_problem(text.encode("utf-8")) is None
