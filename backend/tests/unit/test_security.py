"""Kiểm thử tính năng băm và xác thực mật khẩu với argon2-cffi."""

from app.core.security import hash_password, verify_password


def test_hash_password_salts_uniquely() -> None:
    """Kiểm tra hash cùng một mật khẩu 2 lần sinh ra 2 chuỗi hash khác nhau do salt."""
    password = "TestPassword_123!"
    hash_1 = hash_password(password)
    hash_2 = hash_password(password)

    assert hash_1 != hash_2
    assert hash_1.startswith("$argon2")
    assert hash_2.startswith("$argon2")


def test_verify_password_success() -> None:
    """Kiểm tra xác thực thành công khi truyền đúng mật khẩu thô."""
    password = "SecurePassword_2026"
    hashed = hash_password(password)

    assert verify_password(password, hashed) is True


def test_verify_password_failure() -> None:
    """Kiểm tra xác thực thất bại khi truyền sai mật khẩu hoặc chuỗi hash không hợp lệ."""
    password = "CorrectPassword_123"
    hashed = hash_password(password)

    assert verify_password("WrongPassword_456", hashed) is False
    assert verify_password(password, "invalid_hash_string") is False
    assert verify_password(password, "$argon2id$v=19$m=65536,t=3,p=4$badformat") is False
