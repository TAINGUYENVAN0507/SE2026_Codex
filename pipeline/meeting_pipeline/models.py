"""Tải trước và kiểm tra model của pipeline (AI-16).

    uv run python -m meeting_pipeline download-models           # tải vào cache (HF_HOME)
    uv run python -m meeting_pipeline download-models --check   # chỉ kiểm cache, không tải

- ASR: model faster-whisper theo `ASR_MODEL`, repo công khai, không cần token.
- Diarization: `DIARIZATION_MODEL` (mặc định `pyannote/speaker-diarization-community-1`) là model
  gated. Cần `HF_TOKEN` (hoặc token đã lưu bằng `hf auth login`) của tài khoản đã bấm đồng ý
  điều kiện trên trang model.
- Thiếu token, token sai hoặc chưa đồng ý điều kiện thì báo rõ cần làm gì, exit code 2. Thông
  điệp không bao giờ chứa token hay message gốc của Hugging Face (có thể chứa URL kèm token).

Cần extra `asr` và `diarize` (huggingface_hub và faster-whisper được import trong hàm).
"""

from __future__ import annotations

import os
import sys
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol, TextIO

EXIT_OK = 0
EXIT_FAILED = 2


class ModelCheckError(Exception):
    """Lỗi kèm hướng dẫn cho người chạy. Message không chứa token."""


class Hub(Protocol):
    def get_token(self) -> str | None: ...

    def check_token(self, token: str) -> None: ...

    def check_access(self, repo: str, token: str | None) -> None: ...

    def download(self, repo: str, token: str | None, local_only: bool) -> None: ...


def _page(repo: str) -> str:
    return f"https://huggingface.co/{repo}"


class HuggingFaceHub:
    """`Hub` thật, dịch lỗi của huggingface_hub thành `ModelCheckError`."""

    def _call(self, repo: str, fn: Callable[[], object]) -> None:
        from huggingface_hub.errors import (
            GatedRepoError,
            HfHubHTTPError,
            LocalEntryNotFoundError,
            RepositoryNotFoundError,
        )

        try:
            fn()
        except GatedRepoError:
            raise ModelCheckError(
                f"tài khoản chưa đồng ý điều kiện của {repo}: mở {_page(repo)} và bấm đồng ý"
            ) from None
        except RepositoryNotFoundError:
            raise ModelCheckError(f"không thấy {repo}, hoặc token không có quyền đọc") from None
        except LocalEntryNotFoundError:
            raise ModelCheckError(
                f"chưa có {repo} trong cache, chạy lại không có --check"
            ) from None
        except HfHubHTTPError as e:
            status = getattr(getattr(e, "response", None), "status_code", None)
            if status == 401:
                raise ModelCheckError("HF_TOKEN không hợp lệ hoặc đã bị thu hồi") from None
            raise ModelCheckError(f"Hugging Face trả lỗi {status} khi đọc {repo}") from None
        except OSError as e:
            raise ModelCheckError(
                f"không kết nối được Hugging Face khi đọc {repo} ({type(e).__name__})"
            ) from None

    def get_token(self) -> str | None:
        from huggingface_hub import get_token

        return os.environ.get("HF_TOKEN") or get_token()

    def check_token(self, token: str) -> None:
        from huggingface_hub import whoami

        self._call("tài khoản", lambda: whoami(token=token))

    def check_access(self, repo: str, token: str | None) -> None:
        from huggingface_hub import auth_check

        self._call(repo, lambda: auth_check(repo, token=token))

    def download(self, repo: str, token: str | None, local_only: bool) -> None:
        from huggingface_hub import snapshot_download

        self._call(repo, lambda: snapshot_download(repo, token=token, local_files_only=local_only))


@dataclass(frozen=True)
class ModelSpec:
    name: str
    repo: str
    gated: bool


def asr_repo(model: str) -> str:
    """Repo Hugging Face của model faster-whisper (`large-v3-turbo` → repo của nó)."""
    from faster_whisper.utils import _MODELS

    return _MODELS.get(model, model)


def model_specs() -> list[ModelSpec]:
    from meeting_pipeline.engines.pyannote import PyannoteConfig
    from meeting_pipeline.engines.whisper import WhisperConfig

    asr = WhisperConfig.from_env().model
    diarize = PyannoteConfig.from_env().model
    return [
        ModelSpec(f"ASR {asr}", asr_repo(asr), gated=False),
        ModelSpec("diarization", diarize, gated=True),
    ]


def prepare(
    specs: list[ModelSpec],
    hub: Hub,
    check_only: bool = False,
    out: TextIO = sys.stdout,
) -> int:
    """Kiểm quyền rồi tải (hoặc chỉ kiểm cache) từng model. Trả về exit code."""
    token = hub.get_token()
    failed = 0
    if any(s.gated for s in specs) and not token:
        print(
            "lỗi: model diarization là model gated, cần HF_TOKEN (hoặc `hf auth login`) của "
            "tài khoản đã đồng ý điều kiện tại " + _page(next(s.repo for s in specs if s.gated)),
            file=out,
        )
        return EXIT_FAILED
    if token and not check_only:
        try:
            hub.check_token(token)
        except ModelCheckError as e:
            print(f"lỗi: {e}", file=out)
            return EXIT_FAILED
    for spec in specs:
        try:
            if spec.gated and not check_only:
                hub.check_access(spec.repo, token)
            hub.download(spec.repo, token if spec.gated else None, local_only=check_only)
        except ModelCheckError as e:
            print(f"lỗi: {spec.name}: {e}", file=out)
            failed += 1
            continue
        print(
            f"ok: {spec.name} ({spec.repo}) {'có trong cache' if check_only else 'đã tải'}",
            file=out,
        )
    return EXIT_FAILED if failed else EXIT_OK


def main(check_only: bool = False) -> int:
    return prepare(model_specs(), HuggingFaceHub(), check_only=check_only)
