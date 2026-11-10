#!/usr/bin/env python3
# ruff: noqa: E501
"""Harness tải VT-018 (AI-19): N client đồng thời tạo cuộc họp rồi poll trạng thái job.

Chạy trong backend/:  uv run python scripts/load_vt018.py --db postgresql+psycopg://... --clients 40

Dựng DB trống bằng alembic, chạy API (uvicorn) và worker (fake pipeline) như hai process thật,
bắn N client cùng lúc (barrier), ghi latency từng request. Kết quả vào --out:
env.json (máy, phiên bản, tham số), raw.csv (từng request), summary.json và summary.md.

Với 1 process API, harness đọc /metrics ngay trước khi thả barrier và sau khi mọi client xong;
hiệu hai lần đọc cho số phía server (tổng thời gian ở app, thời gian chờ admission) đặt cạnh số
phía client. Nhiều process thì /metrics chỉ là của một process nên phần này bị bỏ qua.

Giới hạn của phép đo (cũng được ghi vào summary.md):
- worker chạy MỖI LÚC 1 job nên hàng đợi tăng dần; harness đo độ trễ API, không đo thông lượng pipeline;
- pipeline là fake, audio là WAV im lặng 3 giây;
- client, API, worker và Postgres cùng một máy.
"""

from __future__ import annotations

import argparse
import csv
import json
import multiprocessing as mp
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
from prometheus_client.parser import text_string_to_metric_families

BACKEND = Path(__file__).resolve().parent.parent
PASSWORD = "LoadTest!2026"
LOGIN_CONCURRENCY = 8  # chia đều cho các process client
LOGIN_SLOTS = threading.Semaphore(LOGIN_CONCURRENCY)
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


def frac_le(values: list[float], limit: float) -> float | None:
    return round(sum(v <= limit for v in values) / len(values), 4) if values else None


SERVER_ROUTES = {"create": "/api/v1/meetings", "poll": "/api/v1/jobs/{job_id}"}
THRESHOLDS = (1.5, 2.0)


def scrape(base: str) -> dict:
    text = httpx.get(f"{base}/metrics", timeout=30).text
    return {
        (s.name, tuple(sorted(s.labels.items()))): s.value
        for fam in text_string_to_metric_families(text)
        for s in fam.samples
    }


def hist_delta(before: dict, after: dict, name: str, **labels: str):
    """Hiệu histogram giữa hai lần scrape: bucket tích lũy [(le, count)], sum, count."""
    want = tuple(sorted(labels.items()))
    buckets = []
    for (n, lab), v in after.items():
        if n != f"{name}_bucket":
            continue
        d = dict(lab)
        le = float(d.pop("le"))
        if tuple(sorted(d.items())) == want:
            buckets.append((le, v - before.get((n, lab), 0.0)))
    buckets.sort()
    sum_key, count_key = (f"{name}_sum", want), (f"{name}_count", want)
    return (
        buckets,
        after.get(sum_key, 0.0) - before.get(sum_key, 0.0),
        after.get(count_key, 0.0) - before.get(count_key, 0.0),
    )


def hist_summary(buckets, total: float, count: float) -> dict:
    """Từ bucket chỉ biết quantile nằm trong khoảng (lo, hi]; tỷ lệ dưới mốc thì chính xác."""
    if not count:
        return {"n": 0}

    def bounds(q: float) -> list:
        prev = 0.0
        for le, c in buckets:
            if c >= q * count:
                return [prev, None if le == float("inf") else le]
            prev = le
        return [prev, None]

    out = {
        "n": int(count),
        "mean_s": round(total / count, 4),
        "p50_in_s": bounds(0.5),
        "p95_in_s": bounds(0.95),
    }
    for limit in THRESHOLDS:
        hit = [c for le, c in buckets if le == limit]
        out[f"le_{limit}"] = round(hit[0] / count, 4) if hit else None
    return out


def server_view(before: dict, after: dict) -> dict:
    view = {
        kind: hist_summary(*hist_delta(before, after, "http_request_duration_seconds", route=r))
        for kind, r in SERVER_ROUTES.items()
    }
    view["admission_wait"] = hist_summary(*hist_delta(before, after, "api_admission_wait_seconds"))
    return view


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


def client_run(i, base, wav, ready, start, polls, interval, rows, errors, idle, detail):
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
            ready.abort()
            return
        logged_in = time.perf_counter()
        try:
            ready.wait()
        except threading.BrokenBarrierError:
            return
        start.wait()
        body = wav.read_bytes()
        t0 = time.perf_counter()
        # Kết nối nằm rảnh từ lúc đăng nhập tới lúc upload (so với timeout keep-alive của uvicorn).
        idle.append(t0 - logged_in)
        try:
            r = c.post(
                "/api/v1/meetings",
                data={
                    "title": f"Tải {i}",
                    "consent_confirmed": "true",
                    "meeting_date": "2026-11-07",
                },
                files={"file": ("load.wav", body, "audio/wav")},
                headers={"Idempotency-Key": str(uuid.uuid4())},
            )
        except httpx.HTTPError as e:
            # Trước đây lỗi ở đây làm thread chết im lặng: lượt đo biến mất khỏi kết quả (lệch 1/247).
            errors.append(("create", type(e).__name__))
            detail.append(
                {
                    "kind": type(e).__name__,
                    "message": str(e)[:200],
                    "idle_before_s": round(t0 - logged_in, 3),
                    "after_s": round(time.perf_counter() - t0, 3),
                }
            )
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


