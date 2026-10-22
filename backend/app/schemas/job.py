"""Pydantic schemas cho Job xử lý tiến trình AI."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

JobStatus = Literal[
    "queued",
    "running",
    "retry_scheduled",
    "succeeded",
    "failed",
    "cancelled",
]

PipelineStage = Literal[
    "preprocess",
    "vad",
    "asr",
    "diarize",
    "merge",
    "summarize",
]


class JobErrorOut(BaseModel):
    """Thông tin lỗi khi stage hoặc job gặp sự cố."""

    code: str = Field(..., description="Mã lỗi của pipeline hoặc hệ thống")
    message: str = Field(..., description="Mô tả lỗi")
    retryable: bool = Field(..., description="Cờ xác định lỗi có thể retry tự động hay không")
    stage: str | None = Field(default=None, description="Stage phát sinh lỗi")

    model_config = ConfigDict(extra="forbid")


class JobOut(BaseModel):
    """Schema thông tin Job xử lý bất đồng bộ theo hợp đồng REST API."""

    id: str = Field(..., description="UUID của job")
    meeting_id: str = Field(..., description="UUID của cuộc họp tương ứng")
    status: JobStatus = Field(..., description="Trạng thái hiện tại của job")
    stage: PipelineStage | None = Field(default=None, description="Stage đang chạy hoặc vừa chạy")
    from_stage: PipelineStage | None = Field(
        default=None,
        description="Stage bắt đầu chạy lại nếu có",
    )
    progress: float = Field(..., ge=0.0, le=1.0, description="Tiến độ tổng thể từ 0.0 đến 1.0")
    stages: dict[str, str] = Field(
        default_factory=dict,
        description="Trạng thái chi tiết của từng stage trong pipeline",
    )
    attempt: int = Field(..., ge=1, description="Lượt chạy hiện tại (bắt đầu từ 1)")
    max_attempts: int = Field(default=3, description="Số lượt chạy tối đa cho phép")
    next_run_at: datetime | str | None = Field(
        default=None,
        description="Thời điểm ISO 8601 UTC dự kiến chạy lượt tiếp theo",
    )
    error: JobErrorOut | None = Field(
        default=None,
        description="Thông tin lỗi nếu trạng thái là retry_scheduled hoặc failed",
    )
    created_at: datetime | str = Field(
        ...,
        description="Thời điểm tạo job theo chuẩn ISO 8601 UTC",
    )
    started_at: datetime | str | None = Field(
        default=None,
        description="Thời điểm bắt đầu chạy job",
    )
    finished_at: datetime | str | None = Field(
        default=None,
        description="Thời điểm hoàn tất hoặc dừng job",
    )

    model_config = ConfigDict(extra="forbid")


class JobRetryCreate(BaseModel):
    """Yêu cầu chạy lại tiến trình xử lý cuộc họp từ một stage."""

    from_stage: PipelineStage | None = Field(
        default=None,
        description="Stage bắt đầu chạy lại (asr, diarize, summarize) hoặc null",
    )

    model_config = ConfigDict(extra="forbid")
