"""Kiểm thử cho các endpoint health check và readiness probe."""

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

from app.core.database import get_db_health_checker
from app.main import create_app


class MockDatabaseHealthChecker:
    """Mock database health checker cho mục đích test."""

    def __init__(self, healthy: bool = True) -> None:
        self._healthy = healthy

    def is_healthy(self) -> bool:
        return self._healthy


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    """Fixture tạo TestClient cho ứng dụng FastAPI."""
    app = create_app()
    with TestClient(app) as test_client:
        yield test_client


def test_health_check_returns_200(client: TestClient) -> None:
    """Kiểm tra GET /api/v1/health luôn trả về 200 và status ok."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ready_check_when_database_is_healthy(client: TestClient) -> None:
    """Kiểm tra GET /api/v1/ready trả về 200 khi kết nối cơ sở dữ liệu hoạt động."""
    app = client.app
    app.dependency_overrides[get_db_health_checker] = lambda: MockDatabaseHealthChecker(
        healthy=True
    )

    try:
        response = client.get("/api/v1/ready")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ready"
        assert data["database"] == "connected"
    finally:
        app.dependency_overrides.clear()


def test_ready_check_when_database_is_unhealthy(client: TestClient) -> None:
    """Kiểm tra GET /api/v1/ready trả về 503 khi kết nối cơ sở dữ liệu gặp sự cố."""
    app = client.app
    app.dependency_overrides[get_db_health_checker] = lambda: MockDatabaseHealthChecker(
        healthy=False
    )

    try:
        response = client.get("/api/v1/ready")
        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "unhealthy"
        assert data["database"] == "disconnected"
    finally:
        app.dependency_overrides.clear()
