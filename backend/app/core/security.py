"""Module bảo mật và mã hóa mật khẩu người dùng sử dụng argon2-cffi."""

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

_hasher = PasswordHasher()


def hash_password(raw_password: str) -> str:
    """Băm mật khẩu người dùng với salt ngẫu nhiên sử dụng Argon2."""
    return _hasher.hash(raw_password)


def verify_password(raw_password: str, hashed_password: str) -> bool:
    """Xác thực mật khẩu thô với chuỗi hash Argon2 đã lưu."""
    try:
        return _hasher.verify(hashed_password, raw_password)
    except (VerifyMismatchError, InvalidHashError):
        return False
    except Exception:
        return False
