"""Kiểm thử API POST /meetings/{id}/jobs chạy lại job (BE-13).

Bao gồm:
- Tạo job thành công với from_stage=None hoặc from_stage cụ thể
- RT-06: 5 request đồng thời -> đúng 1 job thành công (202), 4 request nhận 409 JOB_ALREADY_ACTIVE
- RT-10: Gửi lại với cùng Idempotency-Key nhận lại kết quả cũ (Idempotent-Replayed)
- 409 JOB_ALREADY_SUCCEEDED khi job đã thành công gửi lại cùng yêu cầu
- 409 HAS_USER_EDITS khi người dùng đã sửa transcript mà chạy lại từ ASR/diarize/đầu
- from_stage="summarize" vẫn được phép khi đã có user edits
- 409 JOB_ALREADY_ACTIVE khi có job đang active (queued, running, retry_scheduled)
- PRIV-12: 404 khi gọi trên meeting của người khác hoặc không tồn tại
- 401 khi chưa xác thực
"""

import concurrent.futures
import uuid
from collections.abc import Generator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import create_access_token
from app.db.base import Base
from app.db.models.edit_event import EditEvent
from app.db.models.idempotency import IdempotencyKey
from app.db.models.job import Job
from app.db.models.meeting import Meeting
from app.db.models.transcript import Segment, Speaker
from app.db.models.user import User
from app.db.session import get_db
from app.main import create_app
from app.schemas.job import JobOut


@pytest.fixture
def test_db() -> Generator[Session, None, None]:
    """Tạo database SQLite in-memory dùng cho test."""
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
def app_with_db(test_db: Session):
    """Tạo FastAPI application gắn kèm database test."""
    app = create_app()

    def _override_get_db() -> Generator[Session, None, None]:
        yield test_db

    app.dependency_overrides[get_db] = _override_get_db
    return app


@pytest.fixture
def users(test_db: Session) -> dict[str, User]:
    """Tạo user A (owner) và user B."""
    user_a = User(
        id=str(uuid.uuid4()),
        email="user_a@example.com",
        display_name="User A",
        password_hash="mock_hash_a",
    )
    user_b = User(
        id=str(uuid.uuid4()),
        email="user_b@example.com",
        display_name="User B",
        password_hash="mock_hash_b",
    )
    test_db.add_all([user_a, user_b])
    test_db.commit()
    return {"a": user_a, "b": user_b}


def create_auth_client(app, user: User | None) -> TestClient:
    """Tạo client kèm cookie xác thực nếu user được cung cấp."""
    client = TestClient(app)
    if user:
        token = create_access_token(user.id)
        client.cookies.set("session_token", token)
    return client


def test_create_job_success_all_stages(
    app_with_db, test_db: Session, users: dict[str, User]
) -> None:
    """Tạo job mới từ đầu (from_stage=None) trả về 202 ACCEPTED."""
    owner = users["a"]
    meeting = Meeting(
        id=str(uuid.uuid4()),
        owner_id=owner.id,
        title="Cuộc họp cần chạy lại",
        source="upload",
        status="failed",
        version=1,
    )
    test_db.add(meeting)
    test_db.commit()

    client = create_auth_client(app_with_db, owner)
    response = client.post(
        f"/api/v1/meetings/{meeting.id}/jobs",
        json={"from_stage": None},
    )
    assert response.status_code == 202

    data = response.json()
    job = JobOut.model_validate(data)
    assert job.meeting_id == meeting.id
    assert job.status == "queued"
    assert job.stage == "preprocess"
    assert job.from_stage is None
    assert job.progress == 0.0
    assert job.stages["preprocess"] == "queued"
    assert job.stages["summarize"] == "queued"

    test_db.refresh(meeting)
    assert meeting.status == "processing"


def test_create_job_from_summarize_success(
    app_with_db, test_db: Session, users: dict[str, User]
) -> None:
    """Tạo job từ stage summarize: các stage trước được đánh dấu succeeded."""
    owner = users["a"]
    meeting = Meeting(
        id=str(uuid.uuid4()),
        owner_id=owner.id,
        title="Cuộc họp tạo lại tóm tắt",
        source="upload",
        status="partial",
        version=1,
    )
    test_db.add(meeting)
    test_db.commit()

    client = create_auth_client(app_with_db, owner)
    response = client.post(
        f"/api/v1/meetings/{meeting.id}/jobs",
        json={"from_stage": "summarize"},
    )
    assert response.status_code == 202

    data = response.json()
    job = JobOut.model_validate(data)
    assert job.from_stage == "summarize"
    assert job.stage == "summarize"
    assert job.stages["preprocess"] == "succeeded"
    assert job.stages["asr"] == "succeeded"
    assert job.stages["merge"] == "succeeded"
    assert job.stages["summarize"] == "queued"
    assert job.progress > 0.0


