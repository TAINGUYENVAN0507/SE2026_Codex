"""Pydantic schemas cho lịch sử chỉnh sửa (Audit / Edit Events)."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class EditActorOut(BaseModel):
    """Người thực hiện hành động chỉnh sửa."""

    id: str = Field(..., description="UUID của actor")
    display_name: str = Field(..., description="Tên hiển thị của actor")

    model_config = ConfigDict(extra="forbid")


class EditEventOut(BaseModel):
    """Thông tin một sự kiện chỉnh sửa audit event."""

    id: str = Field(..., description="UUID của audit event")
    meeting_id: str = Field(..., description="UUID của cuộc họp")
    entity_type: str = Field(
        ...,
        description="Loại entity được sửa (segment/speaker/summary/action_item)",
    )
    entity_id: str = Field(..., description="UUID của entity được sửa")
    action: str = Field(..., description="Hành động (update/create/delete)")
    field: str | None = Field(default=None, description="Tên trường dữ liệu bị thay đổi")
    before: Any = Field(default=None, description="Giá trị trước khi sửa")
    after: Any = Field(default=None, description="Giá trị sau khi sửa")
    actor: EditActorOut = Field(..., description="Người thực hiện chỉnh sửa")
    entity_version_after: int = Field(..., description="Phiên bản entity sau khi sửa")
    request_id: str | None = Field(default=None, description="Mã định danh request")
    created_at: datetime | str = Field(..., description="Thời điểm ghi nhận sự kiện ISO 8601 UTC")

    model_config = ConfigDict(extra="forbid")


class EditListOut(BaseModel):
    """Danh sách các sự kiện chỉnh sửa."""

    items: list[EditEventOut] = Field(
        default_factory=list, description="Danh sách lịch sử chỉnh sửa"
    )
    total: int = Field(..., description="Tổng số sự kiện")

    model_config = ConfigDict(extra="forbid")
