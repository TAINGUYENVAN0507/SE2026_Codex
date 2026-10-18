"""Phân loại lỗi của pipeline.

Worker của backend chỉ cần biết 3 loại để quyết định retry (mục 4 của kế hoạch):

- `PermanentPipelineError`: file hỏng, quá dài, không có tiếng nói, output sai schema.
  Job chuyển `failed` ngay.
- `TransientPipelineError`: lỗi mạng, 429/5xx, OOM lần đầu. Job được retry.
- `StageTimeoutError`: stage chạy quá thời gian và bị kill. Là một dạng transient.

Khi stage chạy qua CLI, lỗi được ghi vào `<stage>.error.json` và báo bằng exit code.
`message` chỉ chứa thông tin kỹ thuật (mã, tham số, kích thước), không bao giờ chứa
nội dung transcript hay audio.
"""

from __future__ import annotations

from enum import StrEnum
from typing import ClassVar

from pydantic import Field

from meeting_pipeline.schemas import Artifact, Stage

EXIT_OK = 0
EXIT_PERMANENT = 10
EXIT_TRANSIENT = 20


class ErrorCode(StrEnum):
    # preprocess
    AUDIO_INVALID = "AUDIO_INVALID"
    AUDIO_TOO_SHORT = "AUDIO_TOO_SHORT"
    AUDIO_TOO_LONG = "AUDIO_TOO_LONG"
    # vad / asr / diarize
    NO_SPEECH_DETECTED = "NO_SPEECH_DETECTED"
    MODEL_UNAVAILABLE = "MODEL_UNAVAILABLE"
    OUT_OF_MEMORY = "OUT_OF_MEMORY"
    DIARIZATION_FAILED = "DIARIZATION_FAILED"
    # summarize
    LLM_UNAVAILABLE = "LLM_UNAVAILABLE"
    LLM_REQUEST_INVALID = "LLM_REQUEST_INVALID"
    LLM_OUTPUT_INVALID = "LLM_OUTPUT_INVALID"
    # runner / chung
    STAGE_TIMEOUT = "STAGE_TIMEOUT"
    STAGE_CRASHED = "STAGE_CRASHED"
    STAGE_NOT_IMPLEMENTED = "STAGE_NOT_IMPLEMENTED"
    MISSING_INPUT = "MISSING_INPUT"
    PIPELINE_OUTPUT_INVALID = "PIPELINE_OUTPUT_INVALID"
    PIPELINE_CANCELLED = "PIPELINE_CANCELLED"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class ErrorKind(StrEnum):
    PERMANENT = "permanent"
    TRANSIENT = "transient"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


Detail = str | int | float | bool | None


class ErrorReport(Artifact):
    """Nội dung file `<stage>.error.json`."""

    stage: Stage | None
    code: ErrorCode
    kind: ErrorKind
    retryable: bool
    message: str = Field(max_length=2000)
    details: dict[str, Detail] = {}


class PipelineError(Exception):
    kind: ClassVar[ErrorKind] = ErrorKind.PERMANENT
    exit_code: ClassVar[int] = EXIT_PERMANENT

    def __init__(
        self,
        code: ErrorCode,
        stage: Stage | None = None,
        message: str = "",
        details: dict[str, Detail] | None = None,
    ) -> None:
        self.code = ErrorCode(code)
        self.stage = Stage(stage) if stage is not None else None
        self.message = message
        self.details = dict(details or {})
        super().__init__(str(self))

    def __str__(self) -> str:
        where = self.stage.value if self.stage else "pipeline"
        return f"{self.code.value} at {where}" + (f": {self.message}" if self.message else "")

    @property
    def retryable(self) -> bool:
        return self.kind in (ErrorKind.TRANSIENT, ErrorKind.TIMEOUT)

    def to_report(self) -> ErrorReport:
        return ErrorReport(
            stage=self.stage,
            code=self.code,
            kind=self.kind,
            retryable=self.retryable,
            message=self.message[:2000],
            details=self.details,
        )

    @staticmethod
    def from_report(report: ErrorReport) -> PipelineError:
        if report.kind is ErrorKind.TIMEOUT:
            timeout = report.details.get("timeout_sec")
            return StageTimeoutError(
                report.stage or Stage.PREPROCESS,
                timeout_sec=float(timeout) if isinstance(timeout, int | float) else None,
                message=report.message,
            )
        cls = _KIND_TO_CLASS[report.kind]
        return cls(report.code, report.stage, report.message, report.details)


class PermanentPipelineError(PipelineError):
    kind = ErrorKind.PERMANENT
    exit_code = EXIT_PERMANENT


class TransientPipelineError(PipelineError):
    kind = ErrorKind.TRANSIENT
    exit_code = EXIT_TRANSIENT


class StageTimeoutError(TransientPipelineError):
    kind = ErrorKind.TIMEOUT
    exit_code = EXIT_TRANSIENT

    def __init__(self, stage: Stage, timeout_sec: float | None = None, message: str = "") -> None:
        self.timeout_sec = timeout_sec
        if not message and timeout_sec is not None:
            message = f"stage chạy quá {timeout_sec:.0f} s và đã bị dừng"
        details: dict[str, Detail] = {"timeout_sec": timeout_sec}
        super().__init__(ErrorCode.STAGE_TIMEOUT, stage, message, details)


class PipelineCancelledError(PipelineError):
    """Job bị hủy (ví dụ người dùng xóa meeting). Runner kiểm tra giữa các stage."""

    kind = ErrorKind.CANCELLED
    exit_code = EXIT_PERMANENT

    def __init__(self, stage: Stage | None = None) -> None:
        super().__init__(ErrorCode.PIPELINE_CANCELLED, stage, "job đã bị hủy")


_KIND_TO_CLASS: dict[ErrorKind, type[PipelineError]] = {
    ErrorKind.PERMANENT: PermanentPipelineError,
    ErrorKind.TRANSIENT: TransientPipelineError,
}
