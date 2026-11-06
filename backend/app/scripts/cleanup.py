"""Script dòng lệnh dọn dẹp âm thanh và dữ liệu vận hành hết hạn lưu trữ (BE-14).

Sử dụng:
    python -m app.scripts.cleanup
    python -m app.scripts.cleanup --dry-run
"""

import argparse
import sys

from app.db.session import get_session_factory
from app.services.retention import run_retention_cleanup
from app.services.storage import get_storage


def main() -> int:
    """Entrypoint thực thi CLI dọn dẹp retention."""
    parser = argparse.ArgumentParser(
        description="Dọn dẹp audio và dữ liệu vận hành hết hạn theo Retention Policy (BE-14)."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Chỉ quét và in kết quả thống kê, không xóa tệp và không thay đổi database.",
    )
    args = parser.parse_args()

    session_factory = get_session_factory()
    storage = get_storage()

    with session_factory() as db:
        result = run_retention_cleanup(db, storage=storage, dry_run=args.dry_run)

    mode_str = "[DRY-RUN] " if result.dry_run else ""
    print(
        f"{mode_str}Dọn dẹp hoàn tất: "
        f"{result.audio_expired_meetings} cuộc họp hết hạn audio, "
        f"{result.operational_keys_cleaned} idempotency_keys hết hạn."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
