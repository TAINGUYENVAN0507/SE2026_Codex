"""App factory và khởi tạo ứng dụng FastAPI."""

from fastapi import FastAPI

from app.api.v1.health import router as health_router
from app.core.config import get_settings


def create_app() -> FastAPI:
    """Khởi tạo và cấu hình instance FastAPI cho backend."""
    settings = get_settings()

    application = FastAPI(
        title=settings.PROJECT_NAME,
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    # Đăng ký router health dưới prefix /api/v1 và root
    application.include_router(health_router, prefix=settings.API_V1_PREFIX)
    application.include_router(health_router)

    return application


app = create_app()
