"""Kiểm thử Prometheus metrics endpoint /metrics và middleware đo lường (BE-19).

Bao gồm:
- Endpoint /metrics trả về dữ liệu chuẩn định dạng Prometheus với mã 200.
- PRIV-10 / An toàn dữ liệu: Tuyệt đối không chứa UUID hoặc thông tin cá nhân trong nhãn (labels).
- HTTP metrics ghi nhận route dạng template (/api/v1/meetings/{meeting_id}), không dùng ID cụ thể.
- Job metrics phản ánh chính xác trạng thái cơ sở dữ liệu (jobs_total,
  job_oldest_queued_seconds, jobs_failed_total).
"""

import re
import uuid
from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import get_current_user
from app.core.security import create_access_token
from app.db.base import Base
from app.db.models.action_item import ActionItem
from app.db.models.ai_output import AIOutput
from app.db.models.edit_event import EditEvent
from app.db.models.idempotency import IdempotencyKey
from app.db.models.job import Job
from app.db.models.meeting import Meeting
from app.db.models.summary import Summary
from app.db.models.transcript import Segment, Speaker
from app.db.models.user import User
from app.db.session import get_db
from app.main import create_app
from app.services.storage import Storage, get_storage
from app.services.storage.local import LocalStorage


@pytest.fixture
def test_storage(tmp_path: Path) -> Storage:
    """Tạo storage tạm thời cho test."""
    return LocalStorage(base_dir=tmp_path)


