"""Kiểm thử các kịch bản độ tin cậy hệ thống (Reliability Scenarios - BE-15).

Bao gồm 3 kịch bản trọng tâm:
1. Worker chết giữa chừng: reaper phát hiện lease timeout và thu hồi job đưa về 'queued'.
   Sau đó worker khác claim lại và xử lý thành công.
2. Retry cạn kiệt lượt: khi attempt >= max_attempts (job.can_retry is False),
   lỗi tạm thời hoặc lease timeout chuyển trạng thái dứt khoát sang 'failed'.
3. Tải lên trùng khóa (Idempotent replay): gửi 2 lần cùng một Idempotency-Key
   cho POST /meetings, hệ thống không tạo bản ghi trùng và trả về kết quả cũ
   kèm header Idempotent-Replayed: true.
"""

import io
import uuid
from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from meeting_pipeline.errors import ErrorCode, TransientPipelineError
from meeting_pipeline.schemas import Stage
from sqlalchemy import create_engine, func, select
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
from app.services.audio_validator import AudioProbeResult
from app.services.storage import Storage, get_storage
from app.services.storage.local import LocalStorage
from app.worker.queue import JobStatus
from app.worker.reaper import reap_expired_jobs
from app.worker.runner import run_worker_once


@pytest.fixture
def test_storage(tmp_path: Path) -> Storage:
    """Tạo storage tạm thời trên đĩa cho test."""
    return LocalStorage(base_dir=tmp_path)


@pytest.fixture
def test_db() -> Generator[Session, None, None]:
    """Tạo SQLite in-memory database cho test."""
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
    """Tạo tài khoản kiểm thử."""
    user = User(
        id=str(uuid.uuid4()),
        email="reliability_user@example.com",
        display_name="Reliability User",
        password_hash="hash_pw",
    )
    test_db.add(user)
    test_db.commit()
    return user


@pytest.fixture
def auth_headers(sample_user: User) -> dict[str, str]:
    """Tạo auth token Bearer cho người dùng."""
    token = create_access_token(sample_user.id)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def client(
    test_db: Session,
    test_storage: Storage,
    sample_user: User,
) -> Generator[TestClient, None, None]:
    """Khởi tạo TestClient với test_db và test_storage."""
    app = create_app()
    app.dependency_overrides[get_db] = lambda: test_db
    app.dependency_overrides[get_storage] = lambda: test_storage
    app.dependency_overrides[get_current_user] = lambda: sample_user
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_reliability_worker_crash_and_reaper_reclaims_job(
    test_db: Session,
    test_storage: Storage,
    sample_user: User,
) -> None:
    """Kịch bản 1: Worker chết giữa chừng, reaper lấy lại job và worker mới hoàn thành.

    - Job đang chạy bị chết (locked_by='worker-crashed-1', locked_until đã quá hạn).
    - Reaper chạy tại thời điểm hiện tại: phát hiện job hết hạn lease,
      đưa về 'queued', xóa lock, tăng attempt từ 1 lên 2.
    - Worker mới ('worker-healthy-2') tiếp quản job và xử lý thành công.
    """
    now = datetime.now(UTC)
    meeting = Meeting(
        id=str(uuid.uuid4()),
        owner_id=sample_user.id,
        title="Cuộc họp kiểm thử Reaper",
        status="processing",
        created_at=now - timedelta(minutes=5),
    )
    test_db.add(meeting)

    job = Job(
        id=str(uuid.uuid4()),
        meeting_id=meeting.id,
        status=JobStatus.RUNNING.value,
        stage="asr",
        stage_status={"preprocess": "succeeded", "vad": "succeeded", "asr": "running"},
        progress=0.33,
        attempt=1,
        max_attempts=3,
        locked_by="worker-crashed-1",
        locked_until=now - timedelta(seconds=10),  # Đã quá hạn 10s
        started_at=now - timedelta(minutes=2),
        created_at=now - timedelta(minutes=5),
        updated_at=now - timedelta(seconds=10),
    )
    test_db.add(job)
    test_db.commit()

    # 1. Reaper quét và thu hồi các job hết hạn lease
    reaped_jobs = reap_expired_jobs(test_db, now=now)
    assert len(reaped_jobs) == 1
    assert reaped_jobs[0].id == job.id

    # 2. Khẳng định trạng thái sau khi reaper thu hồi
    test_db.refresh(job)
    assert job.status == JobStatus.QUEUED.value
    assert job.locked_by is None
    assert job.locked_until is None
    assert job.attempt == 2  # Đã tăng lượt thử
    assert job.can_retry is True

    # 3. Giả lập audio trong storage để worker mới xử lý thành công
    test_storage.save_upload(
        meeting_id=meeting.id,
        extension="wav",
        stream=io.BytesIO(b"RIFF" + b"\x00" * 100),
    )

    # 4. Worker mới claim và hoàn thành job
    ran = run_worker_once(
        test_db,
        storage=test_storage,
        worker_id="worker-healthy-2",
        backend="fake",
    )
    assert ran is True

    test_db.refresh(job)
    assert job.status == JobStatus.SUCCEEDED.value
    assert job.progress == 1.0


