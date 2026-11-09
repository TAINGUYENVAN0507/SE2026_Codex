"""Biến thể chẩn đoán: đo thời gian chờ threadpool và thời gian giữ kết nối, ghi ra file."""
import os, time, threading
import anyio.to_thread
from app.main import app
from app.db import session as dbsession

LOG = os.environ.get("PROBE_LOG", "/tmp/probe.log")
lock = threading.Lock()
def emit(line):
    with lock, open(LOG, "a") as f:
        f.write(line + "\n")

TOK = int(os.environ.get("PROBE_TOKENS", "0"))
async def _startup():
    if TOK:
        anyio.to_thread.current_default_thread_limiter().total_tokens = TOK
app.router.on_startup.append(_startup)

# thời gian chờ để có thread (queue) cho mỗi lần run_sync
_orig = anyio.to_thread.run_sync
async def run_sync(func, *a, **kw):
    t0 = time.perf_counter()
    started = []
    def wrapped(*aa):
        started.append(time.perf_counter())
        return func(*aa)
    try:
        return await _orig(wrapped, *a, **kw)
    finally:
        t1 = time.perf_counter()
        emit(f"thread name={getattr(func,'__name__',str(func))} wait={started[0]-t0:.3f} total={t1-t0:.3f}" if started else f"thread name={getattr(func,'__name__',str(func))} nostart total={t1-t0:.3f}")
anyio.to_thread.run_sync = run_sync
import starlette.concurrency as sc
sc.anyio.to_thread.run_sync = run_sync
