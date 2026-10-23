"""Kiểm thử tính năng xác thực file âm thanh tải lên qua whitelist và ffprobe (BE-04)."""

import json
import shutil
import subprocess
import wave
from pathlib import Path

import pytest

from app.core.errors import APIError
from app.services.audio_validator import (
    probe_audio,
    validate_audio_file,
    validate_extension_and_mime,
)


@pytest.fixture
def sample_wav_file(tmp_path: Path) -> Path:
    """Tạo một file wav hợp lệ chuẩn 16kHz mono thời lượng 1 giây bằng thư viện wave chuẩn."""
    wav_path = tmp_path / "valid_meeting.wav"
    with wave.open(str(wav_path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        # 16000 mẫu âm thanh (mỗi mẫu 2 byte) tương đương 1 giây
        wf.writeframes(b"\x00\x00" * 16000)
    return wav_path


@pytest.fixture
def fake_mp3_txt_file(tmp_path: Path) -> Path:
    """Tạo một file text bình thường nhưng đổi phần mở rộng thành .mp3."""
    fake_path = tmp_path / "fake_audio.mp3"
    fake_path.write_text(
        "Đây là nội dung văn bản thuần túy, hoàn toàn không có âm thanh.",
        encoding="utf-8",
    )
    return fake_path


def test_validate_extension_invalid_raises_415() -> None:
    """Đuôi file lạ không nằm trong whitelist phải ném 415 UNSUPPORTED_MEDIA_TYPE."""
    with pytest.raises(APIError) as exc_info:
        validate_extension_and_mime("document.pdf", "application/pdf")
    assert exc_info.value.status_code == 415
    assert exc_info.value.code == "UNSUPPORTED_MEDIA_TYPE"

    with pytest.raises(APIError) as exc_info2:
        validate_extension_and_mime("script.exe")
    assert exc_info2.value.status_code == 415
    assert exc_info2.value.code == "UNSUPPORTED_MEDIA_TYPE"

    with pytest.raises(APIError) as exc_info3:
        validate_extension_and_mime("no_extension_file")
    assert exc_info3.value.status_code == 415
    assert exc_info3.value.code == "UNSUPPORTED_MEDIA_TYPE"


def test_validate_mime_invalid_raises_415() -> None:
    """MIME type không hợp lệ phải ném 415 UNSUPPORTED_MEDIA_TYPE."""
    with pytest.raises(APIError) as exc_info:
        validate_extension_and_mime("audio.mp3", "application/x-executable")
    assert exc_info.value.status_code == 415
    assert exc_info.value.code == "UNSUPPORTED_MEDIA_TYPE"


def test_validate_valid_extension_and_mime_passes() -> None:
    """Các đuôi và MIME hợp lệ phải vượt qua bước kiểm tra định dạng sơ bộ."""
    assert validate_extension_and_mime("meeting.wav", "audio/wav") == "wav"
    assert validate_extension_and_mime("meeting.mp3", "audio/mpeg") == "mp3"
    assert validate_extension_and_mime("meeting.m4a", "audio/mp4") == "m4a"
    assert validate_extension_and_mime("record.webm", "audio/webm; codecs=opus") == "webm"


def test_ffprobe_valid_wav_file(sample_wav_file: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Kiểm tra file wav hợp lệ trích xuất đúng thông tin duration, sample_rate, channels."""
    has_ffprobe = shutil.which("ffprobe") is not None

    if not has_ffprobe:
        # Giả lập kết quả trả về từ ffprobe nếu môi trường local không có binary
        mock_output = {
            "streams": [
                {
                    "codec_type": "audio",
                    "sample_rate": "16000",
                    "channels": 1,
                    "duration": "1.000000",
                }
            ],
            "format": {
                "format_name": "wav",
                "duration": "1.000000",
            },
        }

        def mock_run(*args, **kwargs):
            return subprocess.CompletedProcess(
                args=args[0],
                returncode=0,
                stdout=json.dumps(mock_output),
                stderr="",
            )

        monkeypatch.setattr("subprocess.run", mock_run)

    result = probe_audio(sample_wav_file)
    assert result.duration_sec >= 0.99
    assert result.channels == 1
    assert result.sample_rate == 16000


def test_ffprobe_txt_renamed_to_mp3_raises_422(
    fake_mp3_txt_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """File .txt đổi đuôi thành .mp3 bị phát hiện không có audio stream -> ném 422 AUDIO_INVALID."""
    has_ffprobe = shutil.which("ffprobe") is not None

    if not has_ffprobe:
        # Giả lập ffprobe báo lỗi returncode != 0
        def mock_run(*args, **kwargs):
            return subprocess.CompletedProcess(
                args=args[0],
                returncode=1,
                stdout="",
                stderr="Invalid data found when processing input",
            )

        monkeypatch.setattr("subprocess.run", mock_run)

    with pytest.raises(APIError) as exc_info:
        validate_audio_file(
            file_path=fake_mp3_txt_file,
            filename="fake_audio.mp3",
            content_type="audio/mpeg",
        )

    assert exc_info.value.status_code == 422
    assert exc_info.value.code == "AUDIO_INVALID"


def test_ffprobe_timeout_raises_422(sample_wav_file: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """ffprobe bị quá hạn timeout phải ném 422 AUDIO_INVALID."""

    def mock_timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd=args[0], timeout=1.0)

    monkeypatch.setattr("subprocess.run", mock_timeout)

    with pytest.raises(APIError) as exc_info:
        probe_audio(sample_wav_file, timeout_sec=0.1)

    assert exc_info.value.status_code == 422
    assert exc_info.value.code == "AUDIO_INVALID"
