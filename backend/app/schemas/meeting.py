"""Pydantic schemas cho Cuộc họp (Meeting) và Người nói (Speaker)."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.job import JobOut

MeetingStatus = Literal["queued", "processing", "ready", "partial", "failed"]
MeetingSource = Literal["upload", "recording"]


class MeetingAudioOut(BaseModel):
    """Thông tin file audio của cuộc họp."""

    available: bool = Field(..., description="Cờ xác định file audio có sẵn để nghe/tải không")
    mime_type: str | None = Field(default=None, description="MIME type của file audio")
    size_bytes: int | None = Field(default=None, description="Dung lượng file tính bằng bytes")
    retention_until: datetime | str | None = Field(
        default=None, description="Thời điểm hết hạn lưu trữ audio theo retention policy"
    )

    model_config = ConfigDict(extra="forbid")


class MeetingArtifactsOut(BaseModel):
    """Trạng thái các artifact AI của cuộc họp."""

    transcript: str = Field(..., description="Trạng thái transcript (pending/ready/failed)")
    diarization: str = Field(..., description="Trạng thái diarization (ok/fallback/pending/failed)")
    summary: str = Field(
        ...,
        description="Trạng thái summary (pending/ready/failed/insufficient_content/disabled)",
    )

    model_config = ConfigDict(extra="forbid")


class SpeakerOut(BaseModel):
    """Thông tin người nói trong cuộc họp."""

    id: str = Field(..., description="UUID của speaker")
    meeting_id: str = Field(..., description="UUID của cuộc họp")
    label: str = Field(..., description="Nhãn thô từ diarization, ví dụ SPEAKER_00")
    default_name: str = Field(..., description="Tên mặc định có thứ tự xuất hiện, ví dụ Speaker 1")
    display_name: str = Field(..., description="Tên hiển thị do người dùng đặt hoặc mặc định")
    version: int = Field(default=1, description="Phiên bản phục vụ optimistic locking")

    model_config = ConfigDict(extra="forbid")


class MeetingOut(BaseModel):
    """Schema thông tin Cuộc họp theo hợp đồng REST API."""

    id: str = Field(..., description="UUID của cuộc họp")
    title: str = Field(..., description="Tiêu đề cuộc họp")
    source: MeetingSource = Field(..., description="Nguồn audio (upload hoặc recording)")
    status: MeetingStatus = Field(..., description="Trạng thái xử lý tổng thể của cuộc họp")
    language: str = Field(default="vi", description="Ngôn ngữ chính (mặc định 'vi')")
    meeting_date: str | None = Field(
        default=None,
        description="Ngày diễn ra cuộc họp định dạng YYYY-MM-DD",
    )
    duration_sec: float | None = Field(default=None, description="Thời lượng audio tính bằng giây")
    num_speakers_hint: int | None = Field(
        default=None,
        description="Số lượng người nói gợi ý từ người dùng",
    )
    audio: MeetingAudioOut = Field(..., description="Thông tin tệp âm thanh")
    artifacts: MeetingArtifactsOut = Field(..., description="Trạng thái các artifacts được sinh ra")
    warnings: list[str] = Field(default_factory=list, description="Danh sách các cảnh báo xử lý")
    latest_job_id: str | None = Field(default=None, description="UUID của job xử lý gần nhất")
    created_at: datetime | str = Field(..., description="Thời điểm tạo cuộc họp ISO 8601 UTC")
    updated_at: datetime | str = Field(..., description="Thời điểm cập nhật gần nhất ISO 8601 UTC")
    version: int = Field(default=1, description="Phiên bản phục vụ optimistic locking")

    model_config = ConfigDict(extra="forbid")


class MeetingDetailOut(MeetingOut):
    """Schema chi tiết cuộc họp kèm job gần nhất và danh sách người nói."""

    latest_job: JobOut | None = Field(default=None, description="Chi tiết job xử lý gần nhất")
    speakers: list[SpeakerOut] = Field(default_factory=list, description="Danh sách người nói")

    model_config = ConfigDict(extra="forbid")
