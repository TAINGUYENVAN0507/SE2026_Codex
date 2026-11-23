#!/usr/bin/env python3
# ruff: noqa: E501
"""Harness tải VT-018 (AI-19): N client đồng thời tạo cuộc họp rồi poll trạng thái job.

Chạy trong backend/:  uv run python scripts/load_vt018.py --db postgresql+psycopg://... --clients 40

Dựng DB trống bằng alembic, chạy API (uvicorn) và worker (fake pipeline) như hai process thật,
bắn N client cùng lúc (barrier), ghi latency từng request. Kết quả vào --out:
env.json (máy, phiên bản, tham số), raw.csv (từng request), summary.json và summary.md.

Harness đọc /metrics ngay trước khi thả barrier và sau khi mọi client xong; hiệu hai lần đọc cho
số phía server (tổng thời gian ở app, thời gian chờ admission) đặt cạnh số phía client. Mỗi lượt
đo có một PROMETHEUS_MULTIPROC_DIR trống riêng (như Compose từ #48), nên /metrics gộp đủ mọi
process API; summary.json đối chiếu số request server đếm được với số client đã gửi.

Giới hạn của phép đo (cũng được ghi vào summary.md):
- worker chạy MỖI LÚC 1 job nên hàng đợi tăng dần; harness đo độ trễ API, không đo thông lượng pipeline;
- pipeline là fake, audio là WAV im lặng 3 giây;
- client, API, worker và Postgres cùng một máy.

--server-cpus và --client-cpus (Linux) ghim API, worker và các process sinh tải vào hai tập CPU
riêng, để tách phần chậm do máy sinh tải tranh CPU với server. Postgres chạy ngoài harness nên
phải ghim riêng (taskset). summary.json ghi số CPU mà máy sinh tải thật sự dùng trong lúc đo.

--search K: sau upload, mỗi client gửi K lượt GET /api/v1/meetings?q=..., xoay vòng ba từ khóa
wildcard (%, _, 100%) và tiêu đề của chính client. Tiêu đề lượt đo là "Tải i" nên ba wildcard phải
ra total 0 và tiêu đề phải ra ít nhất 1; sai thì tính lỗi search_wrong (bắt lại lỗi #67 dưới tải).
Histogram phía server chỉ có nhãn route nên GET tìm kiếm gộp vào dòng upload phía server.

--storage temp (mặc định từ 11-23): API và worker ghi vào thư mục trống của lượt đo qua STORAGE_DIR
(app đọc biến này từ #70), không chạm backend/appdata. --storage real dùng backend/appdata như các
lượt trước 11-23 (thư mục đầy), để so với số cũ. summary.json ghi kiểu thư mục trong storage_cleanup.

Sau mỗi lượt, harness xóa audio/ và artifacts/ của các meeting lượt đó tạo (--keep-audio để giữ).
Trước 11-16 harness không dọn, nên thư mục lưu lớn dần qua các lượt (22.947 thư mục ngày 11-16).
"""

from __future__ import annotations

import argparse
import csv
import json
import multiprocessing as mp
import os
import platform
import re
import shutil
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
# Thư mục lưu mặc định của app (STORAGE_DIR trong app/core/config.py); --storage real dùng nó,
# test khóa hai đường dẫn bằng nhau.
STORAGE = BACKEND / "appdata"
PASSWORD = "LoadTest!2026"
LOGIN_CONCURRENCY = 8  # chia đều cho các process client
LOGIN_SLOTS = threading.Semaphore(LOGIN_CONCURRENCY)
EMAIL = "load@example.com"


