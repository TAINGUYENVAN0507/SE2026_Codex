"""AD-018, RE-018: hết kết nối DB phải trả 503 SERVICE_UNAVAILABLE, không phải 500.

Đo tải 239 client (docs/evidence/load-239) cho 101 lỗi 500 `QueuePool limit ... reached`.
"""

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.exc import TimeoutError as PoolTimeoutError

from app.core.config import Settings
from app.core.errors import setup_exception_handlers


def make_client() -> TestClient:
    app = FastAPI()
    setup_exception_handlers(app)

    @app.get("/boom")
    def boom():
        raise PoolTimeoutError("QueuePool limit of size 5 overflow 10 reached")

    return TestClient(app, raise_server_exceptions=False)


def test_pool_timeout_returns_503_with_retry_after():
    res = make_client().get("/boom")
    assert res.status_code == 503
    assert res.json()["error"]["code"] == "SERVICE_UNAVAILABLE"
    assert res.headers["Retry-After"].isdigit()


def test_pool_timeout_message_does_not_leak_internals():
    body = make_client().get("/boom").text
    assert "QueuePool" not in body


def test_pool_settings_have_safe_defaults_below_postgres_max_connections():
    s = Settings()
    assert s.DB_POOL_SIZE + s.DB_MAX_OVERFLOW <= 60  # Postgres mặc định max_connections=100
    assert s.DB_POOL_SIZE > 5  # mặc định cũ của SQLAlchemy không đủ cho tải đã đo
