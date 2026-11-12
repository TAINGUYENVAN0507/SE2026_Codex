"""App factory và khởi tạo ứng dụng FastAPI."""

import contextlib
import os
from collections.abc import AsyncGenerator

from fastapi import FastAPI

from app.api.v1.auth import router as auth_router
from app.api.v1.config import router as config_router
from app.api.v1.health import router as health_router
from app.api.v1.jobs import router as jobs_router
from app.api.v1.meetings import router as meetings_router
from app.core.admission import AdmissionControlMiddleware
from app.core.config import get_settings
from app.core.errors import setup_exception_handlers
from app.core.logging import setup_logging
from app.core.metrics import PrometheusMetricsMiddleware, mark_process_dead, metrics_endpoint
from app.core.middleware import RequestIDAndLoggingMiddleware


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Quản lý vòng đời khởi động và dừng ứng dụng (BE-19)."""
    yield
    if "PROMETHEUS_MULTIPROC_DIR" in os.environ:
        with contextlib.suppress(Exception):
            mark_process_dead(os.getpid())


def create_app() -> FastAPI:
    """Khởi tạo và cấu hình instance FastAPI cho backend."""
    setup_logging()
    settings = get_settings()

    application = FastAPI(
        title=settings.PROJECT_NAME,
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # Thêm đầu tiên nên nằm trong cùng: request chờ ở đây đã có request_id và được đo bởi metrics
    application.add_middleware(
        AdmissionControlMiddleware,
        max_inflight=settings.API_MAX_INFLIGHT,
        queue_timeout_sec=settings.API_QUEUE_TIMEOUT_SEC,
    )

    # Đăng ký middleware request_id, logging và prometheus metrics
    application.add_middleware(RequestIDAndLoggingMiddleware)
    application.add_middleware(PrometheusMetricsMiddleware)

    # Đăng ký exception handlers chuẩn hóa error envelope
    setup_exception_handlers(application)

    # Đăng ký routers dưới prefix /api/v1
    application.include_router(health_router, prefix=settings.API_V1_PREFIX)
    application.include_router(auth_router, prefix=settings.API_V1_PREFIX)
    application.include_router(config_router, prefix=settings.API_V1_PREFIX)
    application.include_router(meetings_router, prefix=settings.API_V1_PREFIX)
    application.include_router(jobs_router, prefix=settings.API_V1_PREFIX)

    # Đăng ký health ở root cho liveness probe
    application.include_router(health_router)

    # Đăng ký endpoint /metrics cho Prometheus (nằm ngoài /api/v1, không đưa vào openapi schema)
    application.add_api_route(
        "/metrics",
        metrics_endpoint,
        methods=["GET"],
        include_in_schema=False,
    )

    return application


app = create_app()
