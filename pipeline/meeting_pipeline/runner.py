"""Stage runner: chạy cả pipeline cho một job (AI-04).

Worker của backend gọi `run_job()`. Runner chịu trách nhiệm ở cấp stage:

- Mỗi stage chạy trong một subprocess riêng (`python -m meeting_pipeline run-stage`),
  trong process group riêng. Quá timeout thì kill cả group, kể cả ffmpeg con.
- Timeout tính theo thời lượng audio: `base_sec + per_audio_sec × duration_sec`.
- Checkpoint: stage đã có artifact hợp lệ thì bỏ qua, nên retry không chạy lại ASR
  khi chỉ summary lỗi.
- Diarization không bao giờ chặn transcript: lỗi permanent, hoặc lỗi ở lượt cuối,
  thì ghi output fallback 1 speaker và đi tiếp.
- Kiểm tra hủy job giữa các stage.

Worker (B) chịu trách nhiệm ở cấp job: lease, heartbeat, số lượt retry, persist.
Mọi callback được gọi trên thread của người gọi `run_job()`.
"""

from __future__ import annotations

import contextlib
import json
import logging
import os
import queue
import signal
import subprocess
import sys
import threading
import time
from collections import deque
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from pydantic import ValidationError

from meeting_pipeline.errors import (
    EXIT_PERMANENT,
    EXIT_TRANSIENT,
    ErrorCode,
    ErrorReport,
    PermanentPipelineError,
    PipelineCancelledError,
    PipelineError,
    StageTimeoutError,
    TransientPipelineError,
)
from meeting_pipeline.fallbacks import diarization_fallback
from meeting_pipeline.schemas import (
    ARTIFACT_FILES,
    RTTM_FILE,
    STAGES,
    JobSpec,
    PipelineWarning,
    PreprocessOutput,
    Stage,
    error_file,
)
from meeting_pipeline.workdir import (
    artifact_path,
    has_valid_artifact,
    read_artifact,
    write_job,
    write_json_atomic,
)

log = logging.getLogger("meeting_pipeline.runner")

StageStatus = Literal["succeeded", "skipped", "fallback"]
ProgressFn = Callable[[Stage, float], None]
StageDoneFn = Callable[[Stage, Path], None]
CancelledFn = Callable[[], bool]

# Tỉ trọng ước lượng của từng stage trong tổng thời gian, dùng cho thanh progress.
STAGE_WEIGHTS: dict[Stage, float] = {
    Stage.PREPROCESS: 0.05,
    Stage.VAD: 0.05,
    Stage.ASR: 0.50,
    Stage.DIARIZE: 0.20,
    Stage.MERGE: 0.05,
    Stage.SUMMARIZE: 0.15,
}


def overall_progress(stage: Stage, value: float) -> float:
    """Đổi progress trong một stage thành progress của cả job (0..1)."""
    done = sum(STAGE_WEIGHTS[s] for s in STAGES[: STAGES.index(stage)])
    return round(done + STAGE_WEIGHTS[stage] * min(max(value, 0.0), 1.0), 3)


@dataclass(frozen=True)
class StageTimeout:
    base_sec: float
    per_audio_sec: float


@dataclass(frozen=True)
class TimeoutPolicy:
    """Giá trị khởi tạo, đặt bảo thủ. Hiệu chỉnh thành 2 × p95 sau benchmark AI-13."""

    stages: Mapping[Stage, StageTimeout] = field(
        default_factory=lambda: {
            Stage.PREPROCESS: StageTimeout(120, 0.2),
            Stage.VAD: StageTimeout(120, 0.2),
            Stage.ASR: StageTimeout(300, 2.0),
            Stage.DIARIZE: StageTimeout(300, 1.5),
            Stage.MERGE: StageTimeout(60, 0.02),
            Stage.SUMMARIZE: StageTimeout(300, 0.1),
        }
    )
    # Trước khi preprocess xong chưa biết thời lượng thật, dùng giới hạn trên.
    unknown_duration_sec: float = 3600

    def timeout_for(self, stage: Stage, duration_sec: float | None) -> float:
        t = self.stages[stage]
        duration = self.unknown_duration_sec if duration_sec is None else duration_sec
        return t.base_sec + t.per_audio_sec * duration


@dataclass
class PipelineOutcome:
    stage_status: dict[Stage, StageStatus]
    transcript_path: Path | None
    summary_path: Path | None
    warnings: list[PipelineWarning]
    timings: dict[Stage, float]


