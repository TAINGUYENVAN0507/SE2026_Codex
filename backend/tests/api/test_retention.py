"""Kiểm thử chính sách lưu trữ (Retention Policy) và dọn dẹp tự động (BE-14, PRIV-14).

Bao gồm:
- Test biên: đúng lúc retention_until thì chưa xóa, sau 1 giây thì xóa.
- Test --dry-run: chỉ báo cáo thống kê, không xóa file và không thay đổi database.
- PRIV-14: Audio hết hạn bị xóa trên đĩa, meeting.audio_path=None, GET /audio trả 410 AUDIO_EXPIRED.
  Transcript và summary trong DB vẫn giữ nguyên vẹn.
- Bỏ qua meeting đã hết hạn nhưng đang có job active (queued, running, retry_scheduled).
- Xóa idempotency_keys cũ hơn 28 ngày, giữ lại các keys trong hạn.
- Script dòng lệnh python -m app.scripts.cleanup chạy thành công.
"""

import uuid
from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import get_current_user
from app.core.config import get_settings
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
from app.services.retention import run_retention_cleanup
from app.services.storage import Storage, get_storage
from app.services.storage.local import LocalStorage


@pytest.fixture
def test_storage(tmp_path: Path) -> Storage:
    """Tạo storage tạm thời cho test."""
    return LocalStorage(base_dir=tmp_path)


@pytest.fixture
def test_db() -> Generator[Session, None, None]:
    """Tạo database SQLite in-memory dùng cho test retention."""
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
        Summary.__table__,
        ActionItem.__table__,
        AIOutput.__table__,
    ]
    Base.metadata.create_all(bind=engine, tables=tables)
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def test_user(test_db: Session) -> User:
    """Tạo người dùng sở hữu cuộc họp."""
    user = User(
        id=str(uuid.uuid4()),
        email="retention_owner@example.com",
        display_name="Chủ Cuộc Họp",
        password_hash="mock_hash",
    )
    test_db.add(user)
    test_db.commit()
    test_db.refresh(user)
    return user


@pytest.fixture
def auth_client(
    test_db: Session, test_user: User, test_storage: Storage
) -> Generator[TestClient, None, None]:
    """TestClient có xác thực của test_user."""
    app = create_app()
    app.dependency_overrides[get_db] = lambda: test_db
    app.dependency_overrides[get_current_user] = lambda: test_user
    app.dependency_overrides[get_storage] = lambda: test_storage
    with TestClient(app) as client:
        token = create_access_token(test_user.id)
        client.headers.update({"Authorization": f"Bearer {token}"})
        yield client
    app.dependency_overrides.clear()


def test_retention_boundary_condition(
    test_db: Session,
    test_user: User,
    test_storage: Storage,
) -> None:
    """Test biên: đúng lúc retention_until thì chưa xóa, sau 1 giây thì xóa."""
    meeting_id = str(uuid.uuid4())
    retention_ts = datetime(2026, 11, 6, 12, 0, 0, tzinfo=UTC)

    audio_file = test_storage.get_audio_path(meeting_id, "wav")
    audio_file.parent.mkdir(parents=True, exist_ok=True)
    audio_file.write_bytes(b"RIFFtest")

    art_dir = Path(test_storage.base_dir) / "artifacts" / meeting_id / "job-1"
    art_dir.mkdir(parents=True, exist_ok=True)
    (art_dir / "transcript.json").write_text("{}", encoding="utf-8")

    meeting = Meeting(
        id=meeting_id,
        owner_id=test_user.id,
        title="Cuộc họp kiểm tra biên retention",
        source="upload",
        status="ready",
        audio_path=f"audio/{meeting_id}/original.wav",
        retention_until=retention_ts,
        version=1,
    )
    test_db.add(meeting)
    test_db.commit()

    # 1. Tại đúng thời điểm retention_until: CHƯA XÓA
    res_at_exact = run_retention_cleanup(test_db, storage=test_storage, now=retention_ts)
    assert res_at_exact.audio_expired_meetings == 0
    test_db.refresh(meeting)
    assert meeting.audio_path is not None
    assert audio_file.exists()
    assert art_dir.exists()

    # 2. Sau đúng 1 giây: ĐÃ XÓA
    res_after_1s = run_retention_cleanup(
        test_db,
        storage=test_storage,
        now=retention_ts + timedelta(seconds=1),
    )
    assert res_after_1s.audio_expired_meetings == 1
    test_db.refresh(meeting)
    assert meeting.audio_path is None
    assert not audio_file.exists()
    assert not (Path(test_storage.base_dir) / "artifacts" / meeting_id).exists()


