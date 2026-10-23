"""Test provider Anthropic bằng HTTP transport giả (AI-09). Không gọi mạng, không cần key."""

import json

import anthropic
import httpx2
import pytest

from meeting_pipeline.errors import (
    ErrorCode,
    PermanentPipelineError,
    TransientPipelineError,
)
from meeting_pipeline.llm.anthropic import FALLBACK_BETA, AnthropicConfig, AnthropicProvider
from meeting_pipeline.llm.base import SummaryRequest
from meeting_pipeline.schemas import Stage

REQUEST = SummaryRequest(
    system="Bạn viết biên bản.",
    user="<transcript>\n[0] (00:00:00) Speaker 1: CANARY_TRANSCRIPT_7f3a\n</transcript>",
    prompt_version="summary-v1",
)
DRAFT = {
    "overview": "Nhóm chốt phạm vi sprint.",
    "key_points": [{"text": "Ý chính", "evidence": [0]}],
    "decisions": [],
    "action_items": [
        {
            "description": "Làm API",
            "assignee_name": None,
            "due_date_text": None,
            "due_date": None,
            "evidence": [0],
        }
    ],
}


DRAFT_JSON = json.dumps(DRAFT)


def message(stop_reason="end_turn", text=DRAFT_JSON, model="claude-opus-5-5", **extra):
    return {
        "id": "msg_test",
        "type": "message",
        "role": "assistant",
        "model": model,
        "content": [{"type": "text", "text": text}],
        "stop_reason": stop_reason,
        "stop_sequence": None,
        "usage": {"input_tokens": 10, "output_tokens": 20},
        **extra,
    }


def provider(status=200, body=None, error=None, captured=None):
    def handler(request: httpx2.Request) -> httpx2.Response:
        if captured is not None:
            captured.append(request)
        if error is not None:
            raise error
        return httpx2.Response(status, json=body if body is not None else message())

    client = anthropic.Anthropic(
        api_key="test-key",
        max_retries=0,
        http_client=anthropic.DefaultHttpxClient(transport=httpx2.MockTransport(handler)),
    )
    return AnthropicProvider(AnthropicConfig(), client=client)


def api_error(kind: str) -> dict:
    return {"type": "error", "error": {"type": kind, "message": "x"}}


def test_request_shape_and_parsed_result():
    captured = []
    result = provider(captured=captured).summarize(REQUEST)
    assert result.model == "claude-opus-5-5"
    assert result.draft.overview == "Nhóm chốt phạm vi sprint."
    assert result.draft.action_items[0].evidence == [0]

    [sent] = captured
    body = json.loads(sent.content)
    assert body["model"] == "claude-opus-5-5"
    assert body["system"] == REQUEST.system
    assert body["messages"] == [{"role": "user", "content": REQUEST.user}]
    assert body["output_config"]["effort"] == "medium"
    assert body["output_config"]["format"]["type"] == "json_schema"
    assert body["fallbacks"] == "default"
    assert FALLBACK_BETA in sent.headers["anthropic-beta"]


def test_served_model_is_recorded_when_fallback_ran():
    result = provider(body=message(model="claude-opus-5")).summarize(REQUEST)
    assert result.model == "claude-opus-5"


@pytest.mark.parametrize(
    ("status", "kind"),
    [
        (429, "rate_limit_error"),
        (500, "api_error"),
        (503, "api_error"),
        (504, "api_error"),
        (529, "overloaded_error"),
        (408, "timeout_error"),
    ],
)
def test_retryable_http_errors_are_transient(status, kind):
    with pytest.raises(TransientPipelineError) as exc:
        provider(status=status, body=api_error(kind)).summarize(REQUEST)
    assert (exc.value.code, exc.value.stage) == (ErrorCode.LLM_UNAVAILABLE, Stage.SUMMARIZE)


def test_network_errors_are_transient():
    with pytest.raises(TransientPipelineError):
        provider(error=httpx2.ConnectError("down")).summarize(REQUEST)


@pytest.mark.parametrize(
    ("status", "kind"),
    [(400, "invalid_request_error"), (401, "authentication_error"), (404, "not_found_error")],
)
def test_request_and_config_errors_are_permanent(status, kind):
    with pytest.raises(PermanentPipelineError) as exc:
        provider(status=status, body=api_error(kind)).summarize(REQUEST)
    assert exc.value.code is ErrorCode.LLM_REQUEST_INVALID
    assert str(status) in exc.value.message


def test_refusal_is_permanent_and_names_the_category_only():
    body = message(
        stop_reason="refusal",
        text="",
        stop_details={"type": "refusal", "category": "cyber", "explanation": "x"},
    )
    body["content"] = []
    with pytest.raises(PermanentPipelineError) as exc:
        provider(body=body).summarize(REQUEST)
    assert exc.value.code is ErrorCode.LLM_OUTPUT_INVALID
    assert "cyber" in exc.value.message


def test_max_tokens_is_invalid_output():
    with pytest.raises(PermanentPipelineError) as exc:
        provider(body=message(stop_reason="max_tokens", text='{"overview": "cắt')).summarize(
            REQUEST
        )
    assert exc.value.code is ErrorCode.LLM_OUTPUT_INVALID


def test_errors_never_contain_the_transcript():
    for kwargs in (
        {"status": 400, "body": api_error("invalid_request_error")},
        {"error": httpx2.ConnectError("down")},
    ):
        with pytest.raises((PermanentPipelineError, TransientPipelineError)) as exc:
            provider(**kwargs).summarize(REQUEST)
        assert "CANARY_TRANSCRIPT_7f3a" not in str(exc.value)


def test_config_from_env(monkeypatch):
    monkeypatch.setenv("LLM_EFFORT", "high")
    monkeypatch.setenv("LLM_TIMEOUT_SEC", "60")
    config = AnthropicConfig.from_env()
    assert (config.model, config.effort, config.timeout_sec) == ("claude-opus-5-5", "high", 60.0)


CREDENTIAL_ENV = (
    "ANTHROPIC_API_KEY",
    "ANTHROPIC_AUTH_TOKEN",
    "ANTHROPIC_PROFILE",
    "ANTHROPIC_CONFIG_DIR",
    "ANTHROPIC_IDENTITY_TOKEN",
    "ANTHROPIC_IDENTITY_TOKEN_FILE",
    "ANTHROPIC_FEDERATION_RULE_ID",
    "ANTHROPIC_ORGANIZATION_ID",
)


@pytest.fixture
def no_credentials(monkeypatch, tmp_path):
    for var in CREDENTIAL_ENV:
        monkeypatch.delenv(var, raising=False)
    # HOME rỗng: SDK không tìm thấy profile của `ant auth login` trong ~/.config/anthropic.
    monkeypatch.setenv("HOME", str(tmp_path))


def test_enabled_with_api_key():
    assert provider().enabled


def test_priv16_disabled_without_credentials(no_credentials):
    assert AnthropicProvider.from_env().enabled is False


def test_enabled_with_api_key_from_env(no_credentials, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    assert AnthropicProvider.from_env().enabled


def test_broken_credential_config_is_permanent(no_credentials, monkeypatch, tmp_path):
    # Đặt thư mục cấu hình tường minh mà không có profile: SDK báo CredentialsError.
    monkeypatch.setenv("ANTHROPIC_CONFIG_DIR", str(tmp_path / "missing"))
    with pytest.raises(PermanentPipelineError) as exc:
        AnthropicProvider.from_env().enabled  # noqa: B018
    assert exc.value.code is ErrorCode.LLM_REQUEST_INVALID
    assert str(tmp_path) not in str(exc.value)
