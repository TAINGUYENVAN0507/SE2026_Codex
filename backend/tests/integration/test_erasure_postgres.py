"""Xóa cuộc họp và xóa tài khoản trên Postgres đã migrate thật (AD-018, BE-18).

Các test xóa trong `tests/api/` và `tests/privacy/` dùng SQLite in-memory và tự viết lại
trigger `edit_events`. Ở đây schema, FK cascade và trigger lấy từ migration Alembic, nên
test bắt được lỗi chỉ có trên Postgres. Mọi bảng đều có dữ liệu, gồm `jobs`, `ai_outputs`
và `edit_events` mà các test SQLite chưa điền đủ.
"""

import json
import logging
import uuid
from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

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
from app.services.storage import LocalStorage, Storage, get_storage

CANARY = "CANARY_PG_ERASURE_5e1c"


@pytest.fixture
def storage(tmp_path: Path) -> Storage:
    return LocalStorage(base_dir=tmp_path)


def _client(db: Session, storage: Storage, user: User) -> TestClient:
    app = create_app()

    def _db() -> Generator[Session, None, None]:
        yield db

    app.dependency_overrides[get_db] = _db
    app.dependency_overrides[get_storage] = lambda: storage
    return TestClient(app, cookies={"session_token": create_access_token(user.id)})


def _user(db: Session, name: str) -> User:
    user = User(
        id=str(uuid.uuid4()),
        email=f"{name}-{uuid.uuid4().hex[:8]}@example.com",
        display_name=f"{name} {CANARY}" if name == "owner" else name,
        password_hash="x",
    )
    db.add(user)
    db.commit()
    return user


def _seed_meeting(db: Session, storage: Storage, owner: User, *, canary: bool = True) -> str:
    """Một cuộc họp có dữ liệu ở mọi bảng con, audio và artifact trên đĩa."""
    mark = CANARY if canary else "an toàn"
    meeting_id = str(uuid.uuid4())
    job_id = str(uuid.uuid4())
    db.add(
        Meeting(
            id=meeting_id,
            owner_id=owner.id,
            title=f"Họp {mark}",
            source="upload",
            status="ready",
            meeting_date="2026-11-13",
            duration_sec=10.0,
            audio_path=f"audio/{meeting_id}/original.wav",
            version=1,
        )
    )
    db.flush()
    db.add(
        Job(
            id=job_id,
            meeting_id=meeting_id,
            status="succeeded",
            stage="summarize",
            progress=1.0,
            attempt=1,
            max_attempts=3,
            error_message=f"lỗi {mark}",
        )
    )
    speaker_id = str(uuid.uuid4())
    db.add(
        Speaker(
            id=speaker_id,
            meeting_id=meeting_id,
            label="SPEAKER_00",
            default_name="Speaker 1",
            display_name=f"Người nói {mark}",
            version=1,
        )
    )
    db.flush()
    db.add_all(
        [
            Segment(
                id=str(uuid.uuid4()),
                meeting_id=meeting_id,
                idx=0,
                start_sec=0.0,
                end_sec=5.0,
                speaker_id=speaker_id,
                ai_speaker_id=speaker_id,
                text=f"Lời thoại {mark}",
                ai_text=f"AI {mark}",
                version=1,
            ),
            Summary(
                id=str(uuid.uuid4()),
                meeting_id=meeting_id,
                status="ready",
                content={"overview": f"Tóm tắt {mark}", "key_points": [], "decisions": []},
                ai_content={"overview": f"AI {mark}", "key_points": [], "decisions": []},
                version=1,
            ),
            ActionItem(
                id=str(uuid.uuid4()),
                meeting_id=meeting_id,
                description=f"Việc {mark}",
                status="open",
                source="ai",
                version=1,
            ),
            AIOutput(
                id=str(uuid.uuid4()),
                meeting_id=meeting_id,
                job_id=job_id,
                stage="summarize",
                payload={"overview": f"Thô {mark}"},
            ),
            EditEvent(
                id=str(uuid.uuid4()),
                meeting_id=meeting_id,
                actor_id=owner.id,
                entity_type="speaker",
                entity_id=speaker_id,
                action="update",
                field="display_name",
                before={"display_name": "Speaker 1"},
                after={"display_name": f"Người nói {mark}"},
                entity_version_after=2,
            ),
            IdempotencyKey(
                id=str(uuid.uuid4()),
                user_id=owner.id,
                key=f"KEY-{uuid.uuid4().hex}",
                endpoint="/api/v1/meetings",
                status="completed",
                response_code=201,
                response_body={"id": meeting_id, "title": f"Họp {mark}"},
            ),
        ]
    )
    db.commit()

    audio = storage.get_audio_path(meeting_id, "wav")
    audio.parent.mkdir(parents=True, exist_ok=True)
    audio.write_text(f"AUDIO {mark}", encoding="utf-8")
    art = Path(storage.base_dir) / "artifacts" / meeting_id / job_id
    art.mkdir(parents=True, exist_ok=True)
    (art / "transcript.json").write_text(json.dumps({"text": mark}), encoding="utf-8")
    return meeting_id