def parse_cpus(spec: str | None) -> set[int] | None:
    """`"0-3,6-9"` thành {0, 1, 2, 3, 6, 7, 8, 9}. Rỗng thì None: không ghim."""
    if not spec:
        return None
    cpus: set[int] = set()
    for part in spec.split(","):
        lo, _, hi = part.strip().partition("-")
        a, b = int(lo), int(hi or lo)
        if a > b:
            raise ValueError(f"khoảng CPU ngược: {part}")
        cpus.update(range(a, b + 1))
    n = os.cpu_count() or 1
    if missing := sorted(c for c in cpus if c >= n):
        raise ValueError(f"CPU {missing} không có trên máy {n} CPU")
    return cpus


def check_disjoint(server: set[int] | None, client: set[int] | None) -> None:
    if server and client and server & client:
        raise ValueError(f"--server-cpus và --client-cpus trùng CPU {sorted(server & client)}")


def pin_to(cpus: set[int] | None):
    """preexec_fn cho Popen: process con, và mọi process nó sinh ra, chỉ chạy trên `cpus`."""
    if not cpus:
        return None
    return lambda: os.sched_setaffinity(0, cpus)


def api_log_stats(path: Path) -> dict[str, int]:
    """Đếm dòng stdout của API: dòng access của app, và dòng có query string (AD-018, BE-19).

    Dòng của app (`app.access`) là JSON có khóa `path`; dòng access mặc định của uvicorn có dạng
    `"GET /đường/dẫn HTTP/1.1"`. Cả hai kiểu đều không được mang `?` sau đường dẫn."""
    lines = app_access = uvicorn_access = with_query = 0
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not raw.strip():
            continue
        lines += 1
        is_app = False
        if raw.startswith("{"):
            try:
                rec = json.loads(raw)
            except ValueError:
                rec = {}
            if isinstance(rec, dict) and rec.get("message") == "HTTP request completed":
                app_access += 1
                is_app = True
                if "?" in str(rec.get("path", "")):
                    with_query += 1
        if not is_app and re.search(r'"(GET|POST|PUT|PATCH|DELETE) \S+ HTTP/', raw):
            uvicorn_access += 1
            if re.search(r'"(?:GET|POST|PUT|PATCH|DELETE) \S*\?\S* HTTP/', raw):
                with_query += 1
    return {
        "lines": lines,
        "app_access": app_access,
        "uvicorn_access": uvicorn_access,
        "with_query_string": with_query,
    }


def count_dirs(path: Path) -> int:
    """Số thư mục con trực tiếp của `path`; 0 nếu chưa có."""
    try:
        with os.scandir(path) as entries:
            return sum(1 for e in entries if e.is_dir(follow_symlinks=False))
    except FileNotFoundError:
        return 0


def storage_dir(mode: str, tmp: Path) -> Path:
    """Thư mục API và worker của lượt đo ghi vào: `temp` là thư mục trống trong `tmp` của lượt,
    `real` là backend/appdata (mặc định của app)."""
    if mode == "temp":
        return tmp / "storage"
    if mode == "real":
        return STORAGE
    raise ValueError(f"--storage phải là temp hoặc real: {mode!r}")


def server_env(base: dict, db: str, api_workers: int, prom_dir: Path, storage: Path) -> dict:
    """Biến môi trường cho API, worker, alembic. STORAGE_DIR luôn được đặt (ghi đè giá trị có
    sẵn), để API và worker ghi đúng thư mục harness đếm và dọn."""
    return {
        **base,
        "DATABASE_URL": db,
        "PIPELINE_BACKEND": "fake",
        "FAKE_SCENARIO": "ok",
        # Để kiểm tra ngân sách kết nối trong Settings áp dụng cho đúng số process được chạy.
        "API_WORKERS": str(api_workers),
        # Thư mục trống mỗi lượt: /metrics gộp mọi process API, không lẫn số của lượt trước.
        "PROMETHEUS_MULTIPROC_DIR": str(prom_dir),
        "STORAGE_DIR": str(storage),
    }


