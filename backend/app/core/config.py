"""Cấu hình ứng dụng backend sử dụng pydantic-settings."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Cấu hình hệ thống đọc từ biến môi trường hoặc file .env."""

    PROJECT_NAME: str = "Vietnamese Meeting Minutes Assistant"
    API_V1_PREFIX: str = "/api/v1"
    DATABASE_URL: str = "postgresql+psycopg://postgres:postgres@localhost:5432/meeting_minutes"
    ENVIRONMENT: str = "development"
    DEBUG: bool = False

    # Giới hạn upload theo kế hoạch
    MAX_UPLOAD_MB: int = 200
    MAX_DURATION_SEC: int = 7200

    # Cấu hình xác thực JWT
    JWT_SECRET: str = "dev-insecure-jwt-secret-key-change-in-prod"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60 * 24 * 7

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Trả về singleton instance của cấu hình ứng dụng."""
    return Settings()