def _noop_progress(stage: Stage, value: float) -> None:
    pass


def _noop_done(stage: Stage, path: Path) -> None:
    pass


def _never_cancelled() -> bool:
    return False


def run_job(
    spec: JobSpec,
    *,
    workdir: Path,
    on_progress: ProgressFn = _noop_progress,
    on_stage_done: StageDoneFn = _noop_done,
    is_cancelled: CancelledFn = _never_cancelled,
    timeouts: TimeoutPolicy | None = None,
    backend: str | None = None,
    env: Mapping[str, str] | None = None,
) -> PipelineOutcome:
    """Chạy pipeline cho `spec` trong `workdir`.

    Raise `PermanentPipelineError`, `TransientPipelineError` (gồm `StageTimeoutError`)
    hoặc `PipelineCancelledError`. Artifact của các stage đã xong vẫn nằm trong
    workdir, nên lần retry sau chạy tiếp từ checkpoint.
    """
    timeouts = timeouts or TimeoutPolicy()
    workdir.mkdir(parents=True, exist_ok=True)
    write_job(workdir, spec)

    plan = _plan(spec, workdir)
    status: dict[Stage, StageStatus] = {}
    timings: dict[Stage, float] = {}

    for stage in plan:
        if is_cancelled():
            raise PipelineCancelledError(stage)

        if has_valid_artifact(workdir, stage):
            status[stage] = "skipped"
            timings[stage] = 0.0
            on_progress(stage, 1.0)
            on_stage_done(stage, artifact_path(workdir, stage))
            continue

        started = time.monotonic()
        try:
            _run_stage_subprocess(
                stage,
                workdir,
                timeout_sec=timeouts.timeout_for(stage, _duration(workdir)),
                on_progress=on_progress,
                backend=backend,
                env=env,
            )
            status[stage] = "succeeded"
        except PipelineError as e:
            if stage is not Stage.DIARIZE or (e.retryable and not spec.is_last_attempt):
                raise
            log.warning("diarization lỗi (%s), dùng fallback 1 speaker", e.code.value)
            fallback = diarization_fallback(f"diarization lỗi ({e.code.value}), gộp 1 speaker")
            write_json_atomic(artifact_path(workdir, stage), fallback)
            status[stage] = "fallback"
        finally:
            timings[stage] = round(time.monotonic() - started, 3)

        on_progress(stage, 1.0)
        on_stage_done(stage, artifact_path(workdir, stage))

    transcript = artifact_path(workdir, Stage.MERGE)
    summary = artifact_path(workdir, Stage.SUMMARIZE)
    return PipelineOutcome(
        stage_status=status,
        transcript_path=transcript if transcript.exists() else None,
        summary_path=summary if summary.exists() else None,
        warnings=_collect_warnings(workdir, plan),
        timings=timings,
    )


def _plan(spec: JobSpec, workdir: Path) -> list[Stage]:
    """Danh sách stage cần xét, và xóa artifact của các stage phải chạy lại."""
    if spec.from_stage is None:
        return list(STAGES)

    start = STAGES.index(spec.from_stage)
    for stage in STAGES[start:]:
        artifact_path(workdir, stage).unlink(missing_ok=True)
        (workdir / error_file(stage)).unlink(missing_ok=True)
        if stage is Stage.DIARIZE:
            (workdir / RTTM_FILE).unlink(missing_ok=True)

    # Tạo lại tóm tắt từ transcript đã sửa: không cần các stage trước.
    if spec.from_stage is Stage.SUMMARIZE and spec.transcript_override_path:
        return [Stage.SUMMARIZE]
    return list(STAGES)


def _duration(workdir: Path) -> float | None:
    try:
        pre = read_artifact(workdir, Stage.PREPROCESS)
    except (OSError, ValidationError, ValueError):
        return None
    return pre.duration_sec if isinstance(pre, PreprocessOutput) else None


def _collect_warnings(workdir: Path, plan: Sequence[Stage]) -> list[PipelineWarning]:
    """Gom warning từ mọi artifact, bỏ trùng theo (code, stage)."""
    seen: set[tuple[str, Stage]] = set()
    result: list[PipelineWarning] = []
    candidates: list[PipelineWarning] = []
    for stage in plan:
        try:
            candidates.extend(getattr(read_artifact(workdir, stage), "warnings", []))
        except (OSError, ValidationError, ValueError):
            continue
    for w in candidates:
        if (w.code, w.stage) not in seen:
            seen.add((w.code, w.stage))
            result.append(w)
    return result


