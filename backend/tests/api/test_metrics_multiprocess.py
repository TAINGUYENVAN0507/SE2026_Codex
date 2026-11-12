"""Kiểm thử multiprocess mode của /metrics khi chạy nhiều worker process (RE-018, BE-19).

Yêu cầu:
- Chạy 2 process, gửi N request (ví dụ 5 request mỗi process, tổng 10 request).
- Đọc /metrics nhiều lần (ở các process khác nhau hoặc process đọc riêng).
- Tổng http_requests_total phải bằng N (10) ở mọi lần đọc.
- api_inflight_requests sử dụng multiprocess_mode='livesum'.
"""

import contextlib
import multiprocessing as mp
import os
import shutil
import tempfile
import uuid

import pytest

from app.core.metrics import clean_multiproc_dir


def _worker_send_requests(
    multiproc_dir: str,
    db_file: str,
    num_requests: int,
    barrier,
    ready_event,
) -> None:
    """Worker process gửi num_requests tới endpoint để tăng metric."""
    os.environ["PROMETHEUS_MULTIPROC_DIR"] = multiproc_dir
    os.environ["DATABASE_URL"] = f"sqlite:///{db_file}"
    from fastapi.testclient import TestClient

    from app.main import create_app

    app = create_app()
    client = TestClient(app)

    # Đợi cả 2 worker sẵn sàng
    barrier.wait()

    for _ in range(num_requests):
        resp = client.get("/api/v1/config")
        assert resp.status_code == 200

    ready_event.set()


def _worker_record_stage_duration(multiproc_dir: str, stage: str, duration: float) -> None:
    """Subprocess giả lập worker ghi nhận số đo thời lượng stage."""
    os.environ["PROMETHEUS_MULTIPROC_DIR"] = multiproc_dir
    from app.core.metrics import PIPELINE_STAGE_DURATION_SECONDS

    PIPELINE_STAGE_DURATION_SECONDS.labels(stage=stage).observe(duration)


def _worker_scrape(multiproc_dir: str, db_file: str, q) -> None:
    """Scrape /metrics từ process độc lập và gửi kết quả qua Queue."""
    os.environ["PROMETHEUS_MULTIPROC_DIR"] = multiproc_dir
    os.environ["DATABASE_URL"] = f"sqlite:///{db_file}"
    from fastapi.testclient import TestClient

    from app.main import create_app

    app = create_app()
    client = TestClient(app)
    resp = client.get("/metrics")
    q.put((resp.status_code, resp.text))


def _scrape_metrics(multiproc_dir: str, db_file: str, ctx) -> str:
    """Scrape /metrics từ một process độc lập với multiproc_dir."""
    q = ctx.Queue()
    p = ctx.Process(target=_worker_scrape, args=(multiproc_dir, db_file, q))
    p.start()
    status_code, text = q.get(timeout=10)
    p.join(timeout=5)
    assert status_code == 200
    return text


def parse_http_requests_total(metrics_text: str, route: str = "/api/v1/config") -> float:
    """Trích xuất tổng số http_requests_total của route chỉ định."""
    total = 0.0
    for line in metrics_text.splitlines():
        if line.startswith("http_requests_total") and f'route="{route}"' in line:
            parts = line.rsplit(" ", 1)
            if len(parts) == 2:
                with contextlib.suppress(ValueError):
                    total += float(parts[1])
    return total


def test_clean_multiproc_dir():
    """Kiểm tra clean_multiproc_dir dọn sạch tệp .db."""
    tmp_dir = tempfile.mkdtemp(prefix="prom_clean_test_")
    try:
        test_file = os.path.join(tmp_dir, "counter_1234.db")
        with open(test_file, "w") as f:
            f.write("dummy")
        assert os.path.exists(test_file)
        clean_multiproc_dir(tmp_dir)
        assert not os.path.exists(test_file)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_metrics_multiprocess_aggregates_across_processes(
    monkeypatch: pytest.MonkeyPatch,
):
    """2 process mỗi process gửi 5 request. Tổng http_requests_total phải là 10 ở mọi lần scrape."""
    prom_dir = tempfile.mkdtemp(prefix="prom_multiproc_test_")
    db_dir = tempfile.mkdtemp(prefix="db_multiproc_test_")
    try:
        db_file = os.path.join(db_dir, "test.db").replace("\\", "/")
        monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_file}")
        from sqlalchemy import create_engine

        import app.db.models  # noqa: F401
        from app.db.base import Base

        eng = create_engine(f"sqlite:///{db_file}")
        Base.metadata.create_all(bind=eng)
        eng.dispose()

        ctx = mp.get_context("spawn")
        barrier = ctx.Barrier(2)
        ready1 = ctx.Event()
        ready2 = ctx.Event()

        monkeypatch.setenv("PROMETHEUS_MULTIPROC_DIR", prom_dir)

        p1 = ctx.Process(
            target=_worker_send_requests,
            args=(prom_dir, db_file, 5, barrier, ready1),
        )
        p2 = ctx.Process(
            target=_worker_send_requests,
            args=(prom_dir, db_file, 5, barrier, ready2),
        )

        p1.start()
        p2.start()

        assert ready1.wait(timeout=15), "Worker 1 không hoàn thành trong 15s"
        assert ready2.wait(timeout=15), "Worker 2 không hoàn thành trong 15s"

        p1.join(timeout=5)
        p2.join(timeout=5)

        # Scrape 3 lần, mỗi lần đọc phải thấy đủ 10 requests tổng cộng từ cả 2 process
        for attempt in range(1, 4):
            metrics_out = _scrape_metrics(prom_dir, db_file, ctx)
            total = parse_http_requests_total(metrics_out, route="/api/v1/config")
            assert total == 10.0, (
                f"Lần đọc {attempt}: mong đợi 10.0 request nhưng nhận được {total}"
            )
    finally:
        from app.core.config import get_settings

        get_settings.cache_clear()
        shutil.rmtree(prom_dir, ignore_errors=True)
        shutil.rmtree(db_dir, ignore_errors=True)


