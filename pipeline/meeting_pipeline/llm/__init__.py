"""LLM cho stage summarize. Chọn provider bằng `LLM_PROVIDER`; test thay `provider()`.

| `LLM_PROVIDER` | Provider |
|---|---|
| không đặt, `disabled` | Không gọi LLM; summary `disabled` |
| `fake` | Bản nháp cố định, không gọi mạng (dev, CI, E2E) |
| `anthropic` | Claude API (`llm/anthropic.py`), cần `uv sync --extra llm` và credential |

Mặc định là `disabled`: transcript không rời máy khi chưa cấu hình rõ ràng (PRIV-16).
"""

from __future__ import annotations

import os

from meeting_pipeline.errors import ErrorCode, PermanentPipelineError
from meeting_pipeline.llm.base import (
    DraftActionItem,
    DraftItem,
    LLMProvider,
    SummaryDraft,
    SummaryRequest,
    SummaryResult,
)

PROVIDERS = ("disabled", "fake", "anthropic")


def provider() -> LLMProvider:
    name = os.environ.get("LLM_PROVIDER", "disabled")
    if name == "disabled":
        from meeting_pipeline.llm.fake import DisabledProvider

        return DisabledProvider()
    if name == "fake":
        from meeting_pipeline.llm.fake import FakeProvider

        return FakeProvider()
    if name == "anthropic":
        from meeting_pipeline.llm.anthropic import AnthropicProvider

        return AnthropicProvider.from_env()
    raise PermanentPipelineError(
        ErrorCode.INTERNAL_ERROR, None, f"LLM_PROVIDER không hợp lệ: {name!r}"
    )


__all__ = [
    "PROVIDERS",
    "DraftActionItem",
    "DraftItem",
    "LLMProvider",
    "SummaryDraft",
    "SummaryRequest",
    "SummaryResult",
    "provider",
]
