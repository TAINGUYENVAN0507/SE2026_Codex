"""Dữ liệu mẫu deterministic cho fake pipeline và fixtures trong `contracts/`.

Cuộc họp giả dài 30 s, 2 speaker, có 1 đoạn nói chen chưa xác định được speaker.
Toàn bộ nội dung là câu tự viết, không lấy từ cuộc họp thật.
"""

from __future__ import annotations

from datetime import date, timedelta

from meeting_pipeline.schemas import ActionItem as SummaryActionItem
from meeting_pipeline.schemas import (
    AsrOutput,
    AsrSegment,
    AudioInfo,
    DiarizeOutput,
    EvidenceItem,
    ModelInfo,
    PipelineWarning,
    PlaybackInfo,
    PreprocessOutput,
    SegmentFlag,
    SourceAudioInfo,
    SpeakerTurn,
    Stage,
    SummaryOutput,
    TimeSpan,
    Transcript,
    TranscriptSegment,
    TranscriptSpeaker,
    VadOutput,
    Word,
)

DURATION_SEC = 30.0
ASR_MODEL = "fake-asr"
VAD_MODEL = "fake-vad"
DIARIZATION_MODEL = "fake-diarization"
LLM_MODEL = "fake-llm"
PROMPT_VERSION = "summary-fake-v1"

# (start, end, speaker_label, text, confidence, flags)
_UTTERANCES: list[tuple[float, float, str | None, str, float | None, list[SegmentFlag]]] = [
    (0.5, 5.8, "SPEAKER_00", "Chào mọi người, hôm nay mình chốt phạm vi sprint 42 nhé.", 0.91, []),
    (
        6.0,
        11.2,
        "SPEAKER_01",
        "Em đề xuất làm xong API upload trước, có chống tạo trùng khi retry.",
        0.86,
        [],
    ),
    (
        11.4,
        16.9,
        "SPEAKER_00",
        "Đồng ý. Anh Minh phụ trách phần upload, hạn thứ Sáu tuần này.",
        0.88,
        [],
    ),
    (17.0, 21.5, "SPEAKER_01", "Còn export DOCX thì mình lùi sang sau MVP.", 0.84, []),
    (21.3, 22.4, None, "Ừ, được.", 0.42, [SegmentFlag.OVERLAP, SegmentFlag.LOW_CONFIDENCE]),
    (
        23.0,
        28.6,
        "SPEAKER_00",
        "Vậy tuần này cần tìm thêm audio có tiếng ồn để đánh giá.",
        0.89,
        [],
    ),
]

_TURNS: list[tuple[float, float, str]] = [
    (0.4, 5.9, "SPEAKER_00"),
    (5.9, 11.3, "SPEAKER_01"),
    (11.3, 17.0, "SPEAKER_00"),
    (17.0, 22.5, "SPEAKER_01"),
    (22.9, 28.8, "SPEAKER_00"),
]


def _words(start: float, end: float, text: str, confidence: float | None) -> list[Word]:
    """Chia đều thời gian của segment cho từng từ."""
    tokens = text.split()
    step = (end - start) / len(tokens)
    return [
        Word(w=tok, s=start + i * step, e=start + (i + 1) * step, p=confidence)
        for i, tok in enumerate(tokens)
    ]


def preprocess_output(size_bytes: int = 0, mime_type: str = "audio/webm") -> PreprocessOutput:
    return PreprocessOutput(
        duration_sec=DURATION_SEC,
        source=SourceAudioInfo(
            format_name="matroska,webm",
            codec="opus",
            sample_rate=48000,
            channels=1,
            header_duration_sec=None,
            size_bytes=size_bytes,
        ),
        playback=PlaybackInfo(source="original", file=None, mime_type=mime_type),
    )


def vad_output() -> VadOutput:
    regions = [TimeSpan(start_sec=0.4, end_sec=22.5), TimeSpan(start_sec=22.9, end_sec=28.8)]
    speech = sum(r.end_sec - r.start_sec for r in regions)
    return VadOutput(
        model=VAD_MODEL, speech_regions=regions, speech_ratio=round(speech / DURATION_SEC, 3)
    )


