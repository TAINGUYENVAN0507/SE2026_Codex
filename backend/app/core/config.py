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
    ENVIRONMENT: str = "development"
    DEBUG: bool = False

    # Giới hạn upload theo kế hoạch
    MAX_UPLOAD_MB: int = 200
    MAX_DURATION_SEC: int = 3600

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
        """Đảm bảo JWT_SECRET an toàn khi chạy trên môi trường production."""
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
