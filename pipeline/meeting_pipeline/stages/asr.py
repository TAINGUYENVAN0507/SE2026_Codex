"""Stage asr (AI-06): nhận dạng tiếng nói trên `audio.wav`, ghi `asr.json`.

1. Cần `preprocess.json` (thời lượng) và `vad.json` (VAD đã xác nhận có lời nói).
2. Gọi ASR engine (`engines.asr_engine()`, mặc định faster-whisper theo ADR-0001).
3. `normalize_segments()`: timestamp hợp lệ, word nằm trong segment.
4. `filter_hallucinations()`: bỏ hoặc cắt đoạn Whisper bịa ra, kèm warning chỉ ghi số lượng.

Lỗi: CUDA OOM là transient `OUT_OF_MEMORY` (worker retry); không load được model là
permanent `MODEL_UNAVAILABLE`. Cả hai do engine ném ra.
"""

from __future__ import annotations

from meeting_pipeline import engines
from meeting_pipeline.errors import PipelineError
from meeting_pipeline.schemas import AUDIO_FILE, AsrOutput, PreprocessOutput, Stage
from meeting_pipeline.stages.asr_post import filter_hallucinations, normalize_segments
from meeting_pipeline.stages.base import StageContext

LANGUAGE = "vi"


def run(ctx: StageContext) -> AsrOutput:
    try:
        return _run(ctx)
    except PipelineError as e:
        if e.stage is None:
            e.stage = ctx.stage
        raise


def _run(ctx: StageContext) -> AsrOutput:
    pre = ctx.input(Stage.PREPROCESS)
    assert isinstance(pre, PreprocessOutput)
    ctx.input(Stage.VAD)
    audio = engines.read_wav(ctx.workdir / AUDIO_FILE)
    engine = engines.asr_engine()
    ctx.progress(0.05)

    raw = engine.transcribe(audio, lambda v: ctx.progress(0.05 + 0.9 * v))
    segments, warnings = filter_hallucinations(normalize_segments(raw, pre.duration_sec))
    return AsrOutput(model=engine.name, language=LANGUAGE, segments=segments, warnings=warnings)
