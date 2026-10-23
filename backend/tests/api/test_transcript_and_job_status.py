"""Kiểm thử API đọc transcript và trạng thái job từ database (BE-05).

Bao gồm:
- GET /meetings/{id}/transcript khi pending trả về 200 OK kèm segments=[]
- GET /meetings/{id}/transcript khi ready trả về đầy đủ speakers và segments
- GET /meetings/{id}/transcript trả về 404 khi không tồn tại hoặc của user khác (PRIV-12)
- GET /jobs/{id} với các trạng thái khác nhau (queued, running, retry_scheduled, succeeded, failed)
- GET /jobs/{id} trả về 404 khi không tồn tại hoặc của user khác (PRIV-12)
"""

import uuid
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import get_current_user
from app.core.security import create_access_token
from app.db.base import Base
from app.db.models.idempotency import IdempotencyKey
from app.db.models.job import Job
from app.db.models.meeting import Meeting
from app.db.models.transcript import Segment, Speaker
from app.db.models.user import User
from app.db.session import get_db
from app.main import create_app


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
def user_a(test_db: Session) -> User:
    """Tạo User A."""
    user = User(
        id=str(uuid.uuid4()),
        email="user_transcript_a@example.com",
        display_name="User Transcript A",
        password_hash="mock_hash_a",
    )
    test_db.add(user)
    test_db.commit()
    return user


@pytest.fixture
def user_b(test_db: Session) -> User:
    """Tạo User B."""
    user = User(
        id=str(uuid.uuid4()),
        email="user_transcript_b@example.com",
        display_name="User Transcript B",
        password_hash="mock_hash_b",
    )
    test_db.add(user)
    test_db.commit()
    return user


@pytest.fixture
def client_a(test_db: Session, user_a: User) -> Generator[TestClient, None, None]:
    """TestClient xác thực với User A."""
    app = create_app()

    def _override_get_db() -> Generator[Session, None, None]:
        yield test_db

    def _override_current_user() -> User:
        return user_a

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_current_user] = _override_current_user

    token = create_access_token(user_a.id)
    with TestClient(app, cookies={"session_token": token}) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def client_b(test_db: Session, user_b: User) -> Generator[TestClient, None, None]:
    """TestClient xác thực với User B."""
    app = create_app()

    def _override_get_db() -> Generator[Session, None, None]:
        yield test_db

    def _override_current_user() -> User:
        return user_b

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_current_user] = _override_current_user

    token = create_access_token(user_b.id)
    with TestClient(app, cookies={"session_token": token}) as c:
        yield c
    app.dependency_overrides.clear()


def test_get_transcript_pending_returns_200_with_empty_segments(
    client_a: TestClient,
    test_db: Session,
    user_a: User,
) -> None:
    """Khi transcript chưa xong, API trả về 200 OK với status='pending' và segments=[]."""
    meeting = Meeting(
        id=str(uuid.uuid4()),
        owner_id=user_a.id,
        title="Cuộc họp đang xử lý",
        source="upload",
        status="queued",
        version=1,
    )
    test_db.add(meeting)
    test_db.commit()

    response = client_a.get(f"/api/v1/meetings/{meeting.id}/transcript")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "pending"
    assert data["diarization_status"] == "pending"
    assert data["segments"] == []
    assert data["speakers"] == []


def test_get_transcript_ready_returns_segments_and_speakers(
    client_a: TestClient,
    test_db: Session,
    user_a: User,
) -> None:
    """Khi transcript sẵn sàng, API trả về đầy đủ speakers và segments."""
    meeting_id = str(uuid.uuid4())
    meeting = Meeting(
        id=meeting_id,
        owner_id=user_a.id,
        title="Cuộc họp đã xong",
        source="upload",
        status="ready",
        version=1,
    )
    speaker_1 = Speaker(
        id=str(uuid.uuid4()),
        meeting_id=meeting_id,
        label="SPEAKER_00",
        default_name="Speaker 1",
        display_name="Nguyễn Văn A",
        version=1,
    )
    speaker_2 = Speaker(
        id=str(uuid.uuid4()),
        meeting_id=meeting_id,
        label="SPEAKER_01",
        default_name="Speaker 2",
        display_name="Trần Thị B",
        version=1,
    )
    seg_1 = Segment(
        id=str(uuid.uuid4()),
        meeting_id=meeting_id,
        idx=0,
        start_sec=0.0,
        end_sec=3.5,
        speaker_id=speaker_1.id,
        ai_speaker_id=speaker_1.id,
        text="Chào buổi sáng mọi người.",
        ai_text="Chào buổi sáng mọi người.",
        confidence=0.95,
        version=1,
    )
    seg_2 = Segment(
        id=str(uuid.uuid4()),
        meeting_id=meeting_id,
        idx=1,
        start_sec=3.6,
        end_sec=6.2,
        speaker_id=speaker_2.id,
        ai_speaker_id=speaker_2.id,
        text="Chào anh, chúng ta bắt đầu cuộc họp.",
        ai_text="Chào anh, chúng ta bắt đầu cuộc họp.",
        confidence=0.98,
        version=1,
    )
    test_db.add_all([meeting, speaker_1, speaker_2, seg_1, seg_2])
    test_db.commit()

    response = client_a.get(f"/api/v1/meetings/{meeting_id}/transcript")
    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "ready"
    assert data["diarization_status"] == "ok"
    assert len(data["speakers"]) == 2
    assert len(data["segments"]) == 2

    assert data["segments"][0]["text"] == "Chào buổi sáng mọi người."
    assert data["segments"][0]["index"] == 0
    assert data["segments"][0]["speaker_id"] == speaker_1.id

    assert data["segments"][1]["text"] == "Chào anh, chúng ta bắt đầu cuộc họp."
    assert data["segments"][1]["index"] == 1
    assert data["segments"][1]["speaker_id"] == speaker_2.id


