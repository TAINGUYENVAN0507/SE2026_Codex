"""Đọc và ghi file trong thư mục làm việc của job.

Mọi file JSON được ghi theo kiểu atomic: ghi ra file tạm cùng thư mục rồi `os.replace`.
Nhờ vậy một stage bị kill giữa chừng không để lại artifact dở dang, và runner có thể
coi "file tồn tại và hợp lệ" là checkpoint.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from pydantic import BaseModel, ValidationError

from meeting_pipeline.schemas import (
    ARTIFACT_FILES,
    JOB_FILE,
    STAGE_OUTPUT_MODELS,
    Artifact,
    JobSpec,
    Stage,
)


def write_json_atomic(path: Path, model: BaseModel) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = model.model_dump_json(indent=2) + "\n"
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
    return path


def artifact_path(workdir: Path, stage: Stage) -> Path:
    return workdir / ARTIFACT_FILES[stage]


def read_artifact(workdir: Path, stage: Stage) -> Artifact:
    """Đọc và validate artifact. Raise FileNotFoundError hoặc ValidationError."""
    path = artifact_path(workdir, stage)
    return STAGE_OUTPUT_MODELS[stage].model_validate_json(path.read_text(encoding="utf-8"))


def has_valid_artifact(workdir: Path, stage: Stage) -> bool:
    try:
        read_artifact(workdir, stage)
    except (OSError, ValidationError, ValueError):
        return False
    return True


def write_job(workdir: Path, spec: JobSpec) -> Path:
    return write_json_atomic(workdir / JOB_FILE, spec)


def read_job(workdir: Path) -> JobSpec:
    return JobSpec.model_validate_json((workdir / JOB_FILE).read_text(encoding="utf-8"))
