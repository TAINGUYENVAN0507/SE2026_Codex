"""Pydantic schemas cho cấu hình hệ thống (Config)."""

from pydantic import BaseModel, ConfigDict, Field


class ConfigOut(BaseModel):
    """Hợp đồng cấu hình hệ thống trả về cho frontend."""

    max_upload_mb: int = Field(..., description="Dung lượng upload tối đa tính bằng MB")
    max_duration_sec: float = Field(..., description="Thời lượng audio tối đa tính bằng giây")
    allowed_extensions: list[str] = Field(..., description="Danh sách đuôi file được hỗ trợ")
    export_formats: list[str] = Field(..., description="Danh sách các định dạng export hỗ trợ")
    llm_enabled: bool = Field(..., description="Cờ xác định tính năng LLM (tóm tắt) có bật không")

    model_config = ConfigDict(extra="forbid")
