"""AD-018, RE-018: giới hạn số request đang xử lý để threadpool và pool DB không chặn nhau.

Đo tải 247 client (docs/evidence/load-247/diagnosis.md): mỗi request giữ một kết nối DB (qua
`get_db`) trong lúc chờ một thread của threadpool, còn các thread lại chờ kết nối. Hai bên chặn nhau
cho tới khi pool timeout (10 s) cắt, nên upload thành công mất ~61 s. Giới hạn số request đang xử lý
nhỏ hơn số thread và số kết nối thì vòng chờ này không xảy ra.
"""

import asyncio

import httpx
import pytest
from fastapi import FastAPI

from app.core.admission import AdmissionControlMiddleware
from app.core.config import Settings


def make_app(*, max_inflight: int, queue_timeout_sec: float, sleep: float = 0.05):
    app = FastAPI()
    state = {"running": 0, "peak": 0}

    @app.get("/work")
    async def work():
        state["running"] += 1
        state["peak"] = max(state["peak"], state["running"])
        try:
            await asyncio.sleep(sleep)
        finally:
            state["running"] -= 1
        return {"ok": True}

    @app.get("/api/v1/health")
    async def health():
        return {"status": "ok"}

    app.add_middleware(
        AdmissionControlMiddleware,
        max_inflight=max_inflight,
        queue_timeout_sec=queue_timeout_sec,
    )
    return app, state


async def run_many(app: FastAPI, n: int, path: str = "/work") -> list[httpx.Response]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
        return await asyncio.gather(*(c.get(path) for _ in range(n)))


@pytest.mark.anyio
async def test_never_more_than_max_inflight_run_at_once_and_all_finish():
    app, state = make_app(max_inflight=3, queue_timeout_sec=5)
    responses = await run_many(app, 12)
    assert [r.status_code for r in responses] == [200] * 12
    assert state["peak"] == 3


@pytest.mark.anyio
async def test_waiting_longer_than_queue_timeout_returns_503_with_retry_after():
    app, _ = make_app(max_inflight=1, queue_timeout_sec=0.05, sleep=0.4)
    responses = await run_many(app, 3)
    codes = sorted(r.status_code for r in responses)
    assert codes == [200, 503, 503]
    rejected = next(r for r in responses if r.status_code == 503)
    assert rejected.json()["error"]["code"] == "SERVICE_UNAVAILABLE"
    assert rejected.headers["Retry-After"].isdigit()


@pytest.mark.anyio
async def test_health_is_not_queued_behind_busy_requests():
    app, _ = make_app(max_inflight=1, queue_timeout_sec=5, sleep=0.3)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
        slow = asyncio.create_task(c.get("/work"))
        await asyncio.sleep(0.05)
        health = await asyncio.wait_for(c.get("/api/v1/health"), timeout=0.2)
        assert health.status_code == 200
        assert (await slow).status_code == 200


@pytest.mark.anyio
async def test_zero_disables_the_limit():
    app, state = make_app(max_inflight=0, queue_timeout_sec=1)
    await run_many(app, 8)
    assert state["peak"] == 8


def test_default_max_inflight_fits_threadpool_and_db_pool():
    s = Settings()
    assert 0 < s.API_MAX_INFLIGHT <= 40, "mặc định threadpool của AnyIO là 40 thread"
    assert s.API_MAX_INFLIGHT <= s.DB_POOL_SIZE + s.DB_MAX_OVERFLOW


def test_inflight_above_db_pool_is_rejected_at_startup():
    with pytest.raises(ValueError, match="API_MAX_INFLIGHT"):
        Settings(API_MAX_INFLIGHT=100, DB_POOL_SIZE=5, DB_MAX_OVERFLOW=10)
