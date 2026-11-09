#!/usr/bin/env python3
# ruff: noqa: E501
"""Harness tải VT-018 (AI-19): N client đồng thời tạo cuộc họp rồi poll trạng thái job.

Chạy trong backend/:  uv run python scripts/load_vt018.py --db postgresql+psycopg://... --clients 40

Dựng DB trống bằng alembic, chạy API (uvicorn) và worker (fake pipeline) như hai process thật,
bắn N client cùng lúc (barrier), ghi latency từng request. Kết quả vào --out:
env.json (máy, phiên bản, tham số), raw.csv (từng request), summary.json và summary.md.

Giới hạn của phép đo (cũng được ghi vào summary.md):
- worker chạy MỖI LÚC 1 job nên hàng đợi tăng dần; harness đo độ trễ API, không đo thông lượng pipeline;
- pipeline là fake, audio là WAV im lặng 3 giây;
- client, API, worker và Postgres cùng một máy.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import platform
import statistics
import subprocess
import sys
import tempfile
import threading
import time
import uuid
import wave
from pathlib import Path

import httpx

BACKEND = Path(__file__).resolve().parent.parent
PASSWORD = "LoadTest!2026"
LOGIN_SLOTS = threading.Semaphore(8)
EMAIL = "load@example.com"


def make_wav(path: Path, seconds: int = 3) -> None:
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(b"\x00\x00" * 16000 * seconds)


def pct(values: list[float], q: float) -> float:
    s = sorted(values)
    return s[min(len(s) - 1, max(0, int(round(q * len(s) + 0.5)) - 1))] if s else float("nan")


def stats(values: list[float]) -> dict:
    return {
        "n": len(values),
        "p50_s": round(statistics.median(values), 4) if values else None,
        "p95_s": round(pct(values, 0.95), 4) if values else None,
        "max_s": round(max(values), 4) if values else None,
    }


def wait_ready(base: str, timeout: float = 60) -> None:
    end = time.time() + timeout
    while time.time() < end:
        try:
            if httpx.get(f"{base}/api/v1/health", timeout=2).status_code == 200:
                return
        except httpx.HTTPError:
            pass
        time.sleep(0.5)
    raise RuntimeError("API không sẵn sàng")


def client_run(i, base, wav, barrier, polls, interval, rows, errors):
    with httpx.Client(base_url=base, timeout=120) as c:
        try:
            # Đăng nhập (argon2, tốn CPU) nằm ngoài phép đo. Giới hạn số lượt đồng thời để
            # N lượt không timeout trước barrier và làm treo cả harness (đã gặp ở N = 239).
            with LOGIN_SLOTS:
                r = c.post("/api/v1/auth/login", json={"email": EMAIL, "password": PASSWORD})
            ok, code = r.status_code == 200, r.status_code
        except httpx.HTTPError as e:
            ok, code = False, type(e).__name__
        if not ok:
            errors.append(("login", code))
            barrier.abort()
            return
        try:
            barrier.wait()
        except threading.BrokenBarrierError:
            return
        t0 = time.perf_counter()
        try:
            r = c.post(
                "/api/v1/meetings",
                data={
                    "title": f"Tải {i}",
                    "consent_confirmed": "true",
                    "meeting_date": "2026-11-07",
                },
                files={"file": ("load.wav", wav.read_bytes(), "audio/wav")},
                headers={"Idempotency-Key": str(uuid.uuid4())},
            )
        except httpx.HTTPError as e:
            # Trước đây lỗi ở đây làm thread chết im lặng: lượt đo biến mất khỏi kết quả (lệch 1/247).
            errors.append(("create", type(e).__name__))
            return
        rows.append(("create", r.status_code, time.perf_counter() - t0))
        if r.status_code != 201:
            errors.append(("create", r.status_code))
            return
        job_id = r.json()["job"]["id"]
        for _ in range(polls):
            time.sleep(interval)
            t0 = time.perf_counter()
            r = c.get(f"/api/v1/jobs/{job_id}")
            rows.append(("poll", r.status_code, time.perf_counter() - t0))
            if r.status_code != 200:
                errors.append(("poll", r.status_code))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True, help="URL Postgres của DB TRỐNG sẽ bị tạo lại schema")
    ap.add_argument("--clients", type=int, default=40)
    ap.add_argument("--polls", type=int, default=5)
    ap.add_argument("--interval", type=float, default=2.0)
    ap.add_argument("--threshold", type=float, default=1.5, help="p95 mục tiêu (giây)")
    ap.add_argument("--port", type=int, default=18000)
    ap.add_argument(
        "--app", default="app.main:app", help="ASGI app (để thử biến thể khi chẩn đoán)"
    )
    ap.add_argument("--api-workers", type=int, default=1, help="số process uvicorn")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    env = {**os.environ, "DATABASE_URL": args.db, "PIPELINE_BACKEND": "fake", "FAKE_SCENARIO": "ok"}
    run = lambda cmd, **kw: subprocess.run(cmd, cwd=BACKEND, env=env, check=True, **kw)  # noqa: E731
    run(["uv", "run", "alembic", "downgrade", "base"], capture_output=True)
    run(["uv", "run", "alembic", "upgrade", "head"], capture_output=True)
    run(
        [
            "uv",
            "run",
            "python",
            "-c",
            "from app.scripts.create_user import create_user;"
            "from app.db.session import get_session_factory;"
            f"s=get_session_factory()();create_user(s,'{EMAIL}','Load','{PASSWORD}');s.commit()",
        ],
        capture_output=True,
    )

    tmp = Path(tempfile.mkdtemp())
    wav = tmp / "load.wav"
    make_wav(wav)
    base = f"http://127.0.0.1:{args.port}"
    api = subprocess.Popen(
        [
            "uv",
            "run",
            "uvicorn",
            args.app,
            "--port",
            str(args.port),
            "--workers",
            str(args.api_workers),
            "--log-level",
            "warning",
        ],
        cwd=BACKEND,
        env=env,
    )
    worker = subprocess.Popen(
        ["uv", "run", "python", "-m", "app.worker.runner"],
        cwd=BACKEND,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        wait_ready(base)
        rows: list = []
        errors: list = []
        barrier = threading.Barrier(args.clients)
        threads = [
            threading.Thread(
                target=client_run,
                args=(i, base, wav, barrier, args.polls, args.interval, rows, errors),
            )
            for i in range(args.clients)
        ]
        wall0 = time.perf_counter()
        [t.start() for t in threads]
        [t.join() for t in threads]
        wall = time.perf_counter() - wall0

        with httpx.Client(base_url=base, timeout=30) as c:
            c.post("/api/v1/auth/login", json={"email": EMAIL, "password": PASSWORD})
            listing = c.get("/api/v1/meetings", params={"page_size": 100}).json()
    finally:
        api.terminate()
        worker.terminate()
        api.wait(timeout=15)
        worker.wait(timeout=15)

    with (out / "raw.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["kind", "status", "latency_s"])
        w.writerows((k, s, f"{d:.4f}") for k, s, d in rows)

    by = {k: [d for kk, s, d in rows if kk == k and s < 400] for k in ("create", "poll")}
    allv = by["create"] + by["poll"]
    items = listing.get("items", []) if isinstance(listing, dict) else []
    statuses: dict[str, int] = {}
    for m in items:
        statuses[m.get("status", "?")] = statuses.get(m.get("status", "?"), 0) + 1
    summary = {
        "clients": args.clients,
        "threshold_p95_s": args.threshold,
        "create": stats(by["create"]),
        "poll": stats(by["poll"]),
        "all_requests": stats(allv),
        "errors": len(errors),
        "error_kinds": {f"{k}:{v}": errors.count((k, v)) for k, v in sorted(set(errors), key=str)},
        "wall_clock_s": round(wall, 2),
        "meeting_status_at_end": statuses,
        "verdict": "PASS" if allv and not errors and pct(allv, 0.95) <= args.threshold else "FAIL",
    }
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2))
    (out / "env.json").write_text(
        json.dumps(
            {
                "date": time.strftime("%Y-%m-%d %H:%M:%S %z"),
                "python": sys.version.split()[0],
                "httpx": httpx.__version__,
                "platform": platform.platform(),
                "cpu_count": os.cpu_count(),
                "git_commit": subprocess.run(
                    ["git", "rev-parse", "--short", "HEAD"],
                    cwd=BACKEND,
                    capture_output=True,
                    text=True,
                ).stdout.strip(),
                "psycopg": subprocess.run(
                    ["uv", "run", "python", "-c", "import psycopg,sys;print(psycopg.__version__)"],
                    cwd=BACKEND,
                    env=env,
                    capture_output=True,
                    text=True,
                ).stdout.strip(),
                "args": {k: v for k, v in vars(args).items() if k != "db"},
                "pipeline_backend": "fake",
                "workers": 1,
                "api_workers": args.api_workers,
            },
            indent=2,
        )
    )
    md = f"""# Kết quả tải VT-018 ({args.clients} client đồng thời)

