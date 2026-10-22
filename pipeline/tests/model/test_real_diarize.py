"""Chạy stage diarize với pyannote thật (AI-07). Cần `uv sync --extra diarize` và quyền tải
model gated `pyannote/speaker-diarization-community-1` (token Hugging Face).

    uv run pytest -m model tests/model/test_real_diarize.py

Audio thử ghép từ 2 bản ghi khác người đọc của cùng một câu FLEURS (giọng 1, 0.5 s lặng,
giọng 2). Chưa tải FLEURS thì test bị skip.
"""

import shutil
import subprocess
from pathlib import Path

import pytest

pytest.importorskip("pyannote.audio")
pytestmark = pytest.mark.model

from meeting_pipeline.registry import get_stage  # noqa: E402
from meeting_pipeline.schemas import DiarizeOutput, JobSpec, Stage  # noqa: E402
from meeting_pipeline.stages.base import execute_stage  # noqa: E402
from meeting_pipeline.workdir import write_job  # noqa: E402

REPO = Path(__file__).resolve().parents[3]
FLEURS = REPO / "evaluation/datasets/raw/fleurs_vi_test_audio/test"
# Câu 1921 của FLEURS vi test, hai người đọc khác nhau.
VOICE_1 = FLEURS / "7702082596424665893.wav"  # 9.42 s
VOICE_2 = FLEURS / "5471256245985564162.wav"  # 9.30 s
BOUNDARY_SEC = 9.92  # hết giọng 1 cộng 0.5 s lặng
TOLERANCE_SEC = 0.5


@pytest.fixture(scope="module")
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


def diarize(tmp_path: Path, audio: Path, hint: int | None) -> DiarizeOutput:
    workdir = tmp_path / "work"
    write_job(
        workdir, JobSpec(meeting_id="m", job_id="j", audio_path=str(audio), num_speakers_hint=hint)
    )
    execute_stage(Stage.PREPROCESS, workdir, get_stage(Stage.PREPROCESS, "real"))
    path = execute_stage(Stage.DIARIZE, workdir, get_stage(Stage.DIARIZE, "real"))
    assert (workdir / "diarization.rttm").read_text().startswith("SPEAKER m 1 ")
    return DiarizeOutput.model_validate_json(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize("hint", [None, 2])
def test_real_diarization_separates_two_voices(tmp_path, two_voices, hint):
    out = diarize(tmp_path, two_voices, hint)
    assert (out.status, out.num_speakers) == ("ok", 2)
    first = [t for t in out.turns if t.speaker_label == "SPEAKER_00"]
    second = [t for t in out.turns if t.speaker_label == "SPEAKER_01"]
    assert max(t.end_sec for t in first) <= BOUNDARY_SEC + TOLERANCE_SEC
    assert min(t.start_sec for t in second) >= BOUNDARY_SEC - TOLERANCE_SEC
