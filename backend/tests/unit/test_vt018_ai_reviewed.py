"""Test do AI sinh cho retry và hàng đợi job (VT-018), BẢN ĐÃ REVIEW.

Bản thô (giữ nguyên như AI viết): tests/ai_raw/vt018_ai_raw.py, không nằm trong bộ test mặc định
vì có một test fail trên code đúng. Mỗi chỗ đổi so với bản thô ghi `REVIEW:` kèm lý do; bằng
chứng mutation trước và sau ở docs/evidence/vt-018/ai-tests/03-mutation-matrix.md và 04-review.md.
"""

import uuid
from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import create_engine, event, text
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


TABLES = [User.__table__, Meeting.__table__, Job.__table__]


@pytest.fixture
def db() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    yield from _session_on(engine)


def _session_on(engine) -> Generator[Session, None, None]:
    Base.metadata.create_all(bind=engine, tables=TABLES)
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
        delays = [compute_backoff_delay(attempt) for _ in range(200)]
        for d in delays:
            assert base * 0.8 <= d <= base * 1.2
        # REVIEW: bản thô chỉ kiểm cận, nên bỏ hẳn jitter (M03) vẫn xanh. Jitter tồn tại để
        # các job lỗi cùng lúc không retry cùng lúc; 200 lần gọi phải ra nhiều giá trị khác nhau.
        assert len(set(delays)) > 1


# REVIEW: xóa test_backoff_returns_float: chỉ kiểm kiểu trả về, giết 0/24 mutant.


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


# REVIEW: xóa test_succeeded_is_terminal: kiểm một hằng số trong code, không kiểm hành vi;
# test_invalid_transitions_raise[succeeded-*] đã kiểm hành vi đó.


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


def test_claim_respects_next_run_at_of_queued_job(db):
    # REVIEW: thêm. Bản thô không có job queued nào có next_run_at, nên M09 sống.
    job = _job(db, next_run_at=T0 + timedelta(seconds=30))
    assert claim_job(db, "w1", now=T0) is None
    claimed = claim_job(db, "w1", now=T0 + timedelta(seconds=30))
    assert claimed is not None and claimed.id == job.id


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


@pytest.fixture
def file_db(tmp_path: Path) -> Generator[Session, None, None]:
    engine = create_engine(f"sqlite:///{tmp_path / 'race.db'}")
    yield from _session_on(engine)


def test_same_job_cannot_be_claimed_twice(file_db):
    # REVIEW: sửa. Bản thô claim hai lần tuần tự: lần hai không thấy job vì job đã running, nên
    # bỏ điều kiện chống race (M12) test vẫn xanh. Bản này cho worker khác claim job vào giữa
    # lúc w1 đã đọc job và lúc w1 cập nhật, qua một kết nối thứ hai tới cùng file DB.
    db = file_db
    job = _job(db)
    other = create_engine(db.get_bind().url)
    fired = []

    def other_worker_claims_first(conn, cursor, statement, params, context, executemany):
        if statement.lstrip().upper().startswith("UPDATE JOBS") and not fired:
            fired.append(True)
            with other.begin() as c:
                c.execute(
                    text("UPDATE jobs SET status='running', locked_by='w2' WHERE id=:id"),
                    {"id": job.id},
                )

    event.listen(db.get_bind(), "before_cursor_execute", other_worker_claims_first)
    try:
        assert claim_job(db, "w1", now=T0) is None
    finally:
        event.remove(db.get_bind(), "before_cursor_execute", other_worker_claims_first)
        other.dispose()
    assert fired
    db.expire_all()
    assert db.get(Job, job.id).locked_by == "w2"


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
    # REVIEW: sửa. Bản thô so trực tiếp và fail trên code đúng: sau commit SQLite trả datetime
    # không có múi giờ. Vì test này fail sẵn, M17 và M18 sống.
    assert _aware(job.next_run_at) == nxt
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


# REVIEW: xóa test_can_retry_is_bool: chỉ kiểm kiểu trả về, giết 0/24 mutant. Bộ tham số
# test_can_retry ở trên đã so bằng `is True` / `is False`.


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


@pytest.mark.parametrize("elapsed", [30, 60])
def test_reaper_ignores_job_with_valid_lease(db, elapsed):
    # REVIEW: sửa. Bản thô chỉ thử giây 30, xa biên, nên M19 (`<` thành `<=`) sống. Đúng giây 60
    # lease vừa hết hạn nhưng chưa quá hạn: worker còn đang heartbeat thì không được thu hồi.
    job = _job(db)
    claim_job(db, "w1", lease_duration_sec=60, now=T0)
    reaped = reap_expired_jobs(db, now=T0 + timedelta(seconds=elapsed))
    assert reaped == []
    assert job.status == "running"


# REVIEW: xóa test_reaper_returns_list: chỉ kiểm kiểu trả về trên DB rỗng, giết 0/24 mutant.


def test_sigterm_requeues_without_incrementing_attempt(db):
    job = _job(db)
    claim_job(db, "w1", now=T0)
    release_job_on_sigterm(db, job, now=T0 + timedelta(seconds=5))
    assert job.status == "queued"
    assert job.attempt == 1
    assert job.locked_by is None


# REVIEW: xóa test_requeued_job_is_not_duplicated: `count() == 1` không thể sai vì reaper không
# tạo job mới; phần claim lại trùng test_claim_picks_queued_job. Rủi ro bản ghi trùng khi chạy
# lại nằm ở segment, đã có test_vt018_rerun_progress.py.