def test_worker_stage_durations_reach_api_metrics(monkeypatch: pytest.MonkeyPatch) -> None:
    """Subprocess đóng vai worker ghi pipeline_stage_duration_seconds vào thư mục chung;

    GET /metrics của API (cùng thư mục) phải có _count > 0 cho stage đó (RE-018, BE-19).
    """
    prom_dir = tempfile.mkdtemp(prefix="prom_worker_test_")
    db_dir = tempfile.mkdtemp(prefix="db_worker_test_")
    try:
        db_file = os.path.join(db_dir, "test.db").replace("\\", "/")
        monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_file}")
        monkeypatch.setenv("PROMETHEUS_MULTIPROC_DIR", prom_dir)

        from sqlalchemy import create_engine

        import app.db.models  # noqa: F401
        from app.db.base import Base

        eng = create_engine(f"sqlite:///{db_file}")
        Base.metadata.create_all(bind=eng)
        eng.dispose()

        ctx = mp.get_context("spawn")
        p = ctx.Process(
            target=_worker_record_stage_duration,
            args=(prom_dir, "transcribe", 1.85),
        )
        p.start()
        p.join(timeout=10)
        assert p.exitcode == 0

        # Scrape /metrics từ API (được chạy với cùng thư mục multiprocess)
        metrics_out = _scrape_metrics(prom_dir, db_file, ctx)
        assert "pipeline_stage_duration_seconds_count" in metrics_out

        found_count = False
        for line in metrics_out.splitlines():
            if (
                line.startswith("pipeline_stage_duration_seconds_count")
                and 'stage="transcribe"' in line
            ):
                parts = line.rsplit(" ", 1)
                if len(parts) == 2:
                    with contextlib.suppress(ValueError):
                        if float(parts[1]) > 0.0:
                            found_count = True
                            break
        assert found_count, (
            f"Không tìm thấy stage transcribe với count > 0 trong metrics:\n{metrics_out}"
        )
    finally:
        from app.core.config import get_settings

        get_settings.cache_clear()
        shutil.rmtree(prom_dir, ignore_errors=True)
        shutil.rmtree(db_dir, ignore_errors=True)


