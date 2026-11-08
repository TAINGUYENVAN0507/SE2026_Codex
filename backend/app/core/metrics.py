"""Quản lý các số đo Prometheus và middleware đo lường hiệu năng (BE-19).

Bao gồm:
- http_requests_total: Đếm tổng số HTTP requests theo method, route template và status.
- http_request_duration_seconds: Histogram đo thời gian xử lý request theo route template.
- jobs_total: Gauge số lượng job theo trạng thái (queued, running, retry_scheduled,
  succeeded, failed, cancelled).
- job_oldest_queued_seconds: Gauge độ tuổi của job đang queued lâu nhất.
- jobs_failed_total: Gauge số lượng job lỗi gom theo stage và error_code.
Tuyệt đối không đưa UUID hoặc thông tin cá nhân vào nhãn (labels).
"""

import time
from datetime import UTC, datetime
from typing import Annotated

from fastapi import Depends, Request, Response
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from app.db.models.job import Job
from app.db.session import get_db

# 1. HTTP Metrics
HTTP_REQUESTS_TOTAL = Counter(
    "http_requests_total",
    "Tổng số HTTP requests đã xử lý",
    ["method", "route", "status"],
)

HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "http_request_duration_seconds",
    "Thời gian xử lý HTTP request tính bằng giây",
    ["route"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

# 2. Job / Queue Metrics
JOBS_TOTAL = Gauge(
    "jobs_total",
    "Số lượng background jobs theo trạng thái",
    ["status"],
)

JOB_OLDEST_QUEUED_SECONDS = Gauge(
    "job_oldest_queued_seconds",
    "Độ tuổi (tính bằng giây) của job ở trạng thái queued lâu nhất",
)

JOBS_FAILED_TOTAL = Gauge(
    "jobs_failed_total",
    "Số lượng jobs thất bại theo stage và mã lỗi",
    ["stage", "error_code"],
)

# 3. Pipeline Metrics
PIPELINE_STAGE_DURATION_SECONDS = Histogram(
    "pipeline_stage_duration_seconds",
    "Thời gian thực thi từng stage trong pipeline tính bằng giây",
    ["stage"],
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0),
)

JOB_STATUSES = (
    "queued",
    "running",
    "retry_scheduled",
    "succeeded",
    "failed",
    "cancelled",
)


class PrometheusMetricsMiddleware(BaseHTTPMiddleware):
    """Middleware ghi nhận số lượng và thời gian xử lý request.

    Sử dụng route template (không dùng URL thô chứa ID) để tránh phân mảnh nhãn
    và tuân thủ bảo vệ dữ liệu cá nhân (PRIV-10).
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        start_time = time.perf_counter()
        response = await call_next(request)
        duration = time.perf_counter() - start_time

        route_obj = request.scope.get("route")
        if route_obj and hasattr(route_obj, "path"):
            route_path = route_obj.path
            if request.url.path.startswith("/api/v1") and not route_path.startswith("/api/v1"):
                route_path = f"/api/v1{route_path}"
        else:
            route_path = "unmatched"

        method = request.method
        status_code = str(response.status_code)

        HTTP_REQUESTS_TOTAL.labels(method=method, route=route_path, status=status_code).inc()
        HTTP_REQUEST_DURATION_SECONDS.labels(route=route_path).observe(duration)

        return response


def collect_db_metrics(db: Session) -> None:
    """Truy vấn cơ sở dữ liệu và cập nhật các số đo Gauge tại thời điểm scrape."""
    # 1. Đếm số lượng job theo trạng thái
    status_counts = {st: 0 for st in JOB_STATUSES}
    rows = db.execute(select(Job.status, func.count(Job.id)).group_by(Job.status)).all()
    for st, count in rows:
        if st in status_counts:
            status_counts[st] = count
        else:
            status_counts[st] = count

    for st, count in status_counts.items():
        JOBS_TOTAL.labels(status=st).set(count)

    # 2. Độ tuổi của job queued lâu nhất
    oldest_created = db.execute(
        select(func.min(Job.created_at)).where(Job.status == "queued")
    ).scalar()
    if oldest_created:
        now = datetime.now(UTC)
        if oldest_created.tzinfo is None:
            oldest_created = oldest_created.replace(tzinfo=UTC)
        age = max(0.0, (now - oldest_created).total_seconds())
        JOB_OLDEST_QUEUED_SECONDS.set(age)
    else:
        JOB_OLDEST_QUEUED_SECONDS.set(0.0)

    # 3. Đếm số lượng job failed theo stage và error_code
    JOBS_FAILED_TOTAL.clear()
    failed_rows = db.execute(
        select(Job.stage, Job.error_code, func.count(Job.id))
        .where(Job.status == "failed")
        .group_by(Job.stage, Job.error_code)
    ).all()
    for stage, error_code, count in failed_rows:
        JOBS_FAILED_TOTAL.labels(
            stage=stage or "unknown",
            error_code=error_code or "UNKNOWN",
        ).set(count)


def metrics_endpoint(db: Annotated[Session, Depends(get_db)]) -> Response:
    """Endpoint Prometheus /metrics trả về text định dạng standard metrics."""
    collect_db_metrics(db)
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST,
    )