def remove_run_files(storage: Path, meeting_ids) -> int:
    """Xóa `audio/<id>` và `artifacts/<id>` của các meeting một lượt đo đã tạo; trả về số thư mục
    đã xóa. Kiểm mọi id trước khi xóa: id nào không đúng dạng UUID thì không xóa gì cả."""
    ids = [str(i) for i in meeting_ids]
    for i in ids:
        try:
            ok = str(uuid.UUID(i)) == i
        except ValueError:
            ok = False
        if not ok:
            raise ValueError(f"id meeting không phải UUID: {i!r}")
    removed = 0
    for i in ids:
        for sub in ("audio", "artifacts"):
            d = storage / sub / i
            if d.is_dir() and not d.is_symlink():
                shutil.rmtree(d)
                removed += 1
    return removed


def run_meeting_ids(db_url: str) -> list[str]:
    """Id các meeting trong DB của lượt đo. Harness tạo lại schema đầu mỗi lượt, nên đây đúng là
    các meeting lượt này tạo."""
    from sqlalchemy import create_engine, text

    engine = create_engine(db_url)
    try:
        with engine.connect() as conn:
            return [str(r[0]) for r in conn.execute(text("select id from meetings"))]
    finally:
        engine.dispose()


CLK_TCK = os.sysconf("SC_CLK_TCK") if hasattr(os, "sysconf") else 100
HAS_PROC = Path("/proc/self/stat").exists()


def stat_fields(text: str) -> list[str]:
    """Các trường của /proc/<pid>/stat sau tên process. Tên nằm trong ngoặc và có thể chứa dấu
    cách hoặc ')', nên tách sau dấu ')' cuối. Phần tử 0 là trường 3 (state) của proc(5)."""
    return text[text.rindex(")") + 2 :].split()


def stat_ticks(path: Path) -> int | None:
    """utime + stime (tick) của một process hoặc một luồng; None nếu nó đã thoát."""
    try:
        f = stat_fields(path.read_text())
    except (OSError, ValueError):
        return None
    return int(f[11]) + int(f[12])  # trường 14 và 15


def process_tree(root: int) -> list[tuple[int, int]]:
    """(pid, độ sâu) của `root` và mọi process con cháu, đọc từ /proc."""
    children: dict[int, list[int]] = {}
    for d in Path("/proc").iterdir():
        if d.name.isdigit():
            try:
                ppid = int(stat_fields((d / "stat").read_text())[1])
            except (OSError, ValueError):
                continue
            children.setdefault(ppid, []).append(int(d.name))
    out, todo = [], [(root, 0)]
    while todo:
        pid, depth = todo.pop()
        out.append((pid, depth))
        todo.extend((c, depth + 1) for c in children.get(pid, []))
    return sorted(out)


def cpu_snapshot(root: int) -> dict[int, dict]:
    """Tick CPU của từng process trong cây `root`: cả process (mọi luồng) và riêng luồng chính.
    Với uvicorn, luồng chính chạy event loop; endpoint `def` chạy ở threadpool, luồng khác."""
    snap = {}
    for pid, depth in process_tree(root):
        total = stat_ticks(Path(f"/proc/{pid}/stat"))
        main = stat_ticks(Path(f"/proc/{pid}/task/{pid}/stat"))
        try:
            comm = Path(f"/proc/{pid}/comm").read_text().strip()
        except OSError:
            continue
        if total is not None and main is not None:
            snap[pid] = {"comm": comm, "depth": depth, "total": total, "main": main}
    return snap


def cpu_busy(before: dict, after: dict, wall: float) -> list[dict]:
    """Số CPU trung bình mỗi process dùng giữa hai lần chụp (process có ở cả hai lần)."""
    wall = max(wall, 1e-9)
    return [
        {
            "comm": after[pid]["comm"],
            "depth": after[pid]["depth"],
            "process_cpus": round((after[pid]["total"] - before[pid]["total"]) / CLK_TCK / wall, 2),
            "main_thread_cpus": round(
                (after[pid]["main"] - before[pid]["main"]) / CLK_TCK / wall, 2
            ),
        }
        for pid in sorted(after)
        if pid in before
    ]


