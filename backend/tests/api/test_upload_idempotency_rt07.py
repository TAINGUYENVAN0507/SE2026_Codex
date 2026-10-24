"""Kiểm thử RT-07: upload lặp lại cùng Idempotency-Key (BE-04).

Đảm bảo yêu cầu RT-07:
- Gửi tuần tự và song song cùng Idempotency-Key.
- Chỉ tạo duy nhất 1 meeting và 1 file trên đĩa.
- Mọi response thành công trả về dữ liệu giống nhau kèm header Idempotent-Replayed.
"""

import concurrent.futures
import io
import shutil
import uuid
from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.api.deps import get_current_user
from app.core.security import create_access_token
from app.db.base import Base
from app.db.models.idempotency import IdempotencyKey
from app.db.models.job import Job
from app.db.models.meeting import Meeting
from app.db.models.user import User
from app.db.session import get_db
from app.main import create_app
from app.services.audio_validator import AudioProbeResult
from app.services.storage import LocalStorage, get_storage


@pytest.fixture
def test_storage(tmp_path: Path) -> LocalStorage:
    """Tạo storage tạm thời cho test RT-07."""
    return LocalStorage(base_dir=tmp_path)


@pytest.fixture
def test_db_factory(tmp_path: Path) -> Generator[sessionmaker, None, None]:
    """Tạo sessionmaker kết nối file SQLite tạm thời hỗ trợ đa luồng an toàn."""
    db_file = tmp_path / "rt07_test.db"
    engine = create_engine(
        f"sqlite:///{db_file}",
        connect_args={"check_same_thread": False, "timeout": 30},
    )
    tables = [User.__table__, Meeting.__table__, Job.__table__, IdempotencyKey.__table__]
    Base.metadata.create_all(bind=engine, tables=tables)
    factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    try:
        yield factory
    finally:
        Base.metadata.drop_all(bind=engine, tables=tables)
        engine.dispose()


@pytest.fixture
def test_db(test_db_factory: sessionmaker) -> Generator[Session, None, None]:
    """Cung cấp database session cho test setup và kiểm tra kết quả."""
    session = test_db_factory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def auth_user(test_db: Session) -> User:
    """Tạo user kiểm thử trong database."""
    user = User(
        id=str(uuid.uuid4()),
        email="rt07_tester@example.com",
        display_name="Tester RT-07",
        password_hash="argon2_mock_hash",
    )
    test_db.add(user)
    test_db.commit()
    return user


@pytest.fixture
def client(
    test_db_factory: sessionmaker,
    test_storage: LocalStorage,
    auth_user: User,
) -> Generator[TestClient, None, None]:
    """Tạo client với dependency overrides, mỗi request nhận session riêng."""
    app = create_app()

    def _override_get_db() -> Generator[Session, None, None]:
        session = test_db_factory()
        try:
            yield session
        finally:
            session.close()

    def _override_get_storage() -> LocalStorage:
        return test_storage

    def _override_current_user() -> User:
        return auth_user

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_storage] = _override_get_storage
    app.dependency_overrides[get_current_user] = _override_current_user

    token = create_access_token(auth_user.id)
    with TestClient(app, cookies={"session_token": token}) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def mock_ffprobe_if_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    """Mock ffprobe nếu không có binary trên môi trường test."""
    if shutil.which("ffprobe") is None:

        def _mock_probe(file_path, timeout_sec=10.0, ffprobe_bin=None):
            return AudioProbeResult(
                duration_sec=95.0,
                format_name="wav",
                sample_rate=16000,
                channels=1,
            )

        monkeypatch.setattr("app.api.v1.meetings.probe_audio", _mock_probe)


