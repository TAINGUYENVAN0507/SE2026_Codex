"""Timeout của stage phải đủ cho số đo benchmark thật (AI-13).

Đọc lại `evaluation/performance/results/*/bench.csv`: với mỗi stage và thiết bị, timeout cho audio
60' phải lớn hơn 1.5 × thời gian đo (RTF lớn nhất × 3600 s). Có benchmark chậm hơn được commit mà
chưa sửa `CPU_TIMEOUTS`, `GPU_TIMEOUTS` trong runner thì test này đỏ.
"""

import csv
from pathlib import Path

import pytest

from meeting_pipeline.errors import ErrorCode, PermanentPipelineError
from meeting_pipeline.runner import GPU_TIMEOUTS, TimeoutPolicy
from meeting_pipeline.schemas import STAGES, Stage

RESULTS = Path(__file__).resolve().parents[3] / "evaluation/performance/results"
SIXTY_MIN = 3600
MARGIN = 1.5

# Thư mục kết quả → thiết bị của stage asr và diarize trong lần đo đó.
SOURCES = {
    "2026-10-24_gtx1650ti-cpu-diarize": {Stage.ASR: "gpu", Stage.DIARIZE: "cpu"},
    "2026-10-25_i7-10750h-cpu-only": {Stage.ASR: "cpu", Stage.DIARIZE: "cpu"},
    "2026-10-29_gtx1650ti-gpu-diarize": {Stage.ASR: "gpu", Stage.DIARIZE: "gpu"},
    "2026-10-29_gtx1650ti-gpu-diarize-60m": {Stage.ASR: "gpu", Stage.DIARIZE: "gpu"},
}
GPU_ENV = {"ASR_DEVICE": "cuda", "DIARIZATION_DEVICE": "cuda"}
CPU_ENV = {"ASR_DEVICE": "cpu", "DIARIZATION_DEVICE": "cpu"}


def measured_rtf() -> dict[tuple[Stage, str], float]:
    """RTF lớn nhất của từng (stage, thiết bị) trong các lần đo."""
    worst: dict[tuple[Stage, str], float] = {}
    for name, devices in SOURCES.items():
        path = RESULTS / name / "bench.csv"
        if not path.exists():
            continue
        with path.open(encoding="utf-8") as f:
            for row in csv.DictReader(f):
                if row["stage"] == "total" or row["status"] != "succeeded":
                    continue
                stage = Stage(row["stage"])
                device = devices.get(stage, "any")
                key = (stage, device)
                worst[key] = max(worst.get(key, 0.0), float(row["rtf"]))
    return worst


@pytest.fixture(scope="module")
def rtf():
    data = measured_rtf()
    if not data:
        pytest.skip("không có kết quả benchmark trong evaluation/performance/results")
    return data


def policy(device: str) -> TimeoutPolicy:
    return TimeoutPolicy.from_env(GPU_ENV if device == "gpu" else CPU_ENV)


@pytest.mark.parametrize("stage", [s for s in STAGES if s not in (Stage.SUMMARIZE,)])
@pytest.mark.parametrize("device", ["gpu", "cpu"])
def test_timeout_covers_measured_time_with_margin(rtf, stage, device):
    candidates = [v for (st, dev), v in rtf.items() if st is stage and dev in (device, "any")]
    if not candidates:
        pytest.skip(f"chưa đo {stage.value} trên {device}")
    measured_sec = max(candidates) * SIXTY_MIN
    timeout = policy(device).timeout_for(stage, SIXTY_MIN)
    assert timeout >= MARGIN * measured_sec, (stage, device, timeout, measured_sec)


def test_timeout_is_not_absurdly_loose(rtf):
    """Timeout để bắt stage treo: không được quá 6 lần thời gian đo (asr, diarize)."""
    for stage in (Stage.ASR, Stage.DIARIZE):
        for device in ("gpu", "cpu"):
            candidates = [v for (st, dev), v in rtf.items() if st is stage and dev == device]
            if candidates:
                timeout = policy(device).timeout_for(stage, SIXTY_MIN)
                assert timeout <= 6 * max(candidates) * SIXTY_MIN, (stage, device)


def test_device_selection_from_env():
    gpu = TimeoutPolicy.from_env({})
    assert gpu.stages[Stage.ASR] == GPU_TIMEOUTS[Stage.ASR]
    assert gpu.stages[Stage.DIARIZE] == GPU_TIMEOUTS[Stage.DIARIZE]

    cpu = TimeoutPolicy.from_env({"ASR_DEVICE": "cpu"})  # DIARIZATION_DEVICE=auto theo ASR
    assert cpu.stages[Stage.ASR] == TimeoutPolicy().stages[Stage.ASR]
    assert cpu.stages[Stage.DIARIZE] == TimeoutPolicy().stages[Stage.DIARIZE]

    mixed = TimeoutPolicy.from_env({"ASR_DEVICE": "cuda", "DIARIZATION_DEVICE": "cpu"})
    assert mixed.stages[Stage.ASR] == GPU_TIMEOUTS[Stage.ASR]
    assert mixed.stages[Stage.DIARIZE] == TimeoutPolicy().stages[Stage.DIARIZE]


def test_default_policy_is_the_slowest_table():
    default, gpu = TimeoutPolicy(), TimeoutPolicy.from_env(GPU_ENV)
    for stage in STAGES:
        assert default.timeout_for(stage, SIXTY_MIN) >= gpu.timeout_for(stage, SIXTY_MIN)


def test_scale_multiplies_base_and_per_audio():
    base = TimeoutPolicy.from_env(GPU_ENV)
    scaled = TimeoutPolicy.from_env({**GPU_ENV, "PIPELINE_TIMEOUT_SCALE": "2.5"})
    for stage in STAGES:
        assert scaled.timeout_for(stage, 600) == pytest.approx(2.5 * base.timeout_for(stage, 600))


@pytest.mark.parametrize("value", ["0.5", "0", "11", "abc", ""])
def test_invalid_scale_is_rejected(value):
    with pytest.raises(PermanentPipelineError) as exc:
        TimeoutPolicy.from_env({"PIPELINE_TIMEOUT_SCALE": value})
    assert exc.value.code is ErrorCode.INTERNAL_ERROR
