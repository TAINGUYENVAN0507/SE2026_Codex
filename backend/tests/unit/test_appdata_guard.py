"""Kiểm thử guard bảo vệ appdata không xóa thư mục rò rỉ (BE-16)."""

from pathlib import Path

import pytest

from tests.conftest import check_directory_leak, snapshot_directory_entries


def test_guard_detects_leak_without_deleting_directory(tmp_path: Path) -> None:
    """Guard phải phát hiện và báo lỗi khi có thư mục mới, nhưng KHÔNG xóa bất kỳ file nào.

    Thư mục bị rò rỉ vẫn phải tồn tại nguyên vẹn sau khi ném lỗi (BE-16).
    """
    watch_dir = tmp_path / "audio"
    watch_dir.mkdir(parents=True)
    before = snapshot_directory_entries(watch_dir)

    # Giả lập một test bị rò rỉ ghi thư mục vào watch_dir
    leaked_dir = watch_dir / "meeting-leak-uuid-1234"
    leaked_dir.mkdir()
    sample_file = leaked_dir / "original.wav"
    sample_file.write_text("dummy-audio-content", encoding="utf-8")

    # Guard phải ném lỗi AssertionError và ghi rõ tên thư mục bị rò rỉ
    with pytest.raises(AssertionError) as exc_info:
        check_directory_leak(watch_dir, before)

    assert "meeting-leak-uuid-1234" in str(exc_info.value)
    assert "Test phải sử dụng storage tạm" in str(exc_info.value)

    # KHẲNG ĐỊNH: thư mục và file không bị xóa
    assert leaked_dir.exists(), "Thư mục bị rò rỉ không được phép bị xóa bởi guard"
    assert sample_file.exists(), "Tập tin trong thư mục bị rò rỉ phải được bảo toàn"
    assert sample_file.read_text(encoding="utf-8") == "dummy-audio-content"


def test_guard_passes_when_no_new_directory(tmp_path: Path) -> None:
    """Guard không báo lỗi khi không có thư mục mới xuất hiện."""
    watch_dir = tmp_path / "audio"
    watch_dir.mkdir(parents=True)
    existing_dir = watch_dir / "existing-dir"
    existing_dir.mkdir()

    before = snapshot_directory_entries(watch_dir)

    # Không có thư mục mới được tạo
    result = check_directory_leak(watch_dir, before)
    assert result == []
