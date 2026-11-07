"""VT-018: chạy lại job không tạo bản ghi trùng, tiến độ không tụt, thời gian job là thật.

Mỗi test dựng API + worker thật trên SQLite in-memory với fake pipeline.
Tiến độ được ghi lại bằng trigger SQL để thấy mọi giá trị đã ghi vào DB, kể cả
giá trị ban đầu lúc tạo job.

Các test đang đánh dấu xfail(strict=True) vì tái hiện lỗi chưa sửa. Lấy log đỏ bằng
``pytest --runxfail``. Khi vá xong thì gỡ xfail tương ứng.
"""

import io
import time
import uuid
from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import hash_password
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
from app.services.storage import LocalStorage, get_storage
from app.worker.runner import run_worker_once

PASSWORD = "Vt018Password!2026"


@pytest.fixture(autouse=True)
def _no_ffprobe(monkeypatch: pytest.MonkeyPatch) -> None:
    def _probe(file_path, timeout_sec=10.0, ffprobe_bin=None):
        return AudioProbeResult(duration_sec=30.0, format_name="wav", sample_rate=16000, channels=1)

    monkeypatch.setattr("app.api.v1.meetings.probe_audio", _probe)


@pytest.fixture
def session() -> Generator[Session, None, None]:
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
        EditEvent.__table__,
    ]
    Base.metadata.create_all(bind=engine, tables=tables)
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE progress_log (job_id TEXT, progress REAL)"))
        conn.execute(
            text(
                "CREATE TRIGGER trg_progress_ins AFTER INSERT ON jobs BEGIN "
                "INSERT INTO progress_log VALUES (NEW.id, NEW.progress); END"
            )
        )
        conn.execute(
            text(
                "CREATE TRIGGER trg_progress_upd AFTER UPDATE OF progress ON jobs BEGIN "
                "INSERT INTO progress_log VALUES (NEW.id, NEW.progress); END"
            )
        )
    db = sessionmaker(autocommit=False, autoflush=False, bind=engine)()
    try:
        yield db
    finally:
        db.close()
        engine.dispose()


class Env:
    def __init__(self, db: Session, client: TestClient, storage: LocalStorage) -> None:
        self.db = db
        self.client = client
        self.storage = storage

    def upload(self, env: dict[str, str] | None = None) -> tuple[str, str]:
        res = self.client.post(
            "/api/v1/meetings",
            data={"title": "Họp VT018", "consent_confirmed": "true", "meeting_date": "2026-11-06"},
            files={"file": ("m.wav", io.BytesIO(b"RIFF" + b"\x00" * 400), "audio/wav")},
            headers={"Idempotency-Key": str(uuid.uuid4())},
        )
        assert res.status_code == 201, res.text
        body = res.json()
        return body["meeting"]["id"], body["job"]["id"]

    def work(self, env: dict[str, str] | None = None, now: datetime | None = None) -> bool:
        return run_worker_once(
            self.db,
            storage=self.storage,
            worker_id="vt018",
            backend="fake",
            env=env or {},
            now=now,
        )

    def rerun(self, meeting_id: str, from_stage: str | None) -> str:
        res = self.client.post(
            f"/api/v1/meetings/{meeting_id}/jobs",
            json={"from_stage": from_stage},
            headers={"Idempotency-Key": str(uuid.uuid4())},
        )
        assert res.status_code == 202, res.text
        return res.json()["id"]

    def progress_of(self, job_id: str) -> list[float]:
        rows = self.db.execute(
            text("SELECT progress FROM progress_log WHERE job_id = :j ORDER BY rowid"),
            {"j": job_id},
        ).all()
        return [r[0] for r in rows]

    def segment_rows(self, meeting_id: str) -> list[tuple[int, str]]:
        self.db.expire_all()
        return [
            (s.idx, s.text)
            for s in self.db.execute(
                select(Segment).where(Segment.meeting_id == meeting_id).order_by(Segment.idx)
            ).scalars()
        ]


@pytest.fixture
def env(session: Session, tmp_path: Path) -> Generator[Env, None, None]:
    storage = LocalStorage(base_dir=tmp_path)
    session.add(
        User(
            id=str(uuid.uuid4()),
            email="vt018@example.com",
            display_name="VT018",
            password_hash=hash_password(PASSWORD),
        )
    )
    session.commit()
    app = create_app()

    def _db() -> Generator[Session, None, None]:
        yield session

    app.dependency_overrides[get_db] = _db
    app.dependency_overrides[get_storage] = lambda: storage
    with TestClient(app) as client:
        res = client.post(
            "/api/v1/auth/login", json={"email": "vt018@example.com", "password": PASSWORD}
        )
        assert res.status_code == 200, res.text
        yield Env(session, client, storage)


