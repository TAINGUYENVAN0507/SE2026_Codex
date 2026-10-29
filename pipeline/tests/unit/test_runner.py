"""Test runner với fake pipeline chạy qua subprocess thật (RT-01, RT-02, RT-08, RT-14)."""

import os
import sys
import time
from pathlib import Path

import pytest

from meeting_pipeline.errors import (
    ErrorCode,
    PermanentPipelineError,
    PipelineCancelledError,
    StageTimeoutError,
    TransientPipelineError,
)
from meeting_pipeline.fake import data
from meeting_pipeline.runner import (
    STAGE_WEIGHTS,
    StageTimeout,
    TimeoutPolicy,
    overall_progress,
    run_job,
    run_process,
    stage_command,
)
from meeting_pipeline.schemas import STAGES, JobSpec, Stage, Transcript
from meeting_pipeline.workdir import artifact_path, read_artifact, write_json_atomic


class Recorder:
    def __init__(self):
        self.done: list[Stage] = []
        self.progress: list[tuple[Stage, float]] = []

    def on_progress(self, stage, value):
        self.progress.append((stage, value))

    def on_stage_done(self, stage, path):
        assert path.exists()
        self.done.append(stage)


def run(spec: JobSpec, workdir: Path, scenario: str = "ok", rec: Recorder | None = None, **kw):
    rec = rec or Recorder()
    return run_job(
        spec,
        workdir=workdir,
        on_progress=rec.on_progress,
        on_stage_done=rec.on_stage_done,
        backend="fake",
        env={"FAKE_SCENARIO": scenario, **kw.pop("env", {})},
        **kw,
    )


def test_full_run_succeeds(job_spec, tmp_path):
    rec = Recorder()
    outcome = run(job_spec, tmp_path / "wd", rec=rec)
    assert outcome.stage_status == dict.fromkeys(STAGES, "succeeded")
    assert rec.done == list(STAGES)
    assert outcome.transcript_path == tmp_path / "wd" / "transcript.json"
    assert outcome.summary_path == tmp_path / "wd" / "summary.json"
    assert outcome.warnings == []
    assert set(outcome.timings) == set(STAGES)
    assert {s for s, v in rec.progress if v == 1.0} == set(STAGES)


def test_resume_from_checkpoint_only_runs_missing_stages(job_spec, tmp_path):
    wd = tmp_path / "wd"
    run(job_spec, wd)
    asr_mtime = artifact_path(wd, Stage.ASR).stat().st_mtime_ns
    artifact_path(wd, Stage.SUMMARIZE).unlink()

    rec = Recorder()
    outcome = run(job_spec, wd, rec=rec)
    assert outcome.stage_status[Stage.ASR] == "skipped"
    assert outcome.stage_status[Stage.SUMMARIZE] == "succeeded"
    assert artifact_path(wd, Stage.ASR).stat().st_mtime_ns == asr_mtime
    # Stage đã xong vẫn được báo lại để worker persist idempotent.
    assert rec.done == list(STAGES)


def test_corrupt_checkpoint_is_recomputed(job_spec, tmp_path):
    wd = tmp_path / "wd"
    run(job_spec, wd)
    artifact_path(wd, Stage.VAD).write_text("{ hỏng")
    outcome = run(job_spec, wd)
    assert outcome.stage_status[Stage.VAD] == "succeeded"
    assert outcome.stage_status[Stage.PREPROCESS] == "skipped"


def test_permanent_error_stops_without_stage_done(job_spec, tmp_path):
    rec = Recorder()
    with pytest.raises(PermanentPipelineError) as exc:
        run(job_spec, tmp_path / "wd", "permanent", rec=rec)
    assert (exc.value.code, exc.value.stage) == (ErrorCode.AUDIO_INVALID, Stage.PREPROCESS)
    assert rec.done == []


def test_transient_error_then_retry_resumes(job_spec, tmp_path):
    wd = tmp_path / "wd"
    with pytest.raises(TransientPipelineError) as exc:
        run(job_spec, wd, "transient_once")
    assert exc.value.stage is Stage.ASR
    retry = job_spec.model_copy(update={"attempt": 2})
    outcome = run(retry, wd, "transient_once")
    assert outcome.stage_status[Stage.PREPROCESS] == "skipped"
    assert outcome.stage_status[Stage.ASR] == "succeeded"


def test_rt01_stage_timeout_kills_subprocess(job_spec, tmp_path):
    policy = TimeoutPolicy(
        stages={**TimeoutPolicy().stages, Stage.ASR: StageTimeout(base_sec=1.5, per_audio_sec=0)}
    )
    started = time.monotonic()
    with pytest.raises(StageTimeoutError) as exc:
        run(job_spec, tmp_path / "wd", "timeout", timeouts=policy)
    elapsed = time.monotonic() - started
    assert exc.value.stage is Stage.ASR
    assert exc.value.retryable
    assert elapsed < 15, elapsed


