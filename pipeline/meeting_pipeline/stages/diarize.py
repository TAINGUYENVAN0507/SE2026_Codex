"""Stage diarize (AI-07): ai nói khi nào, ghi `diarization.json` và `diarization.rttm`.

1. Gọi diarization engine (`engines.diarize_engine()`, mặc định pyannote community-1), truyền
   gợi ý số người nói `num_speakers_hint` của job nếu có.
2. Chuẩn hóa turn: clamp vào thời lượng audio, làm tròn ms, bỏ turn dài 0, sắp xếp. Turn của
   hai người được phép chồng nhau (nói chen).
3. Đổi nhãn của engine sang `SPEAKER_00`, `SPEAKER_01`… theo thứ tự xuất hiện. Merge sẽ đánh
   số lại một lần nữa theo segment của transcript.
4. Ghi RTTM để chấm DER (`evaluation/diarization/run_der.py`).

Lỗi của stage này không làm hỏng job: runner fallback 1 speaker khi lỗi permanent, hoặc khi
lỗi ở lượt retry cuối.
"""

from __future__ import annotations

import os
from collections.abc import Sequence
from pathlib import Path

from meeting_pipeline import engines
from meeting_pipeline.errors import PipelineError
from meeting_pipeline.schemas import (
    AUDIO_FILE,
    RTTM_FILE,
    DiarizeOutput,
    PreprocessOutput,
    SpeakerTurn,
    Stage,
)
from meeting_pipeline.stages.base import StageContext
from meeting_pipeline.timing import clamp


def normalize_turns(raw: Sequence[tuple[float, float, str]], duration: float) -> list[SpeakerTurn]:
    duration = round(duration, 3)
    cleaned = sorted(
        (round(clamp(s, duration), 3), round(clamp(e, duration), 3), label) for s, e, label in raw
    )
    names: dict[str, str] = {}
    turns = []
    for start, end, label in cleaned:
        if end <= start:
            continue
        name = names.setdefault(label, f"SPEAKER_{len(names):02d}")
        turns.append(SpeakerTurn(start_sec=start, end_sec=end, speaker_label=name))
    return turns


def rttm_lines(uri: str, turns: Sequence[SpeakerTurn]) -> list[str]:
    """Dòng RTTM chuẩn: `SPEAKER <uri> 1 <start> <duration> <NA> <NA> <speaker> <NA> <NA>`."""
    return [
        f"SPEAKER {uri} 1 {t.start_sec:.3f} {t.end_sec - t.start_sec:.3f} "
        f"<NA> <NA> {t.speaker_label} <NA> <NA>"
        for t in turns
    ]


def _write_text_atomic(path: Path, text: str) -> None:
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def run(ctx: StageContext) -> DiarizeOutput:
    try:
        return _run(ctx)
    except PipelineError as e:
        if e.stage is None:
            e.stage = ctx.stage
        raise


def _run(ctx: StageContext) -> DiarizeOutput:
    pre = ctx.input(Stage.PREPROCESS)
    assert isinstance(pre, PreprocessOutput)
    audio = engines.read_wav(ctx.workdir / AUDIO_FILE)
    engine = engines.diarize_engine()
    ctx.progress(0.05)

    turns = normalize_turns(engine.turns(audio, ctx.spec.num_speakers_hint), pre.duration_sec)
    ctx.progress(0.9)
    lines = rttm_lines(ctx.spec.meeting_id, turns)
    _write_text_atomic(ctx.workdir / RTTM_FILE, "".join(line + "\n" for line in lines))
    return DiarizeOutput(
        model=engine.name,
        status="ok",
        num_speakers=len({t.speaker_label for t in turns}),
        turns=turns,
    )
