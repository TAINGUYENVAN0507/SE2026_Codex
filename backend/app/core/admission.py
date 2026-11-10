"""Giới hạn số request đang xử lý cùng lúc (AD-018, RE-018).

Vấn đề đã đo ở 247 client (docs/evidence/load-247/diagnosis.md): `get_db` giữ một kết nối DB suốt
request, và endpoint đồng bộ cần một thread của threadpool (mặc định 40). Khi nhiều request hơn số
thread cùng đến, một số request đã giữ kết nối mà chưa có thread, còn các thread lại chờ kết nối từ
pool. Hai bên chặn nhau cho tới khi `DB_POOL_TIMEOUT_SEC` cắt, nên upload thành công mất ~61 s.

Giới hạn `max_inflight` nhỏ hơn số thread và số kết nối thì mỗi request đang xử lý luôn có thread
và kết nối, nên vòng chờ này không xảy ra. Request vượt giới hạn chờ ở đây (không giữ kết nối),
quá `queue_timeout_sec` thì trả 503 kèm `Retry-After`.
"""

from __future__ import annotations

import asyncio
import time

from prometheus_client import Counter, Gauge, Histogram
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from app.core.errors import build_error_envelope, get_request_id
from app.core.metrics import LATENCY_BUCKETS

# Không có nhãn nào chứa id hay dữ liệu người dùng (PRIV-10).
INFLIGHT = Gauge("api_inflight_requests", "Số request đang xử lý trong process API")
REJECTED = Counter(
    "api_admission_rejected_total",
    "Số request bị từ chối 503 vì chờ quá API_QUEUE_TIMEOUT_SEC",
)
# Chỉ đo request được nhận; request bị từ chối đã đếm ở REJECTED (chờ đúng bằng timeout).
# http_request_duration_seconds trừ phần này là thời gian xử lý thật của request.
ADMISSION_WAIT = Histogram(
    "api_admission_wait_seconds",
    "Thời gian request chờ ở hàng đợi admission trước khi được xử lý",
    buckets=LATENCY_BUCKETS,
)

# Đường dẫn không bị xếp hàng: health cho liveness probe, /metrics cho Prometheus.
EXEMPT_PATHS = frozenset({"/health", "/api/v1/health", "/metrics"})


class AdmissionControlMiddleware:
    """ASGI middleware thuần (không dùng BaseHTTPMiddleware để không thêm thread hay task)."""

    def __init__(
        self,
        app: ASGIApp,
        max_inflight: int,
        queue_timeout_sec: float,
        exempt_paths: frozenset[str] = EXEMPT_PATHS,
    ) -> None:
        self.app = app
        self.max_inflight = max_inflight
        self.queue_timeout_sec = queue_timeout_sec
        self.exempt_paths = exempt_paths
        self._semaphore: asyncio.Semaphore | None = None

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or self.max_inflight <= 0 or scope["path"] in self.exempt_paths:
            await self.app(scope, receive, send)
            return

        if self._semaphore is None:
            self._semaphore = asyncio.Semaphore(self.max_inflight)
        start = time.perf_counter()
        try:
            await asyncio.wait_for(self._semaphore.acquire(), timeout=self.queue_timeout_sec)
        except TimeoutError:
            REJECTED.inc()
            await self._reject(scope, receive, send)
            return
        ADMISSION_WAIT.observe(time.perf_counter() - start)
        INFLIGHT.inc()
        try:
            await self.app(scope, receive, send)
        finally:
            INFLIGHT.dec()
            self._semaphore.release()

    async def _reject(self, scope: Scope, receive: Receive, send: Send) -> None:
        body = build_error_envelope(
            code="SERVICE_UNAVAILABLE",
            message="Hệ thống đang bận. Vui lòng thử lại sau ít giây.",
            details=None,
            request_id=get_request_id(Request(scope, receive)),
        )
        response = JSONResponse(status_code=503, content=body, headers={"Retry-After": "2"})
        await response(scope, receive, send)
