"""Pydantic schemas cho Action Items (Hành động cần làm)."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ActionItemSource = Literal["ai", "user"]


class ActionItemAiOriginal(BaseModel):
    """Thông tin trích xuất gốc do AI sinh (bất biến)."""

    description: str = Field(..., description="Mô tả công việc gốc")
    assignee_name: str | None = Field(default=None, description="Tên người nhận việc gốc")
    due_date: str | None = Field(default=None, description="Hạn chót YYYY-MM-DD gốc")
    due_date_text: str | None = Field(default=None, description="Cụm từ hạn chót gốc")

    model_config = ConfigDict(extra="forbid")


class ActionItemOut(BaseModel):
    """Hợp đồng dữ liệu của một Action Item."""

    id: str = Field(..., description="UUID của action item")
    meeting_id: str = Field(..., description="UUID của cuộc họp tương ứng")
    description: str = Field(..., description="Mô tả công việc cần làm")
    assignee_name: str | None = Field(default=None, description="Tên người được giao việc")
    assignee_speaker_id: str | None = Field(
        default=None, description="UUID người nói tương ứng với người nhận việc"
    )
    due_date: str | None = Field(
        default=None, description="Hạn chót hoàn thành định dạng YYYY-MM-DD"
    )
    due_date_text: str | None = Field(
        default=None, description="Cụm từ chỉ thời hạn trong hội thoại"
    )
    status: str = Field(default="open", description="Trạng thái công việc (open/done/cancelled)")
    source: ActionItemSource = Field(
        default="ai", description="Nguồn gốc action item (ai hoặc user)"
    )
    is_edited: bool = Field(
        default=False, description="Cờ đánh dấu công việc đã được người dùng sửa"
    )
    needs_review: bool = Field(default=False, description="Cờ đánh dấu cần người dùng rà soát lại")
    evidence_segment_ids: list[str] = Field(
        default_factory=list,
        description="Danh sách UUID các segment làm căn cứ trích xuất",
    )
    ai_original: ActionItemAiOriginal | None = Field(
        default=None, description="Bản dữ liệu trích xuất ban đầu của AI"
    )
    version: int = Field(default=1, description="Phiên bản phục vụ optimistic locking")
    created_at: datetime | str = Field(..., description="Thời điểm tạo action item ISO 8601 UTC")
    updated_at: datetime | str = Field(..., description="Thời điểm cập nhật gần nhất ISO 8601 UTC")

    model_config = ConfigDict(extra="forbid")


class ActionItemListOut(BaseModel):
    """Danh sách các Action Items của cuộc họp."""

    items: list[ActionItemOut] = Field(
        default_factory=list, description="Danh sách các công việc cần làm"
    )

    model_config = ConfigDict(extra="forbid")


class ActionItemCreate(BaseModel):
    """Schema tạo mới Action Item từ người dùng."""

    description: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="Mô tả công việc cần làm (1-1000 ký tự)",
    )
    assignee_name: str | None = Field(
        default=None, max_length=100, description="Tên người được giao việc"
    )
    assignee_speaker_id: str | None = Field(default=None, description="UUID speaker tương ứng")
    due_date: str | None = Field(default=None, description="Hạn hoàn thành định dạng YYYY-MM-DD")
    status: str = Field(default="open", description="Trạng thái khởi tạo (mặc định 'open')")

    model_config = ConfigDict(extra="forbid")


class ActionItemPatch(BaseModel):
    """Schema cập nhật thông tin Action Item."""

    description: str | None = Field(
        default=None,
        min_length=1,
        max_length=1000,
        description="Mô tả công việc cần làm",
    )
    assignee_name: str | None = Field(
        default=None, max_length=100, description="Tên người được giao việc"
    )
    assignee_speaker_id: str | None = Field(default=None, description="UUID speaker tương ứng")
    due_date: str | None = Field(default=None, description="Hạn hoàn thành định dạng YYYY-MM-DD")
    status: str | None = Field(default=None, description="Trạng thái công việc mới")
    version: int = Field(..., ge=1, description="Phiên bản hiện tại của item ở client")

    model_config = ConfigDict(extra="forbid")
