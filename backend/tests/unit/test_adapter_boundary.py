"""AI-17, AD-018: backend chỉ nói chuyện với pipeline qua một cổng hẹp.

- `app/api/` và mọi nơi ngoài `app/worker/` không được import `meeting_pipeline`.
- `app/worker/` chỉ được dùng `runner`, `schemas`, `errors` của pipeline.
- Không file nào trong backend import SDK của bên thứ ba mà pipeline đã bọc.
"""

from __future__ import annotations

import ast
from pathlib import Path

APP = Path(__file__).resolve().parents[2] / "app"
WORKER_ALLOWED = {"meeting_pipeline.runner", "meeting_pipeline.schemas", "meeting_pipeline.errors"}
BANNED_SDKS = {"anthropic", "faster_whisper", "pyannote", "torch", "huggingface_hub"}


def find_violations(source: str, relpath: str) -> list[str]:
    in_worker = relpath.startswith("worker/")
    found: list[str] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names = [node.module]
            # `from meeting_pipeline import runner` cũng phải đi qua rule
            if node.module == "meeting_pipeline":
                names = [f"meeting_pipeline.{a.name}" for a in node.names]
        else:
            continue
        for name in names:
            top = name.split(".")[0]
            where = f"{relpath}:{node.lineno}: import {name}"
            if top in BANNED_SDKS:
                found.append(where)
            elif top == "meeting_pipeline":
                module = ".".join(name.split(".")[:2])
                if not in_worker or module not in WORKER_ALLOWED:
                    found.append(where)
    return found


def test_backend_respects_pipeline_boundary() -> None:
    violations: list[str] = []
    for path in sorted(APP.rglob("*.py")):
        violations += find_violations(
            path.read_text(encoding="utf-8"), path.relative_to(APP).as_posix()
        )
    assert not violations, "Vi phạm boundary:\n" + "\n".join(violations)


def test_api_importing_pipeline_is_flagged_with_file_and_line() -> None:
    src = "x = 1\nfrom meeting_pipeline.runner import run_job\n"
    assert find_violations(src, "api/v1/meetings.py") == [
        "api/v1/meetings.py:2: import meeting_pipeline.runner"
    ]


def test_worker_may_use_runner_but_not_stages() -> None:
    assert (
        find_violations("from meeting_pipeline.runner import run_job\n", "worker/runner.py") == []
    )
    assert find_violations("from meeting_pipeline.stages import asr\n", "worker/runner.py") == [
        "worker/runner.py:1: import meeting_pipeline.stages"
    ]


def test_from_package_import_is_checked_per_submodule() -> None:
    assert find_violations("from meeting_pipeline import engines\n", "worker/x.py") == [
        "worker/x.py:1: import meeting_pipeline.engines"
    ]
    assert find_violations("from meeting_pipeline import schemas\n", "worker/x.py") == []


def test_sdk_import_inside_function_is_flagged() -> None:
    src = "def f():\n    import anthropic\n"
    assert find_violations(src, "services/x.py") == ["services/x.py:2: import anthropic"]