def test_rt02_diarize_failure_retries_before_last_attempt(job_spec, tmp_path):
    with pytest.raises(TransientPipelineError) as exc:
        run(job_spec, tmp_path / "wd", "diarize_fail")
    assert exc.value.code is ErrorCode.DIARIZATION_FAILED


def test_rt02_diarize_failure_falls_back_on_last_attempt(job_spec, tmp_path):
    last = job_spec.model_copy(update={"attempt": 3, "max_attempts": 3})
    wd = tmp_path / "wd"
    outcome = run(last, wd, "diarize_fail")
    assert outcome.stage_status[Stage.DIARIZE] == "fallback"
    assert outcome.stage_status[Stage.SUMMARIZE] == "succeeded"
    assert [w.code for w in outcome.warnings] == ["DIARIZATION_FALLBACK"]
    transcript = read_artifact(wd, Stage.MERGE)
    assert isinstance(transcript, Transcript)
    assert transcript.diarization_status == "fallback"


def test_rt14_summary_failure_then_regenerate_without_asr(job_spec, tmp_path):
    wd = tmp_path / "wd"
    rec = Recorder()
    with pytest.raises(PermanentPipelineError) as exc:
        run(job_spec, wd, "summary_fail", rec=rec)
    assert exc.value.stage is Stage.SUMMARIZE
    assert Stage.MERGE in rec.done  # transcript đã persist được (meeting "partial")
    asr_mtime = artifact_path(wd, Stage.ASR).stat().st_mtime_ns

    regen = job_spec.model_copy(update={"from_stage": Stage.SUMMARIZE})
    outcome = run(regen, wd, "ok")
    assert outcome.stage_status[Stage.ASR] == "skipped"
    assert outcome.stage_status[Stage.SUMMARIZE] == "succeeded"
    assert artifact_path(wd, Stage.ASR).stat().st_mtime_ns == asr_mtime


def test_from_stage_reruns_that_stage_and_later(job_spec, tmp_path):
    wd = tmp_path / "wd"
    run(job_spec, wd)
    outcome = run(job_spec.model_copy(update={"from_stage": Stage.ASR}), wd)
    assert [outcome.stage_status[s] for s in STAGES] == [
        "skipped",
        "skipped",
        "succeeded",
        "succeeded",
        "succeeded",
        "succeeded",
    ]


@pytest.mark.parametrize("next_attempt", [2, 1], ids=["retry", "requeue-after-sigterm"])
def test_from_stage_is_applied_once_per_job(job_spec, tmp_path, next_attempt):
    """Retry của một job from_stage=asr không được chạy lại ASR đã xong."""
    wd = tmp_path / "wd"
    spec = job_spec.model_copy(update={"from_stage": Stage.ASR})
    with pytest.raises(PermanentPipelineError):
        run(spec, wd, "summary_fail")
    asr_mtime = artifact_path(wd, Stage.ASR).stat().st_mtime_ns

    # SIGTERM trả lease mà không tăng attempt (RT-09), nên attempt có thể vẫn là 1.
    retry = spec.model_copy(update={"attempt": next_attempt})
    outcome = run(retry, wd, "ok")
    assert outcome.stage_status[Stage.ASR] == "skipped"
    assert outcome.stage_status[Stage.SUMMARIZE] == "succeeded"
    assert artifact_path(wd, Stage.ASR).stat().st_mtime_ns == asr_mtime


def test_summarize_only_with_override_skips_other_stages(job_spec, tmp_path):
    override = write_json_atomic(tmp_path / "edited.json", data.transcript())
    spec = job_spec.model_copy(
        update={"from_stage": Stage.SUMMARIZE, "transcript_override_path": str(override)}
    )
    rec = Recorder()
    outcome = run(spec, tmp_path / "wd", rec=rec)
    assert outcome.stage_status == {Stage.SUMMARIZE: "succeeded"}
    assert rec.done == [Stage.SUMMARIZE]
    assert outcome.transcript_path is None


def test_rt15_cancel_between_stages(job_spec, tmp_path):
    rec = Recorder()
    with pytest.raises(PipelineCancelledError) as exc:
        run_job(
            job_spec,
            workdir=tmp_path / "wd",
            on_stage_done=rec.on_stage_done,
            is_cancelled=lambda: Stage.PREPROCESS in rec.done,
            backend="fake",
        )
    assert exc.value.stage is Stage.VAD
    assert rec.done == [Stage.PREPROCESS]