@pytest.fixture
def test_db() -> Generator[Session, None, None]:
    """Tạo database SQLite in-memory dùng chung cho test."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    tables = [
        User.__table__,
        Meeting.__table__,
        Job.__table__,
        IdempotencyKey.__table__,
        Speaker.__table__,
        Segment.__table__,
        AIOutput.__table__,
        Summary.__table__,
        ActionItem.__table__,
        EditEvent.__table__,
    ]
    Base.metadata.create_all(bind=engine, tables=tables)
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine, tables=tables)
        engine.dispose()


@pytest.fixture
def sample_user(test_db: Session) -> User:
    """Tạo user kiểm thử."""
    user = User(
        id=str(uuid.uuid4()),
        email="metrics_tester@example.com",
        display_name="Metrics Tester",
        password_hash="fakehash",
    )
    test_db.add(user)
    test_db.commit()
    return user


@pytest.fixture
def auth_headers(sample_user: User) -> dict[str, str]:
    """Tạo auth header cho user kiểm thử."""
    token = create_access_token(sample_user.id)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def client(
    test_db: Session,
    test_storage: Storage,
    sample_user: User,
) -> Generator[TestClient, None, None]:
    """Khởi tạo TestClient với database và storage giả định."""
    app = create_app()
    app.dependency_overrides[get_db] = lambda: test_db
    app.dependency_overrides[get_storage] = lambda: test_storage
    app.dependency_overrides[get_current_user] = lambda: sample_user
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def parse_prometheus_metrics(raw_text: str) -> dict[str, list[dict[str, str | float]]]:
    """Hỗ trợ phân tích cú pháp dữ liệu Prometheus text format thành dictionary."""
    metrics_data: dict[str, list[dict[str, str | float]]] = {}
    for line in raw_text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        # Format: metric_name{label1="val1",...} 123.45
        # Hoặc: metric_name 123.45
        match = re.match(r"^([a-zA-Z_:][a-zA-Z0-9_:]*)(?:\{(.*)\})?\s+([^\s]+)$", line)
        if not match:
            continue
        metric_name, labels_str, val_str = match.groups()
        labels: dict[str, str] = {}
        if labels_str:
            for pair in re.finditer(r'([a-zA-Z_0-9]+)="([^"]*)"', labels_str):
                labels[pair.group(1)] = pair.group(2)
        try:
            val = float(val_str)
        except ValueError:
            val = 0.0

        if metric_name not in metrics_data:
            metrics_data[metric_name] = []
        metrics_data[metric_name].append({"labels": labels, "value": val})
    return metrics_data


def test_metrics_endpoint_basic(client: TestClient) -> None:
    """Endpoint /metrics trả về HTTP 200 kèm Content-Type chuẩn của Prometheus."""
    res = client.get("/metrics")
    assert res.status_code == 200
    assert "text/plain" in res.headers["content-type"]

    data = res.text
    assert "http_requests_total" in data
    assert "http_request_duration_seconds" in data
    assert "jobs_total" in data
    assert "job_oldest_queued_seconds" in data


def test_metrics_no_uuids_in_output(
    client: TestClient,
    test_db: Session,
    sample_user: User,
    auth_headers: dict[str, str],
) -> None:
    """Kiểm tra PRIV-10: Tuyệt đối không có UUID xuất hiện trong nhãn metric hoặc dữ liệu."""
    meeting_uuid = str(uuid.uuid4())
    meeting = Meeting(
        id=meeting_uuid,
        owner_id=sample_user.id,
        title="Cuộc họp kiểm thử metric UUID",
        source="upload",
        status="ready",
    )
    job_uuid = str(uuid.uuid4())
    job = Job(
        id=job_uuid,
        meeting_id=meeting_uuid,
        status="queued",
        stage="preprocess",
        created_at=datetime.now(UTC),
    )
    test_db.add(meeting)
    test_db.add(job)
    test_db.commit()

    # Thực hiện request gọi vào meeting chi tiết chứa UUID
    res_api = client.get(f"/api/v1/meetings/{meeting_uuid}", headers=auth_headers)
    assert res_api.status_code == 200

    # Lấy metrics
    res_metrics = client.get("/metrics")
    assert res_metrics.status_code == 200
    output = res_metrics.text

    # Đảm bảo meeting_uuid và job_uuid không có trong output metrics
    assert meeting_uuid not in output, f"Meeting UUID {meeting_uuid} bị rò rỉ vào /metrics!"
    assert job_uuid not in output, f"Job UUID {job_uuid} bị rò rỉ vào /metrics!"

    # Kiểm tra nhãn route được chuẩn hóa dạng template
    parsed = parse_prometheus_metrics(output)
    http_samples = parsed.get("http_requests_total", [])
    routes_recorded = [
        sample["labels"].get("route")
        for sample in http_samples
        if isinstance(sample["labels"], dict)
    ]
    assert "/api/v1/meetings/{meeting_id}" in routes_recorded


def test_metrics_job_counts_match_db_state(
    client: TestClient,
    test_db: Session,
    sample_user: User,
) -> None:
    """Số liệu jobs_total, job_oldest_queued_seconds và jobs_failed_total khớp chính xác DB."""
    now = datetime.now(UTC)

    def create_test_meeting() -> Meeting:
        m = Meeting(
            id=str(uuid.uuid4()),
            owner_id=sample_user.id,
            title="Cuộc họp test",
            source="upload",
            status="processing",
        )
        test_db.add(m)
        test_db.flush()
        return m

    # 1. Hai job queued trên 2 meeting riêng biệt: 1 tạo cách đây 10 phút, 1 tạo cách đây 2 phút
    m1 = create_test_meeting()
    m2 = create_test_meeting()
    old_time = now - timedelta(minutes=10)
    recent_time = now - timedelta(minutes=2)
    job_queued_old = Job(
        id=str(uuid.uuid4()),
        meeting_id=m1.id,
        status="queued",
        stage="preprocess",
        created_at=old_time,
    )
    job_queued_recent = Job(
        id=str(uuid.uuid4()),
        meeting_id=m2.id,
        status="queued",
        stage="preprocess",
        created_at=recent_time,
    )

    # 2. Một job running trên meeting thứ 3
    m3 = create_test_meeting()
    job_running = Job(
        id=str(uuid.uuid4()),
        meeting_id=m3.id,
        status="running",
        stage="asr",
        created_at=now,
    )

    # 3. Một job failed ở diarize với DIARIZATION_FAILED
    m4 = create_test_meeting()
    job_failed_diarize = Job(
        id=str(uuid.uuid4()),
        meeting_id=m4.id,
        status="failed",
        stage="diarize",
        error_code="DIARIZATION_FAILED",
        created_at=now,
    )

    # 4. Hai job failed ở preprocess với AUDIO_INVALID
    m5 = create_test_meeting()
    m6 = create_test_meeting()
    job_failed_audio1 = Job(
        id=str(uuid.uuid4()),
        meeting_id=m5.id,
        status="failed",
        stage="preprocess",
        error_code="AUDIO_INVALID",
        created_at=now,
    )
    job_failed_audio2 = Job(
        id=str(uuid.uuid4()),
        meeting_id=m6.id,
        status="failed",
        stage="preprocess",
        error_code="AUDIO_INVALID",
        created_at=now,
    )

    test_db.add_all(
        [
            job_queued_old,
            job_queued_recent,
            job_running,
            job_failed_diarize,
            job_failed_audio1,
            job_failed_audio2,
        ]
    )
    test_db.commit()

    # Scrape metrics
    res = client.get("/metrics")
    assert res.status_code == 200
    parsed = parse_prometheus_metrics(res.text)

    # Kiểm tra jobs_total
    jobs_total_samples = parsed.get("jobs_total", [])
    status_map = {
        sample["labels"]["status"]: sample["value"]
        for sample in jobs_total_samples
        if isinstance(sample["labels"], dict) and "status" in sample["labels"]
    }

    assert status_map.get("queued") == 2.0
    assert status_map.get("running") == 1.0
    assert status_map.get("failed") == 3.0
    assert status_map.get("succeeded") == 0.0

    # Kiểm tra job_oldest_queued_seconds: khoảng 600 giây (10 phút)
    oldest_samples = parsed.get("job_oldest_queued_seconds", [])
    assert len(oldest_samples) == 1
    assert 590.0 <= oldest_samples[0]["value"] <= 650.0

    # Kiểm tra jobs_failed_total
    failed_samples = parsed.get("jobs_failed_total", [])
    failed_map = {
        (sample["labels"].get("stage"), sample["labels"].get("error_code")): sample["value"]
        for sample in failed_samples
        if isinstance(sample["labels"], dict)
    }

    assert failed_map.get(("diarize", "DIARIZATION_FAILED")) == 1.0
    assert failed_map.get(("preprocess", "AUDIO_INVALID")) == 2.0
