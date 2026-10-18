"""Schema I/O của từng stage trong pipeline.

Đây là nguồn sự thật cho `contracts/pipeline/*.schema.json`. Quy ước theo mục 7.1
của kế hoạch:

- Thời gian tính bằng giây kể từ đầu file audio gốc, làm tròn tới ms.
- Bất biến `0 <= start_sec < end_sec <= duration_sec`.
- Mọi field luôn có mặt; giá trị không biết là `null`, danh sách rỗng là `[]`.
- `schema_version` dạng `1.x`: tăng minor khi thêm field, tăng major khi breaking.

Segment trong pipeline chưa có UUID (UUID do backend cấp khi persist), nên evidence
của summary tham chiếu tới `index` của segment trong transcript.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from enum import StrEnum
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

SCHEMA_VERSION = "1.0"
SUPPORTED_MAJOR = "1"


class Stage(StrEnum):
    PREPROCESS = "preprocess"
    VAD = "vad"
    ASR = "asr"
    DIARIZE = "diarize"
    MERGE = "merge"
    SUMMARIZE = "summarize"


STAGES: tuple[Stage, ...] = tuple(Stage)

# Tên file trong thư mục làm việc của job: artifacts/{meeting_id}/{job_id}/
JOB_FILE = "job.json"
AUDIO_FILE = "audio.wav"
RTTM_FILE = "diarization.rttm"
ARTIFACT_FILES: dict[Stage, str] = {
    Stage.PREPROCESS: "preprocess.json",
    Stage.VAD: "vad.json",
    Stage.ASR: "asr.json",
    Stage.DIARIZE: "diarization.json",
    Stage.MERGE: "transcript.json",
    Stage.SUMMARIZE: "summary.json",
}


def error_file(stage: Stage) -> str:
    return f"{stage.value}.error.json"


SPEAKER_LABEL_PATTERN = r"^SPEAKER_\d{2,}$"
CODE_PATTERN = r"^[A-Z][A-Z0-9_]*$"


class _Model(BaseModel):
    # Schema dạng serialization coi mọi field là required, vì output luôn ghi đủ field.
    model_config = ConfigDict(extra="forbid", json_schema_serialization_defaults_required=True)


class Artifact(_Model):
    """Base cho mọi file JSON mà một stage ghi ra."""

    schema_version: str = Field(default=SCHEMA_VERSION, pattern=r"^\d+\.\d+$")

    @field_validator("schema_version")
    @classmethod
    def _supported_major(cls, v: str) -> str:
        if v.split(".")[0] != SUPPORTED_MAJOR:
            raise ValueError(f"schema_version {v} không được hỗ trợ (cần {SUPPORTED_MAJOR}.x)")
        return v


class PipelineWarning(_Model):
    code: str = Field(pattern=CODE_PATTERN)
    stage: Stage
    message: str


class TimeSpan(_Model):
    start_sec: float = Field(ge=0)
    end_sec: float

    @field_validator("start_sec", "end_sec")
    @classmethod
    def _round_ms(cls, v: float) -> float:
        return round(v, 3)

    @model_validator(mode="after")
    def _start_before_end(self) -> Self:
        if not self.start_sec < self.end_sec:
            raise ValueError(f"cần start_sec < end_sec, nhận {self.start_sec} và {self.end_sec}")
        return self


def _check_sorted(spans: Sequence[TimeSpan], what: str) -> None:
    keys = [(s.start_sec, s.end_sec) for s in spans]
    if keys != sorted(keys):
        raise ValueError(f"{what} phải sắp xếp theo (start_sec, end_sec)")


def _check_within(spans: Sequence[TimeSpan], duration_sec: float, what: str) -> None:
    for s in spans:
        if s.end_sec > duration_sec + 1e-3:
            raise ValueError(f"{what}: end_sec {s.end_sec} vượt duration_sec {duration_sec}")


# --------------------------------------------------------------------------- job


class JobSpec(_Model):
    """Thông tin một job, worker ghi vào `job.json` trước khi chạy pipeline."""

    schema_version: str = Field(default=SCHEMA_VERSION, pattern=r"^\d+\.\d+$")
    meeting_id: str = Field(min_length=1)
    job_id: str = Field(min_length=1)
    audio_path: str = Field(min_length=1, description="Đường dẫn tuyệt đối tới file gốc")
    from_stage: Stage | None = None
    num_speakers_hint: int | None = Field(default=None, ge=1, le=10)
    meeting_date: date | None = None
    language: Literal["vi"] = "vi"
    transcript_override_path: str | None = Field(
        default=None,
        description="Transcript đã sửa, dùng khi chạy lại riêng stage summarize",
    )
    attempt: int = Field(default=1, ge=1)
    max_attempts: int = Field(default=3, ge=1)

    @property
    def is_last_attempt(self) -> bool:
        return self.attempt >= self.max_attempts


# -------------------------------------------------------------------- preprocess


class SourceAudioInfo(_Model):
    format_name: str | None
    codec: str | None
    sample_rate: int | None = Field(ge=1)
    channels: int | None = Field(ge=1)
    header_duration_sec: float | None = Field(
        ge=0, description="Duration đọc từ header, có thể thiếu hoặc sai (WebM)"
    )
    size_bytes: int = Field(ge=0)


class PlaybackInfo(_Model):
    source: Literal["original", "transcoded"]
    file: str | None = Field(description="Tên file trong workdir khi source=transcoded")
    mime_type: str

    @model_validator(mode="after")
    def _file_matches_source(self) -> Self:
        if (self.source == "transcoded") != (self.file is not None):
            raise ValueError("file chỉ có giá trị khi source=transcoded")
        return self


class PreprocessOutput(Artifact):
    duration_sec: float = Field(gt=0, description="Tính bằng cách decode, không đọc header")
    sample_rate: Literal[16000] = 16000
    channels: Literal[1] = 1
    audio_file: str = AUDIO_FILE
    source: SourceAudioInfo
    playback: PlaybackInfo
    warnings: list[PipelineWarning] = []


# --------------------------------------------------------------------------- vad


class VadOutput(Artifact):
    model: str
    speech_regions: list[TimeSpan]
    speech_ratio: float = Field(ge=0, le=1)
    warnings: list[PipelineWarning] = []

    @model_validator(mode="after")
    def _regions_disjoint(self) -> Self:
        _check_sorted(self.speech_regions, "speech_regions")
        for prev, cur in zip(self.speech_regions, self.speech_regions[1:], strict=False):
            if cur.start_sec < prev.end_sec:
                raise ValueError("speech_regions không được chồng lấn")
        return self


# --------------------------------------------------------------------------- asr


class Word(_Model):
    w: str = Field(min_length=1)
    s: float = Field(ge=0)
    e: float = Field(ge=0)
    p: float | None = Field(ge=0, le=1)

    @field_validator("s", "e")
    @classmethod
    def _round_ms(cls, v: float) -> float:
        return round(v, 3)

    @model_validator(mode="after")
    def _ordered(self) -> Self:
        if self.e < self.s:
            raise ValueError(f"word '{self.w}': e < s")
        return self


class AsrSegment(TimeSpan):
    text: str
    avg_logprob: float | None
    no_speech_prob: float | None = Field(ge=0, le=1)
    compression_ratio: float | None = Field(ge=0)
    words: list[Word] = []


class AsrOutput(Artifact):
    model: str
    language: str
    segments: list[AsrSegment]
    warnings: list[PipelineWarning] = []

    @model_validator(mode="after")
    def _sorted(self) -> Self:
        _check_sorted(self.segments, "segments")
        return self


# ----------------------------------------------------------------------- diarize


class SpeakerTurn(TimeSpan):
    speaker_label: str = Field(pattern=SPEAKER_LABEL_PATTERN)


class DiarizeOutput(Artifact):
    model: str | None = Field(description="null khi fallback")
    status: Literal["ok", "fallback"]
    num_speakers: int = Field(ge=0)
    turns: list[SpeakerTurn]
    warnings: list[PipelineWarning] = []

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        _check_sorted(self.turns, "turns")
        labels = {t.speaker_label for t in self.turns}
        if self.status == "ok" and self.num_speakers != len(labels):
            raise ValueError(
                f"num_speakers={self.num_speakers} khác số nhãn trong turns ({len(labels)})"
            )
        return self


# ------------------------------------------------------------ merge / transcript


class SegmentFlag(StrEnum):
    OVERLAP = "overlap"
    LOW_CONFIDENCE = "low_confidence"


class AudioInfo(_Model):
    duration_sec: float = Field(gt=0)
    sample_rate: int = Field(ge=1)
    channels: int = Field(ge=1)


class ModelInfo(_Model):
    asr: str | None
    diarization: str | None


class TranscriptSpeaker(_Model):
    label: str = Field(pattern=SPEAKER_LABEL_PATTERN)
    first_start_sec: float = Field(ge=0)
    display_name: str | None = Field(
        default=None,
        min_length=1,
        max_length=50,
        description="null khi do merge sinh ra; backend điền tên đã sửa khi chạy lại summarize",
    )


class TranscriptSegment(TimeSpan):
    index: int = Field(ge=0)
    speaker_label: str | None = Field(description="null khi chưa xác định được speaker")
    text: str = Field(min_length=1, max_length=5000)
    confidence: float | None = Field(ge=0, le=1)
    flags: list[SegmentFlag] = []
    words: list[Word] = []


class Transcript(Artifact):
    """Output của stage merge (`transcript.json`)."""

    audio: AudioInfo
    models: ModelInfo
    diarization_status: Literal["ok", "fallback"]
    speakers: list[TranscriptSpeaker]
    segments: list[TranscriptSegment]
    warnings: list[PipelineWarning] = []

    @model_validator(mode="after")
    def _invariants(self) -> Self:
        for pos, seg in enumerate(self.segments):
            if seg.index != pos:
                raise ValueError(f"segment ở vị trí {pos} có index {seg.index}")
        _check_sorted(self.segments, "segments")
        _check_within(self.segments, self.audio.duration_sec, "segments")

        for prev, cur in zip(self.segments, self.segments[1:], strict=False):
            overlapping = cur.start_sec < prev.end_sec
            flagged = SegmentFlag.OVERLAP in prev.flags or SegmentFlag.OVERLAP in cur.flags
            if overlapping and not flagged:
                raise ValueError(f"segment {prev.index} và {cur.index} chồng lấn nhưng thiếu cờ")

        labels = [s.label for s in self.speakers]
        if len(labels) != len(set(labels)):
            raise ValueError("speakers có label trùng")
        known = set(labels)
        for seg in self.segments:
            if seg.speaker_label is not None and seg.speaker_label not in known:
                raise ValueError(f"segment {seg.index} dùng speaker lạ {seg.speaker_label}")
        return self


# ---------------------------------------------------------------------- summarize


class EvidenceItem(_Model):
    text: str = Field(min_length=1, max_length=500)
    evidence_segment_indices: list[int] = Field(default=[], description="index trong transcript")


class ActionItem(_Model):
    description: str = Field(min_length=1, max_length=1000)
    assignee_name: str | None
    assignee_speaker_label: str | None = Field(pattern=SPEAKER_LABEL_PATTERN)
    due_date: date | None = Field(description="Chỉ điền khi transcript có căn cứ rõ ràng")
    due_date_text: str | None = Field(description="Cụm từ gốc trong transcript, ví dụ 'thứ Sáu'")
    evidence_segment_indices: list[int] = []
    needs_review: bool


class SummaryOutput(Artifact):
    status: Literal["ready", "insufficient_content", "disabled"]
    model: str | None
    prompt_version: str | None
    overview: str | None = Field(max_length=5000)
    key_points: list[EvidenceItem] = Field(default=[], max_length=50)
    decisions: list[EvidenceItem] = Field(default=[], max_length=50)
    action_items: list[ActionItem] = []
    warnings: list[PipelineWarning] = []

    @model_validator(mode="after")
    def _empty_unless_ready(self) -> Self:
        has_content = (
            self.overview is not None or self.key_points or self.decisions or self.action_items
        )
        if self.status != "ready" and has_content:
            raise ValueError(f"summary status={self.status} không được có nội dung")
        if self.status == "ready" and self.overview is None:
            raise ValueError("summary status=ready cần overview")
        return self


STAGE_OUTPUT_MODELS: dict[Stage, type[Artifact]] = {
    Stage.PREPROCESS: PreprocessOutput,
    Stage.VAD: VadOutput,
    Stage.ASR: AsrOutput,
    Stage.DIARIZE: DiarizeOutput,
    Stage.MERGE: Transcript,
    Stage.SUMMARIZE: SummaryOutput,
}