class Beats:
    """Ghi lại thời điểm `on_heartbeat` được gọi."""

    def __init__(self, fail_when=None):
        self.times: list[float] = []
        self.fail_when = fail_when

    def __call__(self):
        self.times.append(time.monotonic())
        if self.fail_when is not None and self.fail_when():
            raise RuntimeError("DB down")

    def max_gap(self) -> float:
        return max(b - a for a, b in zip(self.times, self.times[1:], strict=False))


def test_heartbeat_keeps_beating_through_a_silent_stage(job_spec, tmp_path):
    """ASR treo 3 s không báo progress: worker vẫn phải gia hạn được lease."""
    beats = Beats()
    run(
        job_spec,
        tmp_path / "wd",
        "timeout",
        env={"FAKE_HANG_SEC": "3"},
        on_heartbeat=beats,
        heartbeat_sec=0.5,
    )
    assert len(beats.times) >= 6
    assert beats.max_gap() < 1.5, beats.max_gap()


def test_heartbeat_starts_immediately_and_covers_skipped_stages(job_spec, tmp_path):
    wd = tmp_path / "wd"
    run(job_spec, wd)
    beats = Beats()
    outcome = run(job_spec, wd, on_heartbeat=beats, heartbeat_sec=0)
    assert set(outcome.stage_status.values()) == {"skipped"}
    # Một lần khi bắt đầu, cộng một lần trước mỗi stage.
    assert len(beats.times) == len(STAGES) + 1


def test_heartbeat_error_kills_the_running_stage(job_spec, tmp_path):
    wd = tmp_path / "wd"
    in_asr = Beats(fail_when=lambda: artifact_path(wd, Stage.VAD).exists())
    started = time.monotonic()
    with pytest.raises(RuntimeError, match="DB down"):
        run(job_spec, wd, "timeout", on_heartbeat=in_asr, heartbeat_sec=0.2)
    # ASR treo 3600 s: thoát nhanh nghĩa là stage đã bị kill, không chờ hết.
    assert time.monotonic() - started < 15
    assert not artifact_path(wd, Stage.ASR).exists()


def test_rt15_cancel_during_a_stage_kills_it_within_a_second(job_spec, tmp_path):
    wd = tmp_path / "wd"
    rec = Recorder()
    cancelled_at: list[float] = []

    def is_cancelled():
        # ASR treo 3600 s: hủy ngay khi đã vào ASR.
        if artifact_path(wd, Stage.VAD).exists():
            cancelled_at.append(time.monotonic())
            return True
        return False

    with pytest.raises(PipelineCancelledError) as exc:
        run(job_spec, wd, "timeout", rec=rec, is_cancelled=is_cancelled)

    assert exc.value.stage is Stage.ASR
    assert time.monotonic() - cancelled_at[0] < 2
    assert rec.done == [Stage.PREPROCESS, Stage.VAD]
    assert not artifact_path(wd, Stage.ASR).exists()

    # Chạy lại cùng workdir: tiếp tục từ checkpoint, ASR chạy lại từ đầu.
    outcome = run(job_spec, wd)
    assert outcome.stage_status[Stage.VAD] == "skipped"
    assert outcome.stage_status[Stage.ASR] == "succeeded"


def test_cancel_during_diarize_never_falls_back(job_spec, tmp_path):
    """Lượt cuối, diarize lỗi thì fallback 1 speaker; nhưng bị hủy thì phải dừng."""
    wd = tmp_path / "wd"
    last = job_spec.model_copy(update={"attempt": 3, "max_attempts": 3})
    rec = Recorder()

    def diarize_running():
        return any(stage is Stage.DIARIZE and v < 1 for stage, v in rec.progress)

    with pytest.raises(PipelineCancelledError) as exc:
        run(
            last,
            wd,
            "slow",
            rec=rec,
            env={"FAKE_STAGE_SLEEP_SEC": "2"},
            is_cancelled=diarize_running,
        )
    assert exc.value.stage is Stage.DIARIZE
    assert not artifact_path(wd, Stage.DIARIZE).exists()
    assert Stage.DIARIZE not in rec.done


def test_timeout_scales_with_duration():
    policy = TimeoutPolicy()
    assert policy.timeout_for(Stage.ASR, 600) == 300 + 2.0 * 600
    assert policy.timeout_for(Stage.PREPROCESS, None) == 120 + 0.05 * 3600


def test_overall_progress_weights():
    assert sum(STAGE_WEIGHTS.values()) == pytest.approx(1.0)
    assert overall_progress(Stage.PREPROCESS, 0) == 0
    assert overall_progress(Stage.SUMMARIZE, 1.0) == 1.0
    assert overall_progress(Stage.SUMMARIZE, 0.0) == 0.85


# ---------------------------------------------------------------- run_process


