"""Test stage asr với ASR engine giả (AI-06)."""

import wave

import pytest

from meeting_pipeline import engines
from meeting_pipeline.engines.fake import FakeAsr
from meeting_pipeline.errors import (
    ErrorCode,
    PermanentPipelineError,
    TransientPipelineError,
)
from meeting_pipeline.fake import data
from meeting_pipeline.registry import get_stage
from meeting_pipeline.schemas import AUDIO_FILE, AsrOutput, Stage
from meeting_pipeline.stages.asr_post import HALLUCINATION_FILTERED, RawSegment, RawWord
from meeting_pipeline.stages.base import execute_stage
from meeting_pipeline.workdir import artifact_path, write_json_atomic


@pytest.fixture
def asr_workdir(workdir):
    """Workdir đã có preprocess.json (30 s), vad.json và audio.wav 30 s."""
    write_json_atomic(artifact_path(workdir, Stage.PREPROCESS), data.preprocess_output())
    write_json_atomic(artifact_path(workdir, Stage.VAD), data.vad_output())
    with wave.open(str(workdir / AUDIO_FILE), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(b"\0\0" * 16000 * 30)
    return workdir


def run_asr(workdir, monkeypatch, fake, progress=None):
    monkeypatch.setattr(engines, "asr_engine", lambda: fake)
    kwargs = {"progress": progress} if progress else {}
    path = execute_stage(Stage.ASR, workdir, get_stage(Stage.ASR, "real"), **kwargs)
    return AsrOutput.model_validate_json(path.read_text(encoding="utf-8"))


def test_asr_writes_normalized_segments(asr_workdir, monkeypatch):
    fake = FakeAsr(
        [
            RawSegment(
                5.0,
                9.0,
                " Anh Minh làm phần upload.",
                -0.2,
                0.01,
                1.2,
                (RawWord(" Anh", 5.0, 5.3, 0.9), RawWord(" Minh", 5.3, 5.7, 0.8)),
            ),
            RawSegment(0.5, 4.0, " Chào mọi người."),
            RawSegment(28.0, 31.0, " cuối"),
        ]
    )
    progress = []
    out = run_asr(asr_workdir, monkeypatch, fake, progress.append)
    assert out.model == "fake-asr" and out.language == "vi"
    assert [(s.start_sec, s.end_sec, s.text) for s in out.segments] == [
        (0.5, 4.0, "Chào mọi người."),
        (5.0, 9.0, "Anh Minh làm phần upload."),
        (28.0, 30.0, "cuối"),
    ]
    assert [w.w for w in out.segments[1].words] == ["Anh", "Minh"]
    assert out.warnings == []
    assert progress[0] == 0.05 and progress[-1] == 1.0


def test_hallucinations_are_filtered_with_warning(asr_workdir, monkeypatch):
    fake = FakeAsr(
        [
            RawSegment(0.5, 4.0, "Bắt đầu họp."),
            RawSegment(25.0, 29.0, "Hãy subscribe cho kênh Ghiền Mì Gõ nhé."),
        ]
    )
    out = run_asr(asr_workdir, monkeypatch, fake)
    assert [s.text for s in out.segments] == ["Bắt đầu họp."]
    assert [(w.code, w.stage) for w in out.warnings] == [(HALLUCINATION_FILTERED, Stage.ASR)]
    assert "subscribe" not in out.warnings[0].message


def test_oom_is_transient_and_tagged_with_stage(asr_workdir, monkeypatch):
    oom = TransientPipelineError(ErrorCode.OUT_OF_MEMORY, None, "hết bộ nhớ GPU")
    with pytest.raises(TransientPipelineError) as exc:
        run_asr(asr_workdir, monkeypatch, FakeAsr(error=oom))
    assert exc.value.code is ErrorCode.OUT_OF_MEMORY and exc.value.stage is Stage.ASR


def test_model_unavailable_is_permanent(asr_workdir, monkeypatch):
    err = PermanentPipelineError(ErrorCode.MODEL_UNAVAILABLE, None, "không load được model")
    with pytest.raises(PermanentPipelineError) as exc:
        run_asr(asr_workdir, monkeypatch, FakeAsr(error=err))
    assert exc.value.code is ErrorCode.MODEL_UNAVAILABLE and exc.value.stage is Stage.ASR


def test_asr_requires_vad(asr_workdir, monkeypatch):
    artifact_path(asr_workdir, Stage.VAD).unlink()
    with pytest.raises(PermanentPipelineError) as exc:
        run_asr(asr_workdir, monkeypatch, FakeAsr([RawSegment(0, 1, "a")]))
    assert exc.value.code is ErrorCode.MISSING_INPUT
