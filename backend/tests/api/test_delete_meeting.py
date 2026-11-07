"""Kiểm thử API xóa cuộc họp DELETE /meetings/{id} (BE-14).

Bao gồm:
- Xóa thành công: hủy job, xóa file audio, xóa artifacts và toàn bộ các hàng liên quan trong DB.
- Trigger chặn DELETE của edit_events cho phép xóa khi meeting bị xóa.
- RT-15: Hủy job đang xử lý, không để lại file hay bản ghi mồ côi.
- PRIV-13: GET /audio sau khi xóa trả về 404.
- PRIV-12: Trả về 404 khi người dùng khác cố gắng xóa cuộc họp không thuộc sở hữu.
- Trả về 401 khi chưa xác thực.
- Log chỉ ghi meeting id, không ghi tiêu đề hay nội dung nhạy cảm.
"""

import io
import json
import logging
import shutil
import uuid
from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import get_current_user
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
from app.services.audio_validator import AudioProbeResult
from app.services.storage import Storage, get_storage
from app.services.storage.local import LocalStorage


@pytest.fixture
def test_storage(tmp_path: Path) -> Storage:
    """Tạo storage tạm thời cho test."""
    return LocalStorage(base_dir=tmp_path)


@pytest.fixture
def test_db() -> Generator[Session, None, None]:
    """Tạo database SQLite in-memory dùng chung cho test."""
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

    # Tạo trigger kiểm tra DELETE edit_events có điều kiện theo migration 0005
    with engine.connect() as conn:
        conn.exec_driver_sql("""
        CREATE TRIGGER trg_prevent_edit_events_delete
        BEFORE DELETE ON edit_events
        WHEN EXISTS (SELECT 1 FROM meetings WHERE id = OLD.meeting_id)
        BEGIN
            SELECT RAISE(
                ABORT,
                'edit_events table is append-only and does not allow DELETE operations.'
            );
        END;
        """)

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
    """Tạo 2 user phục vụ kiểm thử phân quyền."""
    user_a = User(
        id=str(uuid.uuid4()),
        email="user_a@example.com",
        display_name="User A",
        password_hash="mock_hash",
    )
    user_b = User(
        id=str(uuid.uuid4()),
        email="user_b@example.com",
        display_name="User B",
        password_hash="mock_hash",
    )
    test_db.add_all([user_a, user_b])
    test_db.commit()
    return {"a": user_a, "b": user_b}


def create_auth_client(
    app, user: User, storage: Storage, session_maker_or_db: Session
) -> TestClient:
    """Tạo TestClient đã được xác thực với user tương ứng."""
    token = create_access_token(user_id=user.id)

    def _override_current_user():
        return user

    def _override_get_db():
        yield session_maker_or_db

    def _override_get_storage():
        return storage

    app.dependency_overrides[get_current_user] = _override_current_user
    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_storage] = _override_get_storage

    return TestClient(app, headers={"Authorization": f"Bearer {token}"})


