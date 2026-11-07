"""VT-018: biên của Job.can_retry và ba nơi dùng nó (RT-04).

Biên là lượt cuối attempt == max_attempts. Một mutant đổi `>` thành `>=` làm lượt cuối
còn retry; mọi test ở đây phải bắt được nó.
"""

from datetime import UTC, datetime, timedelta

import pytest

from app.db.models.job import Job


def job(attempt: int, max_attempts: int = 3, **kw) -> Job:
    return Job(
        id=kw.pop("id", "j1"),
        meeting_id=kw.pop("meeting_id", "m1"),
        status=kw.pop("status", "running"),
        stage="asr",
        stage_status={},
        progress=0.1,
        attempt=attempt,
        max_attempts=max_attempts,
        **kw,
    )


@pytest.mark.parametrize(
    ("attempt", "max_attempts", "expected"),
    [(1, 3, True), (2, 3, True), (3, 3, False), (4, 3, False), (1, 1, False)],
)
def test_can_retry_boundary(attempt: int, max_attempts: int, expected: bool) -> None:
    assert job(attempt, max_attempts).can_retry is expected


def test_reaper_requeues_before_last_attempt_and_fails_on_last() -> None:
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    from app.db.base import Base
    from app.db.models.meeting import Meeting
    from app.db.models.user import User
    from app.worker.reaper import reap_expired_jobs

    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(bind=engine, tables=[User.__table__, Meeting.__table__, Job.__table__])
    db = sessionmaker(bind=engine)()
    now = datetime.now(UTC)
    db.add(User(id="u", email="r@example.com", display_name="R", password_hash="x"))
    db.add(Meeting(id="m_a", owner_id="u", title="a", source="upload", status="processing"))
    db.add(Meeting(id="m_b", owner_id="u", title="b", source="upload", status="processing"))
    expired = now - timedelta(minutes=5)
    for jid, mid, att in (("last", "m_a", 3), ("mid", "m_b", 2)):
        db.add(job(att, id=jid, meeting_id=mid, locked_by="w", locked_until=expired))
    db.commit()

    reap_expired_jobs(db, now=now)
    db.expire_all()
    assert db.get(Job, "mid").status == "queued"
    assert db.get(Job, "mid").attempt == 3
    assert db.get(Job, "last").status == "failed"
    assert db.get(Job, "last").error_code == "LEASE_TIMEOUT"


# fixture dùng chung với test_vt018_rerun_progress (API + worker thật, SQLite)
from tests.unit.test_vt018_rerun_progress import Env, _no_ffprobe, env, session  # noqa: E402,F401


@pytest.mark.parametrize(("attempt", "final_status"), [(2, "retry_scheduled"), (3, "failed")])
def test_worker_transient_error_retries_only_before_last_attempt(
    env: Env,  # noqa: F811
    attempt: int,
    final_status: str,
) -> None:
    _, job_id = env.upload()
    row = env.db.get(Job, job_id)
    row.attempt = attempt
    env.db.commit()

    assert env.work(env={"FAKE_SCENARIO": "transient_once"})
    env.db.expire_all()
    assert env.db.get(Job, job_id).status == final_status


@pytest.mark.parametrize(("attempt", "retryable"), [(2, True), (3, False)])
def test_api_reports_retryable_from_can_retry(
    env: Env,  # noqa: F811
    attempt: int,
    retryable: bool,
) -> None:
    _, job_id = env.upload()
    row = env.db.get(Job, job_id)
    row.status, row.attempt, row.error_code = "failed", attempt, "ASR_FAILED"
    env.db.commit()

    body = env.client.get(f"/api/v1/jobs/{job_id}").json()
    assert body["error"]["retryable"] is retryable
