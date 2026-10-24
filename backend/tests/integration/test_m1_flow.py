"""Kiểm thử tích hợp luồng M1 từ upload tới transcript (M1).

Luồng bao gồm:
1. Đăng nhập qua POST /api/v1/auth/login nhận cookie HttpOnly.
2. Tải lên tệp âm thanh wav qua POST /api/v1/meetings kèm Idempotency-Key và consent.
3. Worker nhận job, chạy fake pipeline qua tất cả các stage.
4. Tra cứu GET /api/v1/jobs/{id} thấy trạng thái succeeded và progress 1.0.
5. Tra cứu GET /api/v1/meetings/{id}/transcript trả về dữ liệu transcript ready khớp với fixture.
"""

import io
import shutil
import uuid
from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import hash_password
from app.db.base import Base
from app.db.models.action_item import ActionItem
from app.db.models.ai_output import AIOutput
from app.db.models.idempotency import IdempotencyKey
from app.db.models.job import Job
from app.db.models.meeting import Meeting
from app.db.models.summary import Summary
from app.db.models.transcript import Segment, Speaker
from app.db.models.user import User
from app.db.session import get_db
from app.main import create_app
from app.services.audio_validator import AudioProbeResult
from app.services.storage import LocalStorage, get_storage
from app.worker.runner import run_worker_once


