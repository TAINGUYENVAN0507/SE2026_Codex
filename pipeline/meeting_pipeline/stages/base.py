"""Khung chạy một stage: đọc job, gọi implementation, validate và ghi artifact."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from pydantic import ValidationError

from meeting_pipeline.errors import ErrorCode, PermanentPipelineError
from meeting_pipeline.schemas import STAGE_OUTPUT_MODELS, Artifact, JobSpec, Stage, Transcript
from meeting_pipeline.workdir import artifact_path, read_artifact, read_job, write_json_atomic


def _ignore_progress(_: float) -> None:
    pass


@dataclass
class StageContext:
    stage: Stage
    workdir: Path
    spec: JobSpec
    progress: Callable[[float], None] = field(default=_ignore_progress)

    def input(self, stage: Stage) -> Artifact:
        """Đọc artifact của stage trước. Thiếu hoặc sai schema là lỗi permanent."""
        try:
            return read_artifact(self.workdir, stage)
        except FileNotFoundError:
            raise PermanentPipelineError(
                ErrorCode.MISSING_INPUT, self.stage, f"thiếu artifact của stage {stage.value}"
            ) from None
        except ValidationError as e:
            raise PermanentPipelineError(
                ErrorCode.PIPELINE_OUTPUT_INVALID,
                self.stage,
                f"artifact của stage {stage.value} sai schema ({e.error_count()} lỗi)",
            ) from None

    def transcript(self) -> Transcript:
        """Transcript dùng cho summarize: bản override (đã sửa) nếu có, ngược lại bản merge."""
        override = self.spec.transcript_override_path
        if override is None:
            result = self.input(Stage.MERGE)
            assert isinstance(result, Transcript)
            return result
        try:
            return Transcript.model_validate_json(Path(override).read_text(encoding="utf-8"))
        except FileNotFoundError:
            raise PermanentPipelineError(
                ErrorCode.MISSING_INPUT, self.stage, "không tìm thấy transcript override"
            ) from None
        except ValidationError as e:
            raise PermanentPipelineError(
                ErrorCode.PIPELINE_OUTPUT_INVALID,
                self.stage,
                f"transcript override sai schema ({e.error_count()} lỗi)",
            ) from None


StageFn = Callable[[StageContext], Artifact]


def execute_stage(
    stage: Stage,
    workdir: Path,
    fn: StageFn,
    progress: Callable[[float], None] = _ignore_progress,
) -> Path:
    """Chạy `fn` cho `stage` và ghi artifact atomic. Trả về đường dẫn artifact."""
    ctx = StageContext(stage=stage, workdir=workdir, spec=read_job(workdir), progress=progress)
    output = fn(ctx)
    expected = STAGE_OUTPUT_MODELS[stage]
    if not isinstance(output, expected):
        raise PermanentPipelineError(
            ErrorCode.PIPELINE_OUTPUT_INVALID,
            stage,
            f"stage trả về {type(output).__name__}, cần {expected.__name__}",
        )
    # Validate lại toàn bộ để bắt cả các model được tạo bằng model_construct.
    try:
        expected.model_validate(output.model_dump())
    except ValidationError as e:
        raise PermanentPipelineError(
            ErrorCode.PIPELINE_OUTPUT_INVALID, stage, f"output sai schema ({e.error_count()} lỗi)"
        ) from None
    path = write_json_atomic(artifact_path(workdir, stage), output)
    progress(1.0)
    return path
