"""Kiểm thử dịch vụ lưu trữ Storage: chunked write, sha256, giới hạn kích thước và cleanup."""

import hashlib
import io
import shutil
import tempfile
import uuid
from pathlib import Path

import pytest

from app.services.storage.base import FileTooLargeError
from app.services.storage.local import LocalStorage


@pytest.fixture
def temp_storage():
    """Tạo LocalStorage với thư mục tạm thời, dọn sạch sau khi test."""
    temp_dir = tempfile.mkdtemp()
    storage = LocalStorage(base_dir=temp_dir, max_upload_mb=2, chunk_size=1024)
    try:
        yield storage, temp_dir
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_save_small_file_content_and_sha256(temp_storage):
    """File nhỏ ghi đúng nội dung, sha256, atomic move và không để lại file tạm."""
    storage, temp_dir = temp_storage
    meeting_id = str(uuid.uuid4())
    content = b"Mock audio content chunked test 1234567890" * 100
    expected_sha256 = hashlib.sha256(content).hexdigest()

    # Ghi file thông qua BytesIO stream
    stream = io.BytesIO(content)
    result = storage.save_upload(meeting_id, "mp3", stream)

    assert result.path == f"audio/{meeting_id}/original.mp3"
    assert result.sha256 == expected_sha256
    assert result.size_bytes == len(content)

    # Kiểm tra file vật lý tồn tại và nội dung chuẩn xác
    physical_path = storage.get_audio_path(meeting_id, "mp3")
    assert physical_path.exists()
    assert physical_path.read_bytes() == content

    # Đảm bảo không còn bất kỳ file tạm nào trong thư mục
    meeting_dir = storage.get_audio_dir(meeting_id)
    tmp_files = list(meeting_dir.glob("*.tmp"))
    assert len(tmp_files) == 0


def test_file_too_large_aborts_and_cleans_temp(temp_storage):
    """File vượt giới hạn MAX_UPLOAD_MB bị dừng, báo lỗi FILE_TOO_LARGE và xóa sạch file tạm."""
    storage, temp_dir = temp_storage
    meeting_id = str(uuid.uuid4())

    # Giới hạn của fixture là 2 MB (2 * 1024 * 1024 = 2,097,152 bytes)
    # Tạo content 2.5 MB
    oversized_content = b"A" * (2500 * 1024)
    stream = io.BytesIO(oversized_content)

    with pytest.raises(FileTooLargeError) as exc_info:
        storage.save_upload(meeting_id, "wav", stream)

    assert exc_info.value.code == "FILE_TOO_LARGE"

    # Kiểm tra không tạo file đích và không để lại file tạm
    meeting_dir = storage.get_audio_dir(meeting_id)
    if meeting_dir.exists():
        files = list(meeting_dir.iterdir())
        assert len(files) == 0


def test_interrupted_upload_cleans_temp(temp_storage):
    """Lỗi phát sinh giữa chừng trong quá trình upload cũng dọn sạch file tạm."""
    storage, temp_dir = temp_storage
    meeting_id = str(uuid.uuid4())

    def failing_stream():
        yield b"chunk_1"
        yield b"chunk_2"
        raise RuntimeError("Mất kết nối đường truyền mạng giữa chừng")

    with pytest.raises(RuntimeError):
        storage.save_upload(meeting_id, "m4a", failing_stream())

    # Kiểm tra không để lại file tạm
    meeting_dir = storage.get_audio_dir(meeting_id)
    if meeting_dir.exists():
        tmp_files = list(meeting_dir.glob("*.tmp"))
        assert len(tmp_files) == 0
        target_file = storage.get_audio_path(meeting_id, "m4a")
        assert not target_file.exists()


def test_delete_meeting_files(temp_storage):
    """Xóa toàn bộ thư mục audio của meeting."""
    storage, temp_dir = temp_storage
    meeting_id = str(uuid.uuid4())
    content = b"Sample audio"
    storage.save_upload(meeting_id, "ogg", io.BytesIO(content))

    target_file = storage.get_audio_path(meeting_id, "ogg")
    assert target_file.exists()

    storage.delete_meeting_files(meeting_id)
    assert not target_file.exists()
    assert not storage.get_audio_dir(meeting_id).exists()


def test_resolve_audio_uses_canonical_then_safe_fallback(tmp_path: Path) -> None:
    """File gốc được ưu tiên; đường dẫn dự phòng trong storage vẫn dùng được."""
    storage = LocalStorage(base_dir=tmp_path)
    meeting_id = str(uuid.uuid4())
    fallback = tmp_path / "legacy.wav"
    fallback.write_bytes(b"legacy")
    storage.save_upload(meeting_id, "wav", b"original")
    canonical = storage.get_audio_path(meeting_id, "wav")
    assert storage.resolve_audio_file(meeting_id, "legacy.wav") == canonical
    assert storage.get_audio_size(meeting_id, "wav", "legacy.wav") == 8
    canonical.unlink()
    assert storage.resolve_audio_file(meeting_id, "legacy.wav") == fallback
    assert storage.get_audio_size(meeting_id, "wav", "legacy.wav") == 6
    fallback.unlink()
    assert storage.resolve_audio_file(meeting_id, "legacy.wav") is None
    assert storage.resolve_audio_file(meeting_id, None) is None


@pytest.mark.parametrize("absolute", [False, True])
def test_resolve_audio_rejects_paths_outside_storage(tmp_path: Path, absolute: bool) -> None:
    """Cả đường dẫn tuyệt đối lẫn ../ đều không được đọc file ngoài storage."""
    storage = LocalStorage(base_dir=tmp_path / "storage")
    outside = tmp_path / "outside.wav"
    outside.write_bytes(b"outside")
    audio_path = str(outside) if absolute else "../outside.wav"
    meeting_id = str(uuid.uuid4())
    assert storage.resolve_audio_file(meeting_id, audio_path) is None
    assert storage.get_audio_size(meeting_id, "wav", audio_path) is None
