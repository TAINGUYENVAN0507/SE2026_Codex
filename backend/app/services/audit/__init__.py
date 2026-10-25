"""Dịch vụ audit ghi nhận nhật ký chỉnh sửa (EditEvent)."""

from app.services.audit.service import record_edit

__all__ = ["record_edit"]
