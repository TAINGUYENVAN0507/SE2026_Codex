"""Test adapter engine ASR và VAD bằng model giả (AI-06). Không cần faster-whisper hay GPU."""

import wave
from pathlib import Path
from types import SimpleNamespace

import pytest

from meeting_pipeline.engines import read_wav
from meeting_pipeline.engines.fake import FakeAsr, FakeVad
from meeting_pipeline.engines.whisper import FasterWhisperAsr, WhisperConfig
from meeting_pipeline.errors import (
    ErrorCode,
    PermanentPipelineError,
    TransientPipelineError,
)
from meeting_pipeline.stages.asr_post import RawSegment


def write_wav(path: Path, seconds: float = 2.0, rate: int = 16000, channels: int = 1) -> Path:
    with wave.open(str(path), "wb") as w:
        w.setnchannels(channels)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"\0\0" * int(seconds * rate) * channels)
    return path


def test_read_wav(tmp_path):
    audio = read_wav(write_wav(tmp_path / "audio.wav", seconds=2.5))
    assert (audio.sample_rate, audio.num_frames, audio.duration_sec) == (16000, 40000, 2.5)


@pytest.mark.parametrize(("rate", "channels"), [(48000, 1), (16000, 2)])
def test_read_wav_rejects_other_formats(tmp_path, rate, channels):
    path = write_wav(tmp_path / "audio.wav", rate=rate, channels=channels)
    with pytest.raises(PermanentPipelineError) as exc:
        read_wav(path)
    assert exc.value.code is ErrorCode.AUDIO_INVALID


def test_read_wav_missing_or_corrupt(tmp_path):
    (tmp_path / "bad.wav").write_bytes(b"not a wav")
    for path in (tmp_path / "missing.wav", tmp_path / "bad.wav"):
        with pytest.raises(PermanentPipelineError) as exc:
            read_wav(path)
        assert exc.value.code is ErrorCode.MISSING_INPUT


def test_config_defaults_follow_adr_and_env_overrides(monkeypatch):
    assert WhisperConfig.from_env() == WhisperConfig("large-v3-turbo", "int8_float16", "cuda", 5)
    monkeypatch.setenv("ASR_MODEL", "small")
    monkeypatch.setenv("ASR_COMPUTE_TYPE", "int8")
    monkeypatch.setenv("ASR_DEVICE", "cpu")
    monkeypatch.setenv("ASR_BEAM_SIZE", "1")
    assert WhisperConfig.from_env() == WhisperConfig("small", "int8", "cpu", 1)


class FakeModel:
    """Giả lập WhisperModel: transcribe trả generator segment và info."""

    def __init__(self, segments=(), error=None, **_):
        self.segments, self.error, self.calls = segments, error, []

    def transcribe(self, samples, **kwargs):
        self.calls.append(kwargs)

        def gen():
            if self.error:
                raise self.error
            yield from self.segments

        return gen(), SimpleNamespace(duration=4.0)


def fw_segment(start, end, text, words=()):
    return SimpleNamespace(
        start=start,
        end=end,
        text=text,
        avg_logprob=-0.2,
        no_speech_prob=0.01,
        compression_ratio=1.2,
        words=[SimpleNamespace(word=w, start=s, end=e, probability=p) for w, s, e, p in words],
    )


CPU = WhisperConfig(device="cpu")


def engine(model):
    return FasterWhisperAsr(CPU, model_factory=lambda *a, **k: model, loader=lambda audio: [0.0])


def test_transcribe_converts_segments_and_reports_progress(tmp_path):
    model = FakeModel(
        [
            fw_segment(0.0, 2.0, " Xin chào", [(" Xin", 0.0, 0.5, 0.9), (" chào", 0.5, 1.0, 0.8)]),
            fw_segment(2.0, 4.0, " nhé"),
        ]
    )
    progress = []
    out = engine(model).transcribe(read_wav(write_wav(tmp_path / "a.wav", 4)), progress.append)
    assert out[0] == RawSegment(0.0, 2.0, " Xin chào", -0.2, 0.01, 1.2, out[0].words)
    assert [(w.w, w.s, w.p) for w in out[0].words] == [(" Xin", 0.0, 0.9), (" chào", 0.5, 0.8)]
    assert progress == [0.5, 1.0]
    call = model.calls[0]
    assert (call["language"], call["beam_size"], call["vad_filter"]) == ("vi", 5, True)
    assert call["condition_on_previous_text"] is False and call["word_timestamps"] is True


def test_oom_while_decoding_is_transient(tmp_path):
    model = FakeModel(error=RuntimeError("CUDA failed with error out of memory"))
    with pytest.raises(TransientPipelineError) as exc:
        engine(model).transcribe(read_wav(write_wav(tmp_path / "a.wav")), lambda v: None)
    assert exc.value.code is ErrorCode.OUT_OF_MEMORY


def test_other_decoding_errors_propagate(tmp_path):
    model = FakeModel(error=RuntimeError("something else"))
    with pytest.raises(RuntimeError):
        engine(model).transcribe(read_wav(write_wav(tmp_path / "a.wav")), lambda v: None)


def test_model_load_failure_is_permanent_and_does_not_leak_message(tmp_path):
    def broken(*a, **k):
        raise OSError("401 Unauthorized for token hf_SECRET_7f3a")

    asr = FasterWhisperAsr(
        WhisperConfig(device="cpu"), model_factory=broken, loader=lambda a: [0.0]
    )
    with pytest.raises(PermanentPipelineError) as exc:
        asr.transcribe(read_wav(write_wav(tmp_path / "a.wav")), lambda v: None)
    assert exc.value.code is ErrorCode.MODEL_UNAVAILABLE
    assert "SECRET" not in exc.value.message and "OSError" in exc.value.message


def test_oom_while_loading_is_transient(tmp_path):
    def oom(*a, **k):
        raise RuntimeError("CUDA failed with error out of memory")

    asr = FasterWhisperAsr(WhisperConfig(device="cpu"), model_factory=oom, loader=lambda a: [0.0])
    with pytest.raises(TransientPipelineError):
        asr.transcribe(read_wav(write_wav(tmp_path / "a.wav")), lambda v: None)


def test_fake_engines(tmp_path):
    audio = read_wav(write_wav(tmp_path / "a.wav", 4))
    progress = []
    assert FakeAsr([RawSegment(0, 2, "a")]).transcribe(audio, progress.append) == [
        RawSegment(0, 2, "a")
    ]
    assert progress == [0.5]
    assert FakeVad([(0.5, 1.5)]).speech_regions(audio) == [(0.5, 1.5)]
    with pytest.raises(ValueError):
        FakeVad(error=ValueError("x")).speech_regions(audio)