def make_wav(path: Path, seconds: int = 3) -> None:
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(b"\x00\x00" * 16000 * seconds)


def pct(values: list[float], q: float) -> float:
    s = sorted(values)
    return s[min(len(s) - 1, max(0, int(round(q * len(s) + 0.5)) - 1))] if s else float("nan")


def verdicts(rows, errors, threshold: float) -> dict:
    """Kết luận theo p95. `all` gộp upload và poll (khóa `verdict` từ trước, quyết định exit code);
    `upload` chỉ tính `POST /meetings`, là số các README dùng để kết luận. Ở 247 client, poll nhanh
    chiếm 5/6 số request, nên `all` có thể PASS khi p95 upload trên mốc (11-16, lượt p1-2)."""

    def one(kinds, failed: bool) -> str:
        ok = [d for k, st, d in rows if k in kinds and st < 400]
        return "PASS" if ok and not failed and pct(ok, 0.95) <= threshold else "FAIL"

    # Lỗi kết nối không có dòng trong `rows`, chỉ có trong `errors`; đăng nhập lỗi thì lượt bị hủy.
    upload_failed = any(k in ("create", "login") for k, _ in errors)
    return {"all": one(("create", "poll"), bool(errors)), "upload": one(("create",), upload_failed)}


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


# httpx mặc định giữ kết nối rảnh 5,0 s, bằng timeout keep-alive của uvicorn: dưới tải, server đóng
# đúng lúc client gửi upload thì ra RemoteProtocolError (6/6.669 upload ở 247 client, 2026-11-10).
# 1 s thì kết nối rảnh qua barrier hay qua khoảng poll 2 s đều được mở lại, giống đường thật:
# nginx dùng proxy_pass không có upstream keepalive nên không dùng lại kết nối tới uvicorn.
CLIENT_KEEPALIVE_EXPIRY_S = 1.0
# Tiêu đề lượt đo là "Tải i": không có %, _ nên các từ khóa này phải ra total 0 (BE-05, #67).
SEARCH_WILDCARDS = ("%", "_", "100%")


def search_terms(i: int, n: int) -> list[str]:
    """n từ khóa cho client i: xoay vòng ba wildcard và tiêu đề của chính client."""
    pool = (*SEARCH_WILDCARDS, f"Tải {i}")
    return [pool[(i + k) % len(pool)] for k in range(n)]


def search_ok(term: str, total: int) -> bool:
    """Wildcard phải khớp đúng ký tự (0 kết quả); tiêu đề của client phải ra chính nó (≥ 1)."""
    return total == 0 if term in SEARCH_WILDCARDS else total >= 1


def make_client(base: str) -> httpx.Client:
    return httpx.Client(
        base_url=base,
        timeout=120,
        limits=httpx.Limits(keepalive_expiry=CLIENT_KEEPALIVE_EXPIRY_S),
    )


def client_run(
    i,
    base,
    wav,
    ready,
    start,
    polls,
    interval,
    rows,
    errors,
    idle,
    detail,
    on_uploaded=None,
    searches=0,
):
    with make_client(base) as c:
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
        finally:
            if on_uploaded:
                on_uploaded()
        rows.append(("create", r.status_code, time.perf_counter() - t0))
        if r.status_code != 201:
            errors.append(("create", r.status_code))
            return
        job_id = r.json()["job"]["id"]
        for term in search_terms(i, searches):
            t0 = time.perf_counter()
            r = c.get("/api/v1/meetings", params={"q": term})
            rows.append(("search", r.status_code, time.perf_counter() - t0))
            if r.status_code != 200:
                errors.append(("search", r.status_code))
            elif not search_ok(term, r.json()["total"]):
                errors.append(("search_wrong", term))
        for _ in range(polls):
            time.sleep(interval)
            t0 = time.perf_counter()
            r = c.get(f"/api/v1/jobs/{job_id}")
            rows.append(("poll", r.status_code, time.perf_counter() - t0))
            if r.status_code != 200:
                errors.append(("poll", r.status_code))