def test_run_process_kills_whole_process_group(tmp_path):
    pid_file = tmp_path / "grandchild.pid"
    script = (
        "import subprocess, sys, time\n"
        "p = subprocess.Popen(['sleep', '60'])\n"
        f"open({str(pid_file)!r}, 'w').write(str(p.pid))\n"
        "time.sleep(60)\n"
    )
    with pytest.raises(StageTimeoutError):
        run_process([sys.executable, "-c", script], stage=Stage.ASR, timeout_sec=1.0)

    grandchild = int(pid_file.read_text())
    for _ in range(50):
        try:
            os.kill(grandchild, 0)
        except ProcessLookupError:
            break
        # Có thể còn là zombie chờ init thu dọn; kiểm tra trạng thái trong /proc.
        stat = Path(f"/proc/{grandchild}/stat")
        if stat.exists() and stat.read_text().split()[2] == "Z":
            break
        time.sleep(0.1)
    else:
        pytest.fail("process cháu vẫn còn chạy sau khi timeout")


def test_run_process_kills_child_when_callback_raises(tmp_path):
    """Callback của worker lỗi (ví dụ mất kết nối DB) không được để lại stage mồ côi."""
    pid_file = tmp_path / "child.pid"
    script = (
        "import json, os, time\n"
        f"open({str(pid_file)!r}, 'w').write(str(os.getpid()))\n"
        "print(json.dumps({'event': 'progress', 'value': 0.1}), flush=True)\n"
        "time.sleep(60)\n"
    )

    def broken_callback(stage, value):
        raise RuntimeError("DB down")

    with pytest.raises(RuntimeError):
        run_process(
            [sys.executable, "-c", script],
            stage=Stage.ASR,
            timeout_sec=30,
            on_progress=broken_callback,
        )
    child = int(pid_file.read_text())
    with pytest.raises(ProcessLookupError):
        os.kill(child, 0)


def test_run_process_kills_child_when_tick_raises(tmp_path):
    pid_file = tmp_path / "child.pid"
    script = (
        f"import os, time\nopen({str(pid_file)!r}, 'w').write(str(os.getpid()))\ntime.sleep(60)\n"
    )

    def tick():
        if pid_file.exists() and pid_file.read_text():
            raise RuntimeError("lease lost")

    with pytest.raises(RuntimeError):
        run_process([sys.executable, "-c", script], stage=Stage.ASR, timeout_sec=30, on_tick=tick)
    child = int(pid_file.read_text())
    with pytest.raises(ProcessLookupError):
        os.kill(child, 0)


def test_run_process_forwards_progress_and_ignores_noise():
    script = (
        "import json\n"
        "print('không phải json')\n"
        "print(json.dumps({'event': 'progress', 'stage': 'asr', 'value': 0.5}))\n"
    )
    seen = []
    code = run_process(
        [sys.executable, "-c", script],
        stage=Stage.ASR,
        timeout_sec=30,
        on_progress=lambda s, v: seen.append((s, v)),
    )
    assert code == 0
    assert seen == [(Stage.ASR, 0.5)]


def test_pipeline_python_selects_the_stage_interpreter(job_spec, tmp_path, monkeypatch):
    monkeypatch.setenv("PIPELINE_PYTHON", sys.executable)
    assert stage_command(Stage.ASR, tmp_path)[0] == sys.executable
    outcome = run(job_spec, tmp_path / "wd")
    assert set(outcome.stage_status.values()) == {"succeeded"}


def test_pipeline_python_must_be_executable(job_spec, tmp_path, monkeypatch):
    monkeypatch.setenv("PIPELINE_PYTHON", str(tmp_path / "missing" / "python"))
    with pytest.raises(PermanentPipelineError) as exc:
        run(job_spec, tmp_path / "wd")
    assert exc.value.code is ErrorCode.INTERNAL_ERROR
    assert str(tmp_path) not in exc.value.message


def test_unknown_exit_code_is_transient_crash(job_spec, tmp_path, monkeypatch):
    from meeting_pipeline import runner

    monkeypatch.setattr(
        runner,
        "stage_command",
        lambda stage, wd, backend=None: [sys.executable, "-c", "import sys; sys.exit(3)"],
    )
    with pytest.raises(TransientPipelineError) as exc:
        runner.run_job(job_spec, workdir=tmp_path / "wd")
    assert exc.value.code is ErrorCode.STAGE_CRASHED


def test_exit_zero_without_artifact_is_invalid_output(job_spec, tmp_path, monkeypatch):
    from meeting_pipeline import runner

    monkeypatch.setattr(
        runner, "stage_command", lambda stage, wd, backend=None: [sys.executable, "-c", "pass"]
    )
    with pytest.raises(PermanentPipelineError) as exc:
        runner.run_job(job_spec, workdir=tmp_path / "wd")
    assert exc.value.code is ErrorCode.PIPELINE_OUTPUT_INVALID
