"""Test chọn LLM provider (AI-09)."""

import pytest

from meeting_pipeline import llm
from meeting_pipeline.errors import ErrorCode, PermanentPipelineError
from meeting_pipeline.llm.base import SummaryRequest
from meeting_pipeline.llm.fake import DisabledProvider, FakeProvider


@pytest.fixture(autouse=True)
def _no_llm_env(monkeypatch):
    monkeypatch.delenv("LLM_PROVIDER", raising=False)


def test_default_is_disabled_so_nothing_leaves_the_machine():
    p = llm.provider()
    assert isinstance(p, DisabledProvider)
    assert (p.enabled, p.model) == (False, None)


def test_fake_provider_from_env(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "fake")
    p = llm.provider()
    assert isinstance(p, FakeProvider) and p.enabled
    request = SummaryRequest(system="s", user="u", prompt_version="v")
    result = p.summarize(request)
    assert result.draft.overview and result.model == "fake-llm"
    assert p.requests == [request]


def test_unknown_provider_is_rejected(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    with pytest.raises(PermanentPipelineError) as exc:
        llm.provider()
    assert exc.value.code is ErrorCode.INTERNAL_ERROR


def test_fake_provider_raises_configured_error():
    with pytest.raises(ValueError):
        FakeProvider(error=ValueError("x")).summarize(SummaryRequest("s", "u", "v"))


def test_disabled_provider_never_summarizes():
    with pytest.raises(RuntimeError):
        DisabledProvider().summarize(SummaryRequest("s", "u", "v"))
