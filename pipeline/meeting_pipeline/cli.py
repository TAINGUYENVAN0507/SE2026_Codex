"""CLI của pipeline.

    python -m meeting_pipeline run-stage <stage> --workdir <dir> [--backend fake|real]
    python -m meeting_pipeline export-contracts [--check]

`run-stage` là giao tiếp giữa runner và subprocess của từng stage:

- stdout: mỗi dòng một sự kiện JSON, ví dụ `{"event": "progress", "stage": "asr", "value": 0.5}`.
- stderr: log kỹ thuật. Không bao giờ in transcript, prompt hay nội dung audio.
- Exit code: 0 = OK, 10 = lỗi permanent, 20 = lỗi transient. Chi tiết lỗi nằm trong
  `<stage>.error.json`.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import traceback
from pathlib import Path

from meeting_pipeline import contracts_export
from meeting_pipeline.errors import (
    EXIT_OK,
    ErrorCode,
    PermanentPipelineError,
    PipelineError,
)
from meeting_pipeline.registry import BACKENDS, get_stage
from meeting_pipeline.schemas import JOB_FILE, STAGES, Stage, error_file
from meeting_pipeline.stages.base import execute_stage
from meeting_pipeline.workdir import write_json_atomic

log = logging.getLogger("meeting_pipeline")


def emit(event: str, stage: Stage, **fields: object) -> None:
    print(json.dumps({"event": event, "stage": stage.value, **fields}), flush=True)


def _describe_unexpected(exc: BaseException) -> str:
    """Mô tả lỗi không lường trước mà không lộ message (có thể chứa dữ liệu người dùng)."""
    frames = traceback.extract_tb(exc.__traceback__)
    where = f" tại {Path(frames[-1].filename).name}:{frames[-1].lineno}" if frames else ""
    return f"{type(exc).__name__}{where}"


def run_stage(stage: Stage, workdir: Path, backend: str | None) -> int:
    err_path = workdir / error_file(stage)
    err_path.unlink(missing_ok=True)
    try:
        if not (workdir / JOB_FILE).is_file():
            raise PermanentPipelineError(ErrorCode.MISSING_INPUT, stage, f"thiếu {JOB_FILE}")
        fn = get_stage(stage, backend)  # type: ignore[arg-type]
        path = execute_stage(
            stage, workdir, fn, progress=lambda v: emit("progress", stage, value=round(v, 3))
        )
    except PipelineError as e:
        if e.stage is None:
            e.stage = stage
        write_json_atomic(err_path, e.to_report())
        log.warning("stage %s lỗi: %s (%s)", stage.value, e.code.value, e.kind.value)
        return e.exit_code
    except Exception as e:
        err = PermanentPipelineError(ErrorCode.INTERNAL_ERROR, stage, _describe_unexpected(e))
        write_json_atomic(err_path, err.to_report())
        log.error("stage %s lỗi không lường trước: %s", stage.value, err.message)
        return err.exit_code
    emit("done", stage, artifact=path.name)
    return EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m meeting_pipeline")
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run-stage", help="chạy một stage trong workdir của job")
    run.add_argument("stage", choices=[s.value for s in STAGES])
    run.add_argument("--workdir", type=Path, required=True)
    run.add_argument("--backend", choices=BACKENDS, default=None, help="mặc định PIPELINE_BACKEND")

    exp = sub.add_parser("export-contracts", help="sinh contracts/pipeline từ Pydantic")
    exp.add_argument("--check", action="store_true")
    exp.add_argument("--root", type=Path, default=contracts_export.REPO_ROOT)
    return parser


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        stream=sys.stderr, level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )
    args = build_parser().parse_args(argv)
    if args.command == "run-stage":
        return run_stage(Stage(args.stage), args.workdir, args.backend)
    extra = ["--check"] if args.check else []
    return contracts_export.main(["--root", str(args.root), *extra])
