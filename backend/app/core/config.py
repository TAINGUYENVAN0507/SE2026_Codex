"""Cấu hình ứng dụng backend sử dụng pydantic-settings."""

from functools import lru_cache
from typing import Self

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_DEV_JWT_SECRET = "dev-insecure-jwt-secret-key-change-in-prod"


class Settings(BaseSettings):
    """Cấu hình hệ thống đọc từ biến môi trường hoặc file .env."""

    PROJECT_NAME: str = "Vietnamese Meeting Minutes Assistant"
    API_V1_PREFIX: str = "/api/v1"
    DATABASE_URL: str = "postgresql+psycopg://postgres:postgres@localhost:5432/meeting_minutes"
    # Pool kết nối DB. Mặc định cũ của SQLAlchemy (5 + 10) làm 239 upload đồng thời trả 500.
    # Tổng phải nhỏ hơn max_connections của Postgres (100), chừa chỗ cho worker và migration.
    DB_POOL_SIZE: int = 20
    DB_MAX_OVERFLOW: int = 30
    DB_POOL_TIMEOUT_SEC: int = 10
    # Số request xử lý cùng lúc trong MỖI process API. Phải nhỏ hơn số thread của threadpool (40)
    # và số kết nối của pool, xem app/core/admission.py. 0 = tắt giới hạn.
    API_MAX_INFLIGHT: int = 40
    API_QUEUE_TIMEOUT_SEC: float = 10.0
    # Số process uvicorn chạy song song trong API image (AD-018, BE-16).
    API_WORKERS: int = 1
    # Giới hạn max_connections của PostgreSQL trong docker-compose (chừa chỗ cho worker & admin).
    POSTGRES_MAX_CONNECTIONS: int = 100
    ENVIRONMENT: str = "development"
    DEBUG: bool = False

    # Giới hạn upload theo kế hoạch
    MAX_UPLOAD_MB: int = 200
    MAX_DURATION_SEC: int = 3600

    # Chính sách lưu trữ (retention policy theo ROADMAP)
    AUDIO_RETENTION_DAYS: int = 14
    OPERATIONAL_RETENTION_DAYS: int = 28

    # Cấu hình xác thực JWT
    JWT_SECRET: str = DEFAULT_DEV_JWT_SECRET
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60 * 24 * 7

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @model_validator(mode="after")
    def validate_production_settings(self) -> Self:
        """Đảm bảo JWT_SECRET an toàn và phép tính kết nối DB hợp lệ (AD-018, BE-16)."""
        if self.API_WORKERS < 1:
            raise ValueError("API_WORKERS phải lớn hơn hoặc bằng 1.")
        total_inflight = self.API_WORKERS * self.API_MAX_INFLIGHT
        if self.API_MAX_INFLIGHT > 0 and total_inflight >= self.POSTGRES_MAX_CONNECTIONS:
            raise ValueError(
                f"Tổng kết nối đồng thời ({self.API_WORKERS} workers × "
                f"{self.API_MAX_INFLIGHT} inflight = {total_inflight}) "
                f"phải nhỏ hơn max_connections của Postgres ({self.POSTGRES_MAX_CONNECTIONS}) "
                "để tránh cạn kiệt pool kết nối cơ sở dữ liệu."
            )
        if self.API_MAX_INFLIGHT > self.DB_POOL_SIZE + self.DB_MAX_OVERFLOW:
            raise ValueError(
                "API_MAX_INFLIGHT không được lớn hơn DB_POOL_SIZE + DB_MAX_OVERFLOW: "
                "request đang xử lý sẽ tranh nhau kết nối DB."
            )
        if self.ENVIRONMENT == "production" and (
            self.JWT_SECRET == DEFAULT_DEV_JWT_SECRET or len(self.JWT_SECRET) < 32
        ):
            raise ValueError(
                "JWT_SECRET không an toàn cho môi trường production: "
                "không được dùng giá trị mặc định và phải có độ dài tối thiểu 32 ký tự."
            )
        return self


@lru_cache
def get_settings() -> Settings:
    """Trả về singleton instance của cấu hình ứng dụng."""
    return Settings()