def test_retention_dry_run_makes_no_changes(
    test_db: Session,
    test_user: User,
    test_storage: Storage,
) -> None:
    """Test --dry-run: phát hiện meeting hết hạn nhưng không xóa file và không đổi DB."""
    meeting_id = str(uuid.uuid4())
    retention_ts = datetime(2026, 11, 1, 0, 0, 0, tzinfo=UTC)

    audio_file = test_storage.get_audio_path(meeting_id, "wav")
    audio_file.parent.mkdir(parents=True, exist_ok=True)
    audio_file.write_bytes(b"RIFFtest")

    meeting = Meeting(
        id=meeting_id,
        owner_id=test_user.id,
        title="Cuộc họp dry-run test",
        source="upload",
        status="ready",
        audio_path=f"audio/{meeting_id}/original.wav",
        retention_until=retention_ts,
        version=1,
    )
    test_db.add(meeting)
    test_db.commit()

    now_clock = datetime(2026, 11, 6, 0, 0, 0, tzinfo=UTC)
    res = run_retention_cleanup(test_db, storage=test_storage, now=now_clock, dry_run=True)
    assert res.dry_run is True
    assert res.audio_expired_meetings == 1

    test_db.refresh(meeting)
    # Khẳng định DB và file vẫn còn nguyên vẹn
    assert meeting.audio_path is not None
    assert audio_file.exists()


def test_priv14_expired_audio_returns_410_transcript_kept(
    test_db: Session,
    test_user: User,
    test_storage: Storage,
    auth_client: TestClient,
) -> None:
    """PRIV-14: Audio hết hạn bị xóa, GET /audio trả 410 AUDIO_EXPIRED, transcript DB còn nguyên."""
    meeting_id = str(uuid.uuid4())
    retention_ts = datetime(2026, 10, 1, 0, 0, 0, tzinfo=UTC)

    audio_file = test_storage.get_audio_path(meeting_id, "wav")
    audio_file.parent.mkdir(parents=True, exist_ok=True)
    audio_file.write_bytes(b"RIFFtest")

    meeting = Meeting(
        id=meeting_id,
        owner_id=test_user.id,
        title="Họp PRIV-14",
        source="upload",
        status="ready",
        audio_path=f"audio/{meeting_id}/original.wav",
        retention_until=retention_ts,
        version=1,
    )
    test_db.add(meeting)

    seg = Segment(
        id=str(uuid.uuid4()),
        meeting_id=meeting_id,
        idx=0,
        start_sec=0.0,
        end_sec=5.0,
        text="Transcript vẫn phải được giữ lại sau khi audio hết hạn.",
        ai_text="Transcript vẫn được giữ.",
        version=1,
    )
    test_db.add(seg)
    test_db.commit()

    # Chạy dọn dẹp tại thời điểm hiện tại
    now_clock = datetime(2026, 11, 6, 0, 0, 0, tzinfo=UTC)
    run_retention_cleanup(test_db, storage=test_storage, now=now_clock)

    # 1. Gọi GET /audio nhận 410 AUDIO_EXPIRED
    resp_audio = auth_client.get(f"/api/v1/meetings/{meeting_id}/audio")
    assert resp_audio.status_code == 410
    assert resp_audio.json()["error"]["code"] == "AUDIO_EXPIRED"

    # 2. Gọi GET /meetings/{id} kiểm tra audio.available == False
    resp_detail = auth_client.get(f"/api/v1/meetings/{meeting_id}")
    assert resp_detail.status_code == 200
    assert resp_detail.json()["audio"]["available"] is False

    # 3. Transcript trong DB vẫn còn nguyên vẹn
    resp_transcript = auth_client.get(f"/api/v1/meetings/{meeting_id}/transcript")
    assert resp_transcript.status_code == 200
    assert "Transcript vẫn phải được giữ lại" in resp_transcript.text


