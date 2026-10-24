"""Pydantic schemas cho Transcript, Segment và Speaker patch."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.meeting import SpeakerOut


class TranscriptSegmentOut(BaseModel):
    """Thông tin đoạn thoại trong transcript."""

    id: str = Field(..., description="UUID của segment")
    index: int = Field(..., description="Số thứ tự của segment trong transcript (0-indexed)")
    start_sec: float = Field(..., description="Thời điểm bắt đầu tính bằng giây")
    end_sec: float = Field(..., description="Thời điểm kết thúc tính bằng giây")
    speaker_id: str | None = Field(
        default=None,
        description="UUID của speaker tương ứng, null nếu chưa xác định",
    )
    ai_speaker_id: str | None = Field(
        default=None, description="UUID của speaker do AI gán gốc (bất biến)"
    )
    text: str = Field(..., description="Nội dung lời thoại hiện tại")
    ai_text: str = Field(..., description="Nội dung lời thoại gốc do AI nhận dạng")
    is_edited: bool = Field(
        default=False, description="Cờ đánh dấu đoạn thoại đã được người dùng sửa"
    )
    confidence: float | None = Field(
        default=None,
        description="Độ tin cậy của mô hình nhận dạng từ 0.0 đến 1.0",
    )
    flags: list[str] = Field(
        default_factory=list,
        description="Danh sách cờ cảnh báo (overlap, low_confidence)",
    )
    version: int = Field(default=1, description="Phiên bản phục vụ optimistic locking")
    updated_at: datetime | str = Field(..., description="Thời điểm cập nhật gần nhất ISO 8601 UTC")

    model_config = ConfigDict(extra="forbid")


class TranscriptOut(BaseModel):
    """Hợp đồng dữ liệu transcript của cuộc họp."""

    status: str = Field(..., description="Trạng thái transcript (pending/ready/failed)")
    diarization_status: str = Field(
        ..., description="Trạng thái phân tách người nói (ok/fallback/pending)"
    )
    speakers: list[SpeakerOut] = Field(
        default_factory=list, description="Danh sách người nói trong cuộc họp"
    )
    segments: list[TranscriptSegmentOut] = Field(
        default_factory=list, description="Danh sách các đoạn thoại"
    )

    model_config = ConfigDict(extra="forbid")


class SegmentPatch(BaseModel):
    """Schema cập nhật nội dung hoặc người nói của đoạn transcript."""

    text: str | None = Field(
        default=None,
        min_length=1,
        max_length=5000,
        description="Nội dung đoạn thoại mới sửa (1-5000 ký tự)",
    )
    speaker_id: str | None = Field(default=None, description="UUID của người nói mới được gán")
    version: int = Field(..., ge=1, description="Phiên bản hiện tại của segment ở client")

    model_config = ConfigDict(extra="forbid")

    @field_validator("text", mode="before")
    @classmethod
    def strip_text(cls, v: str | None) -> str | None:
        if isinstance(v, str):
            return v.strip()
        return v


class SpeakerPatch(BaseModel):
    """Schema cập nhật tên hiển thị của người nói."""

    display_name: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Tên hiển thị mới của người nói (1-50 ký tự)",
    )
    version: int = Field(..., ge=1, description="Phiên bản hiện tại của speaker ở client")

    model_config = ConfigDict(extra="forbid")
