"""Provider Claude API cho stage summarize (AI-09).

Cài bằng `uv sync --extra llm`. Credential do SDK tự tìm: `ANTHROPIC_API_KEY`, hoặc profile
của `ant auth login`. Chỉ gửi transcript dạng text, không gửi audio.

| Biến | Mặc định |
|---|---|
| `LLM_MODEL` | `claude-opus-5-5` |
| `LLM_EFFORT` | `medium` (đặt tường minh; giá trị khởi tạo, chỉnh sau khi chấm rubric AI-14) |
| `LLM_TIMEOUT_SEC` | `180` cho mỗi lần gọi |
| `LLM_MAX_RETRIES` | `2` (SDK tự retry 408, 409, 429, 5xx, lỗi mạng) |

- Structured outputs: `beta.messages.parse(output_format=SummaryDraft)` nên output đúng schema.
- Server-side fallback (`fallbacks="default"`, beta `server-side-fallback-2026-07-01`): model
  từ chối vì bộ lọc an toàn thì API chạy lại trên model dự phòng trong cùng lần gọi.
- Lỗi: 408, 409, 429, mọi 5xx, timeout, lỗi mạng (sau khi SDK đã retry) là transient
  `LLM_UNAVAILABLE`;
  400, 422 và lỗi cấu hình (401, 403, 404) là permanent `LLM_REQUEST_INVALID`; model vẫn từ
  chối (`refusal`) hoặc hết `max_tokens` là permanent `LLM_OUTPUT_INVALID`.
- Không log prompt hay response. Thông điệp lỗi chỉ có mã HTTP và loại lỗi, không có transcript.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

from meeting_pipeline.errors import (
    ErrorCode,
    PermanentPipelineError,
    TransientPipelineError,
)
from meeting_pipeline.llm.base import SummaryDraft, SummaryRequest, SummaryResult
from meeting_pipeline.schemas import Stage

FALLBACK_BETA = "server-side-fallback-2026-07-01"


@dataclass(frozen=True)
class AnthropicConfig:
    model: str = "claude-opus-5-5"
    effort: str = "medium"
    max_tokens: int = 16000
    timeout_sec: float = 180.0
    max_retries: int = 2

    @classmethod
    def from_env(cls) -> AnthropicConfig:
        d = cls()
        return cls(
            model=os.environ.get("LLM_MODEL", d.model),
            effort=os.environ.get("LLM_EFFORT", d.effort),
            timeout_sec=float(os.environ.get("LLM_TIMEOUT_SEC", d.timeout_sec)),
            max_retries=int(os.environ.get("LLM_MAX_RETRIES", d.max_retries)),
        )


def _transient(message: str) -> TransientPipelineError:
    return TransientPipelineError(ErrorCode.LLM_UNAVAILABLE, Stage.SUMMARIZE, message)


def _permanent(code: ErrorCode, message: str) -> PermanentPipelineError:
    return PermanentPipelineError(code, Stage.SUMMARIZE, message)


class AnthropicProvider:
    enabled = True

    def __init__(self, config: AnthropicConfig, client: Any = None) -> None:
        self.config = config
        self.model: str | None = config.model
        self._client = client

    @classmethod
    def from_env(cls) -> AnthropicProvider:
        return cls(AnthropicConfig.from_env())

    def _get_client(self) -> Any:
        if self._client is None:
            import anthropic

            self._client = anthropic.Anthropic(
                timeout=self.config.timeout_sec, max_retries=self.config.max_retries
            )
        return self._client

    def summarize(self, request: SummaryRequest) -> SummaryResult:
        import anthropic

        client = self._get_client()
        try:
            response = client.beta.messages.parse(
                model=self.config.model,
                max_tokens=self.config.max_tokens,
                system=request.system,
                messages=[{"role": "user", "content": request.user}],
                output_format=SummaryDraft,
                output_config={"effort": self.config.effort},
                betas=[FALLBACK_BETA],
                fallbacks="default",
            )
        except anthropic.APIConnectionError as e:  # gồm cả APITimeoutError
            raise _transient(f"không kết nối được dịch vụ LLM ({type(e).__name__})") from None
        except anthropic.APIStatusError as e:
            # Phân loại theo mã HTTP, không theo class: SDK 1.x có class riêng cho 503, 504,
            # 529 (ServiceUnavailableError, DeadlineExceededError, OverloadedError), không phải
            # lớp con của InternalServerError.
            if e.status_code == 429 or e.status_code >= 500 or e.status_code in (408, 409):
                raise _transient(
                    f"dịch vụ LLM tạm thời không nhận yêu cầu ({e.status_code})"
                ) from None
            raise _permanent(
                ErrorCode.LLM_REQUEST_INVALID,
                f"yêu cầu tới LLM bị từ chối ({e.status_code} {type(e).__name__})",
            ) from None
        except ValidationError:
            # parse() đọc JSON ngay khi nhận response: output bị cắt (max_tokens) hoặc sai
            # schema thì lỗi xảy ra ở đây, trước khi xem được stop_reason.
            raise _permanent(
                ErrorCode.LLM_OUTPUT_INVALID, "output có cấu trúc bị cắt hoặc sai schema"
            ) from None

        if response.stop_reason == "refusal":
            details = getattr(response, "stop_details", None)
            category = getattr(details, "category", None) or "không rõ"
            raise _permanent(ErrorCode.LLM_OUTPUT_INVALID, f"model từ chối tóm tắt ({category})")
        if response.stop_reason == "max_tokens":
            raise _permanent(ErrorCode.LLM_OUTPUT_INVALID, "output vượt max_tokens")
        if response.parsed_output is None:
            raise _permanent(ErrorCode.LLM_OUTPUT_INVALID, "không đọc được output có cấu trúc")
        return SummaryResult(draft=response.parsed_output, model=response.model)
