"""Quản lý các số đo Prometheus và middleware đo lường hiệu năng (BE-19).

Bao gồm:
- http_requests_total: Đếm tổng số HTTP requests theo method, route template và status.
- http_request_duration_seconds: Histogram đo thời gian xử lý request theo route template
  (gồm thời gian chờ admission; phần chờ riêng ở api_admission_wait_seconds).
- jobs_total: Gauge số lượng job theo trạng thái (queued, running, retry_scheduled,
  succeeded, failed, cancelled).
- job_oldest_queued_seconds: Gauge độ tuổi của job đang queued lâu nhất.
- jobs_failed_total: Gauge số lượng job lỗi gom theo stage và error_code.
Tuyệt đối không đưa UUID hoặc thông tin cá nhân vào nhãn (labels).
"""

import contextlib
import glob
import json
import os
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

from fastapi import Depends, Request, Response
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
    multiprocess,
)
from prometheus_client.mmap_dict import MmapedDict
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

# 1.5 và 2.0 là mốc p95 của VT-018 và AD-018: tỷ lệ request dưới mốc đọc thẳng từ bucket.
LATENCY_BUCKETS = (
    0.001,
    0.005,
    0.01,
    0.025,
    0.05,
    0.1,
    0.25,
    0.5,
    0.75,
    1.0,
    1.5,
    2.0,
    2.5,
    3.0,
    5.0,
    10.0,
)

HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "http_request_duration_seconds",
    "Thời gian xử lý HTTP request tính bằng giây (gồm cả thời gian chờ admission)",
    ["route"],
    buckets=LATENCY_BUCKETS,
)

# 2. Job / Queue Metrics
JOBS_TOTAL = Gauge(
    "jobs_total",
    "Số lượng background jobs theo trạng thái",
    ["status"],
    multiprocess_mode="livemostrecent",
)

JOB_OLDEST_QUEUED_SECONDS = Gauge(
    "job_oldest_queued_seconds",
    "Độ tuổi (tính bằng giây) của job ở trạng thái queued lâu nhất",
    multiprocess_mode="livemostrecent",
)

JOBS_FAILED_TOTAL = Gauge(
    "jobs_failed_total",
    "Số lượng jobs thất bại theo stage và mã lỗi",
    ["stage", "error_code"],
    multiprocess_mode="livemostrecent",
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
    known_statuses = set(JOB_STATUSES) | {k[0] for k in JOBS_TOTAL._metrics}
    status_counts = {st: 0 for st in known_statuses}
    rows = db.execute(select(Job.status, func.count(Job.id)).group_by(Job.status)).all()
    for st, count in rows:
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
    known_failed_groups: set[tuple[str, str]] = set()
    if "PROMETHEUS_MULTIPROC_DIR" in os.environ:
        target_dir = os.environ["PROMETHEUS_MULTIPROC_DIR"]
        for f in glob.glob(os.path.join(target_dir, "gauge_livemostrecent_*.db")):
            try:
                for raw_key, _, _, _ in MmapedDict.read_all_values_from_file(f):
                    metric_name, _, labels, _ = json.loads(raw_key)
                    if metric_name == "jobs_failed_total":
                        known_failed_groups.add(
                            (labels.get("stage", "unknown"), labels.get("error_code", "UNKNOWN"))
                        )
            except Exception:
                pass
    for key in list(JOBS_FAILED_TOTAL._metrics.keys()):
        known_failed_groups.add((key[0], key[1]))

    if "PROMETHEUS_MULTIPROC_DIR" not in os.environ:
        JOBS_FAILED_TOTAL.clear()

    failed_rows = db.execute(
        select(Job.stage, Job.error_code, func.count(Job.id))
        .where(Job.status == "failed")
        .group_by(Job.stage, Job.error_code)
    ).all()
    active_failed_groups: set[tuple[str, str]] = set()
    for stage, error_code, count in failed_rows:
        stg = stage or "unknown"
        err = error_code or "UNKNOWN"
        active_failed_groups.add((stg, err))
        JOBS_FAILED_TOTAL.labels(stage=stg, error_code=err).set(count)

    # Đưa các nhóm đã về 0 về 0 để cập nhật mmap file ở chế độ multiprocess
    for stg, err in known_failed_groups - active_failed_groups:
        JOBS_FAILED_TOTAL.labels(stage=stg, error_code=err).set(0)


def clean_multiproc_dir(path: str | Path | None = None) -> None:
    """Dọn dẹp các tệp .db trong thư mục multiprocess của Prometheus khi khởi động."""
    target = path or os.environ.get("PROMETHEUS_MULTIPROC_DIR")
    if not target:
        return
    dir_path = Path(target)
    if not dir_path.exists():
        dir_path.mkdir(parents=True, exist_ok=True)
        return
    for p in dir_path.glob("*.db"):
        with contextlib.suppress(OSError):
            p.unlink()


def metrics_endpoint(db: Annotated[Session, Depends(get_db)]) -> Response:
    """Endpoint Prometheus /metrics trả về text định dạng standard metrics."""
    collect_db_metrics(db)
    if "PROMETHEUS_MULTIPROC_DIR" in os.environ:
        registry = CollectorRegistry()
        multiprocess.MultiProcessCollector(registry)
        content = generate_latest(registry)
    else:
        content = generate_latest()
    return Response(
        content=content,
        media_type=CONTENT_TYPE_LATEST,
    )