def run_clients(ids, base, wav, polls, interval, on_ready, on_abort):
    """Chạy các client trong process hiện tại: đăng nhập hết, gọi on_ready (chặn tới lúc thả),
    rồi thả mọi thread cùng lúc. Trả về (rows, errors)."""
    rows: list = []
    errors: list = []
    idle: list = []
    detail: list = []
    ready = threading.Barrier(len(ids) + 1)
    start = threading.Event()
    threads = [
        threading.Thread(
            target=client_run,
            args=(i, base, wav, ready, start, polls, interval, rows, errors, idle, detail),
        )
        for i in ids
    ]
    [t.start() for t in threads]
    try:
        ready.wait()
        on_ready()
    except threading.BrokenBarrierError:
        on_abort()
    start.set()
    [t.join() for t in threads]
    return rows, errors, idle, detail


def child_main(ids, base, wav, polls, interval, login_slots, all_ready, go, results):
    """Một process client (--client-procs > 1): mọi process đăng nhập xong mới cùng được thả."""
    global LOGIN_SLOTS
    LOGIN_SLOTS = threading.Semaphore(login_slots)

    def on_ready() -> None:
        all_ready.wait()
        go.wait()

    results.put(run_clients(ids, base, wav, polls, interval, on_ready, all_ready.abort))


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
    ap.add_argument(
        "--client-procs",
        type=int,
        default=1,
        help="số process sinh tải; client chia đều, mỗi process dùng thread như trước",
    )
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    env = {
        **os.environ,
        "DATABASE_URL": args.db,
        "PIPELINE_BACKEND": "fake",
        "FAKE_SCENARIO": "ok",
        # Để kiểm tra ngân sách kết nối trong Settings áp dụng cho đúng số process được chạy.
        "API_WORKERS": str(args.api_workers),
    }
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
        snaps: dict = {}

        def before_release() -> None:
            # Sau mọi lượt đăng nhập, trước khi thả client.
            if args.api_workers == 1:
                try:
                    snaps["before"] = scrape(base)
                except httpx.HTTPError as e:
                    snaps["error"] = type(e).__name__
            snaps["t0"] = time.perf_counter()

        ids = list(range(args.clients))
        if args.client_procs <= 1:
            rows, errors, idle, detail = run_clients(
                ids, base, wav, args.polls, args.interval, before_release, lambda: None
            )
        else:
            ctx = mp.get_context("spawn")
            all_ready = ctx.Barrier(args.client_procs + 1)
            go = ctx.Event()
            results = ctx.Queue()
            slots = max(1, LOGIN_CONCURRENCY // args.client_procs)
            procs = [
                ctx.Process(
                    target=child_main,
                    args=(
                        ids[k :: args.client_procs],
                        base,
                        wav,
                        args.polls,
                        args.interval,
                        slots,
                        all_ready,
                        go,
                        results,
                    ),
                )
                for k in range(args.client_procs)
            ]
            [p.start() for p in procs]
            try:
                all_ready.wait()
                before_release()
            except threading.BrokenBarrierError:
                pass
            go.set()
            rows, errors, idle, detail = [], [], [], []
            for _ in procs:
                r, e, i, d = results.get()
                rows += r
                errors += e
                idle += i
                detail += d
            [p.join() for p in procs]
        wall = time.perf_counter() - snaps.get("t0", time.perf_counter())
        if "before" in snaps:
            snaps["after"] = scrape(base)

        max_connections = subprocess.run(
            [
                "uv",
                "run",
                "python",
                "-c",
                "from sqlalchemy import create_engine,text;import os;"
                "e=create_engine(os.environ['DATABASE_URL']);"
                "print(e.connect().execute(text('show max_connections')).scalar())",
            ],
            cwd=BACKEND,
            env=env,
            capture_output=True,
            text=True,
        ).stdout.strip()

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
        "create_error_detail": detail,
        "idle_before_upload": {
            **stats(idle),
            "over_uvicorn_keepalive_5s": sum(x > 5 for x in idle),
        },
        "error_kinds": {f"{k}:{v}": errors.count((k, v)) for k, v in sorted(set(errors), key=str)},
        "client_share_within": {
            kind: {f"le_{x}": frac_le(by[kind], x) for x in THRESHOLDS}
            for kind in ("create", "poll")
        },
        "server": server_view(snaps["before"], snaps["after"])
        if "after" in snaps
        else {
            "skipped": "nhiều process API: /metrics chỉ của một process"
            if args.api_workers > 1
            else snaps.get("error", "không đọc được /metrics")
        },
        "burst_wall_clock_s": round(wall, 2),
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
                # Cấu hình có hiệu lực (biến môi trường hoặc mặc định trong Settings) và giới hạn của DB.
                "settings": json.loads(
                    subprocess.run(
                        [
                            "uv",
                            "run",
                            "python",
                            "-c",
                            "import json;from app.core.config import Settings;s=Settings();"
                            "print(json.dumps({k:getattr(s,k) for k in ('API_WORKERS','API_MAX_INFLIGHT',"
                            "'API_QUEUE_TIMEOUT_SEC','DB_POOL_SIZE','DB_MAX_OVERFLOW','DB_POOL_TIMEOUT_SEC')}))",
                        ],
                        cwd=BACKEND,
                        env=env,
                        capture_output=True,
                        text=True,
                    ).stdout
                    or "{}"
                ),
                "postgres_max_connections": max_connections,
                "pipeline_backend": "fake",
                "workers": 1,
                "api_workers": args.api_workers,
                "client_procs": args.client_procs,
            },
            indent=2,
        )
    )
    srv = summary["server"]

    def srv_row(label: str, s: dict) -> str:
        if not s.get("n"):
            return f"| {label} | 0 | | | | | |"
        span = lambda b: f"{b[0]} – {b[1] if b[1] is not None else '∞'}"  # noqa: E731
        return (
            f"| {label} | {s['n']} | {s['mean_s']} | {span(s['p50_in_s'])} | {span(s['p95_in_s'])} "
            f"| {s['le_1.5']} | {s['le_2.0']} |"
        )

    if "skipped" in srv:
        server_md = f"Không có số phía server: {srv['skipped']}."
    else:
        cs = summary["client_share_within"]["create"]
        server_md = "\n".join(
            [
                "| Loại | n | trung bình (s) | p50 trong khoảng (s) | p95 trong khoảng (s) | tỷ lệ ≤ 1,5 s | tỷ lệ ≤ 2,0 s |",
                "|---|---|---|---|---|---|---|",
                srv_row("upload, tổng thời gian ở app", srv["create"]),
                srv_row("poll, tổng thời gian ở app", srv["poll"]),
                srv_row("chờ admission (mọi request, không tách route)", srv["admission_wait"]),
                "",
                f"Phía client cùng lượt, upload: tỷ lệ ≤ 1,5 s = {cs['le_1.5']}, ≤ 2,0 s = {cs['le_2.0']}.",
                "Từ bucket chỉ biết quantile nằm trong khoảng; tỷ lệ dưới mốc 1,5 và 2,0 là chính xác vì đó là biên bucket.",
                "Thời gian ở app gồm chờ admission. Client trừ server là phần ngoài app: máy sinh tải, loopback, uvicorn trước middleware.",
            ]
        )

    md = f"""# Kết quả tải VT-018 ({args.clients} client đồng thời)

| Loại | n | p50 (s) | p95 (s) | max (s) |
|---|---|---|---|---|
| tạo cuộc họp (upload) | {summary["create"]["n"]} | {summary["create"]["p50_s"]} | {summary["create"]["p95_s"]} | {summary["create"]["max_s"]} |
| poll trạng thái job | {summary["poll"]["n"]} | {summary["poll"]["p50_s"]} | {summary["poll"]["p95_s"]} | {summary["poll"]["max_s"]} |
| **tất cả** | {summary["all_requests"]["n"]} | {summary["all_requests"]["p50_s"]} | **{summary["all_requests"]["p95_s"]}** | {summary["all_requests"]["max_s"]} |

Mục tiêu p95 ≤ {args.threshold} s: **{summary["verdict"]}**. Lỗi: {summary["errors"]} {summary["error_kinds"] or ""}. Từ lúc thả client tới khi xong: {summary["burst_wall_clock_s"]} s. Process sinh tải: {args.client_procs}.
Trạng thái meeting khi kết thúc: {statuses}.
Kết nối nằm rảnh từ lúc đăng nhập tới lúc upload: p50 {summary["idle_before_upload"]["p50_s"]} s, max {summary["idle_before_upload"]["max_s"]} s; {summary["idle_before_upload"]["over_uvicorn_keepalive_5s"]}/{summary["idle_before_upload"]["n"]} quá 5 s (timeout keep-alive mặc định của uvicorn). Lỗi upload chi tiết: `summary.json`, khóa `create_error_detail`.

## Phía server (`/metrics`, hiệu giữa lúc thả barrier và lúc mọi client xong)

{server_md}

## Giới hạn của phép đo

- Worker chạy mỗi lúc 1 job, hàng đợi dài dần trong lúc đo; đây là độ trễ của API, không phải thông lượng pipeline.
- Pipeline là fake, audio WAV im lặng 3 giây; chưa phản ánh tải của ASR/diarize thật.
- Client, API, worker và Postgres chung một máy ({os.cpu_count()} CPU), nên tranh chấp CPU làm số đo xấu hơn môi trường tách riêng.
- Client là thread Python ({args.client_procs} process, {-(-args.clients // args.client_procs)} thread mỗi process); số phía client gồm cả thời gian chờ GIL của máy sinh tải.
- Một lần chạy, chưa lặp để lấy khoảng tin cậy. Chi tiết máy ở `env.json`, từng request ở `raw.csv`.
"""
    (out / "summary.md").write_text(md)
    print(md)
    return 0 if summary["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
