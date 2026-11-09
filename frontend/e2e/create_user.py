"""Tạo tài khoản tổng hợp riêng cho E2E xóa tài khoản; không dùng user demo chung."""

import json
import os
import sys
from urllib.parse import urlparse
from uuid import UUID

from app.db.session import get_session_factory
from app.scripts.create_user import create_user


def main() -> None:
    """Chỉ tạo user fixture trong đúng database E2E được chỉ định."""
    database = os.environ.get("E2E_DATABASE_URL", "")
    if "e2e" not in urlparse(database).path.lower() or database != os.environ.get(
        "DATABASE_URL"
    ):
        raise RuntimeError("Fixture chỉ chạy trên database E2E riêng.")
    key = str(UUID(sys.argv[1]))
    password = os.environ.get("SEED_DEMO_PASSWORD")
    if not password:
        raise RuntimeError("Thiếu mật khẩu của môi trường E2E.")
    with get_session_factory()() as db:
        user = create_user(
            db, f"e2e-delete-{key}@example.com", "Tài khoản E2E", password
        )
        print(json.dumps({"id": user.id, "email": user.email}))


if __name__ == "__main__":
    main()
