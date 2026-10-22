"""Test stage diarize với diarizer giả (AI-07)."""

import wave

import pytest

from meeting_pipeline import engines
from meeting_pipeline.engines.fake import FakeDiarizer
from meeting_pipeline.errors import ErrorCode, PermanentPipelineError
from meeting_pipeline.fake import data
from meeting_pipeline.registry import get_stage
from meeting_pipeline.schemas import AUDIO_FILE, RTTM_FILE, DiarizeOutput, JobSpec, Stage
from meeting_pipeline.stages.base import execute_stage
from meeting_pipeline.stages.diarize import normalize_turns
from meeting_pipeline.workdir import artifact_path, read_job, write_job, write_json_atomic


@pytest.fixture
def diar_workdir(workdir):
    write_json_atomic(artifact_path(workdir, Stage.PREPROCESS), data.preprocess_output())
    with wave.open(str(workdir / AUDIO_FILE), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(b"\0\0" * 16000 * 30)
    return workdir


def run_diarize(workdir, monkeypatch, fake):
    monkeypatch.setattr(engines, "diarize_engine", lambda: fake)
    path = execute_stage(Stage.DIARIZE, workdir, get_stage(Stage.DIARIZE, "real"))
    return DiarizeOutput.model_validate_json(path.read_text(encoding="utf-8"))


def test_diarize_writes_turns_and_rttm(diar_workdir, monkeypatch):
    fake = FakeDiarizer([(6.0, 11.25, "spk_b"), (0.4, 5.9, "spk_a"), (11.0, 17.0, "spk_a")])
    out = run_diarize(diar_workdir, monkeypatch, fake)
    assert (out.status, out.num_speakers, out.model) == ("ok", 2, "fake-diarizer")
    assert [(t.start_sec, t.end_sec, t.speaker_label) for t in out.turns] == [
        (0.4, 5.9, "SPEAKER_00"),
        (6.0, 11.25, "SPEAKER_01"),
        (11.0, 17.0, "SPEAKER_00"),
    ]
    meeting = read_job(diar_workdir).meeting_id
    assert (diar_workdir / RTTM_FILE).read_text().splitlines() == [
        f"SPEAKER {meeting} 1 0.400 5.500 <NA> <NA> SPEAKER_00 <NA> <NA>",
        f"SPEAKER {meeting} 1 6.000 5.250 <NA> <NA> SPEAKER_01 <NA> <NA>",
        f"SPEAKER {meeting} 1 11.000 6.000 <NA> <NA> SPEAKER_00 <NA> <NA>",
    ]


def test_speaker_hint_is_passed_to_engine(diar_workdir, monkeypatch):
    spec = read_job(diar_workdir)
    write_job(diar_workdir, JobSpec(**{**spec.model_dump(), "num_speakers_hint": 3}))
    fake = FakeDiarizer([(0.0, 2.0, "x")])
    run_diarize(diar_workdir, monkeypatch, fake)
    assert fake.calls == [3]


def test_turns_are_clamped_and_empty_ones_dropped():
    turns = normalize_turns([(28.0, 31.0, "a"), (-1.0, 2.0, "b"), (5.0, 5.0, "c")], duration=30)
    assert [(t.start_sec, t.end_sec, t.speaker_label) for t in turns] == [
        (0.0, 2.0, "SPEAKER_00"),
        (28.0, 30.0, "SPEAKER_01"),
    ]


def test_no_turns_gives_zero_speakers(diar_workdir, monkeypatch):
    out = run_diarize(diar_workdir, monkeypatch, FakeDiarizer([]))
    assert (out.num_speakers, out.turns) == (0, [])
    assert (diar_workdir / RTTM_FILE).read_text() == ""


def test_engine_error_is_tagged_with_stage(diar_workdir, monkeypatch):
    err = PermanentPipelineError(ErrorCode.MODEL_UNAVAILABLE, None, "không load được model")
    with pytest.raises(PermanentPipelineError) as exc:
        run_diarize(diar_workdir, monkeypatch, FakeDiarizer(error=err))
    assert exc.value.stage is Stage.DIARIZE