def test_db_backed_job_gauges_drop_groups_reaching_zero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Tạo 1 job failed, scrape thấy 1; xóa job, scrape lại phải thấy 0

    hoặc không còn dòng đó (BE-19).
    """
    prom_dir = tempfile.mkdtemp(prefix="prom_drop_zero_")
    db_dir = tempfile.mkdtemp(prefix="db_drop_zero_")
    try:
        db_file = os.path.join(db_dir, "test.db").replace("\\", "/")
        monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_file}")
        monkeypatch.setenv("PROMETHEUS_MULTIPROC_DIR", prom_dir)

        from sqlalchemy import create_engine
        from sqlalchemy.orm import Session

        import app.db.models  # noqa: F401
        from app.db.base import Base
        from app.db.models.job import Job
        from app.db.models.meeting import Meeting
        from app.db.models.user import User

        eng = create_engine(f"sqlite:///{db_file}")
        Base.metadata.create_all(bind=eng)

        uid = str(uuid.uuid4())
        mid = str(uuid.uuid4())
        jid = str(uuid.uuid4())

        with Session(eng) as s:
            u = User(
                id=uid,
                email="zero@example.local",
                display_name="Zero User",
                password_hash="h",
            )
            m = Meeting(
                id=mid,
                owner_id=u.id,
                title="Zero Meeting",
                source="upload",
                status="queued",
            )
            j = Job(
                id=jid,
                meeting_id=m.id,
                status="failed",
                stage="preprocess",
                error_code="AUDIO_INVALID",
            )
            s.add_all([u, m, j])
            s.commit()

        ctx = mp.get_context("spawn")
        metrics_1 = _scrape_metrics(prom_dir, db_file, ctx)
        assert 'jobs_failed_total{error_code="AUDIO_INVALID",stage="preprocess"} 1.0' in metrics_1

        # Xóa job failed khỏi database
        with Session(eng) as s:
            job_to_del = s.get(Job, jid)
            if job_to_del:
                s.delete(job_to_del)
                s.commit()

        # Scrape lại lần 2: nhóm ("preprocess", "AUDIO_INVALID") không được giữ số cũ 1.0
        metrics_2 = _scrape_metrics(prom_dir, db_file, ctx)
        assert (
            'jobs_failed_total{error_code="AUDIO_INVALID",stage="preprocess"} 1.0' not in metrics_2
        )
        # Phải thấy 0.0 hoặc không còn dòng đó
        for line in metrics_2.splitlines():
            if line.startswith("jobs_failed_total") and 'error_code="AUDIO_INVALID"' in line:
                assert line.endswith(" 0.0"), f"Mong đợi nhóm đã hết về 0.0 nhưng nhận: {line}"
    finally:
        from app.core.config import get_settings

        get_settings.cache_clear()
        shutil.rmtree(prom_dir, ignore_errors=True)
        shutil.rmtree(db_dir, ignore_errors=True)


def test_stopped_api_process_no_longer_counts_toward_inflight(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Tạo file gauge của một pid giả đã chết, gọi hàm dọn, rồi scrape không còn cộng số đó

    (BE-19).
    """
    prom_dir = tempfile.mkdtemp(prefix="prom_dead_proc_")
    db_dir = tempfile.mkdtemp(prefix="db_dead_proc_")
    try:
        db_file = os.path.join(db_dir, "test.db").replace("\\", "/")
        monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_file}")
        monkeypatch.setenv("PROMETHEUS_MULTIPROC_DIR", prom_dir)

        import json
        import time

        from prometheus_client.mmap_dict import MmapedDict
        from sqlalchemy import create_engine

        import app.db.models  # noqa: F401
        from app.core.metrics import mark_process_dead
        from app.db.base import Base

        eng = create_engine(f"sqlite:///{db_file}")
        Base.metadata.create_all(bind=eng)

        ctx = mp.get_context("spawn")

        # 1. Giả lập một process đã chết (PID 88888) để lại file gauge_livesum_88888.db
        fake_pid = 88888
        fake_gauge_file = os.path.join(prom_dir, f"gauge_livesum_{fake_pid}.db")
        m = MmapedDict(fake_gauge_file)
        key = json.dumps(["api_inflight_requests", "api_inflight_requests", {}, "help"])
        m.write_value(key, 7.0, time.time())
        m.close()

        # 2. Scrape trước khi dọn: thấy 7.0 từ fake_pid
        metrics_1 = _scrape_metrics(prom_dir, db_file, ctx)
        found_7 = any(
            line.strip() == "api_inflight_requests 7.0" for line in metrics_1.splitlines()
        )
        assert found_7, f"Mong đợi api_inflight_requests 7.0 nhưng nhận:\n{metrics_1}"

        # 3. Gọi hàm dọn mark_process_dead cho fake_pid
        mark_process_dead(fake_pid, path=prom_dir)

        # 4. Scrape lại sau khi dọn: fake_pid không còn được cộng vào
        metrics_2 = _scrape_metrics(prom_dir, db_file, ctx)
        found_7_after = any(
            line.strip() == "api_inflight_requests 7.0" for line in metrics_2.splitlines()
        )
        assert not found_7_after, f"api_inflight_requests vẫn chứa 7.0 sau khi dọn:\n{metrics_2}"
    finally:
        from app.core.config import get_settings

        get_settings.cache_clear()
        shutil.rmtree(prom_dir, ignore_errors=True)
        shutil.rmtree(db_dir, ignore_errors=True)


@pytest.mark.anyio
async def test_fastapi_lifespan_calls_mark_process_dead(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """FastAPI shutdown trong lifespan gọi mark_process_dead cho PID hiện tại (BE-19)."""
    from fastapi import FastAPI

    from app.main import lifespan

    called_with: list[int] = []
    monkeypatch.setenv("PROMETHEUS_MULTIPROC_DIR", "/tmp/fake_multiproc")
    monkeypatch.setattr("app.main.mark_process_dead", lambda pid: called_with.append(pid))

    app = FastAPI()
    async with lifespan(app):
        assert len(called_with) == 0

    assert called_with == [os.getpid()]
