"""Routes kiểm tra sức khỏe và độ sẵn sàng của dịch vụ backend."""

from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from app.core.database import DatabaseHealthChecker, get_db_health_checker

router = APIRouter(tags=["Health"])


@router.get("/health", status_code=status.HTTP_200_OK)
def health_check() -> dict[str, str]:
    """Liveness probe: luôn trả về HTTP 200 khi tiến trình server đang chạy."""
    return {"status": "ok"}


@router.get("/ready")
def readiness_check(
    response: Response,
    db_checker: Annotated[DatabaseHealthChecker, Depends(get_db_health_checker)],
) -> dict[str, str]:
    """Readiness probe: kiểm tra kết nối cơ sở dữ liệu.

    Trả về 200 nếu kết nối cơ sở dữ liệu hoạt động bình thường;
    trả về 503 Service Unavailable nếu mất kết nối DB.
    """
    if db_checker.is_healthy():
        response.status_code = status.HTTP_200_OK
        return {"status": "ready", "database": "connected"}

    response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {"status": "unhealthy", "database": "disconnected"}
