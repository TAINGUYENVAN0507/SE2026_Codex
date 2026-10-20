"""Script sinh file contracts/openapi.json va kiem tra drift."""

import argparse
import json
import sys
from pathlib import Path

from app.main import create_app

# Đảm bảo in unicode ra console trên Windows an toàn
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass


def get_openapi_spec() -> dict:
    """Tạo OpenAPI specification dictionary từ FastAPI application."""
    app = create_app()
    return app.openapi()


def get_contracts_openapi_path() -> Path:
    """Trả về đường dẫn tới file contracts/openapi.json."""
    return Path(__file__).resolve().parents[2] / "contracts" / "openapi.json"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Sinh hoac kiem tra drift file contracts/openapi.json"
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Kiểm tra xem file contracts/openapi.json đã khớp với mã nguồn hay chưa",
    )
    args = parser.parse_args()

    spec = get_openapi_spec()
    output_path = get_contracts_openapi_path()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    formatted_spec = json.dumps(spec, indent=2, ensure_ascii=False) + "\n"

    if args.check:
        if not output_path.is_file():
            print(f"Error: File {output_path} not found. Run without --check to generate it.")
            sys.exit(1)

        with open(output_path, encoding="utf-8") as f:
            existing_content = f.read()

        if existing_content != formatted_spec:
            print(f"Error: OpenAPI drift detected! File {output_path} differs from code schema.")
            print("Run `uv run python scripts/generate_openapi.py` to update it.")
            sys.exit(1)

        print("OpenAPI drift check passed: contracts/openapi.json matches codebase schema.")
    else:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(formatted_spec)
        print(f"Generated OpenAPI contract at: {output_path}")


if __name__ == "__main__":
    main()
