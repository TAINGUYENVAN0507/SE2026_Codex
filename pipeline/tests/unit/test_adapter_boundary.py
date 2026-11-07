"""AI-17: SDK của bên thứ ba chỉ được import trong adapter đã chỉ định.

Test duyệt AST của `meeting_pipeline/`, nên bắt được cả import đặt trong hàm (cách các adapter
đang dùng để package import được khi chưa cài SDK). Thêm SDK mới thì phải khai báo ở RULES.
"""

from __future__ import annotations

import ast
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[2] / "meeting_pipeline"

# SDK -> các file (tính từ meeting_pipeline/) được phép import
RULES: dict[str, set[str]] = {
    "anthropic": {"llm/anthropic.py"},
    "faster_whisper": {"engines/whisper.py"},
    "pyannote": {"engines/pyannote.py"},
    "torch": {"engines/pyannote.py"},
    "huggingface_hub": {"models.py"},
}


def find_violations(source: str, relpath: str, rules: dict[str, set[str]] = RULES) -> list[str]:
    """Trả danh sách `file:dòng: import X` vi phạm trong một đoạn source."""
    found: list[str] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names = [node.module]
        else:
            continue
        for name in names:
            top = name.split(".")[0]
            if top in rules and relpath not in rules[top]:
                found.append(f"{relpath}:{node.lineno}: import {name}")
    return found


def test_third_party_sdks_stay_inside_their_adapters() -> None:
    violations: list[str] = []
    for path in sorted(PACKAGE.rglob("*.py")):
        relpath = path.relative_to(PACKAGE).as_posix()
        violations += find_violations(path.read_text(encoding="utf-8"), relpath)
    assert not violations, "Vi phạm adapter boundary:\n" + "\n".join(violations)


def test_every_allowed_adapter_exists() -> None:
    """Đổi tên hoặc xóa adapter mà quên sửa RULES sẽ làm rule mất tác dụng âm thầm."""
    for sdk, files in RULES.items():
        for rel in files:
            assert (PACKAGE / rel).is_file(), f"{sdk}: {rel} không tồn tại"


def test_checker_flags_top_level_import_with_file_and_line() -> None:
    src = "x = 1\nimport anthropic\n"
    assert find_violations(src, "stages/summarize.py") == [
        "stages/summarize.py:2: import anthropic"
    ]


def test_checker_flags_import_inside_function_and_from_import() -> None:
    src = "def f():\n    from faster_whisper.utils import _MODELS\n    return _MODELS\n"
    assert find_violations(src, "models.py") == ["models.py:2: import faster_whisper.utils"]


def test_checker_accepts_the_allowed_adapter() -> None:
    assert find_violations("import anthropic\n", "llm/anthropic.py") == []


def test_checker_ignores_relative_imports_and_lookalike_names() -> None:
    src = "from . import torch_utils\nimport torchvision_like\nimport anthropic_helpers\n"
    assert find_violations(src, "stages/x.py") == []