def test_delete_meeting_success(
    test_db: Session, users: dict[str, User], test_storage: Storage
) -> None:
    """Xóa cuộc họp thành công: xóa toàn bộ file và các bản ghi trong DB."""
    owner = users["a"]
    meeting_id = str(uuid.uuid4())
    meeting = Meeting(
        id=meeting_id,
        owner_id=owner.id,
        title="Cuộc họp cần xóa hoàn toàn",
        source="upload",
        status="ready",
        audio_path=f"audio/{meeting_id}.wav",
        version=1,
    )
    test_db.add(meeting)

    # 1. Tạo file audio trên đĩa
    audio_path = test_storage.get_audio_path(meeting_id, "wav")
    audio_path.parent.mkdir(parents=True, exist_ok=True)
    audio_path.write_bytes(b"RIFFdummy_audio_bytes")

    # 2. Tạo artifacts trên đĩa
    job_id = str(uuid.uuid4())
    job_dir = Path(test_storage.base_dir) / "artifacts" / meeting_id / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    (job_dir / "transcript.json").write_text("{}", encoding="utf-8")

    # 3. Tạo các bản ghi DB liên quan
    job = Job(
        id=job_id,
        meeting_id=meeting_id,
        status="succeeded",
        stage="summarize",
        progress=1.0,
        attempt=1,
        max_attempts=3,
    )
    speaker = Speaker(
        id=str(uuid.uuid4()),
        meeting_id=meeting_id,
        label="SPEAKER_00",
        default_name="Speaker 1",
        display_name="Anh Nam",
        version=1,
    )
    segment = Segment(
        id=str(uuid.uuid4()),
        meeting_id=meeting_id,
        idx=0,
        start_sec=0.0,
        end_sec=5.0,
        text="Nội dung thảo luận",
        ai_text="Nội dung thảo luận",
        version=1,
    )
    summary = Summary(
        id=str(uuid.uuid4()),
        meeting_id=meeting_id,
        status="ready",
        content={"overview": "Tổng quan", "key_points": [], "decisions": []},
        version=1,
    )
    action_item = ActionItem(
        id=str(uuid.uuid4()),
        meeting_id=meeting_id,
        description="Gửi báo cáo",
        status="open",
        source="ai",
        version=1,
    )
    edit_event = EditEvent(
        id=str(uuid.uuid4()),
        meeting_id=meeting_id,
        actor_id=owner.id,
        entity_type="speaker",
        entity_id=speaker.id,
        action="update",
        field="display_name",
        before={"display_name": "Speaker 1"},
        after={"display_name": "Anh Nam"},
        entity_version_after=2,
    )
    test_db.add_all([job, speaker, segment, summary, action_item, edit_event])
    test_db.commit()

    # Thực hiện gọi DELETE API
    app = create_app()
    client = create_auth_client(app, owner, test_storage, test_db)
    response = client.delete(f"/api/v1/meetings/{meeting_id}")
    assert response.status_code == 204

    # Kiểm tra meeting không còn trong DB
    test_db.expire_all()
    assert (
        test_db.execute(select(Meeting).where(Meeting.id == meeting_id)).scalar_one_or_none()
        is None
    )

    # Kiểm tra các hàng liên quan không còn tồn tại
    assert test_db.execute(select(Job).where(Job.meeting_id == meeting_id)).first() is None
    assert test_db.execute(select(Speaker).where(Speaker.meeting_id == meeting_id)).first() is None
    assert test_db.execute(select(Segment).where(Segment.meeting_id == meeting_id)).first() is None
    assert test_db.execute(select(Summary).where(Summary.meeting_id == meeting_id)).first() is None
    assert (
        test_db.execute(select(ActionItem).where(ActionItem.meeting_id == meeting_id)).first()
        is None
    )
    assert (
        test_db.execute(select(EditEvent).where(EditEvent.meeting_id == meeting_id)).first() is None
    )

    # Kiểm tra file trên đĩa đã bị xóa hoàn toàn
    assert not test_storage.get_audio_dir(meeting_id).exists()
    assert not (Path(test_storage.base_dir) / "artifacts" / meeting_id).exists()


def test_delete_meeting_priv13_audio_returns_404(
    test_db: Session, users: dict[str, User], test_storage: Storage
) -> None:
    """PRIV-13: Sau khi xóa meeting, GET /audio trả về 404."""
    owner = users["a"]
    meeting_id = str(uuid.uuid4())
    meeting = Meeting(
        id=meeting_id,
        owner_id=owner.id,
        title="Họp test PRIV-13",
        source="upload",
        status="ready",
        audio_path=f"audio/{meeting_id}.wav",
        version=1,
    )
    test_db.add(meeting)

    audio_path = test_storage.get_audio_path(meeting_id, "wav")
    audio_path.parent.mkdir(parents=True, exist_ok=True)
    audio_path.write_bytes(b"RIFFheader_data")
    test_db.commit()

    app = create_app()
    client = create_auth_client(app, owner, test_storage, test_db)

    # Trước khi xóa: GET /audio thành công 200
    res_before = client.get(f"/api/v1/meetings/{meeting_id}/audio")
    assert res_before.status_code == 200

    # Xóa cuộc họp
    res_delete = client.delete(f"/api/v1/meetings/{meeting_id}")
    assert res_delete.status_code == 204

    # Sau khi xóa: GET /audio trả về 404
    res_after = client.get(f"/api/v1/meetings/{meeting_id}/audio")
    assert res_after.status_code == 404
    assert res_after.json()["error"]["code"] == "NOT_FOUND"


