"""Test stage summarize thật (AI-09): nối provider, prompt và hậu kiểm."""

import socket
from pathlib import Path

import pytest

from meeting_pipeline import llm
from meeting_pipeline.errors import (
    ErrorCode,
    PermanentPipelineError,
    PipelineError,
    TransientPipelineError,
)
from meeting_pipeline.fake import data
from meeting_pipeline.llm.base import DraftItem
from meeting_pipeline.llm.fake import FAKE_MODEL, FakeProvider, default_draft
from meeting_pipeline.llm.postcheck import EVIDENCE_DROPPED
from meeting_pipeline.llm.prompts import PROMPT_VERSION
from meeting_pipeline.registry import get_stage
from meeting_pipeline.runner import run_job
from meeting_pipeline.schemas import Stage, SummaryOutput
from meeting_pipeline.stages.base import execute_stage
from meeting_pipeline.workdir import (
    artifact_path,
    read_artifact,
    read_job,
    write_job,
    write_json_atomic,
)


@pytest.fixture(autouse=True)
def _no_llm_env(monkeypatch):
    monkeypatch.delenv("LLM_PROVIDER", raising=False)


@pytest.fixture
def merged(workdir: Path) -> Path:
    write_json_atomic(artifact_path(workdir, Stage.MERGE), data.transcript())
    return workdir


def use(monkeypatch, provider: FakeProvider) -> FakeProvider:
    monkeypatch.setattr(llm, "provider", lambda: provider)
    return provider


def no_network(*args, **kwargs):
    raise AssertionError("summarize không được mở kết nối mạng khi LLM tắt")


def summarize(workdir: Path) -> SummaryOutput:
    execute_stage(Stage.SUMMARIZE, workdir, get_stage(Stage.SUMMARIZE, "real"))
    summary = read_artifact(workdir, Stage.SUMMARIZE)
    assert isinstance(summary, SummaryOutput)
    return summary


def test_fake_provider_produces_checked_summary(merged, monkeypatch):
    fake = use(monkeypatch, FakeProvider())
    summary = summarize(merged)

    assert (summary.status, summary.model, summary.prompt_version) == (
        "ready",
        FAKE_MODEL,
        PROMPT_VERSION,
    )
    assert summary.overview == default_draft().overview
    assert [k.evidence_segment_indices for k in summary.key_points] == [[0]]
    assert len(fake.requests) == 1
    request = fake.requests[0]
    assert request.prompt_version == PROMPT_VERSION
    assert "Ngày họp: 2026-10-15 (thứ Năm)" in request.user
    assert data.transcript().segments[0].text in request.user


def test_draft_goes_through_postcheck(merged, monkeypatch):
    draft = default_draft()
    draft.key_points = [DraftItem(text="Ý bịa ra", evidence=[999])]
    use(monkeypatch, FakeProvider(draft=draft))
    summary = summarize(merged)
    assert summary.key_points[0].evidence_segment_indices == []
    assert [w.code for w in summary.warnings] == [EVIDENCE_DROPPED]


def test_priv16_disabled_by_default_sends_nothing(merged, monkeypatch):
    monkeypatch.setattr(socket.socket, "connect", no_network)
    summary = summarize(merged)
    assert (summary.status, summary.model, summary.prompt_version) == ("disabled", None, None)
    assert summary.overview is None


def test_priv16_anthropic_without_credentials_is_disabled(merged, monkeypatch, tmp_path):
    for var in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_PROFILE"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.delenv("ANTHROPIC_CONFIG_DIR", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    monkeypatch.setattr(socket.socket, "connect", no_network)
    assert summarize(merged).status == "disabled"


def test_short_transcript_skips_the_llm(workdir, monkeypatch):
    t = data.transcript()
    short = t.model_copy(update={"segments": t.segments[:1]})
    write_json_atomic(artifact_path(workdir, Stage.MERGE), short)
    fake = use(monkeypatch, FakeProvider())
    summary = summarize(workdir)
    assert (summary.status, summary.model) == ("insufficient_content", FAKE_MODEL)
    assert fake.requests == []


def test_uses_edited_transcript_override(workdir, tmp_path, monkeypatch):
    edited = data.transcript()
    edited.segments[0].text = "Chốt lịch demo vào sáng thứ Sáu tuần này nhé, mọi người."
    edited.speakers[0].display_name = "Chị Lan"
    override = write_json_atomic(tmp_path / "edited.json", edited)
    spec = read_job(workdir).model_copy(update={"transcript_override_path": str(override)})
    write_job(workdir, spec)
    fake = use(monkeypatch, FakeProvider())

    # Không có transcript.json trong workdir: summarize chỉ dùng bản override.
    assert summarize(workdir).status == "ready"
    assert "Chị Lan: Chốt lịch demo vào sáng thứ Sáu" in fake.requests[0].user


@pytest.mark.parametrize(
    "error",
    [
        TransientPipelineError(ErrorCode.LLM_UNAVAILABLE, None, "503"),
        PermanentPipelineError(ErrorCode.LLM_REQUEST_INVALID, None, "400"),
        PermanentPipelineError(ErrorCode.LLM_OUTPUT_INVALID, None, "refusal"),
    ],
    ids=lambda e: e.code.value,
)
def test_provider_errors_are_tagged_with_the_stage(merged, monkeypatch, error):
    use(monkeypatch, FakeProvider(error=error))
    with pytest.raises(PipelineError) as exc:
        summarize(merged)
    # Giữ nguyên loại lỗi (transient hay permanent) để runner quyết định retry.
    assert exc.value is error
    assert exc.value.stage is Stage.SUMMARIZE
    assert not artifact_path(merged, Stage.SUMMARIZE).exists()


def test_unknown_llm_provider_is_permanent(merged, monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    with pytest.raises(PermanentPipelineError) as exc:
        summarize(merged)
    assert (exc.value.code, exc.value.stage) == (ErrorCode.INTERNAL_ERROR, Stage.SUMMARIZE)


def test_missing_transcript_is_permanent(workdir, monkeypatch):
    use(monkeypatch, FakeProvider())
    with pytest.raises(PermanentPipelineError) as exc:
        summarize(workdir)
    assert (exc.value.code, exc.value.stage) == (ErrorCode.MISSING_INPUT, Stage.SUMMARIZE)


def test_run_job_resummarizes_with_real_stage_in_subprocess(job_spec, tmp_path):
    """Đường worker gọi khi người dùng bấm "Tạo lại tóm tắt": `from_stage=summarize`."""
    override = write_json_atomic(tmp_path / "edited.json", data.transcript())
    spec = job_spec.model_copy(
        update={"from_stage": Stage.SUMMARIZE, "transcript_override_path": str(override)}
    )
    wd = tmp_path / "wd"
    outcome = run_job(spec, workdir=wd, backend="real", env={"LLM_PROVIDER": "fake"})

    assert outcome.stage_status == {Stage.SUMMARIZE: "succeeded"}
    summary = read_artifact(wd, Stage.SUMMARIZE)
    assert isinstance(summary, SummaryOutput)
    assert (summary.status, summary.model) == ("ready", FAKE_MODEL)