# ------------------------------------------------------------------ subprocess


def stage_command(stage: Stage, workdir: Path, backend: str | None = None) -> list[str]:
    cmd = [sys.executable, "-m", "meeting_pipeline", "run-stage", stage.value]
    cmd += ["--workdir", str(workdir)]
    if backend:
        cmd += ["--backend", backend]
    return cmd


def _run_stage_subprocess(
    stage: Stage,
    workdir: Path,
    *,
    timeout_sec: float,
    on_progress: ProgressFn,
    backend: str | None,
    env: Mapping[str, str] | None,
) -> None:
    returncode = run_process(
        stage_command(stage, workdir, backend),
        stage=stage,
        timeout_sec=timeout_sec,
        on_progress=on_progress,
        env=env,
    )
    if returncode == 0:
        if not has_valid_artifact(workdir, stage):
            raise PermanentPipelineError(
                ErrorCode.PIPELINE_OUTPUT_INVALID,
                stage,
                f"stage báo thành công nhưng {ARTIFACT_FILES[stage]} thiếu hoặc sai schema",
            )
        return
    raise _error_from_exit(stage, workdir, returncode)


def _error_from_exit(stage: Stage, workdir: Path, returncode: int) -> PipelineError:
    if returncode in (EXIT_PERMANENT, EXIT_TRANSIENT):
        try:
            report = ErrorReport.model_validate_json(
                (workdir / error_file(stage)).read_text(encoding="utf-8")
            )
            return PipelineError.from_report(report)
        except (OSError, ValidationError, ValueError):
            pass
    cls = PermanentPipelineError if returncode == EXIT_PERMANENT else TransientPipelineError
    # Exit code lạ (bị kill bởi OOM killer, segfault...) được coi là transient.
    return cls(ErrorCode.STAGE_CRASHED, stage, f"subprocess kết thúc với mã {returncode}")


def run_process(
    cmd: Sequence[str],
    *,
    stage: Stage,
    timeout_sec: float,
    on_progress: ProgressFn = _noop_progress,
    env: Mapping[str, str] | None = None,
) -> int:
    """Chạy `cmd` trong process group riêng, chuyển sự kiện progress về caller thread.

    Quá `timeout_sec` thì SIGKILL cả group và raise `StageTimeoutError`.
    """
    proc = subprocess.Popen(
        list(cmd),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
        env={**os.environ, **(env or {})},
    )
    events: queue.Queue[float] = queue.Queue()
    stderr_tail: deque[str] = deque(maxlen=20)

    def read_stdout() -> None:
        assert proc.stdout is not None
        for line in proc.stdout:
            try:
                event = json.loads(line)
            except ValueError:
                continue
            if isinstance(event, dict) and event.get("event") == "progress":
                events.put(float(event.get("value", 0.0)))

    def read_stderr() -> None:
        assert proc.stderr is not None
        for line in proc.stderr:
            stderr_tail.append(line.rstrip())

    readers = [threading.Thread(target=f, daemon=True) for f in (read_stdout, read_stderr)]
    for t in readers:
        t.start()

    deadline = time.monotonic() + timeout_sec
    timed_out = False
    while True:
        with contextlib.suppress(queue.Empty):
            on_progress(stage, events.get(timeout=0.1))
        if proc.poll() is not None:
            break
        if time.monotonic() > deadline:
            timed_out = True
            _kill_group(proc)
            break

    proc.wait()
    for t in readers:
        t.join(timeout=2)
    while not events.empty():
        on_progress(stage, events.get_nowait())

    if timed_out:
        log.warning("stage %s quá %.0f s, đã kill process group", stage.value, timeout_sec)
        raise StageTimeoutError(stage, timeout_sec=timeout_sec)
    if proc.returncode != 0:
        # Chỉ ghi ở mức debug: stderr là log kỹ thuật của chính pipeline.
        log.debug("stderr của stage %s:\n%s", stage.value, "\n".join(stderr_tail))
    return proc.returncode


def _kill_group(proc: subprocess.Popen[str]) -> None:
    with contextlib.suppress(ProcessLookupError):
        os.killpg(proc.pid, signal.SIGKILL)
