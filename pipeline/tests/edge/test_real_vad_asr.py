"""Edge case qua stage vad và asr thật (AI-15). Kết quả đo ghi trong `README.md` cùng thư mục.

Cần `uv sync --extra asr`, GPU CUDA cho ASR, FLEURS đã tải:

    uv run pytest -m model tests/edge/test_real_vad_asr.py

Audio sinh bằng ffmpeg lúc chạy từ một clip FLEURS (11.2 s, một người đọc), không commit
file audio. Đặt `EDGE_HYP_OUT=<file.jsonl>` để ghi text ASR của từng case, rồi chấm WER bằng
`evaluation/wer/edge_wer.py`.
"""

import json
import os
from pathlib import Path

import pytest

pytest.importorskip("faster_whisper")
pytestmark = pytest.mark.model

from meeting_pipeline.errors import ErrorCode, PermanentPipelineError  # noqa: E402
from meeting_pipeline.registry import get_stage  # noqa: E402
from meeting_pipeline.schemas import AsrOutput, JobSpec, Stage, VadOutput  # noqa: E402
from meeting_pipeline.stages.base import execute_stage  # noqa: E402
from meeting_pipeline.workdir import write_job  # noqa: E402

from .conftest import ffmpeg  # noqa: E402

REPO = Path(__file__).resolve().parents[3]
CLIP = REPO / "evaluation/datasets/raw/fleurs_vi_test_audio/test/13695736044714235367.wav"
CLIP_ID = "fleurs-1661-13695736044714235367"  # id trong evaluation/datasets/manifest.csv
# Reference: "Ông ấy đã không đưa ra con số cắt giảm, mà nói rằng việc đó sẽ được thực hiện
# dựa vào kết quả của nền kinh tế Trung Quốc."
KEY_PHRASE = "trung quốc"

# RMS của clip (cả phần ngắt nghỉ) là -28.5 dBFS; ồn hồng amplitude 0.05 có RMS -40.4 dBFS.
# Amplitude cho SNR mong muốn: 0.05 × 10^((11.87 − snr) / 20).
SNR5_PINK_AMPLITUDE = 0.1103
SNR0_PINK_AMPLITUDE = 0.1961
MIX = "[0:a]aresample=16000[s];[s][1:a]amix=inputs=2:duration=first:normalize=0"


def lavfi(source: str, seconds: float) -> list[str]:
    return ["-f", "lavfi", "-i", source, "-t", str(seconds)]


NO_SPEECH = {
    "silence_10s": lavfi("anullsrc=r=16000:cl=mono", 10),
    "white_noise_10s": lavfi("anoisesrc=color=white:amplitude=0.1:r=16000:seed=7", 10),
    "pink_noise_10s": lavfi("anoisesrc=color=pink:amplitude=0.3:r=16000:seed=7", 10),
}

DEGRADED = {
    "clean": ["-i", str(CLIP)],
    "phone_8khz": ["-i", str(CLIP), "-af", "highpass=f=300,lowpass=f=3400", "-ar", "8000"],
    "clipped_plus_20db": ["-i", str(CLIP), "-af", "volume=20dB", "-c:a", "pcm_s16le"],
    "quiet_minus_30db": ["-i", str(CLIP), "-af", "volume=-30dB"],
    "pink_noise_snr_5db": [
        "-i",
        str(CLIP),
        *lavfi(f"anoisesrc=color=pink:amplitude={SNR5_PINK_AMPLITUDE}:r=16000:seed=3", 12),
        "-filter_complex",
        MIX,
    ],
    "stereo_48khz_one_side": ["-i", str(CLIP), "-af", "aresample=48000,pan=stereo|c0=c0|c1=0*c0"],
}


# Chỉ đo, không kỳ vọng còn nghe được cụm từ khóa: ghi lại mức suy giảm cho AI-12.
MEASURE_ONLY = {
    "pink_noise_snr_0db": [
        "-i",
        str(CLIP),
        *lavfi(f"anoisesrc=color=pink:amplitude={SNR0_PINK_AMPLITUDE}:r=16000:seed=3", 12),
        "-filter_complex",
        MIX,
    ],
}