| Loại | n | p50 (s) | p95 (s) | max (s) |
|---|---|---|---|---|
| tạo cuộc họp (upload) | {summary["create"]["n"]} | {summary["create"]["p50_s"]} | {summary["create"]["p95_s"]} | {summary["create"]["max_s"]} |
| poll trạng thái job | {summary["poll"]["n"]} | {summary["poll"]["p50_s"]} | {summary["poll"]["p95_s"]} | {summary["poll"]["max_s"]} |
| **tất cả** | {summary["all_requests"]["n"]} | {summary["all_requests"]["p50_s"]} | **{summary["all_requests"]["p95_s"]}** | {summary["all_requests"]["max_s"]} |

Mục tiêu p95 ≤ {args.threshold} s: **{summary["verdict"]}**. Lỗi: {summary["errors"]} {summary["error_kinds"] or ""}. Thời gian toàn bộ: {summary["wall_clock_s"]} s.
Trạng thái meeting khi kết thúc: {statuses}.

## Giới hạn của phép đo

- Worker chạy mỗi lúc 1 job, hàng đợi dài dần trong lúc đo; đây là độ trễ của API, không phải thông lượng pipeline.
- Pipeline là fake, audio WAV im lặng 3 giây; chưa phản ánh tải của ASR/diarize thật.
- Client, API, worker và Postgres chung một máy ({os.cpu_count()} CPU), nên tranh chấp CPU làm số đo xấu hơn môi trường tách riêng.
- Một lần chạy, chưa lặp để lấy khoảng tin cậy. Chi tiết máy ở `env.json`, từng request ở `raw.csv`.
"""
    (out / "summary.md").write_text(md)
    print(md)
    return 0 if summary["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