@pytest.fixture(autouse=True)
def mock_ffprobe_if_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tự động mock probe_audio nếu môi trường test không có sẵn ffprobe binary."""
    if shutil.which("ffprobe") is None:

        def _mock_probe(file_path, timeout_sec=10.0, ffprobe_bin=None):
            return AudioProbeResult(
                duration_sec=30.0,
                format_name="wav",
                sample_rate=16000,
                channels=1,
            )

        monkeypatch.setattr("app.api.v1.meetings.probe_audio", _mock_probe)


def test_m1_full_flow_upload_to_transcript(
    db_session: Session,
    tmp_path: Path,
) -> None:
    """Kiểm thử trọn vẹn luồng M1 trên cơ sở dữ liệu PostgreSQL."""
    test_storage = LocalStorage(base_dir=tmp_path)

    # 1. Khởi tạo người dùng thử nghiệm
    user_id = str(uuid.uuid4())
    raw_password = "M1Password!2026"
    test_user = User(
        id=user_id,
        email="m1_user@example.com",
        display_name="M1 Test User",
        password_hash=hash_password(raw_password),
    )
    db_session.add(test_user)
    db_session.commit()

    # 2. Cấu hình TestClient ghi đè get_db và get_storage
    app = create_app()

    def _override_get_db():
        yield db_session

    def _override_get_storage():
        return test_storage

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_storage] = _override_get_storage

    with TestClient(app) as client:
        # 3. Đăng nhập lấy session cookie
        login_res = client.post(
            "/api/v1/auth/login",
            json={"email": "m1_user@example.com", "password": raw_password},
        )
        assert login_res.status_code == 200, login_res.text
        cookies = login_res.cookies

        # 4. Tải lên tệp âm thanh wav
        fake_wav = io.BytesIO(b"RIFF" + b"\x00" * 400)
        files = {"file": ("meeting_m1.wav", fake_wav, "audio/wav")}
        data = {
            "title": "Cuộc họp Đánh giá Mốc M1",
            "consent_confirmed": "true",
            "meeting_date": "2026-10-24",
        }
        idem_key = str(uuid.uuid4())
        upload_res = client.post(
            "/api/v1/meetings",
            data=data,
            files=files,
            headers={"Idempotency-Key": idem_key},
            cookies=cookies,
        )
        assert upload_res.status_code == 201, upload_res.text
        upload_data = upload_res.json()
        meeting_id = upload_data["meeting"]["id"]
        job_id = upload_data["job"]["id"]

        assert upload_data["meeting"]["status"] == "queued"
        assert upload_data["job"]["status"] == "queued"

        # 5. Worker thực thi xử lý qua fake pipeline
        ran = run_worker_once(
            db_session,
            storage=test_storage,
            worker_id="m1-worker-runner",
            backend="fake",
        )
        assert ran is True

        # 6. Kiểm tra trạng thái job qua GET /jobs/{id}
        job_res = client.get(f"/api/v1/jobs/{job_id}", cookies=cookies)
        assert job_res.status_code == 200, job_res.text
        job_data = job_res.json()
        assert job_data["status"] == "succeeded"
        assert job_data["progress"] == 1.0

        # 7. Kiểm tra trạng thái transcript qua GET /meetings/{id}/transcript
        transcript_res = client.get(
            f"/api/v1/meetings/{meeting_id}/transcript",
            cookies=cookies,
        )
        assert transcript_res.status_code == 200, transcript_res.text
        transcript_data = transcript_res.json()
        assert transcript_data["status"] == "ready"
        assert len(transcript_data["speakers"]) >= 2
        assert len(transcript_data["segments"]) >= 2

        # Phân đoạn đầu tiên khớp với fixture transcript
        first_segment = transcript_data["segments"][0]
        assert "Chào mọi người" in first_segment["text"]
        assert first_segment["start_sec"] == 0.5
        assert first_segment["end_sec"] == 5.8


def test_m1_full_flow_sqlite(tmp_path: Path) -> None:
    """Kiểm thử trọn vẹn luồng M1 trên SQLite in-memory chạy cục bộ không cần Postgres."""
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
        AIOutput.__table__,
        Speaker.__table__,
        Segment.__table__,
        Summary.__table__,
        ActionItem.__table__,
    ]
    Base.metadata.create_all(bind=engine, tables=tables)
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = session_factory()

    test_storage = LocalStorage(base_dir=tmp_path)

    try:
        user_id = str(uuid.uuid4())
        raw_password = "M1Password!2026"
        test_user = User(
            id=user_id,
            email="m1_sqlite_user@example.com",
            display_name="M1 SQLite User",
            password_hash=hash_password(raw_password),
        )
        session.add(test_user)
        session.commit()

        app = create_app()

        def _override_get_db() -> Generator[Session, None, None]:
            yield session

        def _override_get_storage() -> LocalStorage:
            return test_storage

        app.dependency_overrides[get_db] = _override_get_db
        app.dependency_overrides[get_storage] = _override_get_storage

        with TestClient(app) as client:
            login_res = client.post(
                "/api/v1/auth/login",
                json={"email": "m1_sqlite_user@example.com", "password": raw_password},
            )
            assert login_res.status_code == 200, login_res.text
            cookies = login_res.cookies

            fake_wav = io.BytesIO(b"RIFF" + b"\x00" * 400)
            files = {"file": ("meeting_m1_sqlite.wav", fake_wav, "audio/wav")}
            data = {
                "title": "Cuộc họp Đánh giá Mốc M1 SQLite",
                "consent_confirmed": "true",
                "meeting_date": "2026-10-24",
            }
            idem_key = str(uuid.uuid4())
            upload_res = client.post(
                "/api/v1/meetings",
                data=data,
                files=files,
                headers={"Idempotency-Key": idem_key},
                cookies=cookies,
            )
            assert upload_res.status_code == 201, upload_res.text
            upload_data = upload_res.json()
            meeting_id = upload_data["meeting"]["id"]
            job_id = upload_data["job"]["id"]

            ran = run_worker_once(
                session,
                storage=test_storage,
                worker_id="m1-worker-sqlite",
                backend="fake",
            )
            assert ran is True

            job_res = client.get(f"/api/v1/jobs/{job_id}", cookies=cookies)
            assert job_res.status_code == 200, job_res.text
            assert job_res.json()["status"] == "succeeded"
            assert job_res.json()["progress"] == 1.0

            transcript_res = client.get(
                f"/api/v1/meetings/{meeting_id}/transcript",
                cookies=cookies,
            )
            assert transcript_res.status_code == 200, transcript_res.text
            transcript_data = transcript_res.json()
            assert transcript_data["status"] == "ready"
            assert len(transcript_data["speakers"]) >= 2
            assert len(transcript_data["segments"]) >= 2
            assert "Chào mọi người" in transcript_data["segments"][0]["text"]
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine, tables=tables)
        engine.dispose()