def test_rt07_sequential_repeated_upload_with_same_key(
    client: TestClient,
    test_db: Session,
    test_storage: LocalStorage,
) -> None:
    """Kiểm tra upload lặp lại tuần tự với cùng Idempotency-Key."""
    idem_key = f"idem-rt07-seq-{uuid.uuid4()}"

    # Lần gửi 1: tạo meeting mới
    fake_audio_1 = io.BytesIO(b"RIFF" + b"\x00" * 128)
    files_1 = {"file": ("team_sync.wav", fake_audio_1, "audio/wav")}
    data_1 = {
        "title": "Họp Đồng Bộ Kỹ Thuật",
        "consent_confirmed": "true",
        "num_speakers": "2",
        "meeting_date": "2026-10-23",
    }
    headers = {"Idempotency-Key": idem_key}

    res_1 = client.post("/api/v1/meetings", data=data_1, files=files_1, headers=headers)
    assert res_1.status_code == 201
    assert res_1.headers.get("Idempotent-Replayed") is None
    body_1 = res_1.json()
    meeting_id = body_1["meeting"]["id"]
    job_id = body_1["job"]["id"]

    # Lần gửi 2: cùng Idempotency-Key
    fake_audio_2 = io.BytesIO(b"RIFF" + b"\x00" * 128)
    files_2 = {"file": ("team_sync_duplicate.wav", fake_audio_2, "audio/wav")}
    data_2 = {
        "title": "Họp Đồng Bộ Kỹ Thuật (Gửi lại)",
        "consent_confirmed": "true",
    }
    res_2 = client.post("/api/v1/meetings", data=data_2, files=files_2, headers=headers)
    assert res_2.status_code == 201
    assert res_2.headers.get("Idempotent-Replayed") == "true"
    body_2 = res_2.json()

    # Mọi response phải khớp nhau hoàn toàn
    assert body_2["meeting"]["id"] == meeting_id
    assert body_2["job"]["id"] == job_id
    assert body_2["meeting"]["title"] == body_1["meeting"]["title"]
    assert body_2 == body_1

    # Kiểm tra database chỉ có 1 meeting và 1 job
    meetings = test_db.execute(select(Meeting)).scalars().all()
    assert len(meetings) == 1
    assert meetings[0].id == meeting_id

    jobs = test_db.execute(select(Job)).scalars().all()
    assert len(jobs) == 1
    assert jobs[0].id == job_id

    # Kiểm tra chỉ có duy nhất 1 thư mục/file audio trên đĩa
    audio_dir = test_storage.base_dir / "audio"
    meeting_dirs = list(audio_dir.iterdir())
    assert len(meeting_dirs) == 1
    assert meeting_dirs[0].name == meeting_id
    assert (meeting_dirs[0] / "original.wav").is_file()


def test_rt07_concurrent_repeated_upload_with_same_key(
    client: TestClient,
    test_db: Session,
    test_storage: LocalStorage,
) -> None:
    """Kiểm tra upload lặp lại song song với cùng Idempotency-Key (2 luồng đồng thời)."""
    idem_key = f"idem-rt07-par-{uuid.uuid4()}"

    def send_upload(thread_idx: int):
        fake_audio = io.BytesIO(b"RIFF" + b"\x00" * 128)
        files = {"file": (f"concurrent_{thread_idx}.wav", fake_audio, "audio/wav")}
        data = {
            "title": f"Họp Song Song {thread_idx}",
            "consent_confirmed": "true",
        }
        headers = {"Idempotency-Key": idem_key}
        return client.post("/api/v1/meetings", data=data, files=files, headers=headers)

    # Chạy 2 luồng đồng thời
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        future_1 = executor.submit(send_upload, 1)
        future_2 = executor.submit(send_upload, 2)
        res_1 = future_1.result()
        res_2 = future_2.result()

    responses = [res_1, res_2]
    status_codes = [r.status_code for r in responses]

    # Ít nhất một request phải thành công tạo meeting (201)
    assert 201 in status_codes

    # Request thứ hai có thể là 201 (replayed) hoặc 409 (REQUEST_IN_PROGRESS)
    success_responses = [r for r in responses if r.status_code == 201]
    conflict_responses = [r for r in responses if r.status_code == 409]

    assert len(success_responses) + len(conflict_responses) == 2

    first_meeting_id = success_responses[0].json()["meeting"]["id"]

    if conflict_responses:
        # Nếu gặp 409, gửi lại request sau đó phải nhận kết quả 201 replayed
        retry_res = send_upload(3)
        assert retry_res.status_code == 201
        assert retry_res.headers.get("Idempotent-Replayed") == "true"
        assert retry_res.json()["meeting"]["id"] == first_meeting_id
    elif len(success_responses) == 2:
        # Cả hai đều 201: một cái là request gốc, một cái là replayed
        replayed_found = any(
            r.headers.get("Idempotent-Replayed") == "true" for r in success_responses
        )
        assert replayed_found
        assert (
            success_responses[0].json()["meeting"]["id"]
            == success_responses[1].json()["meeting"]["id"]
        )

    # Kiểm tra database chỉ có duy nhất 1 meeting và 1 job
    meetings = test_db.execute(select(Meeting)).scalars().all()
    assert len(meetings) == 1

    jobs = test_db.execute(select(Job)).scalars().all()
    assert len(jobs) == 1

    # Kiểm tra storage chỉ có duy nhất 1 thư mục meeting
    audio_dir = test_storage.base_dir / "audio"
    meeting_dirs = list(audio_dir.iterdir())
    assert len(meeting_dirs) == 1
    assert meeting_dirs[0].name == meetings[0].id
