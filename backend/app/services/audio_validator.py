"""Dịch vụ kiểm tra và xác thực tính hợp lệ của tệp âm thanh (BE-04)."""

import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

from fastapi import status

from app.core.errors import APIError

SUPPORTED_EXTENSIONS = {"wav", "mp3", "m4a", "aac", "flac", "ogg", "webm"}

SUPPORTED_MIME_TYPES = {
    "audio/wav",
    "audio/x-wav",
    "audio/wave",
    "audio/mpeg",
    "audio/mp3",
    "audio/mp4",
    "audio/x-m4a",
    "audio/m4a",
    "audio/aac",
    "audio/x-aac",
    "audio/flac",
    "audio/x-flac",
    "audio/ogg",
    "audio/vorbis",
    "audio/webm",
    "application/octet-stream",
}


@dataclass
class AudioProbeResult:
    """Kết quả phân tích tệp âm thanh qua ffprobe."""

    duration_sec: float
    format_name: str
    sample_rate: int | None = None
    channels: int | None = None


def validate_extension_and_mime(filename: str, content_type: str | None = None) -> str:
    """Kiểm tra whitelist phần mở rộng và MIME type của tệp."""
    if "." not in filename:
        raise APIError(
            code="UNSUPPORTED_MEDIA_TYPE",
            message="Tệp không có phần mở rộng hợp lệ.",
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
        )

    ext = filename.rsplit(".", 1)[-1].lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise APIError(
            code="UNSUPPORTED_MEDIA_TYPE",
            message=f"Định dạng tệp '.{ext}' không được hỗ trợ.",
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
        )

    if content_type:
        clean_mime = content_type.split(";")[0].strip().lower()
        if clean_mime not in SUPPORTED_MIME_TYPES:
            raise APIError(
                code="UNSUPPORTED_MEDIA_TYPE",
                message=f"Định dạng MIME '{clean_mime}' không được hỗ trợ.",
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            )

    return ext


def probe_audio(
    file_path: Path | str,
    timeout_sec: float = 10.0,
    ffprobe_bin: str | None = None,
) -> AudioProbeResult:
    """Sử dụng ffprobe để xác thực stream âm thanh và trích xuất metadata."""
    bin_path = ffprobe_bin or os.environ.get("FFPROBE_BIN", "ffprobe")
    cmd = [
        bin_path,
        "-v",
        "error",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        str(file_path),
    ]

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_sec,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise APIError(
            code="AUDIO_INVALID",
            message="Quá thời gian kiểm tra tệp âm thanh bằng ffprobe.",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        ) from exc
    except FileNotFoundError as exc:
        raise APIError(
            code="INTERNAL_SERVER_ERROR",
            message="Công cụ ffprobe không khả dụng trên hệ thống.",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        ) from exc

    if proc.returncode != 0:
        raise APIError(
            code="AUDIO_INVALID",
            message="Tệp âm thanh bị lỗi hoặc không thể giải mã.",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    try:
        data = json.loads(proc.stdout)
    except Exception as exc:
        raise APIError(
            code="AUDIO_INVALID",
            message="Kết quả phân tích từ ffprobe không đúng cấu trúc JSON.",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        ) from exc

    streams = data.get("streams", [])
    audio_streams = [s for s in streams if s.get("codec_type") == "audio"]
    if not audio_streams:
        raise APIError(
            code="AUDIO_INVALID",
            message="Tệp tải lên không chứa luồng âm thanh (audio stream) hợp lệ.",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    audio = audio_streams[0]
    format_info = data.get("format", {})

    duration_raw = audio.get("duration") or format_info.get("duration")
    try:
        duration_sec = float(duration_raw) if duration_raw is not None else 0.0
    except (ValueError, TypeError):
        duration_sec = 0.0

    sample_rate_raw = audio.get("sample_rate")
    sample_rate = int(sample_rate_raw) if sample_rate_raw and sample_rate_raw.isdigit() else None

    channels = audio.get("channels")
    format_name = format_info.get("format_name", "")

    return AudioProbeResult(
        duration_sec=duration_sec,
        format_name=format_name,
        sample_rate=sample_rate,
        channels=channels,
    )


def validate_audio_file(
    file_path: Path | str,
    filename: str,
    content_type: str | None = None,
    timeout_sec: float = 10.0,
    ffprobe_bin: str | None = None,
) -> AudioProbeResult:
    """Xác thực toàn diện tệp âm thanh: whitelist đuôi, MIME và cấu trúc audio qua ffprobe."""
    validate_extension_and_mime(filename, content_type)
    return probe_audio(file_path, timeout_sec=timeout_sec, ffprobe_bin=ffprobe_bin)