def record(case: str, asr: AsrOutput) -> str:
    text = " ".join(s.text for s in asr.segments)
    out = os.environ.get("EDGE_HYP_OUT")
    if out:
        with open(out, "a", encoding="utf-8") as f:
            f.write(json.dumps({"case": case, "id": CLIP_ID, "text": text}, ensure_ascii=False))
            f.write("\n")
    return text


@pytest.fixture(scope="module")
def gpu():
    import ctranslate2

    from meeting_pipeline.engines.whisper import preload_cuda_libs

    preload_cuda_libs()
    if ctranslate2.get_cuda_device_count() == 0:
        pytest.skip("không có GPU CUDA cho ASR")


@pytest.fixture
def clip():
    if not CLIP.exists():
        pytest.skip("chưa tải FLEURS: evaluation/datasets/download.py fleurs_vi_test_audio")
    return CLIP


def run_stages(tmp_path: Path, ffmpeg_args: list[str], *stages: Stage) -> Path:
    audio = tmp_path / "input.wav"
    ffmpeg(*ffmpeg_args, str(audio))
    workdir = tmp_path / "work"
    write_job(workdir, JobSpec(meeting_id="m", job_id="j", audio_path=str(audio)))
    for stage in (Stage.PREPROCESS, *stages):
        execute_stage(stage, workdir, get_stage(stage, "real"))
    return workdir


def read(workdir: Path, stage: Stage, model):
    name = {Stage.VAD: "vad.json", Stage.ASR: "asr.json"}[stage]
    return model.model_validate_json((workdir / name).read_text(encoding="utf-8"))


@pytest.mark.parametrize("args", NO_SPEECH.values(), ids=NO_SPEECH.keys())
def test_no_speech_is_rejected_before_asr(tmp_path, args):
    with pytest.raises(PermanentPipelineError) as exc:
        run_stages(tmp_path, args, Stage.VAD)
    assert exc.value.code is ErrorCode.NO_SPEECH_DETECTED


@pytest.mark.parametrize("case", DEGRADED)
def test_degraded_speech_is_still_transcribed(tmp_path, gpu, clip, case):
    workdir = run_stages(tmp_path, DEGRADED[case], Stage.VAD, Stage.ASR)
    vad = read(workdir, Stage.VAD, VadOutput)
    asr = read(workdir, Stage.ASR, AsrOutput)
    assert vad.speech_ratio > 0.5
    assert KEY_PHRASE in record(case, asr).lower()
    assert all(s.words for s in asr.segments)


@pytest.mark.parametrize("case", MEASURE_ONLY)
def test_heavy_noise_still_produces_text(tmp_path, gpu, clip, case):
    workdir = run_stages(tmp_path, MEASURE_ONLY[case], Stage.VAD, Stage.ASR)
    assert record(case, read(workdir, Stage.ASR, AsrOutput)).strip()


def test_speech_between_long_silences_keeps_timestamps(tmp_path, gpu, clip):
    """20 s lặng trước và sau: không có chữ bịa trong khoảng lặng, timestamp không lệch."""
    args = ["-i", str(clip), "-af", "adelay=20000:all=1,apad=pad_dur=20", "-ar", "16000"]
    workdir = run_stages(tmp_path, args, Stage.VAD, Stage.ASR)
    vad = read(workdir, Stage.VAD, VadOutput)
    asr = read(workdir, Stage.ASR, AsrOutput)
    assert vad.speech_ratio < 0.3
    assert vad.speech_regions[0].start_sec >= 20.0
    assert asr.segments
    for seg in asr.segments:
        assert 19.5 <= seg.start_sec < seg.end_sec <= 31.7, (seg.start_sec, seg.end_sec)
    assert KEY_PHRASE in record("silence_20s_both_sides", asr).lower()
