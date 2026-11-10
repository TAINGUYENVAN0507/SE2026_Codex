"""Kiểm thử kiến trúc giới hạn kích thước controller và ranh giới module (AD-018).

Yêu cầu:
- Mọi module controller trong `app/api/v1/` không được vượt quá 500 dòng code.
- Mọi module controller trong `app/api/v1/` tuyệt đối không được import `app.worker`.
"""

import ast
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[2]
API_V1_DIR = BACKEND_DIR / "app" / "api" / "v1"

MAX_CONTROLLER_LINES = 500


def test_api_v1_controllers_do_not_exceed_line_limit() -> None:
    """Mọi module trong app/api/v1/ phải có số dòng <= 500."""
    controllers = list(API_V1_DIR.glob("*.py"))
    assert len(controllers) > 0, "Không tìm thấy controller nào trong app/api/v1/"

    violating_files: list[tuple[str, int]] = []
    for filepath in controllers:
        line_count = len(filepath.read_text(encoding="utf-8").splitlines())
        if line_count > MAX_CONTROLLER_LINES:
            violating_files.append((filepath.name, line_count))

    assert not violating_files, (
        f"Các controller sau vượt ngưỡng {MAX_CONTROLLER_LINES} dòng: "
        f"{violating_files}. Hãy tách logic nghiệp vụ hoặc route con ra service/router riêng."
    )


def test_api_v1_controllers_never_import_worker() -> None:
    """Các route controller trong app/api/v1/ không được import trực tiếp app.worker."""
    controllers = list(API_V1_DIR.glob("*.py"))
    assert len(controllers) > 0, "Không tìm thấy controller nào trong app/api/v1/"

    forbidden_imports: list[tuple[str, str]] = []
    for filepath in controllers:
        content = filepath.read_text(encoding="utf-8")
        tree = ast.parse(content, filename=str(filepath))

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "app.worker" or alias.name.startswith("app.worker."):
                        forbidden_imports.append((filepath.name, alias.name))
            elif (
                isinstance(node, ast.ImportFrom)
                and node.module
                and (node.module == "app.worker" or node.module.startswith("app.worker."))
            ):
                forbidden_imports.append((filepath.name, node.module))

    assert not forbidden_imports, (
        f"Phát hiện import trái phép từ app.worker trong API controller: {forbidden_imports}. "
        "Controller chỉ tương tác với worker thông qua hàng đợi DB (Job table) hoặc service."
    )
