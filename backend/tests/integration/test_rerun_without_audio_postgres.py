"""Chạy lại xử lý khi audio không còn thì transcript phải còn đọc được (BE-10, BE-16, PRIV).

Trên PostgreSQL ngày 2026-11-28: cuộc họp `ready` có audio đã hết hạn, gọi
`POST /meetings/{id}/jobs` với `from_stage: asr` được 202. Worker đánh job `failed`
(`AUDIO_EXPIRED`), cuộc họp thành `failed` và `GET /transcript` trả danh sách rỗng, dù các
đoạn thoại vẫn còn trong DB. Không chạy lại được nữa vì audio đã xóa.
"""

import uuid
from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.models.job import Job
from app.db.models.meeting import Meeting
from app.db.models.transcript import Segment, Speaker
from app.db.models.user import User
from app.db.session import get_db
from app.main import create_app
from app.services.storage import get_storage
from app.services.storage.local import LocalStorage
from app.worker.runner import run_worker_once


def _ready_meeting(db: Session, retention_until: datetime) -> tuple[User, Meeting]:
    """Cuộc họp đã xử lý xong, có một đoạn thoại và một job thành công; file audio không còn."""
    user = User(
        id=str(uuid.uuid4()),
        email=f"rerun-{uuid.uuid4().hex[:8]}@example.com",
        display_name="Rerun",
        password_hash="x",
    )
    db.add(user)
    db.commit()
    meeting_id = str(uuid.uuid4())
    meeting = Meeting(
        id=meeting_id,
        owner_id=user.id,
        title="Họp đã xử lý",
        source="upload",
        status="ready",
        audio_path=f"audio/{meeting_id}/original.wav",
        retention_until=retention_until,
        version=1,
    )
    db.add(meeting)
    db.commit()
    speaker = Speaker(
        id=str(uuid.uuid4()),
        meeting_id=meeting_id,
        label="SPEAKER_00",
        default_name="Người nói 1",
        display_name="Người nói 1",
        version=1,
    )
    db.add(speaker)
    db.add(
        Job(
            id=str(uuid.uuid4()),
            meeting_id=meeting_id,
            status="succeeded",
            stage="summarize",
            stage_status={},
            progress=1.0,
            attempt=1,
            max_attempts=3,
        )
    )
    db.commit()
    db.add(
        Segment(
            id=str(uuid.uuid4()),
            meeting_id=meeting_id,
            speaker_id=speaker.id,
            idx=0,
            start_sec=0.0,
            end_sec=1.0,
            text="xin chào",
            ai_text="xin chào",
            ai_speaker_id=speaker.id,
            version=1,
        )
    )
    db.commit()
    return user, meeting


@pytest.fixture
def storage(tmp_path: Path) -> LocalStorage:
    return LocalStorage(base_dir=tmp_path)


@pytest.fixture
def make_client(db_session: Session, storage: LocalStorage) -> Generator[object, None, None]:
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_storage] = lambda: storage

    def _make(user: User) -> TestClient:
        app.dependency_overrides[get_current_user] = lambda: user
        return TestClient(app, raise_server_exceptions=False)

    yield _make
    app.dependency_overrides.clear()


@pytest.mark.parametrize(
    ("days", "status", "code"),
    [
        pytest.param(-1, 410, "AUDIO_EXPIRED", id="expired"),
        pytest.param(30, 404, "AUDIO_NOT_FOUND", id="missing-file"),
    ],
)
def test_rerun_that_needs_audio_is_refused_and_the_transcript_stays(
    db_session: Session,
    storage: LocalStorage,
    make_client,
    days: int,
    status: int,
    code: str,
) -> None:
    user, meeting = _ready_meeting(db_session, datetime.now(UTC) + timedelta(days=days))
    client = make_client(user)

    r = client.post(f"/api/v1/meetings/{meeting.id}/jobs", json={"from_stage": "asr"})
    # Chạy worker như production để thấy hậu quả nếu API đã nhận job.
    run_worker_once(db_session, storage=storage, worker_id="rerun-test", backend="fake")
    transcript = client.get(f"/api/v1/meetings/{meeting.id}/transcript").json()

    assert (r.status_code, len(transcript["segments"])) == (status, 1), r.text[:300]
    assert r.json()["error"]["code"] == code

    db_session.expire_all()
    refreshed = db_session.get(Meeting, meeting.id)
    assert refreshed is not None and refreshed.status == "ready"
    job_count = db_session.execute(
        select(func.count()).select_from(Job).where(Job.meeting_id == meeting.id)
    ).scalar_one()
    assert job_count == 1


@pytest.mark.parametrize("from_stage", [None, "preprocess", "vad", "asr", "diarize", "merge"])
@pytest.mark.parametrize(
    ("days", "status", "code"),
    [
        pytest.param(-1, 410, "AUDIO_EXPIRED", id="expired"),
        pytest.param(30, 404, "AUDIO_NOT_FOUND", id="missing-file"),
    ],
)
def test_all_audio_stages_refused_and_idempotency_key_reusable(
    db_session: Session,
    make_client,
    from_stage: str | None,
    days: int,
    status: int,
    code: str,
) -> None:
    """Mọi stage cần audio bị từ chối khi hết hạn/mất file và Idempotency-Key dùng lại được."""
    user, meeting = _ready_meeting(db_session, datetime.now(UTC) + timedelta(days=days))
    if days < 0:
        meeting.audio_path = None
    if from_stage is None:
        # Chạy lại toàn bộ (null) trên job trước failed thay vì JOB_ALREADY_SUCCEEDED
        prior_job = db_session.execute(select(Job).where(Job.meeting_id == meeting.id)).scalar_one()
        prior_job.status = "failed"
    db_session.commit()
    client = make_client(user)

    idem_key = f"rerun-{from_stage or 'full'}-{code}-{uuid.uuid4()}"
    refused = client.post(
        f"/api/v1/meetings/{meeting.id}/jobs",
        json={"from_stage": from_stage},
        headers={"Idempotency-Key": idem_key},
    )
    assert refused.status_code == status, refused.text[:300]
    assert refused.json()["error"]["code"] == code

    # Cùng Idempotency-Key dùng lại ngay cho summarize vẫn được nhận 202
    resumed = client.post(
        f"/api/v1/meetings/{meeting.id}/jobs",
        json={"from_stage": "summarize"},
        headers={"Idempotency-Key": idem_key},
    )
    assert resumed.status_code == 202, resumed.text[:300]


def test_summary_rerun_still_works_after_the_audio_expired(
    db_session: Session, storage: LocalStorage, make_client
) -> None:
    """Tạo lại tóm tắt chỉ cần transcript: vẫn được nhận và chạy xong khi audio đã hết hạn."""
    user, meeting = _ready_meeting(db_session, datetime.now(UTC) - timedelta(days=1))
    client = make_client(user)

    r = client.post(f"/api/v1/meetings/{meeting.id}/jobs", json={"from_stage": "summarize"})
    assert r.status_code == 202, r.text[:300]
    assert run_worker_once(db_session, storage=storage, worker_id="rerun-test", backend="fake")

    job = db_session.get(Job, r.json()["id"])
    db_session.refresh(job)
    assert (job.status, job.error_code) == ("succeeded", None)
    transcript = client.get(f"/api/v1/meetings/{meeting.id}/transcript").json()
    assert len(transcript["segments"]) == 1
