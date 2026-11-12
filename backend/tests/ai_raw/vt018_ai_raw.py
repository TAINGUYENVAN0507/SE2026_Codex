"""Test do AI sinh cho retry và hàng đợi job (VT-018), BẢN THÔ.

Sinh ngày 2026-11-12 bằng Claude Code (Claude Opus 5.5) theo prompt ở
docs/evidence/vt-018/ai-tests/00-prompt.md, plan ở 01-plan-raw.md. File này giữ nguyên như AI
viết, chỉ để nhóm đánh giá bằng mutation (docs/evidence/vt-018/ai-tests/). Bản đã sửa nằm ở
test_vt018_ai_reviewed.py.
"""

import uuid
from collections.abc import Generator
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.models.job import Job
from app.db.models.meeting import Meeting
from app.db.models.user import User
from app.worker.queue import (
    VALID_TRANSITIONS,
    InvalidJobStateTransitionError,
    JobStatus,
    claim_job,
    complete_job,
    enqueue_job,
    fail_job,
    schedule_retry,
    transition_job_status,
    validate_transition,
)
from app.worker.reaper import reap_expired_jobs, release_job_on_sigterm
from app.worker.retry import BACKOFF_DELAYS_SEC, compute_backoff_delay

T0 = datetime(2026, 11, 12, 8, 0, 0, tzinfo=UTC)


@pytest.fixture
def db() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    tables = [User.__table__, Meeting.__table__, Job.__table__]
    Base.metadata.create_all(bind=engine, tables=tables)
    session = sessionmaker(bind=engine, autoflush=False)()
    user = User(
        id=str(uuid.uuid4()),
        email="ai-raw@example.local",
        display_name="AI Raw",
        password_hash="x",
    )
    session.add(user)
    session.commit()
    session.info["user_id"] = user.id
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def _meeting(db: Session) -> str:
    m = Meeting(
        id=str(uuid.uuid4()),
        owner_id=db.info["user_id"],
        title="Cuộc họp tổng hợp",
        source="upload",
        status="queued",
    )
    db.add(m)
    db.commit()
    return m.id


def _job(db: Session, now: datetime = T0, **fields) -> Job:
    job = enqueue_job(db, _meeting(db), now=now)
    for k, v in fields.items():
        setattr(job, k, v)
    db.commit()
    return job


def _aware(dt: datetime | None) -> datetime | None:
    if dt is None or dt.tzinfo is not None:
        return dt
    return dt.replace(tzinfo=UTC)


# --- Backoff ---------------------------------------------------------------


@pytest.mark.parametrize("attempt,expected", [(1, 30.0), (2, 120.0), (3, 480.0)])
def test_backoff_without_jitter_follows_schedule(attempt, expected):
    assert compute_backoff_delay(attempt, with_jitter=False) == expected


def test_backoff_caps_at_last_step():
    assert compute_backoff_delay(10, with_jitter=False) == 480.0


def test_backoff_zero_or_negative_attempt_uses_first_step():
    assert compute_backoff_delay(0, with_jitter=False) == 30.0
    assert compute_backoff_delay(-5, with_jitter=False) == 30.0


def test_backoff_with_jitter_stays_within_twenty_percent():
    for attempt in (1, 2, 3):
        base = BACKOFF_DELAYS_SEC[attempt - 1]
        for _ in range(200):
            d = compute_backoff_delay(attempt)
            assert base * 0.8 <= d <= base * 1.2


def test_backoff_returns_float():
    assert isinstance(compute_backoff_delay(1), float)


# --- Máy trạng thái ----------------------------------------------------------


def test_all_valid_transitions_are_accepted():
    for src, targets in VALID_TRANSITIONS.items():
        for tgt in targets:
            validate_transition(src, tgt)


