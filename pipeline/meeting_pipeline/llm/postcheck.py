"""Hậu kiểm bản nháp của LLM trước khi ghi `summary.json` (AI-09).

LLM có thể bịa: trỏ evidence tới segment không tồn tại, tự đặt hạn chót, ghi tên người
nhận việc không có trong cuộc họp. `finalize()` sửa những gì sửa được và đánh dấu phần
còn lại để người dùng kiểm tra:

- Evidence trỏ tới index không có trong transcript thì bỏ (warning chỉ ghi số lượng).
- Action item không còn evidence thì `needs_review=true`.
- `due_date` chỉ giữ khi có `due_date_text`, có ngày họp, đúng dạng YYYY-MM-DD và không sớm
  hơn ngày họp; bị bỏ thì `needs_review=true`.
- Người nhận việc trùng tên một speaker thì gắn `assignee_speaker_label`.
- Text dài quá giới hạn của schema thì cắt.

Transcript quá ngắn để tóm tắt thì `insufficient_output()`, không gọi LLM. Các ngưỡng là
giá trị khởi tạo.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date

from meeting_pipeline.errors import ErrorCode, PermanentPipelineError
from meeting_pipeline.llm.base import DraftItem, SummaryDraft
from meeting_pipeline.llm.prompts import speaker_names
from meeting_pipeline.schemas import (
    ActionItem,
    EvidenceItem,
    PipelineWarning,
    Stage,
    SummaryOutput,
    Transcript,
)

MIN_SEGMENTS = 2
MIN_WORDS = 30
MAX_ITEMS = 50
MAX_ITEM_CHARS = 500
MAX_OVERVIEW_CHARS = 5000
MAX_DESCRIPTION_CHARS = 1000
EVIDENCE_DROPPED = "SUMMARY_EVIDENCE_DROPPED"


def is_insufficient(transcript: Transcript) -> bool:
    words = sum(len(s.text.split()) for s in transcript.segments)
    return len(transcript.segments) < MIN_SEGMENTS or words < MIN_WORDS


def insufficient_output(model: str | None, prompt_version: str | None) -> SummaryOutput:
    return SummaryOutput(
        status="insufficient_content", model=model, prompt_version=prompt_version, overview=None
    )


def disabled_output() -> SummaryOutput:
    return SummaryOutput(status="disabled", model=None, prompt_version=None, overview=None)


def _clip(text: str, limit: int) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


class _Evidence:
    def __init__(self, valid: set[int]) -> None:
        self.valid = valid
        self.dropped = 0

    def clean(self, indices: Iterable[int]) -> list[int]:
        unique = set(indices)
        kept = sorted(unique & self.valid)
        self.dropped += len(unique) - len(kept)
        return kept


def _parse_date(value: str | None) -> date | None:
    try:
        return date.fromisoformat(value.strip()) if value else None
    except ValueError:
        return None


def _items(drafts: list[DraftItem], evidence: _Evidence) -> list[EvidenceItem]:
    return [
        EvidenceItem(
            text=_clip(d.text, MAX_ITEM_CHARS), evidence_segment_indices=evidence.clean(d.evidence)
        )
        for d in drafts
        if d.text.strip()
    ][:MAX_ITEMS]


def finalize(
    draft: SummaryDraft,
    transcript: Transcript,
    meeting_date: date | None,
    model: str | None,
    prompt_version: str,
) -> SummaryOutput:
    overview = _clip(draft.overview, MAX_OVERVIEW_CHARS)
    if not overview:
        raise PermanentPipelineError(
            ErrorCode.LLM_OUTPUT_INVALID, Stage.SUMMARIZE, "LLM trả về overview rỗng"
        )
    evidence = _Evidence({s.index for s in transcript.segments})
    by_name = {name.casefold(): label for label, name in speaker_names(transcript).items()}

    actions = []
    for a in draft.action_items:
        if not a.description.strip():
            continue
        assignee = " ".join((a.assignee_name or "").split()) or None
        due_text = " ".join((a.due_date_text or "").split()) or None
        due = _parse_date(a.due_date) if due_text and meeting_date else None
        if due is not None and meeting_date is not None and due < meeting_date:
            due = None
        indices = evidence.clean(a.evidence)
        actions.append(
            ActionItem(
                description=_clip(a.description, MAX_DESCRIPTION_CHARS),
                assignee_name=assignee,
                assignee_speaker_label=by_name.get(assignee.casefold()) if assignee else None,
                due_date=due,
                due_date_text=due_text,
                evidence_segment_indices=indices,
                needs_review=not indices or (a.due_date is not None and due is None),
            )
        )

    key_points = _items(draft.key_points, evidence)
    decisions = _items(draft.decisions, evidence)
    warnings = []
    if evidence.dropped:
        warnings.append(
            PipelineWarning(
                code=EVIDENCE_DROPPED,
                stage=Stage.SUMMARIZE,
                message=f"bỏ {evidence.dropped} evidence trỏ tới segment không tồn tại",
            )
        )
    return SummaryOutput(
        status="ready",
        model=model,
        prompt_version=prompt_version,
        overview=overview,
        key_points=key_points,
        decisions=decisions,
        action_items=actions,
        warnings=warnings,
    )