def test_retention_skips_meetings_with_active_jobs(
    test_db: Session,
    test_user: User,
    test_storage: Storage,
) -> None:
    """Cuộc họp hết hạn nhưng đang có job active (running) thì bỏ qua, không xóa audio."""
    meeting_id = str(uuid.uuid4())
    retention_ts = datetime(2026, 10, 1, 0, 0, 0, tzinfo=UTC)

    audio_file = test_storage.get_audio_path(meeting_id, "wav")
    audio_file.parent.mkdir(parents=True, exist_ok=True)
    audio_file.write_bytes(b"RIFFtest")

    meeting = Meeting(
        id=meeting_id,
        owner_id=test_user.id,
        title="Họp có job active",
        source="upload",
        status="processing",
        audio_path=f"audio/{meeting_id}/original.wav",
        retention_until=retention_ts,
        version=1,
    )
    test_db.add(meeting)

    job = Job(
        id=str(uuid.uuid4()),
        meeting_id=meeting_id,
        status="running",
        stage="asr",
        attempt=1,
        max_attempts=3,
    )
    test_db.add(job)
    test_db.commit()

    now_clock = datetime(2026, 11, 6, 0, 0, 0, tzinfo=UTC)
    res = run_retention_cleanup(test_db, storage=test_storage, now=now_clock)
    assert res.audio_expired_meetings == 0

    test_db.refresh(meeting)
    assert meeting.audio_path is not None
    assert audio_file.exists()


def test_retention_cleans_expired_idempotency_keys(
    test_db: Session,
    test_user: User,
    test_storage: Storage,
) -> None:
    """Xóa các bản ghi idempotency_keys cũ hơn 28 ngày, giữ lại các keys trong hạn."""
    now_clock = datetime(2026, 11, 6, 0, 0, 0, tzinfo=UTC)
    settings = get_settings()

    # 1. Key quá hạn (> 28 ngày)
    old_created = now_clock - timedelta(days=settings.OPERATIONAL_RETENTION_DAYS + 1)
    old_key = IdempotencyKey(
        id=str(uuid.uuid4()),
        user_id=test_user.id,
        key="key-too-old",
        endpoint="/api/v1/meetings",
        status="completed",
        response_code=201,
        created_at=old_created,
    )
    # 2. Key còn hạn (< 28 ngày)
    fresh_created = now_clock - timedelta(days=settings.OPERATIONAL_RETENTION_DAYS - 1)
    fresh_key = IdempotencyKey(
        id=str(uuid.uuid4()),
        user_id=test_user.id,
        key="key-still-valid",
        endpoint="/api/v1/meetings",
        status="completed",
        response_code=201,
        created_at=fresh_created,
    )
    test_db.add_all([old_key, fresh_key])
    test_db.commit()

    res = run_retention_cleanup(test_db, storage=test_storage, now=now_clock)
    assert res.operational_keys_cleaned == 1

    remaining_keys = test_db.execute(select(IdempotencyKey.key)).scalars().all()
    assert "key-still-valid" in remaining_keys
    assert "key-too-old" not in remaining_keys


def test_cleanup_cli_dry_run(
    test_db: Session,
    test_storage: Storage,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture,
) -> None:
    """Test CLI python -m app.scripts.cleanup --dry-run chạy thành công."""
    from contextlib import contextmanager

    from app.scripts.cleanup import main as cleanup_main

    @contextmanager
    def _mock_session_factory():
        yield test_db

    monkeypatch.setattr("app.scripts.cleanup.get_session_factory", lambda: _mock_session_factory)
    monkeypatch.setattr("app.scripts.cleanup.get_storage", lambda: test_storage)
    monkeypatch.setattr("sys.argv", ["cleanup.py", "--dry-run"])

    exit_code = cleanup_main()
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "[DRY-RUN]" in captured.out
    assert "Dọn dẹp hoàn tất:" in captured.out
