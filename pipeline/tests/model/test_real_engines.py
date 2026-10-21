"""Chạy stage vad (và asr) với model thật. Cần `uv sync --extra asr`; asr cần GPU.

    uv run pytest -m model tests/model

Audio có lời nói lấy từ FLEURS đã tải bằng `evaluation/datasets/download.py`; chưa tải thì
test đó bị skip. Audio im lặng sinh bằng ffmpeg lúc chạy.
"""

import shutil
import subprocess
from pathlib import Path

import pytest

pytest.importorskip("faster_whisper")
pytestmark = pytest.mark.model

from meeting_pipeline.errors import ErrorCode, PermanentPipelineError  # noqa: E402
from meeting_pipeline.registry import get_stage  # noqa: E402
from meeting_pipeline.schemas import JobSpec, Stage, VadOutput  # noqa: E402
from meeting_pipeline.stages.base import execute_stage  # noqa: E402
from meeting_pipeline.workdir import write_job  # noqa: E402

REPO = Path(__file__).resolve().parents[3]
FLEURS_CLIP = REPO / "evaluation/datasets/raw/fleurs_vi_test_audio/test/13695736044714235367.wav"


def prepare(tmp_path: Path, audio: Path) -> Path:
    workdir = tmp_path / "work"
    write_job(workdir, JobSpec(meeting_id="m", job_id="j", audio_path=str(audio)))
    execute_stage(Stage.PREPROCESS, workdir, get_stage(Stage.PREPROCESS, "real"))
    return workdir


@pytest.fixture
def silence(tmp_path) -> Path:
    if shutil.which("ffmpeg") is None:
        pytest.skip("cần ffmpeg")
    path = tmp_path / "silence.wav"
    subprocess.run(
        [
            "ffmpeg",
            "-nostdin",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            "anullsrc=r=16000:cl=mono",
            "-t",
            "5",
            str(path),
        ],
        check=True,
    )
    return path


@pytest.fixture
def speech() -> Path:
    if not FLEURS_CLIP.exists():
        pytest.skip("chưa tải FLEURS: evaluation/datasets/download.py fleurs_vi_test_audio")
    return FLEURS_CLIP


def test_real_vad_rejects_silence(tmp_path, silence):
    workdir = prepare(tmp_path, silence)
    with pytest.raises(PermanentPipelineError) as exc:
        execute_stage(Stage.VAD, workdir, get_stage(Stage.VAD, "real"))
    assert exc.value.code is ErrorCode.NO_SPEECH_DETECTED


def test_real_vad_finds_speech(tmp_path, speech):
    workdir = prepare(tmp_path, speech)
    path = execute_stage(Stage.VAD, workdir, get_stage(Stage.VAD, "real"))
    out = VadOutput.model_validate_json(path.read_text(encoding="utf-8"))
    assert out.speech_regions and out.speech_ratio > 0.5
    assert out.model.startswith("silero-vad")


def cuda_available() -> bool:
    import ctranslate2

    from meeting_pipeline.engines.whisper import preload_cuda_libs

    preload_cuda_libs()
    return ctranslate2.get_cuda_device_count() > 0


def test_real_asr_on_fleurs_clip(tmp_path, speech):
    import os

    from meeting_pipeline.schemas import AsrOutput

    if os.environ.get("ASR_DEVICE", "cuda") == "cuda" and not cuda_available():
        pytest.skip("không có GPU CUDA")
    workdir = prepare(tmp_path, speech)
    execute_stage(Stage.VAD, workdir, get_stage(Stage.VAD, "real"))
    path = execute_stage(Stage.ASR, workdir, get_stage(Stage.ASR, "real"))
    out = AsrOutput.model_validate_json(path.read_text(encoding="utf-8"))
    text = " ".join(s.text for s in out.segments).lower()
    # Reference: "...dựa vào kết quả của nền kinh tế Trung Quốc."
    assert "trung quốc" in text
    assert all(s.words for s in out.segments)
