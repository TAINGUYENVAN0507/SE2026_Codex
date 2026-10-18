"""Fake stages cho backend (worker, test reliability) và E2E của frontend.

Chọn kịch bản bằng biến môi trường `FAKE_SCENARIO`:

| Kịch bản | Hành vi |
|---|---|
| `ok` (mặc định) | Mọi stage thành công, ra dữ liệu mẫu trong `fake/data.py` |
| `slow` | Mỗi stage ngủ `FAKE_STAGE_SLEEP_SEC` giây (mặc định 1) và báo progress |
| `transient_once` | `asr` lỗi transient ở lần chạy đầu, lần sau thành công |
| `permanent` | `preprocess` lỗi `AUDIO_INVALID` |
| `timeout` | `asr` treo `FAKE_HANG_SEC` giây (mặc định 3600) để runner kill |
| `no_speech` | `vad` lỗi `NO_SPEECH_DETECTED` |
| `diarize_fail` | `diarize` lỗi transient; runner fallback 1 speaker ở lượt cuối |
| `summary_fail` | `summarize` lỗi permanent `LLM_REQUEST_INVALID` |
| `summary_flaky` | `summarize` lỗi transient 2 lần đầu, lần thứ 3 thành công |
| `summary_disabled` | `summarize` trả `status=disabled` (không có key LLM) |

Trạng thái giữa các lần chạy (ví dụ "đã lỗi một lần chưa") lưu bằng file ẩn trong
workdir, vì retry dùng lại cùng workdir.
"""

from __future__ import annotations

import os
import time
from pathlib import Path

from meeting_pipeline.errors import (
    ErrorCode,
    PermanentPipelineError,
    TransientPipelineError,
)
from meeting_pipeline.fake import data
from meeting_pipeline.schemas import (
    Artifact,
    DiarizeOutput,
    Stage,
    SummaryOutput,
)
from meeting_pipeline.stages.base import StageContext, StageFn

SCENARIOS = (
    "ok",
    "slow",
    "transient_once",
    "permanent",
    "timeout",
    "no_speech",
    "diarize_fail",
    "summary_fail",
    "summary_flaky",
    "summary_disabled",
)

_MIME_BY_SUFFIX = {
    ".webm": "audio/webm",
    ".ogg": "audio/ogg",
    ".mp3": "audio/mpeg",
    ".m4a": "audio/mp4",
    ".mp4": "audio/mp4",
    ".wav": "audio/wav",
}


def current_scenario() -> str:
    scenario = os.environ.get("FAKE_SCENARIO", "ok")
    if scenario not in SCENARIOS:
        raise PermanentPipelineError(
            ErrorCode.INTERNAL_ERROR, None, f"FAKE_SCENARIO không hợp lệ: {scenario!r}"
        )
    return scenario


def _count_runs(ctx: StageContext) -> int:
    """Tăng và trả về số lần stage này đã chạy trong workdir (bắt đầu từ 1)."""
    marker = ctx.workdir / f".fake_{ctx.stage.value}_runs"
    runs = int(marker.read_text()) + 1 if marker.exists() else 1
    marker.write_text(str(runs))
    return runs


def _maybe_sleep(ctx: StageContext, scenario: str) -> None:
    if scenario != "slow":
        return
    total = float(os.environ.get("FAKE_STAGE_SLEEP_SEC", "1"))
    steps = 4
    for i in range(steps):
        time.sleep(total / steps)
        ctx.progress((i + 1) / steps)


def _preprocess(ctx: StageContext) -> Artifact:
    scenario = current_scenario()
    _maybe_sleep(ctx, scenario)
    if scenario == "permanent":
        raise PermanentPipelineError(
            ErrorCode.AUDIO_INVALID, ctx.stage, "fake: file không decode được"
        )
    src = Path(ctx.spec.audio_path)
    size = src.stat().st_size if src.exists() else 0
    mime = _MIME_BY_SUFFIX.get(src.suffix.lower(), "application/octet-stream")
    return data.preprocess_output(size_bytes=size, mime_type=mime)


def _vad(ctx: StageContext) -> Artifact:
    scenario = current_scenario()
    ctx.input(Stage.PREPROCESS)
    _maybe_sleep(ctx, scenario)
    if scenario == "no_speech":
        raise PermanentPipelineError(
            ErrorCode.NO_SPEECH_DETECTED, ctx.stage, "fake: không phát hiện lời nói"
        )
    return data.vad_output()


def _asr(ctx: StageContext) -> Artifact:
    scenario = current_scenario()
    ctx.input(Stage.VAD)
    _maybe_sleep(ctx, scenario)
    if scenario == "timeout":
        time.sleep(float(os.environ.get("FAKE_HANG_SEC", "3600")))
    if scenario == "transient_once" and _count_runs(ctx) == 1:
        raise TransientPipelineError(ErrorCode.OUT_OF_MEMORY, ctx.stage, "fake: CUDA OOM")
    return data.asr_output()


def _diarize(ctx: StageContext) -> Artifact:
    scenario = current_scenario()
    ctx.input(Stage.PREPROCESS)
    _maybe_sleep(ctx, scenario)
    if scenario == "diarize_fail":
        raise TransientPipelineError(
            ErrorCode.DIARIZATION_FAILED, ctx.stage, "fake: diarization lỗi"
        )
    return data.diarize_output()


def _merge(ctx: StageContext) -> Artifact:
    scenario = current_scenario()
    ctx.input(Stage.ASR)
    diarization = ctx.input(Stage.DIARIZE)
    assert isinstance(diarization, DiarizeOutput)
    _maybe_sleep(ctx, scenario)
    return data.transcript(diarization)


def _summarize(ctx: StageContext) -> Artifact:
    scenario = current_scenario()
    transcript = ctx.transcript()
    _maybe_sleep(ctx, scenario)
    if scenario == "summary_fail":
        raise PermanentPipelineError(ErrorCode.LLM_REQUEST_INVALID, ctx.stage, "fake: LLM trả 400")
    if scenario == "summary_flaky" and _count_runs(ctx) <= 2:
        raise TransientPipelineError(ErrorCode.LLM_UNAVAILABLE, ctx.stage, "fake: LLM trả 503")
    if scenario == "summary_disabled":
        return SummaryOutput(status="disabled", model=None, prompt_version=None, overview=None)
    if len(transcript.segments) < 2:
        return data.summary_insufficient()
    return data.summary_output(ctx.spec.meeting_date)


FAKE_STAGES: dict[Stage, StageFn] = {
    Stage.PREPROCESS: _preprocess,
    Stage.VAD: _vad,
    Stage.ASR: _asr,
    Stage.DIARIZE: _diarize,
    Stage.MERGE: _merge,
    Stage.SUMMARIZE: _summarize,
}
