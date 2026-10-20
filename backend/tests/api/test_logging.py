"""Kiểm thử tính năng request_id middleware và structured JSON logging."""

import io
import json
import logging
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

from app.core.logging import JSONLogFormatter
from app.main import create_app


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    """Fixture khởi tạo TestClient."""
    app = create_app()
    with TestClient(app) as test_client:
        yield test_client


def test_request_id_generated_when_missing(client: TestClient) -> None:
    """Kiểm tra hệ thống tự động sinh X-Request-ID khi client không truyền."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert "X-Request-ID" in response.headers
    request_id = response.headers["X-Request-ID"]
    assert len(request_id) >= 16


def test_request_id_preserved_when_provided(client: TestClient) -> None:
    """Kiểm tra X-Request-ID do client gửi được giữ nguyên và trả lại trong response."""
    custom_id = "custom-test-req-id-12345"
    response = client.get("/api/v1/health", headers={"X-Request-ID": custom_id})
    assert response.status_code == 200
    assert response.headers.get("X-Request-ID") == custom_id


def test_json_logging_and_privacy_redaction(client: TestClient) -> None:
    """Kiểm tra định dạng JSON của log và đảm bảo không lộ Authorization header."""
    log_stream = io.StringIO()
    handler = logging.StreamHandler(log_stream)
    handler.setFormatter(JSONLogFormatter())

    app_logger = logging.getLogger("app.access")
    app_logger.setLevel(logging.INFO)
    app_logger.addHandler(handler)

    canary_token = "SUPER_SECRET_AUTH_TOKEN_CANARY_9999"
    try:
        response = client.get(
            "/api/v1/health",
            headers={
                "X-Request-ID": "test-privacy-req-id",
                "Authorization": f"Bearer {canary_token}",
            },
        )
        assert response.status_code == 200
    finally:
        app_logger.removeHandler(handler)

    log_output = log_stream.getvalue().strip()
    assert log_output != "", "Log output không được rỗng"

    # Đảm bảo không chứa token bí mật trong log output
    assert canary_token not in log_output

    # Phân tích dòng log JSON
    parsed_log = json.loads(log_output)
    assert parsed_log["request_id"] == "test-privacy-req-id"
    assert parsed_log["method"] == "GET"
    assert parsed_log["path"] == "/api/v1/health"
    assert parsed_log["status_code"] == 200
    assert "duration_ms" in parsed_log
    assert isinstance(parsed_log["duration_ms"], (int, float))
