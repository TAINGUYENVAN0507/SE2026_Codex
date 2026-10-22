"""Adapter cho model AI. Stage gọi `asr_engine()`, `vad_engine()`; test thay hai hàm này."""

from meeting_pipeline.engines.base import (
    AsrEngine,
    DiarizeEngine,
    VadEngine,
    WavAudio,
    read_wav,
)


def asr_engine() -> AsrEngine:
    from meeting_pipeline.engines.whisper import FasterWhisperAsr, WhisperConfig

    return FasterWhisperAsr(WhisperConfig.from_env())


def vad_engine() -> VadEngine:
    from meeting_pipeline.engines.whisper import SileroVad

    return SileroVad()


def diarize_engine() -> DiarizeEngine:
    from meeting_pipeline.engines.pyannote import PyannoteConfig, PyannoteDiarizer

    return PyannoteDiarizer(PyannoteConfig.from_env())


__all__ = [
    "AsrEngine",
    "DiarizeEngine",
    "VadEngine",
    "WavAudio",
    "asr_engine",
    "diarize_engine",
    "read_wav",
    "vad_engine",
]
