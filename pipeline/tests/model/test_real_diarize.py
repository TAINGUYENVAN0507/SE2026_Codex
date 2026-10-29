"""Chạy stage diarize với pyannote thật (AI-07). Cần `uv sync --extra diarize` (hoặc
`--extra diarize-gpu` cho test GPU) và quyền tải model gated
`pyannote/speaker-diarization-community-1` (token Hugging Face).

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


def _gpu_ready() -> bool:
    import torch

    return torch.cuda.is_available()


def test_real_diarization_on_gpu_matches_cpu_and_reports_vram(tmp_path, two_voices, monkeypatch):
    """Cần `uv sync --extra asr --extra diarize-gpu` (AI-16). Kết quả phải giống bản CPU."""
    import torch

    if not _gpu_ready():
        pytest.skip("không có GPU CUDA cho torch (cần extra diarize-gpu)")

    monkeypatch.setenv("DIARIZATION_DEVICE", "cpu")
    cpu = diarize(tmp_path / "cpu", two_voices, hint=2)

    monkeypatch.setenv("DIARIZATION_DEVICE", "cuda")
    torch.cuda.reset_peak_memory_stats()
    gpu = diarize(tmp_path / "gpu", two_voices, hint=2)
    peak_mib = torch.cuda.max_memory_allocated() / 2**20

    assert (gpu.status, gpu.num_speakers) == ("ok", 2)
    assert [t.speaker_label for t in gpu.turns] == [t.speaker_label for t in cpu.turns]
    for a, b in zip(gpu.turns, cpu.turns, strict=True):
        assert a.start_sec == pytest.approx(b.start_sec, abs=0.3)
        assert a.end_sec == pytest.approx(b.end_sec, abs=0.3)
    print(f"\nVRAM đỉnh (torch allocator) của diarization: {peak_mib:.0f} MiB")
    assert 0 < peak_mib < 3500  # GPU demo có 4 GB
