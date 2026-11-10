#!/usr/bin/env python3
"""Thử tái hiện RemoteProtocolError khi dùng lại kết nối đúng lúc uvicorn đóng nó (keep-alive 5 s).

Chạy trong backend/:
    uv run python ../docs/evidence/load-247/after-2026-11-10/keepalive/repro_keepalive.py

Khởi động uvicorn (app thật, chỉ gọi /api/v1/health, không cần DB), rồi trên MỘT httpx.Client:
gửi request, nghỉ đúng khoảng gần timeout keep-alive, gửi tiếp. Đếm lỗi theo thời gian nghỉ.
"""

import subprocess
import sys
import time
from collections import Counter

import httpx

PORT = 18099
GAPS = [4.90, 4.95, 4.98, 5.00, 5.02, 5.05, 5.10]  # quanh timeout_keep_alive mặc định = 5 s
REPEAT = 6

api = subprocess.Popen(
    [sys.executable, "-m", "uvicorn", "app.main:app", "--port", str(PORT)]
    + ["--log-level", "warning"],
    stdout=subprocess.DEVNULL,  # log JSON của app không lẫn vào bảng kết quả
)
try:
    for _ in range(60):
        try:
            if httpx.get(f"http://127.0.0.1:{PORT}/api/v1/health", timeout=1).status_code == 200:
                break
        except httpx.HTTPError:
            time.sleep(0.5)
    result: Counter = Counter()
    with httpx.Client(base_url=f"http://127.0.0.1:{PORT}", timeout=5) as c:
        for gap in GAPS:
            for _ in range(REPEAT):
                c.get("/api/v1/health")
                time.sleep(gap)
                try:
                    c.get("/api/v1/health")
                    result[(gap, "ok")] += 1
                except httpx.HTTPError as e:
                    result[(gap, type(e).__name__)] += 1
    print("| Nghỉ trước request (s) | Kết quả | Số lần |")
    print("|---|---|---|")
    for (gap, kind), n in sorted(result.items()):
        print(f"| {gap:.2f} | {kind} | {n} |")
finally:
    api.terminate()
    api.wait(timeout=10)
