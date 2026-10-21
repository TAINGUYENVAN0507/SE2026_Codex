"""Interface của engine ASR và VAD, và cách đọc `audio.wav` của stage preprocess.

Stage chỉ biết các interface này, không import thư viện model. Nhờ vậy CI chạy test bằng
engine giả mà không cần cài faster-whisper hay GPU, và đổi model sau này không đụng tới
stage (ADR-0001).
"""

from __future__ import annotations

import wave
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from meeting_pipeline.errors import ErrorCode, PermanentPipelineError
from meeting_pipeline.stages.asr_post import RawSegment

ProgressFn = Callable[[float], None]


@dataclass(frozen=True)
class WavAudio:
    """Thông tin của `audio.wav` (16 kHz, mono, PCM s16), chưa đọc mẫu vào bộ nhớ."""

    path: Path
    sample_rate: int
    num_frames: int

    @property
    def duration_sec(self) -> float:
        return self.num_frames / self.sample_rate


def read_wav(path: Path, sample_rate: int = 16000) -> WavAudio:
    """Đọc header và kiểm định dạng. Sai định dạng là lỗi của preprocess: permanent."""
    try:
        with wave.open(str(path), "rb") as w:
            channels, width, rate, frames = (
                w.getnchannels(),
                w.getsampwidth(),
                w.getframerate(),
                w.getnframes(),
            )
    except (OSError, wave.Error, EOFError):
        raise PermanentPipelineError(
            ErrorCode.MISSING_INPUT, None, f"không đọc được {path.name}"
        ) from None
    if (channels, width, rate) != (1, 2, sample_rate):
        raise PermanentPipelineError(
            ErrorCode.AUDIO_INVALID,
            None,
            f"{path.name} cần mono s16 {sample_rate} Hz, nhận {channels} kênh, "
            f"{width * 8} bit, {rate} Hz",
        )
    return WavAudio(path=path, sample_rate=rate, num_frames=frames)


def load_float32(audio: WavAudio) -> Any:
    """Mẫu audio dạng numpy float32 trong [-1, 1]. Import numpy trong hàm: CI không cài."""
    import numpy as np

    with wave.open(str(audio.path), "rb") as w:
        raw = w.readframes(w.getnframes())
    return np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0


class AsrEngine(Protocol):
    name: str

    def transcribe(self, audio: WavAudio, progress: ProgressFn) -> list[RawSegment]: ...


class VadEngine(Protocol):
    name: str

    def speech_regions(self, audio: WavAudio) -> list[tuple[float, float]]: ...
