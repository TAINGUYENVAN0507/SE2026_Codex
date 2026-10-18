"""Sinh audio edge case bằng ffmpeg ngay lúc test, không commit file audio."""

import shutil
import subprocess
from functools import cache
from pathlib import Path

import pytest

if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
    pytest.skip("cần ffmpeg và ffprobe", allow_module_level=True)


@cache
def encoders() -> str:
    return subprocess.run(
        ["ffmpeg", "-hide_banner", "-encoders"], capture_output=True, text=True
    ).stdout


def opus_args() -> list[str]:
    """libopus nếu có, ngược lại encoder opus native (experimental) của ffmpeg."""
    if " libopus " in encoders():
        return ["-c:a", "libopus"]
    if " opus " in encoders():
        return ["-c:a", "opus", "-strict", "-2"]
    pytest.skip("ffmpeg không có encoder opus")


def ffmpeg(*args: str) -> None:
    subprocess.run(
        ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y", *args], check=True
    )


@pytest.fixture
def audio_dir(tmp_path: Path) -> Path:
    d = tmp_path / "audio"
    d.mkdir()
    return d


def sine(seconds: float, rate: int = 48000, channels: int = 1) -> list[str]:
    layout = "mono" if channels == 1 else "stereo"
    return [
        "-f",
        "lavfi",
        "-i",
        f"sine=frequency=440:sample_rate={rate}:duration={seconds}",
        "-af",
        f"aformat=channel_layouts={layout}",
    ]
