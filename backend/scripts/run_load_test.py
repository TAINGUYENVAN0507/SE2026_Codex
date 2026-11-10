"""Mô phỏng VT-017 với dữ liệu cố định, barrier và oracle độc lập bằng Python."""

import argparse
import csv
import importlib.metadata
import json
import math
import os
import platform
import random
import tempfile
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from app.api.deps import get_current_user
from app.db.base import Base
from app.db.models.idempotency import IdempotencyKey
from app.db.models.job import Job
from app.db.models.meeting import Meeting
from app.db.models.transcript import Speaker
from app.db.models.user import User
from app.db.session import get_db
from app.main import create_app


def percentile(values, probability):
    """Phân vị nearest-rank, chỉ số ceil(n*p)-1, không nội suy."""
    if not values or not 0 < probability <= 1:
        raise ValueError("Cần mẫu và xác suất trong (0, 1].")
    return sorted(values)[math.ceil(len(values) * probability) - 1]


@contextmanager
def temporary_database(directory):
    """File tạm trong output, tránh quyền thư mục riêng của sandbox Windows."""
    with tempfile.NamedTemporaryFile(suffix=".db", dir=directory, delete=False) as stream:
        path = Path(stream.name)
    try:
        yield path
    finally:
        path.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("evidence/vt017/load/run1"))
    parser.add_argument("--pool", choices=["null", "queue"], default="null")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    fixed = datetime(2026, 11, 5, 12, tzinfo=UTC)
    owner = str(uuid.UUID(int=17017))
    rows = [
        {
            "id": str(uuid.UUID(int=i + 1)),
            "title": f"planning {i:03d}",
            "source": "recording" if i % 3 else "upload",
            "status": "ready" if i % 2 else "queued",
            "meeting_date": f"2026-11-{i % 28 + 1:02d}",
        }
        for i in range(200)
    ]
    queries = [
        {},
        {"page": 2},
        {"status": "ready"},
        {"source": "recording"},
        {"q": "  PLANNING  "},
        {"page_size": 100},
        {"sort_by": "title", "order": "asc"},
        {"from_date": "2026-11-05", "to_date": "2026-11-05"},
        {"source": "upload", "status": "ready", "page_size": 5},
        {"q": "missing"},
    ] * 10
    random.Random(17017).shuffle(queries)

    def expected(params):
        candidates = list(rows)
        for key in ["status", "source"]:
            if key in params:
                candidates = [row for row in candidates if row[key] == params[key]]
        if params.get("q", "").strip():
            q = params["q"].strip().lower()
            candidates = [row for row in candidates if q in row["title"].lower()]
        for key, predicate in [
            ("from_date", lambda a, b: a >= b),
            ("to_date", lambda a, b: a <= b),
        ]:
            if key in params:
                candidates = [
                    row for row in candidates if predicate(row["meeting_date"], params[key])
                ]
        column = params.get("sort_by", "created_at")
        candidates.sort(
            key=lambda row: (row.get(column, fixed.isoformat()), row["id"]),
            reverse=params.get("order", "desc") == "desc",
        )
        size = params.get("page_size", 10)
        offset = (params.get("page", 1) - 1) * size
        return len(candidates), [row["id"] for row in candidates[offset : offset + size]]

    with temporary_database(args.output) as database_path:
        engine = create_engine(
            f"sqlite:///{database_path}",
            connect_args={"check_same_thread": False},
            **({"poolclass": NullPool} if args.pool == "null" else {}),
        )
        actual_pool = type(engine.pool).__name__
        assert actual_pool == ("NullPool" if args.pool == "null" else "QueuePool")
        factory = sessionmaker(bind=engine, expire_on_commit=False)
        Base.metadata.create_all(
            engine,
            tables=[model.__table__ for model in [User, Meeting, Job, IdempotencyKey, Speaker]],
        )
        with factory() as db:
            db.add(
                User(
                    id=owner,
                    email="synthetic@example.com",
                    display_name="Synthetic",
                    password_hash="not-a-real-password",
                )
            )
            db.add_all(
                Meeting(**row, owner_id=owner, created_at=fixed, updated_at=fixed, version=1)
                for row in rows
            )
            db.commit()
        app = create_app()

        def database():
            with factory() as session:
                yield session

        def user():
            with factory() as session:
                return session.get(User, owner)

        app.dependency_overrides[get_db] = database
        app.dependency_overrides[get_current_user] = user
        barrier = threading.Barrier(100, timeout=30)
        lock = threading.Lock()
        state = {"active": 0, "peak_client_tasks": 0}
        with TestClient(app) as client:

            def request(index):
                params = queries[index]
                total, ids = expected(params)
                barrier.wait()
                with lock:
                    state["active"] += 1
                    state["peak_client_tasks"] = max(state["peak_client_tasks"], state["active"])
                start = time.perf_counter()
                status, correct, error = 0, False, ""
                try:
                    response = client.get("/api/v1/meetings", params=params)
                    status = response.status_code
                    data = response.json()
                    correct = (
                        status == 200
                        and data["total"] == total
                        and [item["id"] for item in data["items"]] == ids
                    )
                except Exception as exc:
                    error = type(exc).__name__
                finally:
                    duration = time.perf_counter() - start
                    with lock:
                        state["active"] -= 1
                return {
                    "task": index,
                    "query": json.dumps(params, sort_keys=True),
                    "status": status,
                    "oracle_ok": correct,
                    "latency_s": duration,
                    "error_type": error,
                }

            started = time.perf_counter()
            with ThreadPoolExecutor(max_workers=100) as pool:
                samples = list(pool.map(request, range(100)))
            elapsed = time.perf_counter() - started
        app.dependency_overrides.clear()
        engine.dispose()
    with (args.output / "raw.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(samples[0]))
        writer.writeheader()
        writer.writerows(samples)
    latencies = [sample["latency_s"] for sample in samples]
    summary = {
        "tasks": 100,
        "seed": 17017,
        "records": 200,
        "success": sum(sample["oracle_ok"] for sample in samples),
        "peak_client_tasks": state["peak_client_tasks"],
        "elapsed_s": elapsed,
        "p50_s": percentile(latencies, 0.5),
        "p95_s": percentile(latencies, 0.95),
        "p99_s": percentile(latencies, 0.99),
        "target_p95_s": 3.0,
    }
    summary["passed"] = summary["success"] == 100 and summary["p95_s"] <= 3
    environment = {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "logical_cpus": os.cpu_count(),
        "database": "SQLite file",
        "pool": args.pool,
        "actual_pool": actual_pool,
        "transport": "ASGI TestClient, no network",
        "auth": "dependency override",
        "packages": {
            name: importlib.metadata.version(name)
            for name in ["fastapi", "sqlalchemy", "httpx", "pydantic"]
        },
        "limits": "100 barrier tasks; peak measures client tasks, not server workers. "
        "No PostgreSQL, nginx, network, AI models or concurrent writes.",
    }
    for filename, data in [("summary.json", summary), ("env.json", environment)]:
        (args.output / filename).write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
