"""Kiểm thử cấu trúc error envelope và các exception handler (404, 422, 500)."""

from collections.abc import Generator

import pytest
from fastapi import APIRouter
from fastapi.testclient import TestClient

from app.core.errors import APIError
from app.main import create_app

# Router phục vụ kiểm thử các kịch bản lỗi đặc thù (không đặt tiền tố test_)
mock_error_router = APIRouter(prefix="/mock-errors")


@mock_error_router.get("/validation")
def validation_endpoint(item_id: int) -> dict[str, int]:
    """Endpoint yêu cầu tham số item_id kiểu int để kiểm thử lỗi 422."""
    return {"item_id": item_id}


@mock_error_router.get("/custom-error")
def custom_error_endpoint() -> None:
    """Endpoint ném ra lỗi nghiệp vụ APIError."""
    raise APIError(
        code="CUSTOM_BUSINESS_ERROR",
        message="Lỗi nghiệp vụ tùy chỉnh phục vụ kiểm thử.",
        status_code=400,
        details={"hint": "Kiểm tra lại dữ liệu."},
    )


@mock_error_router.get("/server-error")
def server_error_endpoint() -> None:
    """Endpoint ném exception không bắt để kiểm thử lỗi 500 kèm chuỗi canary."""
    raise RuntimeError("CANARY_LEAK_SECRET_KEY_XYZZY_99999")


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    """Fixture khởi tạo TestClient có gắn mock_error_router."""
    app = create_app()
    app.include_router(mock_error_router)
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


def test_error_404_envelope(client: TestClient) -> None:
    """Kiểm tra lỗi 404 trả về đúng cấu trúc error envelope."""
    response = client.get("/api/v1/non-existent-route-xyz")
    assert response.status_code == 404

    data = response.json()
    assert "error" in data
    error = data["error"]
    assert error["code"] == "NOT_FOUND"
    assert "Không tìm thấy" in error["message"]
    assert error["details"] is None
    assert error["request_id"] is not None


def test_error_422_validation_envelope(client: TestClient) -> None:
    """Kiểm tra lỗi 422 validation trả về đúng cấu trúc error envelope và chi tiết lỗi."""
    response = client.get("/mock-errors/validation?item_id=invalid_string")
    assert response.status_code == 422

    data = response.json()
    assert "error" in data
    error = data["error"]
    assert error["code"] == "VALIDATION_ERROR"
    assert error["message"] == "Dữ liệu yêu cầu không hợp lệ."
    assert isinstance(error["details"], list)
    assert error["request_id"] is not None


def test_custom_api_error_envelope(client: TestClient) -> None:
    """Kiểm tra lỗi nghiệp vụ APIError trả về đúng status và cấu trúc."""
    response = client.get("/mock-errors/custom-error")
    assert response.status_code == 400

    data = response.json()
    assert "error" in data
    error = data["error"]
    assert error["code"] == "CUSTOM_BUSINESS_ERROR"
    assert error["message"] == "Lỗi nghiệp vụ tùy chỉnh phục vụ kiểm thử."
    assert error["details"] == {"hint": "Kiểm tra lại dữ liệu."}
    assert error["request_id"] is not None


def test_error_500_hides_canary_secret_and_stack_trace(client: TestClient) -> None:
    """Kiểm tra lỗi 500 không để lọt chuỗi canary bí mật hay stack trace ra client."""
    canary = "CANARY_LEAK_SECRET_KEY_XYZZY_99999"
    response = client.get("/mock-errors/server-error")

    assert response.status_code == 500

    # Tuyệt đối không chứa canary trong toàn bộ nội dung response
    assert canary not in response.text

    data = response.json()
    assert "error" in data
    error = data["error"]
    assert error["code"] == "INTERNAL_SERVER_ERROR"
    assert error["message"] == "Đã xảy ra lỗi nội bộ hệ thống. Vui lòng thử lại sau."
    assert error["details"] is None
    assert error["request_id"] is not None
