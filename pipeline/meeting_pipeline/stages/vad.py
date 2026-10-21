"""Stage vad (AI-06): tìm các đoạn có lời nói trong `audio.wav`.

- Gọi VAD engine (Silero qua `engines.vad_engine()`), đổi region thô thành `TimeSpan`:
  clamp vào thời lượng audio, làm tròn ms, bỏ region dài 0, gộp region chồng hoặc chạm nhau.
- Tổng thời lượng lời nói dưới `MIN_SPEECH_SEC` thì lỗi permanent `NO_SPEECH_DETECTED`:
  không có gì để nhận dạng, retry cũng không đổi kết quả. Đây cũng là chốt chặn đầu tiên
  chống hallucination của Whisper trên audio im lặng.

`speech_ratio` = tổng lời nói / thời lượng audio, dùng để cảnh báo audio gần như im lặng.
"""

from __future__ import annotations

from collections.abc import Sequence

from meeting_pipeline import engines
from meeting_pipeline.errors import ErrorCode, PermanentPipelineError, PipelineError
from meeting_pipeline.schemas import AUDIO_FILE, PreprocessOutput, Stage, TimeSpan, VadOutput
from meeting_pipeline.stages.base import StageContext
from meeting_pipeline.timing import clamp

# Giá trị khởi tạo: dưới nửa giây lời nói thì coi như không có lời nói.
MIN_SPEECH_SEC = 0.5


def to_spans(raw: Sequence[tuple[float, float]], duration: float) -> list[TimeSpan]:
    """Region thô của engine thành danh sách `TimeSpan` đã sắp xếp, không chồng lấn."""
    cleaned = sorted(
        (round(clamp(s, duration), 3), round(clamp(e, duration), 3)) for s, e in raw if e > s
    )
    merged: list[list[float]] = []
    for start, end in cleaned:
        if end <= start:
            continue
        if merged and start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return [TimeSpan(start_sec=s, end_sec=e) for s, e in merged]


def run(ctx: StageContext) -> VadOutput:
    try:
        return _run(ctx)
    except PipelineError as e:
        if e.stage is None:
            e.stage = ctx.stage
        raise


def _run(ctx: StageContext) -> VadOutput:
    pre = ctx.input(Stage.PREPROCESS)
    assert isinstance(pre, PreprocessOutput)
    audio = engines.read_wav(ctx.workdir / AUDIO_FILE)
    engine = engines.vad_engine()
    ctx.progress(0.1)

    regions = to_spans(engine.speech_regions(audio), pre.duration_sec)
    speech = sum(r.end_sec - r.start_sec for r in regions)
    if speech < MIN_SPEECH_SEC:
        raise PermanentPipelineError(
            ErrorCode.NO_SPEECH_DETECTED,
            ctx.stage,
            f"chỉ phát hiện {speech:.1f} s lời nói, tối thiểu {MIN_SPEECH_SEC} s",
            {"speech_sec": round(speech, 3), "min_speech_sec": MIN_SPEECH_SEC},
        )
    return VadOutput(
        model=engine.name,
        speech_regions=regions,
        speech_ratio=round(min(speech / pre.duration_sec, 1.0), 3),
    )
