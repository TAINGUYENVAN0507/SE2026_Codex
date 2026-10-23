"""Interface của LLM tóm tắt cuộc họp (AI-09).

Stage `summarize` chỉ biết interface này. Provider nhận `SummaryRequest` (transcript đã dựng
thành prompt) và trả `SummaryDraft`: bản nháp có cấu trúc do LLM viết. Bản nháp chưa đáng
tin: stage hậu kiểm (`postcheck.py`) bỏ evidence sai, đặt `needs_review`, rồi mới thành
`SummaryOutput` theo contract.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from pydantic import BaseModel, Field


class DraftItem(BaseModel):
    """Một ý chính hoặc một quyết định, kèm index của các segment làm căn cứ."""

    text: str
    evidence: list[int] = Field(description="index của segment trong transcript")


class DraftActionItem(BaseModel):
    description: str
    assignee_name: str | None = Field(description="tên người nhận việc như trong transcript")
    due_date_text: str | None = Field(description="cụm từ chỉ hạn trong transcript")
    due_date: str | None = Field(description="YYYY-MM-DD, chỉ khi tính được từ ngày họp")
    evidence: list[int]


class SummaryDraft(BaseModel):
    """Output có cấu trúc mà LLM phải trả về (structured outputs)."""

    overview: str
    key_points: list[DraftItem]
    decisions: list[DraftItem]
    action_items: list[DraftActionItem]


@dataclass(frozen=True)
class SummaryRequest:
    system: str
    user: str
    prompt_version: str


@dataclass(frozen=True)
class SummaryResult:
    draft: SummaryDraft
    #: model thật sự đã trả lời; có thể khác model yêu cầu khi server-side fallback chạy
    model: str


class LLMProvider(Protocol):
    #: tên model ghi vào `summary.json`; None với provider không gọi model
    model: str | None
    #: False: stage ghi `status=disabled`, không có request nào ra ngoài
    enabled: bool

    def summarize(self, request: SummaryRequest) -> SummaryResult: ...
