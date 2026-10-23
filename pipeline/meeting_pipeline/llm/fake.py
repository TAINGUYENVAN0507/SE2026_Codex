"""Provider cho test và dev: không gọi mạng, trả bản nháp cố định hoặc ném lỗi chỉ định."""

from __future__ import annotations

from dataclasses import dataclass, field

from meeting_pipeline.llm.base import DraftActionItem, DraftItem, SummaryDraft, SummaryRequest

FAKE_MODEL = "fake-llm"


def default_draft() -> SummaryDraft:
    return SummaryDraft(
        overview="Nhóm thống nhất phạm vi công việc và phân công người phụ trách.",
        key_points=[DraftItem(text="Cần hoàn thiện phần đã thảo luận.", evidence=[0])],
        decisions=[DraftItem(text="Thống nhất làm theo đề xuất.", evidence=[1])],
        action_items=[
            DraftActionItem(
                description="Hoàn thiện phần việc đã thảo luận",
                assignee_name=None,
                due_date_text=None,
                due_date=None,
                evidence=[1],
            )
        ],
    )


@dataclass
class FakeProvider:
    draft: SummaryDraft = field(default_factory=default_draft)
    error: Exception | None = None
    model: str | None = FAKE_MODEL
    enabled: bool = True
    requests: list[SummaryRequest] = field(default_factory=list)

    def summarize(self, request: SummaryRequest) -> SummaryDraft:
        self.requests.append(request)
        if self.error is not None:
            raise self.error
        return self.draft


@dataclass
class DisabledProvider:
    """LLM bị tắt: stage ghi `status=disabled`, transcript không rời máy (PRIV-16)."""

    model: str | None = None
    enabled: bool = False

    def summarize(self, request: SummaryRequest) -> SummaryDraft:
        raise RuntimeError("DisabledProvider không bao giờ được gọi summarize()")