def asr_output() -> AsrOutput:
    return AsrOutput(
        model=ASR_MODEL,
        language="vi",
        segments=[
            AsrSegment(
                start_sec=start,
                end_sec=end,
                text=text,
                avg_logprob=-0.25 if (conf or 0) > 0.5 else -1.1,
                no_speech_prob=0.02,
                compression_ratio=1.3,
                words=_words(start, end, text, conf),
            )
            for start, end, _, text, conf, _ in _UTTERANCES
        ],
    )


def diarize_output() -> DiarizeOutput:
    turns = [SpeakerTurn(start_sec=s, end_sec=e, speaker_label=lbl) for s, e, lbl in _TURNS]
    return DiarizeOutput(
        model=DIARIZATION_MODEL,
        status="ok",
        num_speakers=len({t.speaker_label for t in turns}),
        turns=turns,
    )


def diarize_fallback_output(reason: str = "") -> DiarizeOutput:
    """Output khi diarization lỗi: không có turn nào, merge gộp thành 1 speaker."""
    return DiarizeOutput(
        model=None,
        status="fallback",
        num_speakers=1,
        turns=[],
        warnings=[
            PipelineWarning(
                code="DIARIZATION_FALLBACK",
                stage=Stage.DIARIZE,
                message=reason or "không tách được speaker, gộp thành 1 speaker",
            )
        ],
    )


def transcript(diarization: DiarizeOutput | None = None) -> Transcript:
    fallback = diarization is not None and diarization.status == "fallback"
    segments = []
    for i, (start, end, label, text, conf, flags) in enumerate(_UTTERANCES):
        if fallback:
            label = "SPEAKER_00"
        segments.append(
            TranscriptSegment(
                index=i,
                start_sec=start,
                end_sec=end,
                speaker_label=label,
                text=text,
                confidence=conf,
                flags=list(flags),
                words=_words(start, end, text, conf),
            )
        )
    first_seen: dict[str, float] = {}
    for seg in segments:
        if seg.speaker_label is not None:
            first_seen.setdefault(seg.speaker_label, seg.start_sec)
    return Transcript(
        audio=AudioInfo(duration_sec=DURATION_SEC, sample_rate=16000, channels=1),
        models=ModelInfo(asr=ASR_MODEL, diarization=None if fallback else DIARIZATION_MODEL),
        diarization_status="fallback" if fallback else "ok",
        speakers=[TranscriptSpeaker(label=lbl, first_start_sec=t) for lbl, t in first_seen.items()],
        segments=segments,
        warnings=list(diarization.warnings) if fallback and diarization else [],
    )


def _this_friday(d: date) -> date:
    return d + timedelta(days=(4 - d.weekday()) % 7)


def summary_output(meeting_date: date | None = None) -> SummaryOutput:
    return SummaryOutput(
        status="ready",
        model=LLM_MODEL,
        prompt_version=PROMPT_VERSION,
        overview=(
            "Nhóm chốt phạm vi sprint 42: ưu tiên API upload có chống tạo trùng, "
            "lùi export DOCX sang sau MVP."
        ),
        key_points=[
            EvidenceItem(
                text="API upload phải chống tạo meeting trùng khi retry.",
                evidence_segment_indices=[1],
            )
        ],
        decisions=[
            EvidenceItem(text="Lùi export DOCX sang sau MVP.", evidence_segment_indices=[3])
        ],
        action_items=[
            SummaryActionItem(
                description="Hoàn thiện API upload audio",
                assignee_name="Anh Minh",
                assignee_speaker_label=None,
                due_date=_this_friday(meeting_date) if meeting_date else None,
                due_date_text="thứ Sáu tuần này",
                evidence_segment_indices=[2],
                needs_review=meeting_date is None,
            ),
            SummaryActionItem(
                description="Tìm thêm audio có tiếng ồn để đánh giá",
                assignee_name=None,
                assignee_speaker_label=None,
                due_date=None,
                due_date_text=None,
                evidence_segment_indices=[5],
                needs_review=False,
            ),
        ],
    )


def summary_insufficient() -> SummaryOutput:
    return SummaryOutput(
        status="insufficient_content",
        model=LLM_MODEL,
        prompt_version=PROMPT_VERSION,
        overview=None,
    )