def run_clients(
    ids, base, wav, polls, interval, on_ready, on_abort, on_uploads_done=None, searches=0
):
    """Chạy các client trong process hiện tại: đăng nhập hết, gọi on_ready (chặn tới lúc thả),
    rồi thả mọi thread cùng lúc. Trả về (rows, errors)."""
    rows: list = []
    errors: list = []
    idle: list = []
    detail: list = []
    ready = threading.Barrier(len(ids) + 1)
    start = threading.Event()
    pending = [len(ids)]
    lock = threading.Lock()
    uploads_done = threading.Event()

    def on_uploaded() -> None:
        with lock:
            pending[0] -= 1
            if pending[0] == 0:
                uploads_done.set()

    threads = [
        threading.Thread(
            target=client_run,
            args=(i, base, wav, ready, start, polls, interval, rows, errors, idle, detail),
            kwargs={"on_uploaded": on_uploaded, "searches": searches},
        )
        for i in ids
    ]
    [t.start() for t in threads]
    try:
        ready.wait()
        on_ready()
    except threading.BrokenBarrierError:
        on_abort()
        uploads_done.set()
    if not ids:
        uploads_done.set()
    start.set()
    # CPU time của cả process (mọi thread) chia cho wall = số CPU máy sinh tải dùng. Chỉ tính pha
    # upload (tới lúc upload cuối của process xong), vì pha poll phần lớn là ngủ.
    cpu0, wall0 = time.process_time(), time.perf_counter()
    uploads_done.wait(timeout=600)
    cpu = {"cpu_s": time.process_time() - cpu0, "wall_s": time.perf_counter() - wall0}
    if on_uploads_done:
        on_uploads_done()
    [t.join() for t in threads]
    return rows, errors, idle, detail, cpu


