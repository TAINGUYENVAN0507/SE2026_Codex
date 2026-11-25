"""Kiểm thử hành vi của hàm check_postgres_or_skip và preflight Postgres trên local và CI."""

import contextlib
import os
import socket
from urllib.parse import urlparse, urlunparse

import pytest

from app.core.config import get_settings
from tests.conftest import _check_postgres_connection, check_postgres_or_skip


def _replace_url_host(db_url: str, new_host: str) -> str:
    """Thay thế phần hostname trong DATABASE_URL, giữ nguyên user, password, port và db."""
    parsed = urlparse(db_url)
    port_part = f":{parsed.port}" if parsed.port else ""
    auth_part = ""
    if parsed.username is not None:
        auth_part = parsed.username
        if parsed.password is not None:
            auth_part += f":{parsed.password}"
        auth_part += "@"
    return urlunparse(parsed._replace(netloc=f"{auth_part}{new_host}{port_part}"))


def test_require_postgres_skips_locally_when_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    """Kiểm tra khi không có Postgres và không phải CI thì hàm gọi pytest.skip."""
    monkeypatch.delenv("CI", raising=False)
    monkeypatch.setattr("tests.conftest._check_postgres_connection", lambda _url: False)

    with pytest.raises(pytest.skip.Exception, match="cần Postgres: docker compose up -d db"):
        check_postgres_or_skip("postgresql+psycopg://dummy:dummy@localhost:5432/dummy")


def test_require_postgres_fails_on_ci_when_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    """Kiểm tra khi không có Postgres và CI=true thì hàm gọi pytest.fail."""
    monkeypatch.setenv("CI", "true")
    monkeypatch.setattr("tests.conftest._check_postgres_connection", lambda _url: False)

    with pytest.raises(pytest.fail.Exception, match="cần Postgres: docker compose up -d db"):
        check_postgres_or_skip("postgresql+psycopg://dummy:dummy@localhost:5432/dummy")


def test_preflight_accepts_ipv6_loopback_socket(monkeypatch: pytest.MonkeyPatch) -> None:
    """Preflight TCP phải chấp nhận host IPv6 [::1] khi không có DB thật."""
    if not socket.has_ipv6:
        pytest.skip("Máy không hỗ trợ IPv6")

    try:
        server = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
        server.bind(("::1", 0))
        server.listen(1)
    except OSError:
        pytest.skip("Không thể mở socket nghe trên ::1")

    port = server.getsockname()[1]
    seen_urls: list[str] = []

    class _FakeConn:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def execute(self, _stmt):
            return None

    class _FakeEngine:
        def connect(self):
            return _FakeConn()

        def dispose(self):
            return None

    def _fake_create_engine(url: str, **_kwargs):
        seen_urls.append(url)
        return _FakeEngine()

    monkeypatch.setattr("tests.conftest.create_engine", _fake_create_engine)
    try:
        url = f"postgresql+psycopg://postgres:postgres@[::1]:{port}/meeting_assistant"
        assert _check_postgres_connection(url) is True
        assert seen_urls == [url]
    finally:
        with contextlib.suppress(OSError):
            server.close()


def test_preflight_matches_ipv4_and_ipv6_on_real_postgres() -> None:
    """Cùng một Postgres nghe cả 127.0.0.1 và ::1 thì preflight phải trả True cho cả hai URL."""
    base_url = os.environ.get("DATABASE_URL") or get_settings().DATABASE_URL
    if not base_url.startswith("postgresql"):
        pytest.skip("DATABASE_URL không trỏ tới PostgreSQL")

    port = urlparse(base_url).port or 5432
    for host in ("127.0.0.1", "::1"):
        try:
            with socket.create_connection((host, port), timeout=0.5):
                pass
        except OSError:
            pytest.skip("Postgres không nghe trên cả 127.0.0.1 và ::1")

    ipv4_url = _replace_url_host(base_url, "127.0.0.1")
    ipv6_url = _replace_url_host(base_url, "[::1]")
    assert _check_postgres_connection(ipv4_url) is True
    assert _check_postgres_connection(ipv6_url) is True
