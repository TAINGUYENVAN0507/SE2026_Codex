"""Kiểm thử cấu hình API_WORKERS và phép tính kết nối cơ sở dữ liệu (AD-018, BE-16)."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from app.core.config import Settings

ROOT = Path(__file__).resolve().parents[3]


def test_default_api_workers_and_connections_math_valid() -> None:
    """Cấu hình mặc định: 1 worker x 40 inflight + 20 reserved = 60 <= 100 max_connections."""
    settings = Settings()
    assert settings.API_WORKERS == 1
    assert settings.API_MAX_INFLIGHT == 40
    assert settings.DB_RESERVED_CONNECTIONS == 20
    assert settings.POSTGRES_MAX_CONNECTIONS == 100
    total = settings.API_WORKERS * settings.API_MAX_INFLIGHT + settings.DB_RESERVED_CONNECTIONS
    assert total <= settings.POSTGRES_MAX_CONNECTIONS


def test_four_workers_with_limit_twenty_valid() -> None:
    """4 workers x 20 inflight + 20 reserved = 100 <= 100 max_connections (chạm đúng biên)."""
    settings = Settings(API_WORKERS=4, API_MAX_INFLIGHT=20)
    assert settings.API_WORKERS == 4
    assert settings.API_MAX_INFLIGHT == 20
    assert settings.DB_RESERVED_CONNECTIONS == 20
    total = settings.API_WORKERS * settings.API_MAX_INFLIGHT + settings.DB_RESERVED_CONNECTIONS
    assert total == 100
    assert total <= settings.POSTGRES_MAX_CONNECTIONS


def test_boundary_budget_exact_match_passes() -> None:
    """Kiểm thử ở biên: 2 workers x 40 inflight + 20 reserved = 100 <= 100 -> vừa đủ thì qua."""
    settings = Settings(
        API_WORKERS=2,
        API_MAX_INFLIGHT=40,
        DB_RESERVED_CONNECTIONS=20,
        POSTGRES_MAX_CONNECTIONS=100,
    )
    total = settings.API_WORKERS * settings.API_MAX_INFLIGHT + settings.DB_RESERVED_CONNECTIONS
    assert total == 100
    assert total <= settings.POSTGRES_MAX_CONNECTIONS


def test_boundary_budget_exceeded_by_one_raises_error() -> None:
    """Kiểm thử ở biên: 2 workers x 40 inflight + 21 reserved = 101 > 100 -> vượt 1 thì báo lỗi."""
    with pytest.raises(ValidationError, match="vượt quá max_connections"):
        Settings(
            API_WORKERS=2,
            API_MAX_INFLIGHT=40,
            DB_RESERVED_CONNECTIONS=21,
            POSTGRES_MAX_CONNECTIONS=100,
        )


def test_four_workers_with_limit_forty_exceeds_max_connections() -> None:
    """4 workers x 40 inflight + 20 reserved = 180 > 100 -> ném lỗi từ chối khởi động."""
    with pytest.raises(ValidationError, match="vượt quá max_connections"):
        Settings(API_WORKERS=4, API_MAX_INFLIGHT=40)


def test_api_workers_must_be_positive() -> None:
    """API_WORKERS không được nhỏ hơn 1."""
    with pytest.raises(ValidationError, match="API_WORKERS phải lớn hơn hoặc bằng 1"):
        Settings(API_WORKERS=0)


def test_web_concurrency_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    """Hỗ trợ biến môi trường WEB_CONCURRENCY làm fallback cho API_WORKERS."""
    monkeypatch.setenv("WEB_CONCURRENCY", "3")
    monkeypatch.delenv("API_WORKERS", raising=False)
    settings = Settings(API_MAX_INFLIGHT=20, DB_RESERVED_CONNECTIONS=20)
    assert settings.API_WORKERS == 3
    total = settings.API_WORKERS * settings.API_MAX_INFLIGHT + settings.DB_RESERVED_CONNECTIONS
    assert total == 3 * 20 + 20  # 80 <= 100


def test_docker_readme_documents_connection_math() -> None:
    """Tài liệu README.md phải mô tả API_WORKERS, DB_RESERVED_CONNECTIONS và phép tính kết nối."""
    readme_path = ROOT / "infra" / "docker" / "README.md"
    assert readme_path.exists(), "Tệp infra/docker/README.md không tồn tại"
    text = readme_path.read_text(encoding="utf-8")
    assert "API_WORKERS" in text
    assert "WEB_CONCURRENCY" in text
    assert "API_MAX_INFLIGHT" in text
    assert "DB_RESERVED_CONNECTIONS" in text
    assert "POSTGRES_MAX_CONNECTIONS" in text
