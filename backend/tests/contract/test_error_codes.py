"""Kiểm thử tính đầy đủ của danh mục mã lỗi trong contracts/error_codes.md."""

import json
import re
from pathlib import Path


def get_contracts_root() -> Path:
    """Trả về đường dẫn tới thư mục contracts/."""
    return Path(__file__).resolve().parents[3] / "contracts"


def get_backend_app_root() -> Path:
    """Trả về đường dẫn tới thư mục backend/app/."""
    return Path(__file__).resolve().parents[2] / "app"


def parse_documented_error_codes() -> set[str]:
    """Trích xuất tất cả các mã lỗi trong bảng markdown của contracts/error_codes.md."""
    md_file = get_contracts_root() / "error_codes.md"
    assert md_file.is_file(), f"Không tìm thấy file {md_file}"

    with open(md_file, encoding="utf-8") as f:
        content = f.read()

    # Tìm các mã lỗi trong cột đầu tiên của bảng dạng | `ERROR_CODE` |
    codes = set(re.findall(r"\|\s*`([A-Z0-9_]+)`\s*\|", content))
    assert len(codes) > 0, "Không trích xuất được mã lỗi nào từ error_codes.md"
    return codes


def test_pipeline_error_codes_are_documented() -> None:
    """Kiểm tra mọi mã lỗi trong enum ErrorCode của pipeline/error.schema.json.

    Mọi mã trong schema đều phải có mặt trong contracts/error_codes.md.
    Tuân thủ ranh giới module: đọc file JSON trực tiếp, không import package meeting_pipeline.
    """

    schema_file = get_contracts_root() / "pipeline" / "error.schema.json"
    assert schema_file.is_file(), f"Không tìm thấy schema {schema_file}"

    with open(schema_file, encoding="utf-8") as f:
        data = json.load(f)

    pipeline_enum_codes = data["$defs"]["ErrorCode"]["enum"]
    assert len(pipeline_enum_codes) > 0

    documented_codes = parse_documented_error_codes()
    missing_codes = [c for c in pipeline_enum_codes if c not in documented_codes]
    assert not missing_codes, (
        f"Các mã lỗi pipeline sau chưa có trong error_codes.md: {missing_codes}"
    )


def test_backend_error_codes_are_documented() -> None:
    """Kiểm tra mọi mã lỗi backend trả ra đều có trong contracts/error_codes.md."""
    documented_codes = parse_documented_error_codes()
    backend_root = get_backend_app_root()

    found_backend_codes = set()

    # Tìm mã lỗi trong code_map và các lệnh raise APIError hoặc build_error_envelope
    pattern_api_error = re.compile(r'code\s*=\s*["\']([A-Z0-9_]+)["\']')
    pattern_code_map = re.compile(r'\d{3}\s*:\s*["\']([A-Z0-9_]+)["\']')

    for py_file in backend_root.rglob("*.py"):
        with open(py_file, encoding="utf-8") as f:
            content = f.read()

        for m in pattern_api_error.finditer(content):
            found_backend_codes.add(m.group(1))

        for m in pattern_code_map.finditer(content):
            found_backend_codes.add(m.group(1))

    # Bổ sung các mã lỗi chuẩn đã biết
    found_backend_codes.add("HTTP_ERROR")

    assert len(found_backend_codes) > 0
    missing_codes = [c for c in found_backend_codes if c not in documented_codes]
    assert not missing_codes, (
        f"Các mã lỗi backend sau chưa có trong error_codes.md: {missing_codes}"
    )