XFAIL_PROGRESS = pytest.mark.xfail(
    strict=True, reason="BE-17: tiến độ job chạy lại bị ghi thấp hơn giá trị khởi tạo"
)
XFAIL_TIME = pytest.mark.xfail(
    strict=True, reason="BE-17: started_at và finished_at luôn null trong API"
)


def test_vt018_second_job_keeps_one_segment_set(env: Env) -> None:
    meeting_id, _ = env.upload()
    assert env.work()
    first = env.segment_rows(meeting_id)
    assert first, "fixture phải có segment"

    env.rerun(meeting_id, "asr")
    assert env.work()

    after = env.segment_rows(meeting_id)
    assert len(after) == len(first), f"segment nhân đôi: {len(first)} -> {len(after)}"
    assert [i for i, _ in after] == list(range(len(after))), "idx bị lặp"


@XFAIL_PROGRESS
def test_vt018_progress_never_decreases_on_rerun(env: Env) -> None:
    meeting_id, _ = env.upload()
    assert env.work()
    job2 = env.rerun(meeting_id, "asr")
    assert env.work()

    seq = env.progress_of(job2)
    assert len(seq) >= 3
    assert seq == sorted(seq), f"tiến độ tụt lùi: {seq}"
    assert seq[-1] == 1.0


@XFAIL_PROGRESS
def test_vt018_progress_never_decreases_after_transient_retry(env: Env) -> None:
    meeting_id, job1 = env.upload()
    assert env.work()
    job2 = env.rerun(meeting_id, "asr")
    assert env.work(env={"FAKE_SCENARIO": "transient_once"})
    env.db.expire_all()
    assert env.db.get(Job, job2).status == "retry_scheduled"

    later = datetime.now(UTC) + timedelta(hours=1)
    assert env.work(env={"FAKE_SCENARIO": "transient_once"}, now=later)

    seq = env.progress_of(job2)
    assert seq == sorted(seq), f"tiến độ tụt lùi sau retry: {seq}"
    assert env.db.get(Job, job2).status == "succeeded"


@XFAIL_TIME
def test_vt018_job_out_has_real_timestamps(env: Env) -> None:
    _, job_id = env.upload()
    before = datetime.now(UTC)
    time.sleep(0.01)
    assert env.work()

    body = env.client.get(f"/api/v1/jobs/{job_id}").json()
    assert body["status"] == "succeeded"
    assert body["started_at"] is not None
    assert body["finished_at"] is not None
    started = datetime.fromisoformat(body["started_at"]).replace(tzinfo=UTC)
    finished = datetime.fromisoformat(body["finished_at"]).replace(tzinfo=UTC)
    assert started >= before.replace(microsecond=0)
    assert finished >= started


def test_vt018_merge_rerun_with_user_edits_is_rejected(env: Env) -> None:
    meeting_id, _ = env.upload()
    assert env.work()
    segs = env.client.get(f"/api/v1/meetings/{meeting_id}/transcript").json()["segments"]
    res = env.client.patch(
        f"/api/v1/meetings/{meeting_id}/segments/{segs[0]['id']}",
        json={"text": "Đã sửa tay", "version": segs[0]["version"]},
    )
    assert res.status_code == 200, res.text

    res = env.client.post(
        f"/api/v1/meetings/{meeting_id}/jobs",
        json={"from_stage": "merge"},
        headers={"Idempotency-Key": str(uuid.uuid4())},
    )
    assert res.status_code == 409
    assert res.json()["error"]["code"] == "HAS_USER_EDITS"


def test_vt018_count_helper_is_sane(env: Env) -> None:
    """Đối chứng: chạy một job duy nhất thì mỗi idx đúng một lần."""
    meeting_id, _ = env.upload()
    assert env.work()
    total = env.db.execute(
        select(func.count()).select_from(Segment).where(Segment.meeting_id == meeting_id)
    ).scalar_one()
    assert total == len(env.segment_rows(meeting_id))


def test_vt018_failed_summarize_leaves_no_dangling_evidence(env: Env) -> None:
    """Job mới thay segment rồi lỗi ở summarize: evidence cũ không được trỏ vào segment đã xóa."""
    meeting_id, _ = env.upload()
    assert env.work()
    env.rerun(meeting_id, "asr")
    assert env.work(env={"FAKE_SCENARIO": "summary_fail"})

    env.db.expire_all()
    valid = {s.id for s in env.db.execute(select(Segment)).scalars()}
    summary = env.db.execute(select(Summary)).scalar_one()
    for section in ("key_points", "decisions"):
        for entry in (summary.content or {}).get(section, []):
            assert set(entry["evidence_segment_ids"]) <= valid
    for item in env.db.execute(select(ActionItem)).scalars():
        assert set(item.evidence_segment_ids or []) <= valid
