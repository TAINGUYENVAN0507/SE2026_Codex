"""Kiểm thử hành vi của hàm check_postgres_or_skip trên local và CI."""

import pytest

from tests.conftest import check_postgres_or_skip


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
