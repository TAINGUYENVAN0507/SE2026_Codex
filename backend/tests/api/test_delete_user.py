"""Kiểm thử xóa tài khoản người dùng và toàn bộ dữ liệu thuộc sở hữu (BE-18, PRIV-10, PRIV-12).

Bao gồm:
- Canary test: tiêu đề, transcript, tóm tắt, action item, idempotency_keys, audio, artifacts,
  thông tin user chứa CANARY_PERSONAL_7f3a; sau khi xóa thì chuỗi này không còn trong mọi bảng DB,
  cây appdata/ và log.
- Người dùng khác không bị ảnh hưởng (PRIV-12).
- Gọi lần thứ 2 với token cũ trả về 401 UNAUTHENTICATED.
- Cookie session_token bị xóa trong phản hồi.
"""

import json
import logging
import uuid
from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import create_access_token, hash_password
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


@pytest.fixture
def test_storage(tmp_path: Path) -> Storage:
    """Fixture cung cấp Storage với thư mục tạm riêng biệt."""
    storage_dir = tmp_path / "appdata"
    storage_dir.mkdir(parents=True, exist_ok=True)
    return LocalStorage(base_dir=storage_dir)


@pytest.fixture
def test_db() -> Generator[Session, None, None]:
    """Tạo database SQLite in-memory độc lập cho mỗi test case."""
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
        AIOutput.__table__,
        Summary.__table__,
        ActionItem.__table__,
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
def users(test_db: Session) -> dict[str, User]:
    """Tạo 2 người dùng để kiểm thử cô lập dữ liệu (PRIV-12)."""
    user_a = User(
        id=str(uuid.uuid4()),
        email="user_a@example.com",
        display_name="User A",
        password_hash=hash_password("PassA_123!"),
    )
    user_b = User(
        id=str(uuid.uuid4()),
        email="user_b@example.com",
        display_name="User B Khác",
        password_hash=hash_password("PassB_123!"),
    )
    test_db.add_all([user_a, user_b])
    test_db.commit()
    return {"a": user_a, "b": user_b}


def create_client(
    app,
    user: User | None,
    storage: Storage,
    db: Session,
) -> TestClient:
    """Tạo TestClient gắn session_token của user."""

    def _override_get_db() -> Generator[Session, None, None]:
        yield db

    def _override_get_storage() -> Storage:
        return storage

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_storage] = _override_get_storage

    cookies = {}
    if user:
        token = create_access_token(user.id)
        cookies["session_token"] = token

    return TestClient(app, cookies=cookies)