@pytest.mark.parametrize(
    "src,tgt",
    [
        ("succeeded", "queued"),
        ("succeeded", "running"),
        ("queued", "succeeded"),
        ("queued", "failed"),
        ("failed", "running"),
    ],
)
def test_invalid_transitions_raise(src, tgt):
    with pytest.raises(InvalidJobStateTransitionError):
        validate_transition(src, tgt)


def test_unknown_status_raises():
    with pytest.raises(InvalidJobStateTransitionError):
        validate_transition("paused", "running")
    with pytest.raises(InvalidJobStateTransitionError):
        validate_transition("queued", "paused")


def test_error_message_mentions_both_states():
    with pytest.raises(InvalidJobStateTransitionError) as exc:
        validate_transition("succeeded", "queued", job_id="abc")
    assert "succeeded" in str(exc.value)
    assert "queued" in str(exc.value)


def test_succeeded_is_terminal():
    assert VALID_TRANSITIONS[JobStatus.SUCCEEDED] == set()


def test_transition_to_queued_clears_schedule_and_lock(db):
    job = _job(db, status="running", locked_by="w1", locked_until=T0, next_run_at=T0)
    transition_job_status(job, JobStatus.QUEUED, now=T0)
    assert job.status == "queued"
    assert job.next_run_at is None
    assert job.locked_by is None
    assert job.locked_until is None


@pytest.mark.parametrize("terminal", ["succeeded", "failed", "cancelled"])
def test_transition_to_terminal_sets_finished_at(db, terminal):
    job = _job(db, status="running", locked_by="w1")
    transition_job_status(job, terminal, now=T0 + timedelta(minutes=5))
    assert job.finished_at == T0 + timedelta(minutes=5)
    assert job.locked_by is None


def test_transition_updates_updated_at(db):
    job = _job(db, status="queued")
    later = T0 + timedelta(seconds=42)
    transition_job_status(job, JobStatus.RUNNING, now=later)
    assert job.updated_at == later


# --- Enqueue / claim / complete / fail / retry ---------------------------


def test_enqueue_job_defaults(db):
    job = enqueue_job(db, _meeting(db), now=T0)
    db.commit()
    assert job.status == "queued"
    assert job.attempt == 1
    assert job.max_attempts == 3
    assert job.progress == 0.0
    assert job.stage == "preprocess"
    assert job.id is not None


def test_enqueue_job_from_stage(db):
    job = enqueue_job(db, _meeting(db), from_stage="summarize", now=T0)
    assert job.stage == "summarize"
    assert job.from_stage == "summarize"


def test_claim_picks_queued_job(db):
    job = _job(db)
    claimed = claim_job(db, "w1", now=T0)
    assert claimed is not None
    assert claimed.id == job.id
    assert claimed.status == "running"
    assert claimed.locked_by == "w1"
    assert _aware(claimed.locked_until) == T0 + timedelta(seconds=60)


def test_claim_returns_none_when_empty(db):
    assert claim_job(db, "w1", now=T0) is None


def test_claim_skips_retry_not_due(db):
    _job(db, status="retry_scheduled", next_run_at=T0 + timedelta(seconds=30))
    assert claim_job(db, "w1", now=T0) is None


def test_claim_takes_retry_when_due(db):
    job = _job(db, status="retry_scheduled", next_run_at=T0)
    claimed = claim_job(db, "w1", now=T0)
    assert claimed is not None and claimed.id == job.id


def test_claim_orders_by_created_at(db):
    newer = _job(db, now=T0 + timedelta(seconds=10))
    older = _job(db, now=T0)
    claimed = claim_job(db, "w1", now=T0 + timedelta(seconds=20))
    assert claimed.id == older.id
    assert claimed.id != newer.id


def test_claim_sets_started_at_once(db):
    job = _job(db)
    claim_job(db, "w1", now=T0)
    first_start = _aware(job.started_at)
    assert first_start == T0
    schedule_retry(db, job, next_run_at=T0 + timedelta(seconds=30), now=T0 + timedelta(seconds=1))
    claim_job(db, "w2", now=T0 + timedelta(minutes=1))
    db.refresh(job)
    assert _aware(job.started_at) == first_start


