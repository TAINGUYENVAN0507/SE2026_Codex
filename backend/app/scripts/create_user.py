"""Script dòng lệnh (CLI) tạo tài khoản người dùng mới.

Mật khẩu được đọc an toàn từ prompt tương tác hoặc stdin,
không nhận qua cờ dòng lệnh nhằm tránh lộ trong lịch sử shell.
"""

import argparse
import getpass
import sys
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.db.models.user import User
from app.db.session import get_session_factory


def create_user(session: Session, email: str, display_name: str, password: str) -> User:
    """Tạo người dùng mới trong database. Báo lỗi nếu email đã tồn tại hoặc mật khẩu rỗng."""
    email_clean = email.strip()
    name_clean = display_name.strip()
    pwd_clean = password.strip()

    if not email_clean:
        raise ValueError("Email không được để trống.")
    if not name_clean:
        raise ValueError("Tên hiển thị không được để trống.")
    if not pwd_clean:
        raise ValueError("Mật khẩu không được để trống.")

    existing_user = session.execute(
        select(User).where(User.email == email_clean)
    ).scalar_one_or_none()
    if existing_user:
        raise ValueError(f"Email '{email_clean}' đã tồn tại trong hệ thống.")

    user = User(
        id=str(uuid.uuid4()),
        email=email_clean,
        display_name=name_clean,
        password_hash=hash_password(pwd_clean),
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def parse_args(args: list[str] | None = None) -> argparse.Namespace:
    """Đọc tham số dòng lệnh --email và --name."""
    parser = argparse.ArgumentParser(
        description="CLI tạo tài khoản người dùng cho Vietnamese Meeting Minutes Assistant.",
    )
    parser.add_argument(
        "--email",
        required=True,
        help="Địa chỉ email đăng nhập của người dùng mới",
    )
    parser.add_argument(
        "--name",
        required=True,
        help="Tên hiển thị của người dùng mới",
    )
    return parser.parse_args(args)


def main(args: list[str] | None = None) -> None:
    """Điểm khởi chạy CLI cho lệnh python -m app.scripts.create_user."""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parsed = parse_args(args)

    # Đọc mật khẩu an toàn từ prompt hoặc stdin
    if sys.stdin.isatty():
        raw_password = getpass.getpass("Nhập mật khẩu người dùng: ")
    else:
        raw_password = sys.stdin.readline().strip()

    session_factory = get_session_factory()
    with session_factory() as session:
        try:
            user = create_user(
                session=session,
                email=parsed.email,
                display_name=parsed.name,
                password=raw_password,
            )
            print(
                f"Tạo người dùng thành công: ID={user.id}\n"
                f"  Email: {user.email}\n"
                f"  Tên: {user.display_name}"
            )
        except ValueError as err:
            print(f"Lỗi: {err}", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    main()
