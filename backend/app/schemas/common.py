"""Schema dùng chung: error envelope và các định dạng chuẩn."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ErrorDetail(BaseModel):
    """Thông tin chi tiết của lỗi trong error envelope."""

    code: str = Field(..., description="Mã lỗi dạng UPPER_SNAKE ổn định theo hợp đồng")
    message: str = Field(..., description="Thông điệp lỗi thân thiện bằng tiếng Việt")
    details: Any = Field(
        default=None,
        description="Chi tiết lỗi (danh sách validation hoặc metadata)",
    )
    request_id: str | None = Field(default=None, description="Mã định danh request")

    model_config = ConfigDict(extra="forbid")


class ErrorResponse(BaseModel):
    """Cấu trúc Error Envelope chuẩn theo contracts/error_codes.md."""

    error: ErrorDetail

    model_config = ConfigDict(extra="forbid")
