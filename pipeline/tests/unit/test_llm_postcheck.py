"""Test hậu kiểm bản nháp tóm tắt (AI-09)."""

from datetime import date

import pytest

from meeting_pipeline.errors import ErrorCode, PermanentPipelineError
from meeting_pipeline.fake import data
from meeting_pipeline.llm.base import DraftActionItem, DraftItem, SummaryDraft
from meeting_pipeline.llm.postcheck import (
    EVIDENCE_DROPPED,
    MAX_ITEM_CHARS,
    finalize,
    insufficient_output,
    is_insufficient,
)
from meeting_pipeline.schemas import SummaryOutput

MEETING = date(2026, 10, 15)  # thứ Năm


def transcript():
    t = data.transcript(data.diarize_output())
    t.speakers[0].display_name = "Anh Minh"
    return t


def action(**overrides) -> DraftActionItem:
    base = dict(
        description="Hoàn thiện API upload",
        assignee_name=None,
        due_date_text=None,
        due_date=None,
        evidence=[2],
    )
    base.update(overrides)
    return DraftActionItem(**base)


def draft(**overrides) -> SummaryDraft:
    base = dict(
        overview="Nhóm chốt phạm vi sprint 42.",
        key_points=[DraftItem(text="Upload chống tạo trùng.", evidence=[1])],
        decisions=[DraftItem(text="Lùi DOCX.", evidence=[3])],
        action_items=[action()],
    )
    base.update(overrides)
    return SummaryDraft(**base)


def run(d: SummaryDraft, meeting_date=MEETING) -> SummaryOutput:
    out = finalize(d, transcript(), meeting_date, "test-model", "summary-v1")
    assert SummaryOutput.model_validate(out.model_dump()) == out
    return out


def test_valid_draft_becomes_ready_summary():
    out = run(draft())
    assert (out.status, out.model, out.prompt_version) == ("ready", "test-model", "summary-v1")
    assert out.key_points[0].evidence_segment_indices == [1]
    assert out.action_items[0].needs_review is False
    assert out.warnings == []


def test_unknown_evidence_is_dropped_with_count_only():
    out = run(draft(key_points=[DraftItem(text="Ý chính", evidence=[1, 99, 99, -1])]))
    assert out.key_points[0].evidence_segment_indices == [1]
    assert [(w.code, w.message) for w in out.warnings] == [
        (EVIDENCE_DROPPED, "bỏ 2 evidence trỏ tới segment không tồn tại")
    ]


def test_action_without_evidence_needs_review():
    out = run(draft(action_items=[action(evidence=[42])]))
    assert out.action_items[0].evidence_segment_indices == []
    assert out.action_items[0].needs_review is True


@pytest.mark.parametrize(
    ("due_text", "due", "meeting_date", "expected", "review"),
    [
        ("thứ Sáu tuần này", "2026-10-16", MEETING, date(2026, 10, 16), False),
        (None, "2026-10-16", MEETING, None, True),  # có ngày mà không có căn cứ
        ("thứ Sáu tuần này", "2026-10-16", None, None, True),  # không biết ngày họp
        ("thứ Sáu", "16/10/2026", MEETING, None, True),  # sai định dạng
        ("tuần trước", "2026-10-01", MEETING, None, True),  # sớm hơn ngày họp
        ("cuối tháng", None, MEETING, None, False),  # chỉ có cụm từ, không đoán ngày
    ],
)
def test_due_dates_need_grounding(due_text, due, meeting_date, expected, review):
    out = run(draft(action_items=[action(due_date_text=due_text, due_date=due)]), meeting_date)
    item = out.action_items[0]
    assert (item.due_date, item.needs_review) == (expected, review)
    assert item.due_date_text == due_text


def test_assignee_matches_speaker_name_case_insensitively():
    out = run(
        draft(action_items=[action(assignee_name="  anh   minh "), action(assignee_name="Chị Hoa")])
    )
    assert [(a.assignee_name, a.assignee_speaker_label) for a in out.action_items] == [
        ("anh minh", "SPEAKER_00"),
        ("Chị Hoa", None),
    ]


def test_long_and_empty_texts_are_clipped_or_dropped():
    out = run(
        draft(
            key_points=[
                DraftItem(text="x " * 400, evidence=[0]),
                DraftItem(text="  ", evidence=[0]),
            ],
            action_items=[action(description=" ")],
        )
    )
    assert len(out.key_points) == 1 and len(out.key_points[0].text) == MAX_ITEM_CHARS
    assert out.action_items == []


def test_empty_overview_is_invalid_output():
    with pytest.raises(PermanentPipelineError) as exc:
        run(draft(overview="   "))
    assert exc.value.code is ErrorCode.LLM_OUTPUT_INVALID


def test_short_transcript_is_insufficient():
    t = transcript()  # 6 segment, 63 từ
    assert not is_insufficient(t)
    assert is_insufficient(t.model_copy(update={"segments": t.segments[:1]}))  # 1 segment
    assert is_insufficient(t.model_copy(update={"segments": t.segments[3:5]}))  # 2 segment, 11 từ
    out = insufficient_output("m", "summary-v1")
    assert (out.status, out.overview, out.action_items) == ("insufficient_content", None, [])