def test_rt06_concurrent_retry_requests(tmp_path: Path, users: dict[str, User]) -> None:
    """RT-06: 5 request đồng thời gửi tới cùng meeting -> đúng 1 job active, 4 nhận 409."""
    owner = users["a"]
    meeting_id = str(uuid.uuid4())

    db_file = tmp_path / "rt06_test.db"
    engine = create_engine(
        f"sqlite:///{db_file}",
        connect_args={"check_same_thread": False, "timeout": 30},
    )
    with engine.connect() as conn:
        conn.exec_driver_sql("PRAGMA journal_mode=WAL")

    tables = [
        User.__table__,
        Meeting.__table__,
        Job.__table__,
        IdempotencyKey.__table__,
        Speaker.__table__,
        Segment.__table__,
        EditEvent.__table__,
    ]
    Base.metadata.create_all(bind=engine, tables=tables)
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    with session_factory() as s:
        s.add(
            User(id=owner.id, email=owner.email, display_name=owner.display_name, password_hash="h")
        )
        s.add(
            Meeting(
                id=meeting_id,
                owner_id=owner.id,
                title="Cuộc họp test đồng thời RT-06",
                source="upload",
                status="failed",
                version=1,
            )
        )
        s.commit()

    app = create_app()

    def _get_db_override():
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = _get_db_override

    def send_request(idx: int) -> tuple[int, dict]:
        client = create_auth_client(app, owner)
        res = client.post(
            f"/api/v1/meetings/{meeting_id}/jobs",
            json={"from_stage": None},
        )
        return res.status_code, res.json()

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(send_request, i) for i in range(5)]
        results = [f.result() for f in futures]

    statuses = [r[0] for r in results]
    assert statuses.count(202) == 1, f"Kỳ vọng đúng 1 request 202, nhận được: {statuses}"
    assert statuses.count(409) == 4, f"Kỳ vọng 4 request 409, nhận được: {statuses}"

    for st, body in results:
        if st == 409:
            assert body["error"]["code"] == "JOB_ALREADY_ACTIVE"
            assert "job" in body["error"]["details"]
            assert body["error"]["details"]["job"]["status"] == "queued"


def test_rt10_idempotency_replay_and_succeeded(
    app_with_db, test_db: Session, users: dict[str, User]
) -> None:
    """RT-10: Gửi lại với cùng Idempotency-Key nhận kết quả cũ; gửi mới sau khi xong nhận 409."""
    owner = users["a"]
    meeting = Meeting(
        id=str(uuid.uuid4()),
        owner_id=owner.id,
        title="Cuộc họp test RT-10",
        source="upload",
        status="failed",
        version=1,
    )
    test_db.add(meeting)
    test_db.commit()

    client = create_auth_client(app_with_db, owner)
    key = "rt10-idempotency-key-001"

    # 1. Gửi lần 1: thành công 202
    res1 = client.post(
        f"/api/v1/meetings/{meeting.id}/jobs",
        json={"from_stage": None},
        headers={"Idempotency-Key": key},
    )
    assert res1.status_code == 202
    job1_id = res1.json()["id"]

    # 2. Gửi lại với cùng key: nhận lại response cũ kèm header Idempotent-Replayed
    res2 = client.post(
        f"/api/v1/meetings/{meeting.id}/jobs",
        json={"from_stage": None},
        headers={"Idempotency-Key": key},
    )
    assert res2.status_code == 202
    assert res2.headers.get("Idempotent-Replayed") == "true"
    assert res2.json()["id"] == job1_id

    # 3. Giả lập job hoàn thành thành công trong DB
    job_in_db = test_db.execute(select(Job).where(Job.id == job1_id)).scalar_one()
    job_in_db.status = "succeeded"
    meeting_in_db = test_db.execute(select(Meeting).where(Meeting.id == meeting.id)).scalar_one()
    meeting_in_db.status = "ready"
    test_db.commit()

    # Dùng lại key cũ vẫn nhận lại response cũ
    res3 = client.post(
        f"/api/v1/meetings/{meeting.id}/jobs",
        json={"from_stage": None},
        headers={"Idempotency-Key": key},
    )
    assert res3.status_code == 202
    assert res3.headers.get("Idempotent-Replayed") == "true"

    # 4. Gửi yêu cầu mới khi đã thành công: 409 JOB_ALREADY_SUCCEEDED
    res4 = client.post(
        f"/api/v1/meetings/{meeting.id}/jobs",
        json={"from_stage": None},
        headers={"Idempotency-Key": "rt10-new-key"},
    )
    assert res4.status_code == 409
    assert res4.json()["error"]["code"] == "JOB_ALREADY_SUCCEEDED"


