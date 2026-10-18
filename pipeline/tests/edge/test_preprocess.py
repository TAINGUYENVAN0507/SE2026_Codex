"""Edge case của stage preprocess (AI-05, một phần AI-15)."""

import subprocess
import wave
from pathlib import Path

import pytest

from meeting_pipeline import cli
from meeting_pipeline.errors import ErrorCode, PermanentPipelineError
from meeting_pipeline.schemas import AUDIO_FILE, JobSpec, PreprocessOutput, Stage
from meeting_pipeline.stages import preprocess
from meeting_pipeline.stages.base import execute_stage
from meeting_pipeline.workdir import read_artifact, write_job

from .conftest import ffmpeg, opus_args, sine

pytestmark = pytest.mark.ffmpeg


def run_preprocess(src: Path, workdir: Path) -> PreprocessOutput:
    write_job(workdir, JobSpec(meeting_id="m", job_id="j", audio_path=str(src)))
    execute_stage(Stage.PREPROCESS, workdir, preprocess.run)
    out = read_artifact(workdir, Stage.PREPROCESS)
    assert isinstance(out, PreprocessOutput)
    return out


def assert_normalized_wav(path: Path, expected_sec: float) -> None:
    with wave.open(str(path), "rb") as w:
        assert (w.getframerate(), w.getnchannels(), w.getsampwidth()) == (16000, 1, 2)
        assert w.getnframes() / w.getframerate() == pytest.approx(expected_sec, abs=0.06)


@pytest.mark.parametrize(
    ("name", "args", "mime", "codec"),
    [
        ("stereo48k.wav", [*sine(3, 48000, 2), "-c:a", "pcm_s16le"], "audio/wav", "pcm_s16le"),
        ("mono8k.wav", [*sine(3, 8000), "-c:a", "pcm_s16le"], "audio/wav", "pcm_s16le"),
        ("speech.mp3", [*sine(3, 44100), "-c:a", "libmp3lame"], "audio/mpeg", "mp3"),
        ("safari.m4a", [*sine(3, 44100), "-c:a", "aac"], "audio/mp4", "aac"),
    ],
)
def test_playable_formats_keep_original(audio_dir, tmp_path, name, args, mime, codec):
    src = audio_dir / name
    ffmpeg(*args, str(src))
    out = run_preprocess(src, tmp_path / "wd")
    assert out.duration_sec == pytest.approx(3.0, abs=0.06)
    assert out.playback.source == "original"
    assert out.playback.mime_type == mime
    assert out.source.codec == codec
    assert_normalized_wav(tmp_path / "wd" / AUDIO_FILE, 3.0)


def test_stereo_source_info_is_recorded(audio_dir, tmp_path):
    src = audio_dir / "a.wav"
    ffmpeg(*sine(2, 48000, 2), "-c:a", "pcm_s16le", str(src))
    out = run_preprocess(src, tmp_path / "wd")
    assert (out.source.sample_rate, out.source.channels) == (48000, 2)
    assert out.source.size_bytes == src.stat().st_size
    assert (out.sample_rate, out.channels) == (16000, 1)


def test_unplayable_codec_is_transcoded_to_aac(audio_dir, tmp_path):
    src = audio_dir / "phone.wav"
    ffmpeg(*sine(3, 8000), "-c:a", "pcm_mulaw", str(src))
    wd = tmp_path / "wd"
    out = run_preprocess(src, wd)
    assert out.playback.source == "transcoded"
    assert out.playback.file == "playback.m4a"
    probe = preprocess.probe(wd / "playback.m4a")
    assert probe["streams"][0]["codec_name"] == "aac"


def test_webm_opus_from_recorder(audio_dir, tmp_path):
    src = audio_dir / "rec.webm"
    ffmpeg(*sine(3, 48000), *opus_args(), str(src))
    out = run_preprocess(src, tmp_path / "wd")
    assert out.playback.mime_type == "audio/webm"
    assert out.duration_sec == pytest.approx(3.0, abs=0.1)


