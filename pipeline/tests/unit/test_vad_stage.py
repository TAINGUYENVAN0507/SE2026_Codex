"""Test stage vad với VAD engine giả (AI-06)."""

import wave

import pytest

from meeting_pipeline import engines
from meeting_pipeline.engines.fake import FakeVad
from meeting_pipeline.errors import ErrorCode, PermanentPipelineError
from meeting_pipeline.fake import data
from meeting_pipeline.registry import get_stage
from meeting_pipeline.schemas import AUDIO_FILE, Stage, VadOutput
from meeting_pipeline.stages.base import execute_stage
from meeting_pipeline.stages.vad import to_spans
from meeting_pipeline.workdir import artifact_path, write_json_atomic


@pytest.fixture
def vad_workdir(workdir):
    """Workdir đã có preprocess.json (30 s) và audio.wav 30 s im lặng."""
    write_json_atomic(artifact_path(workdir, Stage.PREPROCESS), data.preprocess_output())
    with wave.open(str(workdir / AUDIO_FILE), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(b"\0\0" * 16000 * 30)
    return workdir


def run_vad(workdir, monkeypatch, fake):
    monkeypatch.setattr(engines, "vad_engine", lambda: fake)
    path = execute_stage(Stage.VAD, workdir, get_stage(Stage.VAD, "real"))
    return VadOutput.model_validate_json(path.read_text(encoding="utf-8"))


def test_vad_writes_regions_and_ratio(vad_workdir, monkeypatch):
    out = run_vad(vad_workdir, monkeypatch, FakeVad([(0.5, 10.5), (12.0, 17.0)]))
    assert [(r.start_sec, r.end_sec) for r in out.speech_regions] == [(0.5, 10.5), (12.0, 17.0)]
    assert out.speech_ratio == 0.5
    assert out.model == "fake-vad"


def test_regions_are_clamped_sorted_and_merged():
    spans = to_spans([(20, 35), (-1, 2), (1.5, 3), (5, 5), (8, 7), (3, 4)], duration=30)
    assert [(s.start_sec, s.end_sec) for s in spans] == [(0.0, 4.0), (20.0, 30.0)]


@pytest.mark.parametrize("regions", [[], [(1.0, 1.2), (5.0, 5.1)]])
def test_no_or_too_little_speech_is_permanent(vad_workdir, monkeypatch, regions):
    with pytest.raises(PermanentPipelineError) as exc:
        run_vad(vad_workdir, monkeypatch, FakeVad(regions))
    assert exc.value.code is ErrorCode.NO_SPEECH_DETECTED
    assert exc.value.stage is Stage.VAD


def test_missing_audio_is_permanent(vad_workdir, monkeypatch):
    (vad_workdir / AUDIO_FILE).unlink()
    with pytest.raises(PermanentPipelineError) as exc:
        run_vad(vad_workdir, monkeypatch, FakeVad([(0, 5)]))
    assert exc.value.code is ErrorCode.MISSING_INPUT
    assert exc.value.stage is Stage.VAD