def test_reliability_retry_exhaustion_transitions_to_failed(
    test_db: Session,
    test_storage: Storage,
    sample_user: User,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Kịch bản 2: Job retry hết lượt (attempt >= max_attempts) dứt khoát chuyển sang 'failed'.

    A. Worker gặp lỗi transient nhưng đã ở lần thử cuối:
       Chuyển sang 'failed', không còn lên lịch 'retry_scheduled'.
    B. Reaper gặp job hết lease mà attempt >= max_attempts:
       Chuyển sang 'failed' với mã lỗi 'LEASE_TIMEOUT'.
    """
    now = datetime.now(UTC)

    # Phân đoạn A: Worker gặp lỗi transient tại lần thử cuối cùng
    meeting_a = Meeting(
        id=str(uuid.uuid4()),
        owner_id=sample_user.id,
        title="Cuộc họp lỗi cạn kiệt retry",
        status="processing",
        created_at=now,
    )
    test_db.add(meeting_a)

    job_a = Job(
        id=str(uuid.uuid4()),
        meeting_id=meeting_a.id,
        status="queued",
        stage="asr",
        stage_status={"asr": "queued"},
        attempt=3,  # Đã là lần thử thứ 3
        max_attempts=3,  # Tối đa 3 lần
        created_at=now,
    )
    test_db.add(job_a)
    test_db.commit()

    assert job_a.can_retry is False

    # Giả lập pipeline ném lỗi TransientPipelineError (ví dụ OOM)
    def failing_pipeline(*args, **kwargs):
        raise TransientPipelineError(
            code=ErrorCode.OUT_OF_MEMORY,
            stage=Stage.ASR,
            message="GPU hết bộ nhớ VRAM",
        )

    monkeypatch.setattr("app.worker.runner.run_job", failing_pipeline)

    ran = run_worker_once(
        test_db,
        storage=test_storage,
        worker_id="worker-retry-exhaust-test",
        backend="fake",
    )
    assert ran is True

    test_db.refresh(job_a)
    test_db.refresh(meeting_a)
    assert job_a.status == "failed"
    assert job_a.error_code == "OUT_OF_MEMORY"
    assert meeting_a.status == "failed"

    # Phân đoạn B: Reaper thu hồi job đã cạn kiệt số lần thử
    meeting_b = Meeting(
        id=str(uuid.uuid4()),
        owner_id=sample_user.id,
        title="Cuộc họp treo cạn kiệt lượt",
        status="processing",
        created_at=now,
    )
    test_db.add(meeting_b)

    job_b = Job(
        id=str(uuid.uuid4()),
        meeting_id=meeting_b.id,
        status=JobStatus.RUNNING.value,
        stage="diarize",
        attempt=3,
        max_attempts=3,
        locked_by="worker-timed-out",
        locked_until=now - timedelta(seconds=30),  # Đã hết hạn
        created_at=now - timedelta(minutes=10),
    )
    test_db.add(job_b)
    test_db.commit()

    assert job_b.can_retry is False

    reaped = reap_expired_jobs(test_db, now=now)
    assert any(j.id == job_b.id for j in reaped)

    test_db.refresh(job_b)
    assert job_b.status == "failed"
    assert job_b.error_code == "LEASE_TIMEOUT"


def test_reliability_upload_duplicate_idempotency_key_replays_safely(
    client: TestClient,
    test_db: Session,
    auth_headers: dict[str, str],
) -> None:
    """Kịch bản 3: Tải lên trùng khóa Idempotency không tạo bản ghi dư thừa.

    - Gọi lần 1: POST /api/v1/meetings thành công (HTTP 201 Created).
    - Gọi lần 2: gửi lại chính xác với cùng Idempotency-Key.
    - Kết quả: trả về HTTP 201 Created, header Idempotent-Replayed: true,
      dữ liệu trả về đồng nhất, và DB duy trì đúng 1 bản ghi meeting và 1 job.
    """
    idem_key = f"IDEM-RELIABILITY-TEST-{uuid.uuid4()}"

    with patch("app.api.v1.meetings.probe_audio") as mock_probe:
        mock_probe.return_value = AudioProbeResult(
            duration_sec=12.0,
            sample_rate=16000,
            channels=1,
            format_name="wav",
        )
        fake_wav = b"RIFF" + b"\x00" * 150

        # Lần 1: Tạo mới cuộc họp với Idempotency-Key
        res1 = client.post(
            "/api/v1/meetings",
            files={"file": ("meeting.wav", fake_wav, "audio/wav")},
            data={"title": "Cuộc họp Idempotent 1", "consent_confirmed": "true"},
            headers={**auth_headers, "Idempotency-Key": idem_key},
        )
        assert res1.status_code == 201
        data1 = res1.json()
        meeting_id_1 = data1["meeting"]["id"]
        job_id_1 = data1["job"]["id"]

        # Lần 2: Gửi lại yêu cầu với cùng Idempotency-Key
        res2 = client.post(
            "/api/v1/meetings",
            files={"file": ("meeting.wav", fake_wav, "audio/wav")},
            data={"title": "Cuộc họp Idempotent 1", "consent_confirmed": "true"},
            headers={**auth_headers, "Idempotency-Key": idem_key},
        )
        assert res2.status_code == 201
        assert res2.headers.get("Idempotent-Replayed") == "true"
        data2 = res2.json()
        assert data2["meeting"]["id"] == meeting_id_1
        assert data2["job"]["id"] == job_id_1

    # Khẳng định số lượng bản ghi trong cơ sở dữ liệu: không bị nhân bản
    total_meetings = test_db.execute(select(func.count(Meeting.id))).scalar()
    total_jobs = test_db.execute(select(func.count(Job.id))).scalar()
    assert total_meetings == 1, f"Kỳ vọng 1 cuộc họp duy nhất nhưng có {total_meetings}!"
    assert total_jobs == 1, f"Kỳ vọng 1 job duy nhất nhưng có {total_jobs}!"