def test_webm_without_header_duration_uses_decoded_length(audio_dir, tmp_path):
    """MediaRecorder ghi WebM theo luồng nên header không có duration."""
    src = audio_dir / "stream.webm"
    with src.open("wb") as f:
        subprocess.run(
            ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", *sine(4, 48000)]
            + [*opus_args(), "-f", "webm", "pipe:1"],
            stdout=f,
            check=True,
        )
    out = run_preprocess(src, tmp_path / "wd")
    assert out.duration_sec == pytest.approx(4.0, abs=0.1)


def test_header_duration_mismatch_warns(audio_dir, tmp_path, monkeypatch):
    src = audio_dir / "a.wav"
    ffmpeg(*sine(3), "-c:a", "pcm_s16le", str(src))
    real_probe = preprocess.probe

    def lying_probe(path):
        info = real_probe(path)
        info["format"]["duration"] = "60.0"
        return info

    monkeypatch.setattr(preprocess, "probe", lying_probe)
    out = run_preprocess(src, tmp_path / "wd")
    assert [w.code for w in out.warnings] == ["HEADER_DURATION_MISMATCH"]


def expect_error(src: Path, workdir: Path, code: ErrorCode) -> PermanentPipelineError:
    with pytest.raises(PermanentPipelineError) as exc:
        run_preprocess(src, workdir)
    assert exc.value.code is code
    assert exc.value.stage is Stage.PREPROCESS
    assert not (workdir / AUDIO_FILE).exists()
    assert not (workdir / "preprocess.json").exists()
    return exc.value


def test_too_short(audio_dir, tmp_path):
    src = audio_dir / "short.wav"
    ffmpeg(*sine(0.3), "-c:a", "pcm_s16le", str(src))
    err = expect_error(src, tmp_path / "wd", ErrorCode.AUDIO_TOO_SHORT)
    assert err.details["duration_sec"] == pytest.approx(0.3, abs=0.02)


def test_too_long(audio_dir, tmp_path, monkeypatch):
    monkeypatch.setenv("PIPELINE_MAX_DURATION_SEC", "2")
    src = audio_dir / "long.wav"
    ffmpeg(*sine(3), "-c:a", "pcm_s16le", str(src))
    expect_error(src, tmp_path / "wd", ErrorCode.AUDIO_TOO_LONG)


def test_random_bytes(audio_dir, tmp_path):
    src = audio_dir / "garbage.mp3"
    src.write_bytes(bytes(range(256)) * 64)
    expect_error(src, tmp_path / "wd", ErrorCode.AUDIO_INVALID)


def test_text_file_renamed_to_mp3(audio_dir, tmp_path):
    src = audio_dir / "notes.mp3"
    src.write_text("Biên bản họp: đây là file văn bản, không phải audio.\n" * 20)
    expect_error(src, tmp_path / "wd", ErrorCode.AUDIO_INVALID)


def test_video_without_audio(audio_dir, tmp_path):
    src = audio_dir / "screen.mp4"
    ffmpeg("-f", "lavfi", "-i", "testsrc=duration=2:size=64x64:rate=10", "-c:v", "mpeg4", str(src))
    err = expect_error(src, tmp_path / "wd", ErrorCode.AUDIO_INVALID)
    assert "không có audio" in err.message


def test_missing_source_file(tmp_path):
    expect_error(tmp_path / "nope.webm", tmp_path / "wd", ErrorCode.MISSING_INPUT)


def test_cli_real_backend_runs_preprocess(audio_dir, tmp_path):
    src = audio_dir / "a.mp3"
    ffmpeg(*sine(2, 44100), "-c:a", "libmp3lame", str(src))
    wd = tmp_path / "wd"
    write_job(wd, JobSpec(meeting_id="m", job_id="j", audio_path=str(src)))
    assert cli.main(["run-stage", "preprocess", "--workdir", str(wd), "--backend", "real"]) == 0
    assert_normalized_wav(wd / AUDIO_FILE, 2.0)
