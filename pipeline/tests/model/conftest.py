"""Audio dùng chung cho test model thật: ghép 2 bản ghi khác người đọc của câu FLEURS 1921."""

import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
FLEURS = REPO / "evaluation/datasets/raw/fleurs_vi_test_audio/test"
VOICE_1 = FLEURS / "7702082596424665893.wav"  # 9.42 s
VOICE_2 = FLEURS / "5471256245985564162.wav"  # 9.30 s
BOUNDARY_SEC = 9.92  # hết giọng 1 cộng 0.5 s lặng


@pytest.fixture(scope="session")
def two_voices(tmp_path_factory) -> Path:
    if not (VOICE_1.exists() and VOICE_2.exists()):
        pytest.skip("chưa tải FLEURS: evaluation/datasets/download.py fleurs_vi_test_audio")
    if shutil.which("ffmpeg") is None:
        pytest.skip("cần ffmpeg")
    out = tmp_path_factory.mktemp("audio") / "two_voices.wav"
    subprocess.run(
        [
            "ffmpeg",
            "-nostdin",
            "-loglevel",
            "error",
            "-i",
            str(VOICE_1),
            "-i",
            str(VOICE_2),
            "-filter_complex",
            "[0:a]aresample=16000,apad=pad_dur=0.5[a];[1:a]aresample=16000[b];"
            "[a][b]concat=n=2:v=0:a=1",
            "-ac",
            "1",
            str(out),
        ],
        check=True,
    )
    return out
