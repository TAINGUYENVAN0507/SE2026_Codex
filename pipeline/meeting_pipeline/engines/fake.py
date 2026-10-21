"""Engine giả cho test: trả kết quả cố định hoặc ném lỗi được chỉ định."""

from __future__ import annotations

from dataclasses import dataclass, field

from meeting_pipeline.engines.base import ProgressFn, WavAudio
from meeting_pipeline.stages.asr_post import RawSegment


@dataclass
class FakeAsr:
    segments: list[RawSegment] = field(default_factory=list)
    error: Exception | None = None
    name: str = "fake-asr"

    def transcribe(self, audio: WavAudio, progress: ProgressFn) -> list[RawSegment]:
        if self.error is not None:
            raise self.error
        for seg in self.segments:
            progress(min(seg.end / audio.duration_sec, 1.0) if audio.duration_sec else 1.0)
        return list(self.segments)


@dataclass
class FakeVad:
    regions: list[tuple[float, float]] = field(default_factory=list)
    error: Exception | None = None
    name: str = "fake-vad"

    def speech_regions(self, audio: WavAudio) -> list[tuple[float, float]]:
        if self.error is not None:
            raise self.error
        return list(self.regions)
