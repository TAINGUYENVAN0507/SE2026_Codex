"""Adapter cho model AI. Stage gọi `asr_engine()`, `vad_engine()`; test thay hai hàm này."""

from meeting_pipeline.engines.base import AsrEngine, VadEngine, WavAudio, read_wav


def asr_engine() -> AsrEngine:
    from meeting_pipeline.engines.whisper import FasterWhisperAsr, WhisperConfig

    return FasterWhisperAsr(WhisperConfig.from_env())


def vad_engine() -> VadEngine:
    from meeting_pipeline.engines.whisper import SileroVad

    return SileroVad()


__all__ = ["AsrEngine", "VadEngine", "WavAudio", "asr_engine", "read_wav", "vad_engine"]
