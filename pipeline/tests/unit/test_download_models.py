"""Test download-models (AI-16) với Hub giả: thiếu token, token sai, chưa đồng ý điều kiện."""

import io

import pytest

from meeting_pipeline import cli, models
from meeting_pipeline.models import EXIT_FAILED, EXIT_OK, ModelCheckError, ModelSpec, prepare

TOKEN = "hf_CANARYSECRET123"
SPECS = [
    ModelSpec("ASR large-v3-turbo", "mobiuslabsgmbh/faster-whisper-large-v3-turbo", gated=False),
    ModelSpec("diarization", "pyannote/speaker-diarization-community-1", gated=True),
]


class FakeHub:
    def __init__(self, token=TOKEN, bad_token=False, not_accepted=(), not_cached=()):
        self.token = token
        self.bad_token = bad_token
        self.not_accepted = set(not_accepted)
        self.not_cached = set(not_cached)
        self.downloads: list[tuple[str, str | None, bool]] = []

    def get_token(self):
        return self.token

    def check_token(self, token):
        if self.bad_token:
            raise ModelCheckError("HF_TOKEN không hợp lệ hoặc đã bị thu hồi")

    def check_access(self, repo, token):
        if repo in self.not_accepted:
            raise ModelCheckError(f"tài khoản chưa đồng ý điều kiện của {repo}")

    def download(self, repo, token, local_only):
        if local_only and repo in self.not_cached:
            raise ModelCheckError(f"chưa có {repo} trong cache")
        self.downloads.append((repo, token, local_only))


def run(hub, check_only=False):
    out = io.StringIO()
    code = prepare(SPECS, hub, check_only=check_only, out=out)
    text = out.getvalue()
    assert TOKEN not in text
    return code, text


def test_downloads_every_model_and_sends_the_token_only_to_gated_repos():
    hub = FakeHub()
    code, text = run(hub)
    assert code == EXIT_OK
    assert hub.downloads == [(SPECS[0].repo, None, False), (SPECS[1].repo, TOKEN, False)]
    assert text.count("ok:") == 2


def test_missing_token_explains_how_to_fix():
    hub = FakeHub(token=None)
    code, text = run(hub)
    assert code == EXIT_FAILED
    assert "HF_TOKEN" in text and "https://huggingface.co/pyannote/" in text
    assert hub.downloads == []


def test_invalid_token_fails_before_downloading():
    hub = FakeHub(bad_token=True)
    code, text = run(hub)
    assert code == EXIT_FAILED and "không hợp lệ" in text
    assert hub.downloads == []


def test_terms_not_accepted_fails_but_asr_still_downloads():
    hub = FakeHub(not_accepted={SPECS[1].repo})
    code, text = run(hub)
    assert code == EXIT_FAILED
    assert "chưa đồng ý điều kiện" in text
    assert [repo for repo, *_ in hub.downloads] == [SPECS[0].repo]


def test_check_mode_reads_cache_only():
    hub = FakeHub(not_cached={SPECS[0].repo})
    code, text = run(hub, check_only=True)
    assert code == EXIT_FAILED
    assert "chưa có" in text and "ok: diarization" in text
    assert all(local for *_, local in hub.downloads)


def test_cli_subcommand_calls_models_main(monkeypatch):
    seen = []
    monkeypatch.setattr(models, "main", lambda check_only=False: seen.append(check_only) or 0)
    assert cli.main(["download-models", "--check"]) == 0
    assert seen == [True]


def test_real_hub_translates_errors_without_leaking_the_token():
    hub_errors = pytest.importorskip("huggingface_hub.errors")
    import httpx2

    hub = models.HuggingFaceHub()
    request = httpx2.Request("GET", f"https://huggingface.co/api/whoami?token={TOKEN}")
    response = httpx2.Response(401, request=request)

    def raise_(exc):
        def fn():
            raise exc

        return fn

    cases = [
        (hub_errors.GatedRepoError(f"gated {TOKEN}", response=response), "chưa đồng ý"),
        (hub_errors.HfHubHTTPError(f"401 {TOKEN}", response=response), "không hợp lệ"),
        (ConnectionError(TOKEN), "không kết nối được"),
    ]
    for exc, message in cases:
        with pytest.raises(ModelCheckError, match=message) as info:
            hub._call("pyannote/x", raise_(exc))
        assert TOKEN not in str(info.value)