def test_delete_me_canary_erased_from_all_stores_and_other_user_intact(
    test_db: Session,
    users: dict[str, User],
    test_storage: Storage,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Canary test (BE-18, PRIV-10, PRIV-12):
    Toàn bộ dữ liệu của User A chứa CANARY_PERSONAL_7f3a bị xóa sạch khỏi mọi bảng,
    appdata/ và log. Dữ liệu của User B vẫn nguyên vẹn. Gọi lần 2 trả 401.
    """
    canary = "CANARY_PERSONAL_7f3a"
    user_a = users["a"]
    user_b = users["b"]

    # Đặt canary vào User A
    user_a.display_name = f"Người dùng {canary}"
    test_db.commit()

    # Tạo cuộc họp của User A chứa canary
    meeting_a_id = str(uuid.uuid4())
    meeting_a = Meeting(
        id=meeting_a_id,
        owner_id=user_a.id,
        title=f"Tiêu đề User A {canary}",
        source="upload",
        status="ready",
        meeting_date="2026-11-07",
        version=1,
    )
    test_db.add(meeting_a)
    test_db.flush()

    # Thêm speaker, segment, summary, action item của User A
    spk_a = Speaker(
        id=str(uuid.uuid4()),
        meeting_id=meeting_a_id,
        label="SPEAKER_00",
        default_name="Speaker 1",
        display_name=f"Người nói {canary}",
        version=1,
    )
    test_db.add(spk_a)
    test_db.flush()

    seg_a = Segment(
        id=str(uuid.uuid4()),
        meeting_id=meeting_a_id,
        idx=0,
        start_sec=0.0,
        end_sec=10.0,
        speaker_id=spk_a.id,
        ai_speaker_id=spk_a.id,
        text=f"Lời thoại {canary}",
        ai_text=f"AI gốc {canary}",
        version=1,
    )
    test_db.add(seg_a)

    summary_a = Summary(
        id=str(uuid.uuid4()),
        meeting_id=meeting_a_id,
        status="ready",
        content={"overview": f"Tóm tắt {canary}"},
        ai_content={"overview": f"AI Tóm tắt {canary}"},
        version=1,
    )
    test_db.add(summary_a)

    action_a = ActionItem(
        id=str(uuid.uuid4()),
        meeting_id=meeting_a_id,
        description=f"Công việc {canary}",
        status="open",
        version=1,
    )
    test_db.add(action_a)

    # Idempotency key của User A
    idem_a = IdempotencyKey(
        id=str(uuid.uuid4()),
        user_id=user_a.id,
        key=f"IDEM_{canary}",
        endpoint="/api/v1/meetings",
        status="completed",
        response_code=201,
        response_body={"meeting_id": meeting_a_id, "detail": canary},
    )
    test_db.add(idem_a)

    # Thêm file audio và artifact của User A chứa canary
    audio_path = test_storage.get_audio_path(meeting_a_id, "wav")
    audio_path.parent.mkdir(parents=True, exist_ok=True)
    audio_path.write_text(f"AUDIO_BYTES_{canary}", encoding="utf-8")

    art_dir = Path(test_storage.base_dir) / "artifacts" / meeting_a_id / "job-1"
    art_dir.mkdir(parents=True, exist_ok=True)
    (art_dir / "transcript.json").write_text(f'{{"text": "{canary}"}}', encoding="utf-8")

    # Tạo cuộc họp của User B (để kiểm chứng User B không bị ảnh hưởng - PRIV-12)
    meeting_b_id = str(uuid.uuid4())
    meeting_b = Meeting(
        id=meeting_b_id,
        owner_id=user_b.id,
        title="Cuộc họp an toàn của User B",
        source="upload",
        status="ready",
        meeting_date="2026-11-07",
        version=1,
    )
    test_db.add(meeting_b)
    test_db.commit()

    app = create_app()
    client_a = create_client(app, user_a, test_storage, test_db)

    # Thực hiện DELETE /api/v1/auth/me
    with caplog.at_level(logging.INFO):
        res = client_a.delete("/api/v1/auth/me")
        assert res.status_code == 204

    # Cookie session_token bị xóa
    set_cookie = res.headers.get("set-cookie", "")
    assert "session_token=" in set_cookie

    # 1. Duyệt tất cả các bảng trong Base.metadata: chuỗi canary không còn xuất hiện ở bất cứ đâu
    test_db.expire_all()
    for table in Base.metadata.sorted_tables:
        rows = test_db.execute(select(table)).fetchall()
        for row in rows:
            row_dict = dict(row._mapping)
            for col_name, val in row_dict.items():
                val_str = json.dumps(val) if isinstance(val, (dict, list)) else str(val)
                assert canary not in val_str, (
                    f"Canary vẫn còn sót lại trong bảng {table.name}, cột {col_name}: {val_str}"
                )

    # 2. Cây appdata/ không còn chứa canary trong tên file hoặc nội dung
    storage_root = Path(test_storage.base_dir)
    if storage_root.exists():
        for p in storage_root.rglob("*"):
            assert canary not in p.name, f"Canary còn trong tên đường dẫn: {p}"
            if p.is_file():
                content = p.read_text(encoding="utf-8", errors="ignore")
                assert canary not in content, f"Canary còn trong nội dung file: {p}"

    assert not (storage_root / "audio" / meeting_a_id).exists()
    assert not (storage_root / "artifacts" / meeting_a_id).exists()

    # 3. Log không chứa canary (PRIV-10)
    assert canary not in caplog.text
    # Log có ghi user_id
    assert user_a.id in caplog.text

    # 4. User B hoàn toàn nguyên vẹn (PRIV-12)
    user_b_db = test_db.get(User, user_b.id)
    assert user_b_db is not None
    assert user_b_db.email == "user_b@example.com"
    meeting_b_db = test_db.get(Meeting, meeting_b_id)
    assert meeting_b_db is not None

    # 5. Gọi lại lần 2 với token cũ trả về 401 UNAUTHENTICATED
    res_second = client_a.delete("/api/v1/auth/me")
    assert res_second.status_code == 401
    assert res_second.json()["error"]["code"] == "UNAUTHENTICATED"


def test_delete_me_unauthenticated_returns_401(
    test_db: Session,
    test_storage: Storage,
) -> None:
    """Gọi DELETE /auth/me mà không có cookie trả về 401."""
    app = create_app()
    unauthed_client = create_client(app, None, test_storage, test_db)
    res = unauthed_client.delete("/api/v1/auth/me")
    assert res.status_code == 401
    assert res.json()["error"]["code"] == "UNAUTHENTICATED"