def test_delete_meeting_priv12_owner_scoping(
    test_db: Session, users: dict[str, User], test_storage: Storage
) -> None:
    """PRIV-12: Người dùng khác không thể xóa cuộc họp của người khác, trả về 404."""
    owner = users["a"]
    attacker = users["b"]
    meeting_id = str(uuid.uuid4())
    meeting = Meeting(
        id=meeting_id,
        owner_id=owner.id,
        title="Cuộc họp của User A",
        source="upload",
        status="ready",
        version=1,
    )
    test_db.add(meeting)
    test_db.commit()

    app = create_app()
    client_b = create_auth_client(app, attacker, test_storage, test_db)

    res = client_b.delete(f"/api/v1/meetings/{meeting_id}")
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "MEETING_NOT_FOUND"

    # Cuộc họp vẫn còn nguyên trong DB
    test_db.expire_all()
    assert (
        test_db.execute(select(Meeting).where(Meeting.id == meeting_id)).scalar_one_or_none()
        is not None
    )


def test_delete_meeting_unauthenticated_returns_401(
    test_db: Session, users: dict[str, User], test_storage: Storage
) -> None:
    """Request không có JWT token trả về 401."""
    meeting_id = str(uuid.uuid4())
    app = create_app()

    def _override_get_db():
        yield test_db

    app.dependency_overrides[get_db] = _override_get_db
    client = TestClient(app)

    res = client.delete(f"/api/v1/meetings/{meeting_id}")
    assert res.status_code == 401


def test_delete_meeting_not_found_returns_404(
    test_db: Session, users: dict[str, User], test_storage: Storage
) -> None:
    """Xóa meeting không tồn tại trả về 404."""
    owner = users["a"]
    app = create_app()
    client = create_auth_client(app, owner, test_storage, test_db)

    res = client.delete(f"/api/v1/meetings/{uuid.uuid4()}")
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "MEETING_NOT_FOUND"


def test_rt15_delete_meeting_cancels_running_job(
    test_db: Session, users: dict[str, User], test_storage: Storage
) -> None:
    """RT-15: Xóa khi job đang chạy -> job bị chuyển cancelled, không còn file hay row mồ côi."""
    owner = users["a"]
    meeting_id = str(uuid.uuid4())
    meeting = Meeting(
        id=meeting_id,
        owner_id=owner.id,
        title="Cuộc họp đang chạy tiến trình RT-15",
        source="upload",
        status="processing",
        version=1,
    )
    test_db.add(meeting)

    job_id = str(uuid.uuid4())
    running_job = Job(
        id=job_id,
        meeting_id=meeting_id,
        status="running",
        stage="asr",
        progress=0.3,
        attempt=1,
        max_attempts=3,
    )
    test_db.add(running_job)

    # Tạo audio và artifacts
    audio_path = test_storage.get_audio_path(meeting_id, "wav")
    audio_path.parent.mkdir(parents=True, exist_ok=True)
    audio_path.write_bytes(b"RIFFtest_audio")

    artifacts_dir = Path(test_storage.base_dir) / "artifacts" / meeting_id / job_id
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    (artifacts_dir / "vad.json").write_text("{}", encoding="utf-8")
    test_db.commit()

    app = create_app()
    client = create_auth_client(app, owner, test_storage, test_db)

    response = client.delete(f"/api/v1/meetings/{meeting_id}")
    assert response.status_code == 204

    # Kiểm tra không còn file hay row mồ côi nào
    test_db.expire_all()
    assert (
        test_db.execute(select(Meeting).where(Meeting.id == meeting_id)).scalar_one_or_none()
        is None
    )
    assert test_db.execute(select(Job).where(Job.id == job_id)).scalar_one_or_none() is None
    assert not test_storage.get_audio_dir(meeting_id).exists()
    assert not (Path(test_storage.base_dir) / "artifacts" / meeting_id).exists()


