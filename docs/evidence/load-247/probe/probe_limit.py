"""Biến thể: giới hạn số request đang xử lý trước khi vào dependency (thử giả thuyết deadlock thread/connection)."""
import asyncio, os
from app.main import app as inner
N = int(os.environ.get("PROBE_INFLIGHT", "40"))
sem = None
class Limit:
    def __init__(self, app): self.app = app
    async def __call__(self, scope, receive, send):
        global sem
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        if sem is None:
            sem = asyncio.Semaphore(N)
        async with sem:
            await self.app(scope, receive, send)
app = Limit(inner)
