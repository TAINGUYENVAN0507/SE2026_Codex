"""Test adapter pyannote bằng pipeline giả (AI-07). Không cần pyannote hay torch."""

import wave
from types import SimpleNamespace

import pytest

from meeting_pipeline.engines import read_wav
from meeting_pipeline.engines.fake import FakeDiarizer
from meeting_pipeline.engines.pyannote import PyannoteConfig, PyannoteDiarizer
from meeting_pipeline.errors import ErrorCode, PermanentPipelineError, TransientPipelineError


@pytest.fixture
def audio(tmp_path):
    path = tmp_path / "audio.wav"
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(b"\0\0" * 16000 * 3)
    return read_wav(path)


class FakeAnnotation:
    def __init__(self, tracks):
        self.tracks = tracks

    def itertracks(self, yield_label=False):
        for start, end, label in self.tracks:
            yield SimpleNamespace(start=start, end=end), "_", label


class FakePipeline:
    def __init__(self, tracks=(), error=None, v4=True):
        self.tracks, self.error, self.v4, self.calls = tracks, error, v4, []

    def __call__(self, file, num_speakers=None):
        self.calls.append((file["sample_rate"], num_speakers))
        if self.error:
            raise self.error
        annotation = FakeAnnotation(self.tracks)
        return SimpleNamespace(speaker_diarization=annotation) if self.v4 else annotation


def diarizer(pipeline):
    return PyannoteDiarizer(
        PyannoteConfig(), pipeline_factory=lambda c: pipeline, loader=lambda a: "w"
    )


@pytest.mark.parametrize("v4", [True, False])
def test_turns_from_pyannote_3_and_4(audio, v4):
    pipeline = FakePipeline([(0.5, 1.5, "SPEAKER_01"), (1.4, 2.9, "SPEAKER_00")], v4=v4)
    assert diarizer(pipeline).turns(audio, num_speakers=2) == [
        (0.5, 1.5, "SPEAKER_01"),
        (1.4, 2.9, "SPEAKER_00"),
    ]
    assert pipeline.calls == [(16000, 2)]


def test_config_from_env(monkeypatch):
    assert PyannoteConfig.from_env() == PyannoteConfig(
        "pyannote/speaker-diarization-community-1", "auto"
    )
    monkeypatch.setenv("DIARIZATION_MODEL", "pyannote/speaker-diarization-3.1")
    monkeypatch.setenv("DIARIZATION_DEVICE", "cpu")
    assert PyannoteConfig.from_env() == PyannoteConfig("pyannote/speaker-diarization-3.1", "cpu")


def test_gated_model_is_permanent_without_leaking_token(audio):
    def gated(config):
        raise OSError("401 Client Error for token hf_SECRET_7f3a")

    with pytest.raises(PermanentPipelineError) as exc:
        PyannoteDiarizer(PyannoteConfig(), pipeline_factory=gated, loader=lambda a: "w").turns(
            audio
        )
    assert exc.value.code is ErrorCode.MODEL_UNAVAILABLE
    assert "SECRET" not in exc.value.message


@pytest.mark.parametrize("where", ["load", "run"])
def test_out_of_memory_is_transient(audio, where):
    oom = RuntimeError("CUDA out of memory. Tried to allocate 2 GiB")
    if where == "load":

        def factory(config):
            raise oom

        engine = PyannoteDiarizer(PyannoteConfig(), pipeline_factory=factory, loader=lambda a: "w")
    else:
        engine = diarizer(FakePipeline(error=oom))
    with pytest.raises(TransientPipelineError) as exc:
        engine.turns(audio)
    assert exc.value.code is ErrorCode.OUT_OF_MEMORY


def test_other_runtime_errors_propagate(audio):
    with pytest.raises(RuntimeError):
        diarizer(FakePipeline(error=RuntimeError("bad shape"))).turns(audio)


def test_fake_diarizer_records_hint(audio):
    fake = FakeDiarizer([(0.0, 1.0, "A")])
    assert fake.turns(audio, num_speakers=3) == [(0.0, 1.0, "A")]
    assert fake.calls == [3]