def test_job_conflict_when_user_has_edits(
    app_with_db, test_db: Session, users: dict[str, User]
) -> None:
    """Chạy lại từ đầu/ASR/diarize khi đã có chỉnh sửa transcript trả 409 HAS_USER_EDITS."""
    owner = users["a"]
    meeting = Meeting(
        id=str(uuid.uuid4()),
        owner_id=owner.id,
        title="Cuộc họp có chỉnh sửa transcript",
        source="upload",
        status="ready",
        version=1,
    )
    test_db.add(meeting)
    test_db.flush()

    # Thêm segment đã bị sửa text
    seg = Segment(
        id=str(uuid.uuid4()),
        meeting_id=meeting.id,
        idx=0,
        start_sec=0.0,
        end_sec=5.0,
        text="Văn bản đã sửa bởi người dùng",
        ai_text="Văn bản gốc từ AI",
        version=2,
    )
    test_db.add(seg)
    test_db.commit()

    client = create_auth_client(app_with_db, owner)

    # 1. Chạy lại toàn bộ (from_stage=None) -> 409 HAS_USER_EDITS
    res_none = client.post(
        f"/api/v1/meetings/{meeting.id}/jobs",
        json={"from_stage": None},
    )
    assert res_none.status_code == 409
    assert res_none.json()["error"]["code"] == "HAS_USER_EDITS"

    # 2. Chạy lại từ ASR -> 409 HAS_USER_EDITS
    res_asr = client.post(
        f"/api/v1/meetings/{meeting.id}/jobs",
        json={"from_stage": "asr"},
    )
    assert res_asr.status_code == 409
    assert res_asr.json()["error"]["code"] == "HAS_USER_EDITS"

    # 3. Chạy lại từ diarize -> 409 HAS_USER_EDITS
    res_diarize = client.post(
        f"/api/v1/meetings/{meeting.id}/jobs",
        json={"from_stage": "diarize"},
    )
    assert res_diarize.status_code == 409
    assert res_diarize.json()["error"]["code"] == "HAS_USER_EDITS"

    # 4. Chạy lại từ summarize -> ĐƯỢC PHÉP (202 ACCEPTED)
    res_summarize = client.post(
        f"/api/v1/meetings/{meeting.id}/jobs",
        json={"from_stage": "summarize"},
    )
    assert res_summarize.status_code == 202
    assert res_summarize.json()["from_stage"] == "summarize"


def test_job_conflict_already_active(app_with_db, test_db: Session, users: dict[str, User]) -> None:
    """Khi có job đang running/queued thì trả về 409 JOB_ALREADY_ACTIVE kèm job detail."""
    owner = users["a"]
    meeting = Meeting(
        id=str(uuid.uuid4()),
        owner_id=owner.id,
        title="Cuộc họp đang chạy job",
        source="upload",
        status="processing",
        version=1,
    )
    test_db.add(meeting)
    test_db.flush()

    active_job = Job(
        id=str(uuid.uuid4()),
        meeting_id=meeting.id,
        status="running",
        stage="asr",
        from_stage=None,
        progress=0.4,
        stage_status={"preprocess": "succeeded", "vad": "succeeded", "asr": "running"},
        attempt=1,
        max_attempts=3,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    test_db.add(active_job)
    test_db.commit()

    client = create_auth_client(app_with_db, owner)
    res = client.post(
        f"/api/v1/meetings/{meeting.id}/jobs",
        json={"from_stage": "summarize"},
    )
    assert res.status_code == 409
    data = res.json()
    assert data["error"]["code"] == "JOB_ALREADY_ACTIVE"
    assert data["error"]["details"]["job"]["id"] == active_job.id
    assert data["error"]["details"]["job"]["status"] == "running"


def test_retry_job_priv12_other_user_404(
    app_with_db, test_db: Session, users: dict[str, User]
) -> None:
    """PRIV-12: User B không thể tạo job trên meeting của User A -> 404."""
    user_a = users["a"]
    user_b = users["b"]

    meeting = Meeting(
        id=str(uuid.uuid4()),
        owner_id=user_a.id,
        title="Meeting riêng của A",
        source="upload",
        status="failed",
        version=1,
    )
    test_db.add(meeting)
    test_db.commit()

    client_b = create_auth_client(app_with_db, user_b)
    res = client_b.post(
        f"/api/v1/meetings/{meeting.id}/jobs",
        json={"from_stage": None},
    )
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "MEETING_NOT_FOUND"


def test_retry_job_unauthenticated_401(app_with_db) -> None:
    """Chưa xác thực trả về 401 UNAUTHENTICATED."""
    client = TestClient(app_with_db)
    res = client.post(
        f"/api/v1/meetings/{uuid.uuid4()}/jobs",
        json={"from_stage": None},
    )
    assert res.status_code == 401
    assert res.json()["error"]["code"] == "UNAUTHENTICATED"