def test_get_transcript_not_found_and_scoping_404(
    client_a: TestClient,
    client_b: TestClient,
    test_db: Session,
    user_a: User,
) -> None:
    """Truy cập transcript không tồn tại hoặc của user khác nhận 404 (PRIV-12)."""
    # 1. Không tồn tại
    res_404 = client_a.get(f"/api/v1/meetings/{uuid.uuid4()}/transcript")
    assert res_404.status_code == 404
    assert res_404.json()["error"]["code"] == "MEETING_NOT_FOUND"

    # 2. Thuộc user khác -> 404 không trả 403
    m_a = Meeting(
        id=str(uuid.uuid4()),
        owner_id=user_a.id,
        title="Cuộc họp của User A",
        source="upload",
        status="ready",
        version=1,
    )
    test_db.add(m_a)
    test_db.commit()

    res_user_b = client_b.get(f"/api/v1/meetings/{m_a.id}/transcript")
    assert res_user_b.status_code == 404
    assert res_user_b.status_code != 403
    assert res_user_b.json()["error"]["code"] == "MEETING_NOT_FOUND"


def test_get_job_statuses(client_a: TestClient, test_db: Session, user_a: User) -> None:
    """Kiểm tra đọc chi tiết Job ở các trạng thái khác nhau (queued, running, failed, ...)."""
    meeting = Meeting(
        id=str(uuid.uuid4()),
        owner_id=user_a.id,
        title="Cuộc họp test job",
        source="upload",
        status="processing",
        version=1,
    )
    job_running = Job(
        id=str(uuid.uuid4()),
        meeting_id=meeting.id,
        status="running",
        stage="asr",
        progress=0.45,
        stage_status={
            "preprocess": "succeeded",
            "vad": "succeeded",
            "asr": "running",
            "diarize": "queued",
            "merge": "queued",
            "summarize": "queued",
        },
        attempt=1,
        max_attempts=3,
    )
    job_failed = Job(
        id=str(uuid.uuid4()),
        meeting_id=meeting.id,
        status="failed",
        stage="diarize",
        progress=0.5,
        stage_status={
            "preprocess": "succeeded",
            "vad": "succeeded",
            "asr": "succeeded",
            "diarize": "failed",
            "merge": "queued",
            "summarize": "queued",
        },
        attempt=3,
        max_attempts=3,
        error_code="GPU_OUT_OF_MEMORY",
        error_message="Hết bộ nhớ VRAM trong quá trình diarization.",
    )
    test_db.add_all([meeting, job_running, job_failed])
    test_db.commit()

    # Kiểm tra job running
    res_run = client_a.get(f"/api/v1/jobs/{job_running.id}")
    assert res_run.status_code == 200
    data_run = res_run.json()
    assert data_run["id"] == job_running.id
    assert data_run["status"] == "running"
    assert data_run["stage"] == "asr"
    assert data_run["progress"] == 0.45
    assert data_run["error"] is None

    # Kiểm tra job failed có error envelope
    res_fail = client_a.get(f"/api/v1/jobs/{job_failed.id}")
    assert res_fail.status_code == 200
    data_fail = res_fail.json()
    assert data_fail["id"] == job_failed.id
    assert data_fail["status"] == "failed"
    assert data_fail["error"] is not None
    assert data_fail["error"]["code"] == "GPU_OUT_OF_MEMORY"
    assert data_fail["error"]["stage"] == "diarize"
    assert data_fail["error"]["retryable"] is False


def test_get_job_not_found_and_scoping_404(
    client_a: TestClient,
    client_b: TestClient,
    test_db: Session,
    user_a: User,
) -> None:
    """Truy cập job không tồn tại hoặc của user khác phải nhận 404 (PRIV-12)."""
    # 1. Không tồn tại -> 404
    res_404 = client_a.get(f"/api/v1/jobs/{uuid.uuid4()}")
    assert res_404.status_code == 404
    assert res_404.json()["error"]["code"] == "NOT_FOUND"

    # 2. Job liên kết với meeting của User A nhưng User B truy cập -> 404
    meeting_a = Meeting(
        id=str(uuid.uuid4()),
        owner_id=user_a.id,
        title="Meeting User A",
        source="upload",
        status="queued",
        version=1,
    )
    job_a = Job(
        id=str(uuid.uuid4()),
        meeting_id=meeting_a.id,
        status="queued",
        stage="preprocess",
        progress=0.0,
    )
    test_db.add_all([meeting_a, job_a])
    test_db.commit()

    res_user_b = client_b.get(f"/api/v1/jobs/{job_a.id}")
    assert res_user_b.status_code == 404
    assert res_user_b.status_code != 403
    assert res_user_b.json()["error"]["code"] == "NOT_FOUND"