def test_same_job_cannot_be_claimed_twice(db):
    _job(db)
    first = claim_job(db, "w1", now=T0)
    second = claim_job(db, "w2", now=T0)
    assert first is not None
    assert second is None


def test_complete_job_sets_progress_and_unlocks(db):
    job = _job(db)
    claim_job(db, "w1", now=T0)
    complete_job(db, job, now=T0 + timedelta(minutes=2))
    assert job.status == "succeeded"
    assert job.progress == 1.0
    assert job.locked_by is None


def test_fail_job_records_error(db):
    job = _job(db)
    claim_job(db, "w1", now=T0)
    fail_job(db, job, "ASR_FAILED", "boom", now=T0)
    assert job.status == "failed"
    assert job.error_code == "ASR_FAILED"
    assert job.error_message == "boom"


def test_schedule_retry_increments_attempt_and_sets_next_run(db):
    job = _job(db)
    claim_job(db, "w1", now=T0)
    nxt = T0 + timedelta(seconds=30)
    schedule_retry(db, job, next_run_at=nxt, error_code="TRANSIENT", now=T0)
    assert job.status == "retry_scheduled"
    assert job.attempt == 2
    assert job.next_run_at == nxt
    assert job.locked_by is None


def test_schedule_retry_from_queued_is_rejected(db):
    job = _job(db)
    with pytest.raises(InvalidJobStateTransitionError):
        schedule_retry(db, job, next_run_at=T0, now=T0)


# --- can_retry ---------------------------------------------------------------


@pytest.mark.parametrize(
    "attempt,max_attempts,expected",
    [(1, 3, True), (2, 3, True), (3, 3, False), (4, 3, False)],
)
def test_can_retry(attempt, max_attempts, expected):
    job = Job(attempt=attempt, max_attempts=max_attempts)
    assert job.can_retry is expected


def test_can_retry_is_bool():
    assert isinstance(Job(attempt=1, max_attempts=3).can_retry, bool)


# --- Reaper ------------------------------------------------------------------


def test_reaper_requeues_expired_job_with_attempts_left(db):
    job = _job(db)
    claim_job(db, "w1", lease_duration_sec=60, now=T0)
    reaped = reap_expired_jobs(db, now=T0 + timedelta(seconds=61))
    assert [j.id for j in reaped] == [job.id]
    assert job.status == "queued"
    assert job.attempt == 2
    assert job.locked_by is None


def test_reaper_fails_expired_job_on_last_attempt(db):
    job = _job(db, attempt=3)
    claim_job(db, "w1", lease_duration_sec=60, now=T0)
    reap_expired_jobs(db, now=T0 + timedelta(seconds=61))
    assert job.status == "failed"
    assert job.error_code == "LEASE_TIMEOUT"


def test_reaper_ignores_job_with_valid_lease(db):
    job = _job(db)
    claim_job(db, "w1", lease_duration_sec=60, now=T0)
    reaped = reap_expired_jobs(db, now=T0 + timedelta(seconds=30))
    assert reaped == []
    assert job.status == "running"


def test_reaper_returns_list(db):
    assert isinstance(reap_expired_jobs(db, now=T0), list)


def test_sigterm_requeues_without_incrementing_attempt(db):
    job = _job(db)
    claim_job(db, "w1", now=T0)
    release_job_on_sigterm(db, job, now=T0 + timedelta(seconds=5))
    assert job.status == "queued"
    assert job.attempt == 1
    assert job.locked_by is None


def test_requeued_job_is_not_duplicated(db):
    job = _job(db)
    claim_job(db, "w1", lease_duration_sec=60, now=T0)
    reap_expired_jobs(db, now=T0 + timedelta(seconds=61))
    assert db.query(Job).count() == 1
    again = claim_job(db, "w2", now=T0 + timedelta(seconds=62))
    assert again.id == job.id
