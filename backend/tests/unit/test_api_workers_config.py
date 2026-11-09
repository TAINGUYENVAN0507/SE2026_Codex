"""Kiểm thử cấu hình API_WORKERS và phép tính kết nối cơ sở dữ liệu (AD-018, BE-16)."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from app.core.config import Settings

ROOT = Path(__file__).resolve().parents[3]


def test_default_api_workers_and_connections_math_valid() -> None:
    """Cấu hình mặc định: 1 worker x 40 inflight = 40 < 100 max_connections."""
    settings = Settings()
    assert settings.API_WORKERS == 1
    assert settings.API_MAX_INFLIGHT == 40
    assert settings.POSTGRES_MAX_CONNECTIONS == 100
    assert settings.API_WORKERS * settings.API_MAX_INFLIGHT < settings.POSTGRES_MAX_CONNECTIONS


def test_four_workers_with_limit_twenty_valid() -> None:
    """Cấu hình 4 workers x 20 inflight = 80 < 100 max_connections (thực nghiệm tải)."""
    settings = Settings(API_WORKERS=4, API_MAX_INFLIGHT=20)
    assert settings.API_WORKERS == 4
    assert settings.API_MAX_INFLIGHT == 20
    assert settings.API_WORKERS * settings.API_MAX_INFLIGHT == 80
    assert settings.API_WORKERS * settings.API_MAX_INFLIGHT < settings.POSTGRES_MAX_CONNECTIONS


def test_four_workers_with_limit_forty_exceeds_max_connections() -> None:
    """Cấu hình 4 workers x 40 inflight = 160 >= 100 -> ném ValueError từ chối khởi động."""
    with pytest.raises(ValidationError, match="phải nhỏ hơn max_connections"):
        Settings(API_WORKERS=4, API_MAX_INFLIGHT=40)


def test_five_workers_with_limit_twenty_reaches_boundary() -> None:
    """Cấu hình 5 workers x 20 inflight = 100 >= 100 -> ném ValueError từ chối khởi động."""
    with pytest.raises(ValidationError, match="phải nhỏ hơn max_connections"):
        Settings(API_WORKERS=5, API_MAX_INFLIGHT=20)


def test_api_workers_must_be_positive() -> None:
    """API_WORKERS không được nhỏ hơn 1."""
    with pytest.raises(ValidationError, match="API_WORKERS phải lớn hơn hoặc bằng 1"):
        Settings(API_WORKERS=0)


def test_docker_readme_documents_connection_math() -> None:
    """Tài liệu infra/docker/README.md phải mô tả API_WORKERS và phép tính kết nối."""
    readme_path = ROOT / "infra" / "docker" / "README.md"
    assert readme_path.exists(), "Tệp infra/docker/README.md không tồn tại"
    text = readme_path.read_text(encoding="utf-8")
    assert "API_WORKERS" in text
    assert "API_MAX_INFLIGHT" in text
    assert "max_connections" in text