def child_main(
    ids,
    base,
    wav,
    polls,
    interval,
    login_slots,
    all_ready,
    go,
    results,
    cpus=None,
    uploaded=None,
    searches=0,
):
    """Một process client (--client-procs > 1): mọi process đăng nhập xong mới cùng được thả."""
    global LOGIN_SLOTS
    if cpus:
        os.sched_setaffinity(0, cpus)
    LOGIN_SLOTS = threading.Semaphore(login_slots)

    def on_ready() -> None:
        all_ready.wait()
        go.wait()

    results.put(
        run_clients(
            ids,
            base,
            wav,
            polls,
            interval,
            on_ready,
            all_ready.abort,
            uploaded and uploaded.set,
            searches,
        )
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True, help="URL Postgres của DB TRỐNG sẽ bị tạo lại schema")
    ap.add_argument("--clients", type=int, default=40)
    ap.add_argument("--polls", type=int, default=5)
    ap.add_argument("--interval", type=float, default=2.0)
    ap.add_argument(
        "--search",
        type=int,
        default=0,
        help="số lượt GET /meetings?q=... mỗi client gửi sau upload (wildcard và tiêu đề)",
    )
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
    ap.add_argument("--server-cpus", help="ghim API và worker, ví dụ 0-3,6-9 (Linux)")
    ap.add_argument("--client-cpus", help="ghim các process sinh tải, ví dụ 4,5,10,11 (Linux)")
    ap.add_argument(
        "--storage",
        choices=("temp", "real"),
        default="temp",
        help="temp: thư mục trống mỗi lượt (mặc định); real: backend/appdata như trước 11-23",
    )
    ap.add_argument(
        "--keep-audio",
        action="store_true",
        help="giữ audio/ và artifacts/ của các meeting lượt đo tạo (mặc định xóa sau lượt)",
    )
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    server_cpus = parse_cpus(args.server_cpus)
    client_cpus = parse_cpus(args.client_cpus)
    check_disjoint(server_cpus, client_cpus)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp())
    prom_dir = tmp / "prometheus"
    prom_dir.mkdir()
    storage = storage_dir(args.storage, tmp)
    storage.mkdir(parents=True, exist_ok=True)
    # Thư mục audio có sẵn lúc bắt đầu: ở 40 client, thư mục đầy chậm hơn thư mục rỗng (11-15).
    audio_dirs_at_start = count_dirs(storage / "audio")

    env = server_env(dict(os.environ), args.db, args.api_workers, prom_dir, storage)
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

    wav = tmp / "load.wav"
    make_wav(wav)
    base = f"http://127.0.0.1:{args.port}"
    api_log = tmp / "api.stdout"
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
        stdout=api_log.open("wb"),
        stderr=subprocess.STDOUT,
        preexec_fn=pin_to(server_cpus),
    )
    worker = subprocess.Popen(
        ["uv", "run", "python", "-m", "app.worker.runner"],
        cwd=BACKEND,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        preexec_fn=pin_to(server_cpus),
    )
    affinity = (
        {
            "api": sorted(os.sched_getaffinity(api.pid)),
            "worker": sorted(os.sched_getaffinity(worker.pid)),
        }
        if hasattr(os, "sched_getaffinity")
        else {}
    )
    try:
        wait_ready(base)
        snaps: dict = {}

        def before_release() -> None:
            # Sau mọi lượt đăng nhập, trước khi thả client.
            try:
                snaps["before"] = scrape(base)
            except httpx.HTTPError as e:
                snaps["error"] = type(e).__name__
            if HAS_PROC:
                snaps["cpu_before"] = {
                    "api": cpu_snapshot(api.pid),
                    "worker": cpu_snapshot(worker.pid),
                }
            snaps["t0"] = time.perf_counter()

        def after_uploads() -> None:
            # Upload cuối của mọi process sinh tải đã xong; pha poll sau đó phần lớn là ngủ.
            snaps["t_uploads"] = time.perf_counter()
            if HAS_PROC:
                snaps["cpu_after"] = {
                    "api": cpu_snapshot(api.pid),
                    "worker": cpu_snapshot(worker.pid),
                }

        ids = list(range(args.clients))
        if args.client_procs <= 1:
            if client_cpus:
                os.sched_setaffinity(0, client_cpus)
            rows, errors, idle, detail, cpu = run_clients(
                ids,
                base,
                wav,
                args.polls,
                args.interval,
                before_release,
                lambda: None,
                after_uploads,
                args.search,
            )
            client_cpu = [cpu]
        else:
            ctx = mp.get_context("spawn")
            all_ready = ctx.Barrier(args.client_procs + 1)
            go = ctx.Event()
            results = ctx.Queue()
            slots = max(1, LOGIN_CONCURRENCY // args.client_procs)
            uploaded = [ctx.Event() for _ in range(args.client_procs)]
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
                        client_cpus,
                        uploaded[k],
                        args.search,
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
            for event in uploaded:
                event.wait(timeout=600)
            after_uploads()
            rows, errors, idle, detail, client_cpu = [], [], [], [], []
            for _ in procs:
                r, e, i, d, cpu = results.get()
                rows += r
                errors += e
                idle += i
                detail += d
                client_cpu.append(cpu)
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

    # Worker đã dừng nên không còn ghi artifact. Lượt lỗi giữa chừng không tới đây và để lại file.
    storage_cleanup = {
        "storage": args.storage,
        "audio_dirs_at_start": audio_dirs_at_start,
        "kept": args.keep_audio,
    }
    if not args.keep_audio:
        meeting_ids = run_meeting_ids(args.db)
        storage_cleanup["meetings"] = len(meeting_ids)
        storage_cleanup["removed_dirs"] = remove_run_files(storage, meeting_ids)
    storage_cleanup["audio_dirs_at_end"] = count_dirs(storage / "audio")

    with (out / "raw.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["kind", "status", "latency_s"])
        w.writerows((k, s, f"{d:.4f}") for k, s, d in rows)

    by = {k: [d for kk, s, d in rows if kk == k and s < 400] for k in ("create", "poll", "search")}
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
        "search": {
            **stats(by["search"]),
            "per_client": args.search,
            "wrong_results": sum(1 for k, _ in errors if k == "search_wrong"),
        },
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
        else {"skipped": snaps.get("error", "không đọc được /metrics")},
        "burst_wall_clock_s": round(wall, 2),
        # Trung bình số CPU các process sinh tải dùng từ lúc thả tới upload cuối (không tính poll).
        "client_cpu": {
            "cpu_s": round(sum(c["cpu_s"] for c in client_cpu), 2),
            "wall_s": round(max(c["wall_s"] for c in client_cpu), 2),
            "cpus_busy": round(
                sum(c["cpu_s"] for c in client_cpu)
                / max(max(c["wall_s"] for c in client_cpu), 1e-9),
                2,
            ),
            "cpus_allowed": len(client_cpus) if client_cpus else os.cpu_count(),
        },
        "meeting_status_at_end": statuses,
        "storage_cleanup": storage_cleanup,
        # stdout của API không giữ lại (có request_id); chỉ giữ số đếm, để kiểm log dưới tải.
        "api_log": api_log_stats(api_log),
        # Số CPU từng process API và worker dùng từ lúc thả tới upload cuối; luồng chính của
        # process uvicorn là event loop, nên main_thread_cpus gần 1,0 là event loop đã bão hòa.
        "server_cpu": {
            "wall_s": round(snaps["t_uploads"] - snaps["t0"], 2),
            **{
                role: cpu_busy(
                    snaps["cpu_before"][role],
                    snaps["cpu_after"][role],
                    snaps["t_uploads"] - snaps["t0"],
                )
                for role in ("api", "worker")
            },
        }
        if "cpu_after" in snaps and "cpu_before" in snaps
        else {"skipped": "không có /proc (chỉ đo trên Linux)"},
        "verdict": verdicts(rows, errors, args.threshold)["all"],
        "verdict_upload": verdicts(rows, errors, args.threshold)["upload"],
    }
    if "skipped" not in summary["server"]:
        # Server đếm đủ request của mọi process thì hai số này bằng nhau (BE-19, #48).
        sent = {k: sum(1 for kk, _, _ in rows if kk == k) for k in ("create", "poll")}
        # Histogram chỉ có nhãn route: GET tìm kiếm cùng route /api/v1/meetings với upload.
        sent["create"] += sum(1 for kk, _, _ in rows if kk == "search")
        summary["server_count_vs_client"] = {
            k: {"server": summary["server"][k].get("n", 0), "client": sent[k]} for k in sent
        }
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2))
    (out / "env.json").write_text(
        json.dumps(
            {
                "date": time.strftime("%Y-%m-%d %H:%M:%S %z"),
                "python": sys.version.split()[0],
                "httpx": httpx.__version__,
                "client_keepalive_expiry_s": CLIENT_KEEPALIVE_EXPIRY_S,
                "prometheus_multiproc": True,
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
                "server_cpus": sorted(server_cpus) if server_cpus else None,
                "client_cpus": sorted(client_cpus) if client_cpus else None,
                "affinity_read_back": affinity,
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
                "Số request server đếm / client gửi: "
                + ", ".join(
                    f"{k} {v['server']}/{v['client']}"
                    for k, v in summary["server_count_vs_client"].items()
                )
                + f" ({args.api_workers} process API).",
            ]
        )

    sc = summary["server_cpu"]
    server_cpu_md = (
        "CPU phía server trong pha upload ({} s), process dùng ≥ 0,05 CPU: {}.".format(
            sc["wall_s"],
            "; ".join(
                f"{role} {r['comm']} cấp {r['depth']}: luồng chính {r['main_thread_cpus']}, "
                f"cả process {r['process_cpus']}"
                for role in ("api", "worker")
                for r in sc[role]
                if r["process_cpus"] >= 0.05
            )
            or "không có",
        )
        if "skipped" not in sc
        else f"CPU phía server: {sc['skipped']}."
    )
    md = f"""# Kết quả tải VT-018 ({args.clients} client đồng thời)

| Loại | n | p50 (s) | p95 (s) | max (s) |
|---|---|---|---|---|
| tạo cuộc họp (upload) | {summary["create"]["n"]} | {summary["create"]["p50_s"]} | {summary["create"]["p95_s"]} | {summary["create"]["max_s"]} |
| poll trạng thái job | {summary["poll"]["n"]} | {summary["poll"]["p50_s"]} | {summary["poll"]["p95_s"]} | {summary["poll"]["max_s"]} |
| tìm kiếm `?q=` | {summary["search"]["n"]} | {summary["search"]["p50_s"]} | {summary["search"]["p95_s"]} | {summary["search"]["max_s"]} |
| **tất cả** | {summary["all_requests"]["n"]} | {summary["all_requests"]["p50_s"]} | **{summary["all_requests"]["p95_s"]}** | {summary["all_requests"]["max_s"]} |

Mục tiêu p95 ≤ {args.threshold} s: upload **{summary["verdict_upload"]}** (p95 upload {summary["create"]["p95_s"]} s); mọi request gộp upload và poll **{summary["verdict"]}** (exit code theo số này). Lỗi: {summary["errors"]} {summary["error_kinds"] or ""}. Từ lúc thả client tới khi xong: {summary["burst_wall_clock_s"]} s. Process sinh tải: {args.client_procs}.
Trạng thái meeting khi kết thúc: {statuses}.
Máy sinh tải dùng trung bình {summary["client_cpu"]["cpus_busy"]} CPU trong pha upload (được dùng {summary["client_cpu"]["cpus_allowed"]}). Ghim CPU: server {args.server_cpus or "không"}, client {args.client_cpus or "không"}.

{server_cpu_md}

Tìm kiếm: {args.search} lượt mỗi client sau upload (wildcard `%`, `_`, `100%` và tiêu đề của client); kết quả sai: **{summary["search"]["wrong_results"]}**. Khi có tìm kiếm, dòng upload phía server gộp cả GET `/api/v1/meetings` (histogram chỉ có nhãn route). Dòng "tất cả" chỉ gộp upload và poll.

Stdout của API: {summary["api_log"]["lines"]} dòng, trong đó {summary["api_log"]["app_access"]} dòng access của app, {summary["api_log"]["uvicorn_access"]} dòng access của uvicorn; dòng có query string: **{summary["api_log"]["with_query_string"]}**.

Thư mục lưu ({"thư mục trống của lượt, STORAGE_DIR" if args.storage == "temp" else "`backend/appdata` thật"}) có {storage_cleanup["audio_dirs_at_start"]} thư mục lúc bắt đầu, {storage_cleanup["audio_dirs_at_end"]} lúc kết thúc ({"giữ file của lượt này" if args.keep_audio else f"đã xóa {storage_cleanup['removed_dirs']} thư mục audio và artifact của {storage_cleanup['meetings']} meeting lượt này tạo"}).
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
    # Thư mục tạm của lượt (WAV mẫu, /metrics, storage temp). Trước 11-23 không xóa, nên mỗi lượt
    # để lại một thư mục trong /tmp. --keep-audio với storage temp thì giữ để xem file.
    if args.keep_audio and args.storage == "temp":
        print(f"Giữ file của lượt đo trong {storage}", file=sys.stderr)
    else:
        shutil.rmtree(tmp, ignore_errors=True)
    return 0 if summary["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
