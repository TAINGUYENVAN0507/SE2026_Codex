"""Kiểm thử cấu hình STORAGE_DIR cho LocalStorage, API và Worker (BE-16)."""

import io
from pathlib import Path

import pytest

from app.core.config import Settings, get_settings
from app.services.storage import get_storage
from app.services.storage.local import LocalStorage


def test_storage_dir_default_is_backend_appdata(monkeypatch: pytest.MonkeyPatch) -> None:
    """Mặc định khi không đặt STORAGE_DIR, storage trỏ đúng vào backend/appdata."""
    monkeypatch.delenv("STORAGE_DIR", raising=False)
    get_settings.cache_clear()

    default_settings = Settings()
    expected_default = (Path(__file__).resolve().parent.parent.parent / "appdata").resolve()
    assert Path(default_settings.STORAGE_DIR).resolve() == expected_default

    # Nếu truyền settings mặc định thì storage trỏ về appdata
    monkeypatch.setattr("app.services.storage.local.get_settings", lambda: default_settings)
    assert LocalStorage().base_dir == expected_default


def test_storage_dir_custom_env_affects_api_and_worker(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Khi đặt biến STORAGE_DIR, cả API và worker (qua get_storage) cùng dùng thư mục đó (BE-16)."""
    custom_dir = tmp_path / "custom_storage_dir"
    custom_dir.mkdir(parents=True)

    monkeypatch.setenv("STORAGE_DIR", str(custom_dir))
    get_settings.cache_clear()
    get_storage.cache_clear()

    try:
        # 1. API: LocalStorage() không tham số sử dụng STORAGE_DIR
        api_storage = LocalStorage()
        assert api_storage.base_dir == custom_dir.resolve()

        # 2. Worker: get_storage() singleton sử dụng STORAGE_DIR
        worker_storage = get_storage()
        assert worker_storage.base_dir == custom_dir.resolve()

        # 3. Ghi file thử qua storage: file phải nằm trong custom_dir
        meeting_id = "test-meeting-storage-dir-1234"
        content = b"RIFF-WAVE-TEST-CONTENT"
        upload_result = api_storage.save_upload(
            meeting_id=meeting_id,
            extension="wav",
            stream=io.BytesIO(content),
        )
        abs_saved_file = custom_dir / upload_result.path
        assert abs_saved_file.exists()
        assert abs_saved_file.read_bytes() == content

        # Khẳng định worker đọc đúng file audio từ đường dẫn đó
        audio_path = worker_storage.get_audio_path(meeting_id, "wav")
        assert audio_path == abs_saved_file
        assert audio_path.is_file()
    finally:
        get_settings.cache_clear()
        get_storage.cache_clear()


def test_session_storage_is_temporary_in_tests() -> None:
    """Toàn bộ phiên test pytest sử dụng thư mục tạm, không chạm appdata thật."""
    current_storage = LocalStorage()
    real_appdata = (Path(__file__).resolve().parent.parent.parent / "appdata").resolve()
    assert current_storage.base_dir != real_appdata
    assert "codex_test_storage_" in str(current_storage.base_dir)