def _canary_hits(db: Session, storage: Storage) -> list[str]:
    db.expire_all()
    hits = []
    for table in Base.metadata.sorted_tables:
        for row in db.execute(select(table)).fetchall():
            for col, val in dict(row._mapping).items():
                text = json.dumps(val, default=str) if isinstance(val, dict | list) else str(val)
                if CANARY in text:
                    hits.append(f"{table.name}.{col}")
    for path in Path(storage.base_dir).rglob("*"):
        if CANARY in path.name or (
            path.is_file() and CANARY in path.read_text(encoding="utf-8", errors="ignore")
        ):
            hits.append(str(path.relative_to(storage.base_dir)))
    return hits


def _counts(db: Session, meeting_id: str) -> dict[str, int]:
    models = [Job, Speaker, Segment, Summary, ActionItem, AIOutput, EditEvent]
    return {
        m.__tablename__: len(db.execute(select(m).where(m.meeting_id == meeting_id)).all())
        for m in models
    }


def test_delete_meeting_on_migrated_postgres(
    db_session: Session, storage: Storage, caplog: pytest.LogCaptureFixture
) -> None:
    owner = _user(db_session, "owner")
    meeting_id = _seed_meeting(db_session, storage, owner)
    other_id = _seed_meeting(db_session, storage, owner, canary=False)
    assert set(_counts(db_session, meeting_id).values()) == {1}

    with caplog.at_level(logging.INFO):
        res = _client(db_session, storage, owner).delete(f"/api/v1/meetings/{meeting_id}")
    assert res.status_code == 204, res.text

    assert db_session.get(Meeting, meeting_id) is None
    assert set(_counts(db_session, meeting_id).values()) == {0}
    # Cuộc họp khác của cùng người dùng còn nguyên, kể cả edit_events (trigger chỉ cho xóa
    # khi meeting cha đã bị xóa).
    assert set(_counts(db_session, other_id).values()) == {1}
    hits = [h for h in _canary_hits(db_session, storage) if not h.startswith("users.")]
    assert hits == []
    assert not (Path(storage.base_dir) / "audio" / meeting_id).exists()
    assert not (Path(storage.base_dir) / "artifacts" / meeting_id).exists()
    assert (Path(storage.base_dir) / "audio" / other_id).exists()
    assert CANARY not in caplog.text


def test_delete_account_on_migrated_postgres(
    db_session: Session, storage: Storage, caplog: pytest.LogCaptureFixture
) -> None:
    owner = _user(db_session, "owner")
    bystander = _user(db_session, "bystander")
    owned = [_seed_meeting(db_session, storage, owner) for _ in range(2)]
    kept = _seed_meeting(db_session, storage, bystander, canary=False)

    with caplog.at_level(logging.INFO):
        res = _client(db_session, storage, owner).delete("/api/v1/auth/me")
    assert res.status_code == 204, res.text

    assert db_session.get(User, owner.id) is None
    for meeting_id in owned:
        assert db_session.get(Meeting, meeting_id) is None
        assert set(_counts(db_session, meeting_id).values()) == {0}
    assert _canary_hits(db_session, storage) == []
    assert (
        db_session.execute(select(IdempotencyKey).where(IdempotencyKey.user_id == owner.id)).first()
        is None
    )
    assert db_session.get(User, bystander.id) is not None
    assert set(_counts(db_session, kept).values()) == {1}
    assert CANARY not in caplog.text
