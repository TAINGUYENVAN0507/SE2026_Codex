"""Stage summarize (AI-09): tóm tắt transcript bằng LLM rồi hậu kiểm thành `SummaryOutput`.

1. Đọc transcript: bản override (người dùng đã sửa) nếu job có `transcript_override_path`,
   ngược lại là `transcript.json` của merge.
2. LLM tắt (`LLM_PROVIDER` không đặt hoặc `disabled`) thì ghi `status=disabled` và không
   gửi request nào ra ngoài (PRIV-16).
3. Transcript quá ngắn thì ghi `insufficient_content`, không gọi LLM.
4. Còn lại: dựng prompt `summary-v1`, gọi provider, hậu kiểm bản nháp (`llm/postcheck.py`).

Lỗi của provider đã được phân loại sẵn (transient `LLM_UNAVAILABLE`, permanent
`LLM_REQUEST_INVALID`, `LLM_OUTPUT_INVALID`); runner retry lỗi transient như mọi stage khác.
"""

from __future__ import annotations

from meeting_pipeline import llm
from meeting_pipeline.errors import PipelineError
from meeting_pipeline.llm.postcheck import (
    disabled_output,
    finalize,
    insufficient_output,
    is_insufficient,
)
from meeting_pipeline.llm.prompts import PROMPT_VERSION, build_request
from meeting_pipeline.schemas import SummaryOutput
from meeting_pipeline.stages.base import StageContext


def run(ctx: StageContext) -> SummaryOutput:
    try:
        return _run(ctx)
    except PipelineError as e:
        if e.stage is None:
            e.stage = ctx.stage
        raise


def _run(ctx: StageContext) -> SummaryOutput:
    transcript = ctx.transcript()
    provider = llm.provider()
    if not provider.enabled:
        return disabled_output()
    if is_insufficient(transcript):
        return insufficient_output(provider.model, PROMPT_VERSION)

    meeting_date = ctx.spec.meeting_date
    request = build_request(transcript, meeting_date)
    ctx.progress(0.1)
    result = provider.summarize(request)
    ctx.progress(0.9)
    return finalize(result.draft, transcript, meeting_date, result.model, PROMPT_VERSION)
