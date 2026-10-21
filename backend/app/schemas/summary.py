"""Pydantic schemas cho Summary (Tóm tắt cuộc họp)."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class SummaryPointOut(BaseModel):
    """Điểm chính hoặc quyết định trong tóm tắt cuộc họp kèm ID các đoạn bằng chứng."""

    text: str = Field(..., description="Nội dung điểm chính hoặc quyết định")
    evidence_segment_ids: list[str] = Field(
        default_factory=list,
        description="Danh sách UUID các segment làm bằng chứng trích xuất",
    )

    model_config = ConfigDict(extra="forbid")


class SummaryContentOut(BaseModel):
    """Nội dung chi tiết tóm tắt cuộc họp."""

    overview: str = Field(
        ..., max_length=5000, description="Tổng quan cuộc họp (tối đa 5000 ký tự)"
    )
    key_points: list[SummaryPointOut] = Field(
        default_factory=list,
        max_length=50,
        description="Danh sách điểm chính trao đổi",
    )
    decisions: list[SummaryPointOut] = Field(
        default_factory=list,
        max_length=50,
        description="Danh sách các quyết định đã chốt",
    )

    model_config = ConfigDict(extra="forbid")


class SummaryOut(BaseModel):
    """Hợp đồng dữ liệu tóm tắt cuộc họp."""

    meeting_id: str = Field(..., description="UUID của cuộc họp")
    status: str = Field(
        ...,
        description="Trạng thái tóm tắt (pending/ready/failed/insufficient_content/disabled)",
    )
    content: SummaryContentOut | None = Field(default=None, description="Nội dung tóm tắt hiện tại")
    ai_content: SummaryContentOut | None = Field(
        default=None, description="Nội dung tóm tắt gốc do AI tạo ra (bất biến)"
    )
    is_edited: bool = Field(
        default=False, description="Cờ đánh dấu tóm tắt đã được người dùng chỉnh sửa"
    )
    model: str | None = Field(default=None, description="Tên model AI sinh tóm tắt")
    prompt_version: str | None = Field(default=None, description="Phiên bản prompt được dùng")
    generated_at: datetime | str | None = Field(
        default=None, description="Thời điểm sinh tóm tắt ISO 8601 UTC"
    )
    version: int = Field(default=1, description="Phiên bản phục vụ optimistic locking")

    model_config = ConfigDict(extra="forbid")


class SummaryUpdate(BaseModel):
    """Schema cập nhật nội dung tóm tắt cuộc họp."""

    content: SummaryContentOut = Field(..., description="Nội dung tóm tắt mới")
    version: int = Field(..., ge=1, description="Phiên bản hiện tại của summary ở client")

    model_config = ConfigDict(extra="forbid")
