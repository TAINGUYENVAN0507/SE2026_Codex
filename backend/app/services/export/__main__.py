"""CLI sinh/kiểm tra schema; I/O file chỉ nằm ở CLI, không nằm trong serializer."""

import argparse
import json
from pathlib import Path

from .serializers import export_schema


def main() -> None:
    """Đồng bộ contract JSON export với model Pydantic."""
    parser = argparse.ArgumentParser(description="Sinh contract export JSON")
    parser.add_argument("--check", action="store_true", help="Chỉ kiểm drift, không ghi file")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parents[4] / "contracts/export.schema.json",
    )
    args = parser.parse_args()
    expected = (json.dumps(export_schema(), ensure_ascii=False, indent=2) + "\n").encode()
    if args.check:
        if not args.output.exists() or args.output.read_bytes() != expected:
            parser.exit(1, "Contract export chưa đồng bộ. Chạy python -m app.services.export.\n")
    else:
        args.output.write_bytes(expected)


if __name__ == "__main__":
    main()