def test_delete_meeting_logging_privacy(
    test_db: Session,
    users: dict[str, User],
    test_storage: Storage,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Log chỉ ghi meeting_id, không ghi tiêu đề cuộc họp."""
    owner = users["a"]
    meeting_id = str(uuid.uuid4())
    sensitive_title = "Kế hoạch bí mật công nghệ 2026 TOP SECRET"
    meeting = Meeting(
        id=meeting_id,
        owner_id=owner.id,
        title=sensitive_title,
        source="upload",
        status="ready",
        version=1,
    )
    test_db.add(meeting)
    test_db.commit()

    app = create_app()
    client = create_auth_client(app, owner, test_storage, test_db)

    with caplog.at_level(logging.INFO, logger="backend.api.meetings"):
        response = client.delete(f"/api/v1/meetings/{meeting_id}")
        assert response.status_code == 204

    # Xác minh log chứa meeting_id nhưng KHÔNG chứa tiêu đề nhạy cảm
    logs = caplog.text
    assert meeting_id in logs
    assert sensitive_title not in logs


def test_erasure_removes_canary_from_all_stores_and_logs(
    test_db: Session,
    users: dict[str, User],
    test_storage: Storage,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Canary test (BE-18, PRIV-10): tiêu đề, transcript, tóm tắt, action item, idempotency_keys
    và file chứa CANARY_PERSONAL_7f3a; sau khi xóa thì chuỗi này không còn trong mọi bảng DB,
    cây appdata/ và log đã capture.
    """
    canary = "CANARY_PERSONAL_7f3a"
    owner = users["a"]
    meeting_id = str(uuid.uuid4())
    meeting = Meeting(
        id=meeting_id,
        owner_id=owner.id,
        title=f"Tiêu đề chứa {canary}",
        source="upload",
        status="ready",
        meeting_date="2026-10-15",
        duration_sec=120.0,
        version=1,
    )
    test_db.add(meeting)
    test_db.flush()

    spk = Speaker(
        id=str(uuid.uuid4()),
        meeting_id=meeting.id,
        label="SPEAKER_00",
        default_name="Speaker 1",
        display_name=f"Người nói {canary}",
        version=1,
    )
    test_db.add(spk)
    test_db.flush()

    seg = Segment(
        id=str(uuid.uuid4()),
        meeting_id=meeting.id,
        idx=0,
        start_sec=0.0,
        end_sec=5.0,
        speaker_id=spk.id,
        ai_speaker_id=spk.id,
        text=f"Nội dung lời thoại chứa {canary}",
        ai_text=f"Nội dung AI gốc chứa {canary}",
        version=1,
    )
    test_db.add(seg)

    summary = Summary(
        id=str(uuid.uuid4()),
        meeting_id=meeting.id,
        status="ready",
        content={"overview": f"Tổng quan {canary}", "key_points": [], "decisions": []},
        ai_content={"overview": f"AI {canary}", "key_points": [], "decisions": []},
        version=1,
    )
    test_db.add(summary)

    action = ActionItem(
        id=str(uuid.uuid4()),
        meeting_id=meeting.id,
        description=f"Công việc chứa {canary}",
        assignee_name="Anh A",
        status="open",
        source="ai",
        version=1,
    )
    test_db.add(action)

    # Thêm idempotency key chứa canary
    idem_key = IdempotencyKey(
        id=str(uuid.uuid4()),
        user_id=owner.id,
        key=f"KEY_{canary}",
        endpoint="/api/v1/meetings",
        status="completed",
        response_code=201,
        response_body={"id": meeting_id, "title": f"Tiêu đề chứa {canary}"},
    )
    test_db.add(idem_key)
    test_db.commit()

    # Tạo file audio và artifact chứa canary
    audio_path = test_storage.get_audio_path(meeting_id, "wav")
    audio_path.parent.mkdir(parents=True, exist_ok=True)
    audio_path.write_text(f"AUDIO_DATA_{canary}", encoding="utf-8")

    art_dir = Path(test_storage.base_dir) / "artifacts" / meeting_id / "job-1"
    art_dir.mkdir(parents=True, exist_ok=True)
    (art_dir / "transcript.json").write_text(f'{{"text": "{canary}"}}', encoding="utf-8")

    app = create_app()
    client = create_auth_client(app, owner, test_storage, test_db)

    with caplog.at_level(logging.INFO):
        res = client.delete(f"/api/v1/meetings/{meeting_id}")
        assert res.status_code == 204

    # 1. Kiểm tra toàn bộ các bảng trong Base.metadata
    test_db.expire_all()
    for table in Base.metadata.sorted_tables:
        rows = test_db.execute(select(table)).fetchall()
        for row in rows:
            row_dict = dict(row._mapping)
            for col_name, val in row_dict.items():
                val_str = json.dumps(val) if isinstance(val, (dict, list)) else str(val)
                assert canary not in val_str, (
                    f"Tìm thấy canary trong bảng {table.name}, cột {col_name}: {val_str}"
                )

    # 2. Kiểm tra cây thư mục appdata/ (storage base_dir)
    storage_root = Path(test_storage.base_dir)
    if storage_root.exists():
        for path in storage_root.rglob("*"):
            assert canary not in path.name, f"Tìm thấy canary trong tên file/thư mục: {path}"
            if path.is_file():
                content = path.read_text(encoding="utf-8", errors="ignore")
                assert canary not in content, f"Tìm thấy canary trong nội dung file: {path}"

    # Thư mục artifacts/{meeting_id} và audio/{meeting_id} không còn tồn tại
    assert not (storage_root / "artifacts" / meeting_id).exists()
    assert not (storage_root / "audio" / meeting_id).exists()

    # 3. Kiểm tra log đã capture không chứa canary
    assert canary not in caplog.text
    # Log có ghi meeting_id
    assert meeting_id in caplog.text


def test_erasure_replay_idempotency_key_creates_new_meeting(
    test_db: Session,
    users: dict[str, User],
    test_storage: Storage,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test replay (BE-18): Sau khi xóa meeting, gửi lại cùng Idempotency-Key thì
    tạo meeting mới, không trả lại dữ liệu cũ đã bị xóa.
    """
    owner = users["a"]
    idem_key_str = f"test-key-{uuid.uuid4()}"

    # Mock ffprobe cho endpoint upload meeting
    if shutil.which("ffprobe") is None:

        def _mock_probe(file_path, timeout_sec=10.0, ffprobe_bin=None):
            return AudioProbeResult(
                duration_sec=60.0,
                format_name="wav",
                sample_rate=16000,
                channels=1,
            )

        monkeypatch.setattr("app.api.v1.meetings.probe_audio", _mock_probe)

    app = create_app()
    client = create_auth_client(app, owner, test_storage, test_db)

    # 1. Tạo meeting đầu tiên với Idempotency-Key
    audio_content = (
        b"RIFF$\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00\x80>\x00\x00\x00}"
        b"\x00\x00\x02\x00\x10\x00data\x00\x00\x00\x00"
    )
    files = {"file": ("test.wav", io.BytesIO(audio_content), "audio/wav")}
    data = {"title": "Cuộc họp lần 1", "consent_confirmed": "true"}
    headers = {"Idempotency-Key": idem_key_str}

    res1 = client.post("/api/v1/meetings", data=data, files=files, headers=headers)
    assert res1.status_code == 201, res1.text
    meeting_id_1 = res1.json()["meeting"]["id"]

    # 2. Xóa meeting_id_1
    del_res = client.delete(f"/api/v1/meetings/{meeting_id_1}")
    assert del_res.status_code == 204

    # 3. Gửi lại request với CÙNG Idempotency-Key
    files_replay = {"file": ("test.wav", io.BytesIO(audio_content), "audio/wav")}
    data_replay = {"title": "Cuộc họp lần 2 sau khi xóa", "consent_confirmed": "true"}
    res2 = client.post("/api/v1/meetings", data=data_replay, files=files_replay, headers=headers)

    # Khẳng định tạo meeting MỚI với HTTP 201, ID mới khác ID cũ
    assert res2.status_code == 201
    meeting_id_2 = res2.json()["meeting"]["id"]
    assert meeting_id_2 != meeting_id_1
    assert res2.json()["meeting"]["title"] == "Cuộc họp lần 2 sau khi xóa"
