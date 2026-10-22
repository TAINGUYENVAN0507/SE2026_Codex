"""Chạy stage diarize với pyannote thật (AI-07). Cần `uv sync --extra diarize` và quyền tải
model gated `pyannote/speaker-diarization-community-1` (token Hugging Face).

    uv run pytest -m model tests/model/test_real_diarize.py

Audio thử ghép từ 2 bản ghi khác người đọc của cùng một câu FLEURS (giọng 1, 0.5 s lặng,
giọng 2). Chưa tải FLEURS thì test bị skip.
"""

from pathlib import Path

import pytest

pytest.importorskip("pyannote.audio")
pytestmark = pytest.mark.model

from meeting_pipeline.registry import get_stage  # noqa: E402
from meeting_pipeline.schemas import DiarizeOutput, JobSpec, Stage  # noqa: E402
from meeting_pipeline.stages.base import execute_stage  # noqa: E402
from meeting_pipeline.workdir import write_job  # noqa: E402

# Ranh giới giữa 2 giọng trong fixture two_voices (conftest.py): hết giọng 1 + 0.5 s lặng.
BOUNDARY_SEC = 9.92
TOLERANCE_SEC = 0.5


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
