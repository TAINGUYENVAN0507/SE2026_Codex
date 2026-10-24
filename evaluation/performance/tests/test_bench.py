"""Test phần thuần của bench.py: chọn clip, ghép audio, nhận diện stage, tính RTF."""

import csv
import os
import shutil
import wave
from pathlib import Path

import bench
import pytest


def write_wav(path: Path, seconds: float, rate: int = 16000) -> Path:
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"\0\0" * int(seconds * rate))
    return path


def write_float32_wav(path: Path, seconds: float, rate: int = 16000) -> Path:
    """WAV float32 (format 3) như của FLEURS, có chunk `fmt ` 18 byte và chunk `LIST` lẻ."""
    data = b"\0\0\0\0" * int(seconds * rate)
    fmt = (
        (3).to_bytes(2, "little")
        + (1).to_bytes(2, "little")
        + rate.to_bytes(4, "little")
        + (rate * 4).to_bytes(4, "little")
        + (4).to_bytes(2, "little")
        + (32).to_bytes(2, "little")
        + (0).to_bytes(2, "little")
    )
    chunks = b"fmt " + len(fmt).to_bytes(4, "little") + fmt
    chunks += b"LIST" + (3).to_bytes(4, "little") + b"abc\0"
    chunks += b"data" + len(data).to_bytes(4, "little") + data
    path.write_bytes(b"RIFF" + (4 + len(chunks)).to_bytes(4, "little") + b"WAVE" + chunks)
    return path


def test_wav_duration_reads_pcm_and_float32(tmp_path):
    assert bench.wav_duration(write_wav(tmp_path / "pcm.wav", 2.5)) == pytest.approx(2.5)
    assert bench.wav_duration(write_float32_wav(tmp_path / "f32.wav", 1.25)) == pytest.approx(1.25)


def test_wav_duration_rejects_non_wav(tmp_path):
    path = tmp_path / "x.wav"
    path.write_bytes(b"ID3 not a wav file")
    with pytest.raises(ValueError):
        bench.wav_duration(path)


def test_select_clips_stops_once_target_is_reached():
    clips = [(Path(f"{i}.wav"), 10.0) for i in range(5)]
    assert bench.select_clips(clips, 25) == [Path("0.wav"), Path("1.wav"), Path("2.wav")]
    assert bench.select_clips(clips, 20) == [Path("0.wav"), Path("1.wav")]


def test_select_clips_fails_when_not_enough_audio():
    with pytest.raises(ValueError, match="không đủ audio"):
        bench.select_clips([(Path("a.wav"), 5.0)], 60)


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="cần ffmpeg")
def test_build_audio_concatenates_and_trims(tmp_path):
    clips = [(write_wav(tmp_path / f"{i}.wav", 4.0), 4.0) for i in range(3)]
    out = bench.build_audio(10.0, tmp_path / "out.wav", clips)
    assert bench.wav_duration(out) == pytest.approx(10.0, abs=0.01)
    with wave.open(str(out), "rb") as w:
        assert (w.getframerate(), w.getnchannels()) == (16000, 1)


def test_concat_command_is_16k_mono_and_exact_length(tmp_path):
    cmd = bench.concat_command([], tmp_path / "list.txt", tmp_path / "o.wav", 60)
    assert cmd[cmd.index("-t") + 1] == "60.000"
    assert cmd[cmd.index("-ar") + 1] == "16000" and cmd[cmd.index("-ac") + 1] == "1"


@pytest.mark.parametrize(
    ("cmdline", "stage"),
    [
        (["/venv/python", "-m", "meeting_pipeline", "run-stage", "asr", "--workdir", "w"], "asr"),
        (["python", "-m", "meeting_pipeline", "run-stage", "diarize"], "diarize"),
        (["ffmpeg", "-i", "x.webm"], None),
        (["python", "other.py", "run-stage", "asr"], None),
        ([], None),
    ],
)
def test_stage_of(cmdline, stage):
    assert bench.stage_of(cmdline) == stage


def test_parse_nvidia_apps_sums_per_pid_and_skips_noise():
    text = "1234, 512\n1234, 100\n77, 2048\n[Not Supported], x\n\n"
    assert bench.parse_nvidia_apps(text) == {1234: 612.0, 77: 2048.0}


def test_peaks_keep_the_maximum_per_stage():
    peaks = bench.Peaks()
    peaks.update("asr", 900, 1500)
    peaks.update("asr", 700, None)
    peaks.update("diarize", 1200, None)
    assert peaks.rss_mb == {"asr": 900, "diarize": 1200}
    assert peaks.vram_mb == {"asr": 1500}


def test_fleurs_clips_reads_headers_lazily(tmp_path):
    for name in ("b", "a", "c"):
        write_wav(tmp_path / f"{name}.wav", 1.0)
    (tmp_path / "c.wav").write_bytes(b"broken")  # chỉ lỗi nếu bị đọc tới
    clips = bench.fleurs_clips(tmp_path)
    assert [p.name for p in bench.select_clips(clips, 1.5)] == ["a.wav", "b.wav"]


def test_system_pressure_is_a_dict_or_none():
    pressure = bench.system_pressure()
    assert pressure is None or {"io_some_avg60", "loadavg"} <= set(pressure)


def test_sampler_records_a_running_stage_subprocess():
    """Chạy thật một process có cmdline giống stage để kiểm vòng lấy mẫu và stop()."""
    import subprocess
    import sys
    import time

    code = "import time; x = bytearray(30 * 1024 * 1024); time.sleep(2)"
    sampler = bench.Sampler(os.getpid())
    sampler.start()
    proc = subprocess.Popen(
        [sys.executable, "-c", code, "-m", "meeting_pipeline", "run-stage", "asr"]
    )
    time.sleep(1.5)
    peaks = sampler.stop()
    proc.wait()
    assert not sampler.is_alive()
    assert peaks.rss_mb.get("asr", 0) > 25


def test_rows_have_rtf_and_a_total(tmp_path):
    peaks = bench.Peaks(rss_mb={"asr": 900.4, "merge": 80}, vram_mb={"asr": 1500})
    rows = bench.rows_for_run(
        1,
        60.0,
        ["asr", "merge", "summarize"],
        {"asr": "succeeded", "merge": "succeeded"},
        {"asr": 30.0, "merge": 1.5},
        peaks,
    )
    assert [r["stage"] for r in rows] == ["asr", "merge", "total"]
    assert rows[0]["rtf"] == 0.5 and rows[0]["peak_rss_mb"] == 900
    assert rows[1]["peak_vram_mb"] == ""
    assert rows[-1] == {
        "target_min": 1,
        "audio_sec": 60.0,
        "stage": "total",
        "status": "succeeded",
        "seconds": 31.5,
        "rtf": 0.525,
        "peak_rss_mb": 900,
        "peak_vram_mb": 1500,
        "error_code": "",
    }
    path = tmp_path / "bench.csv"
    bench.write_csv(path, rows)
    with path.open(encoding="utf-8") as f:
        assert next(csv.reader(f)) == bench.COLUMNS


def test_failed_run_marks_total_and_failed_stage():
    rows = bench.rows_for_run(
        5,
        300.0,
        ["preprocess", "asr"],
        {"preprocess": "succeeded", "asr": "failed"},
        {"preprocess": 2.0, "asr": 10.0},
        bench.Peaks(),
        error_code="STAGE_TIMEOUT",
    )
    assert rows[1]["error_code"] == "STAGE_TIMEOUT" and rows[0]["error_code"] == ""
    assert rows[-1]["status"] == "failed" and rows[-1]["error_code"] == "STAGE_TIMEOUT"
