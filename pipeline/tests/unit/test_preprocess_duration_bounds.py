"""Biên độ dài audio của stage preprocess (VT-018, mutation `>` thành `>=`).

Đúng bằng giới hạn thì được nhận; vượt giới hạn dù chỉ một chút thì bị từ chối.
Không cần ffmpeg: `probe`, `decode_to_wav` và `_playback` được thay bằng bản giả.
"""

import pytest

from meeting_pipeline.errors import ErrorCode, PermanentPipelineError
from meeting_pipeline.schemas import PlaybackInfo, Stage
from meeting_pipeline.stages import preprocess as pre
from meeting_pipeline.stages.base import StageContext


@pytest.fixture
def ctx(job_spec, tmp_path, monkeypatch):
    monkeypatch.setenv("PIPELINE_MIN_DURATION_SEC", "2")
    monkeypatch.setenv("PIPELINE_MAX_DURATION_SEC", "10")
    monkeypatch.setattr(
        pre, "probe", lambda _src: {"streams": [{"codec_type": "audio"}], "format": {}}
    )
    monkeypatch.setattr(
        pre,
        "_playback",
        lambda *a, **k: PlaybackInfo(source="original", file=None, mime_type="audio/wav"),
    )
    return StageContext(stage=Stage.PREPROCESS, workdir=tmp_path, spec=job_spec)


def run_with(monkeypatch, ctx, duration):
    monkeypatch.setattr(pre, "decode_to_wav", lambda _src, _dst: duration)
    return pre._run(ctx)


@pytest.mark.parametrize("duration", [2.0, 10.0])
def test_duration_equal_to_limit_is_accepted(ctx, monkeypatch, duration):
    assert run_with(monkeypatch, ctx, duration).duration_sec == duration


@pytest.mark.parametrize(
    ("duration", "code"),
    [(1.999, ErrorCode.AUDIO_TOO_SHORT), (10.001, ErrorCode.AUDIO_TOO_LONG)],
)
def test_duration_beyond_limit_is_rejected(ctx, monkeypatch, duration, code):
    with pytest.raises(PermanentPipelineError) as exc:
        run_with(monkeypatch, ctx, duration)
    assert exc.value.code == code
