"""Module bảo mật, mã hóa mật khẩu sử dụng argon2-cffi và JWT session token."""

from datetime import UTC, datetime, timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

from app.core.config import get_settings

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


def create_access_token(user_id: str, expires_delta: timedelta | None = None) -> str:
    """Tạo JWT session token mã hóa user_id."""
    settings = get_settings()
    expire = datetime.now(UTC) + (expires_delta or timedelta(minutes=settings.JWT_EXPIRE_MINUTES))
    payload = {
        "sub": user_id,
        "exp": expire,
        "iat": datetime.now(UTC),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> str | None:
    """Giải mã JWT session token và trả về user_id, hoặc None nếu không hợp lệ hoặc hết hạn."""
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        return payload.get("sub")
    except jwt.PyJWTError:
        return None
