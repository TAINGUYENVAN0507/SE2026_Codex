"""Kiểm thử API xác thực: login, logout, me với cookie JWT HttpOnly (BE-09)."""

import uuid
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings
from app.core.security import create_access_token, decode_access_token, hash_password
from app.db.base import Base
from app.db.models.user import User
from app.db.session import get_db
from app.main import create_app


@pytest.fixture
def auth_db_session() -> Generator[Session, None, None]:
    """Tạo in-memory SQLite database chứa bảng users và một user mẫu."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine, tables=[User.__table__])
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = session_factory()

    # Tạo user mẫu
    user = User(
        id=str(uuid.uuid4()),
        email="test_auth@example.com",
        display_name="Người Dùng Thử Nghiệm",
        password_hash=hash_password("MatKhau_123!"),
    )
    session.add(user)
    session.commit()

    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine, tables=[User.__table__])
        engine.dispose()


@pytest.fixture
def client(auth_db_session: Session) -> Generator[TestClient, None, None]:
    """TestClient FastAPI với dependency get_db được override sang SQLite in-memory."""
    app = create_app()

    def _override_get_db() -> Generator[Session, None, None]:
        yield auth_db_session

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def test_login_success_sets_httponly_cookie(client: TestClient, auth_db_session: Session) -> None:
    """Đăng nhập thành công trả về thông tin user và cookie session_token HttpOnly."""
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "test_auth@example.com", "password": "MatKhau_123!"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["user"]["email"] == "test_auth@example.com"
    assert data["user"]["display_name"] == "Người Dùng Thử Nghiệm"

    # Kiểm tra cookie
    assert "session_token" in response.cookies
    token_value = response.cookies["session_token"]
    user_id = decode_access_token(token_value)

    user = auth_db_session.query(User).filter_by(email="test_auth@example.com").first()
    assert user is not None
    assert user_id == user.id

    # Kiểm tra các cờ của Set-Cookie header
    set_cookie_header = response.headers.get("set-cookie", "")
    assert "session_token=" in set_cookie_header
    assert "httponly" in set_cookie_header.lower()
    assert "samesite=lax" in set_cookie_header.lower()


def test_login_failure_invalid_password(client: TestClient) -> None:
    """Đăng nhập sai mật khẩu trả về 401 INVALID_CREDENTIALS."""
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "test_auth@example.com", "password": "SaiMatKhau_999"},
    )
    assert response.status_code == 401
    err = response.json()["error"]
    assert err["code"] == "INVALID_CREDENTIALS"
    assert err["message"] == "Email hoặc mật khẩu không chính xác."


def test_login_failure_nonexistent_email(client: TestClient) -> None:
    """Đăng nhập email không tồn tại trả về 401 INVALID_CREDENTIALS."""
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "nobody@example.com", "password": "MatKhau_123!"},
    )
    assert response.status_code == 401
    err = response.json()["error"]
    assert err["code"] == "INVALID_CREDENTIALS"
    assert err["message"] == "Email hoặc mật khẩu không chính xác."


def test_logout_clears_cookie(client: TestClient) -> None:
    """Đăng xuất trả về 204 và xóa session cookie."""
    response = client.post("/api/v1/auth/logout")
    assert response.status_code == 204
    set_cookie_header = response.headers.get("set-cookie", "")
    # Cookie bị xóa thường có Max-Age=0 hoặc rỗng
    assert "session_token=" in set_cookie_header


def test_get_me_without_cookie_returns_401(client: TestClient) -> None:
    """GET /auth/me khi chưa có cookie trả về 401 UNAUTHENTICATED."""
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHENTICATED"


def test_get_me_with_valid_cookie_returns_user(
    client: TestClient, auth_db_session: Session
) -> None:
    """GET /auth/me với cookie hợp lệ trả về đúng thông tin user hiện tại."""
    user = auth_db_session.query(User).filter_by(email="test_auth@example.com").first()
    assert user is not None

    token = create_access_token(user.id)
    client.cookies.set("session_token", token)

    response = client.get("/api/v1/auth/me")
    assert response.status_code == 200
    data = response.json()
    assert data["user"]["id"] == user.id
    assert data["user"]["email"] == user.email
    assert data["user"]["display_name"] == user.display_name


def test_get_me_with_invalid_cookie_returns_401(client: TestClient) -> None:
    """GET /auth/me với cookie giả mạo hoặc hết hạn trả về 401 UNAUTHENTICATED."""
    client.cookies.set("session_token", "invalid_token_xyz")
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHENTICATED"


def test_cookie_secure_flag_in_production(
    client: TestClient, auth_db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Kiểm tra cờ secure của cookie được kích hoạt khi chạy trong môi trường production."""
    settings = get_settings()
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")

    response = client.post(
        "/api/v1/auth/login",
        json={"email": "test_auth@example.com", "password": "MatKhau_123!"},
    )
    assert response.status_code == 200
    set_cookie_header = response.headers.get("set-cookie", "").lower()
    assert "secure" in set_cookie_header
