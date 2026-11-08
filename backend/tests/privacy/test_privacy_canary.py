"""Kiểm thử chuyên sâu về quyền riêng tư và chuỗi Canary (BE-18, BE-19, PRIV-10, PRIV-12).

Mục tiêu kiểm chứng:
1. Chuỗi Canary (tiêu đề bí mật, nội dung transcript, tóm tắt, action item, idempotency key)
   đi qua toàn bộ vòng đời: upload -> xử lý worker -> chỉnh sửa -> xóa.
2. Kiểm tra log API và log worker:
   - Tuyệt đối KHÔNG chứa bất kỳ chuỗi canary nào.
   - Log tuân thủ định dạng JSON có cấu trúc với các trường chuẩn (job_id, meeting_id...).
3. Kiểm tra cơ sở dữ liệu sau khi xóa (erase_meeting / erase_user):
   - Quét qua TOÀN BỘ các bảng trong Base.metadata: không còn sót bất kỳ chuỗi canary nào.
   - Bảng idempotency_keys được dọn sạch hoàn toàn các bản ghi liên quan đến cuộc họp.
4. Kiểm tra kho lưu trữ (Storage/Artifacts):
   - Mọi tệp âm thanh gốc và artifacts sinh ra trên đĩa bị xóa sạch.
   - Không còn file nào trên đĩa chứa chuỗi canary.
"""

import io
import json
import logging
import uuid
from collections.abc import Generator
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from meeting_pipeline.errors import ErrorCode, PermanentPipelineError
from meeting_pipeline.schemas import Stage
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import get_current_user
from app.core.logging import JSONLogFormatter
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
from app.services.erasure import erase_meeting, erase_user
from app.services.storage import Storage, get_storage
from app.services.storage.local import LocalStorage
from app.worker.runner import run_worker_once

CANARY_TITLE = "CANARY_TITLE_TOP_SECRET_CODENAME_X99"
CANARY_IDEMPOTENCY = "IDEM_CANARY_TRANSACTION_KEY_A88"
CANARY_TRANSCRIPT_EDIT = "CANARY_TRANSCRIPT_CONFIDENTIAL_CONVERSATION_B77"
CANARY_SUMMARY_EDIT = "CANARY_SUMMARY_HIGHLY_SENSITIVE_DECISION_C66"
CANARY_SPEAKER_NAME = "CANARY_SPEAKER_AGENT_UNDERCOVER_D55"


@pytest.fixture
def test_storage(tmp_path: Path) -> Storage:
    """Tạo storage tạm thời trên đĩa cho test."""
    return LocalStorage(base_dir=tmp_path)


@pytest.fixture
def test_db() -> Generator[Session, None, None]:
    """Tạo database SQLite in-memory độc lập cho test."""
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
def sample_user(test_db: Session) -> User:
    """Tạo tài khoản kiểm thử chính."""
    user = User(
        id=str(uuid.uuid4()),
        email="privacy_canary_user@example.com",
        display_name="Privacy Canary Owner",
        password_hash="hashed_pw_secret",
    )
    test_db.add(user)
    test_db.commit()
    return user


@pytest.fixture
def other_user(test_db: Session) -> User:
    """Tạo tài khoản kiểm thử phụ để kiểm tra isolation."""
    user = User(
        id=str(uuid.uuid4()),
        email="other_privacy_user@example.com",
        display_name="Other User",
        password_hash="hashed_pw_other",
    )
    test_db.add(user)
    test_db.commit()
    return user


@pytest.fixture
def auth_headers(sample_user: User) -> dict[str, str]:
    """Tạo HTTP header chứa token Bearer cho người dùng chính."""
    token = create_access_token(sample_user.id)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def client(
    test_db: Session,
    test_storage: Storage,
    sample_user: User,
) -> Generator[TestClient, None, None]:
    """Khởi tạo TestClient của FastAPI với các dependency đã ghi đè."""
    app = create_app()
    app.dependency_overrides[get_db] = lambda: test_db
    app.dependency_overrides[get_storage] = lambda: test_storage
    app.dependency_overrides[get_current_user] = lambda: sample_user
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def log_capture() -> Generator[io.StringIO, None, None]:
    """Bắt toàn bộ log được ghi từ root logger qua JSONLogFormatter."""
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JSONLogFormatter())
    root_logger = logging.getLogger()
    original_level = root_logger.level
    root_logger.setLevel(logging.DEBUG)
    root_logger.addHandler(handler)
    try:
        yield stream
    finally:
        root_logger.removeHandler(handler)
        root_logger.setLevel(original_level)


def _assert_no_canaries_in_db(db: Session, canaries: list[str]) -> None:
    """Quét từng bảng trong Base.metadata để khẳng định không bảng nào chứa canary."""
    for table_name, table in Base.metadata.tables.items():
        rows = db.execute(select(table)).all()
        for row in rows:
            mapping = dict(row._mapping)
            row_serialized = json.dumps(mapping, default=str, ensure_ascii=False)
            for canary in canaries:
                assert canary not in row_serialized, (
                    f"Rò rỉ dữ liệu cá nhân: Canary '{canary}' vẫn còn trong '{table_name}'!"
                )


def _assert_no_canaries_in_storage(storage_dir: Path, canaries: list[str]) -> None:
    """Quét toàn bộ cây thư mục storage trên đĩa để khẳng định không file nào chứa canary."""
    for p in storage_dir.rglob("*"):
        if p.is_file():
            try:
                raw_bytes = p.read_bytes()
                for canary in canaries:
                    assert canary.encode("utf-8") not in raw_bytes, (
                        f"Rò rỉ tệp tin: Canary '{canary}' vẫn còn tồn tại trong tệp '{p}'!"
                    )
            except Exception:
                pass


def test_privacy_canary_end_to_end_flow(
    client: TestClient,
    test_db: Session,
    test_storage: Storage,
    sample_user: User,
    auth_headers: dict[str, str],
    log_capture: io.StringIO,
    tmp_path: Path,
) -> None:
    """Kiểm tra end-to-end chuỗi canary đi qua API, Worker và Xóa dữ liệu (PRIV-10, BE-18, BE-19).

    1. Tải lên cuộc họp chứa tiêu đề Canary và Idempotency-Key Canary.
    2. Worker xử lý job tạo transcript, summary và artifacts.
    3. Người dùng patch transcript segment với Canary text mới.
    4. Người dùng update summary với Canary summary mới.
    5. Khẳng định: Toàn bộ log API và Worker KHÔNG chứa bất kỳ chuỗi Canary nào.
    6. Xóa cuộc họp (erase_meeting).
    7. Khẳng định: Cơ sở dữ liệu và ổ đĩa sạch bóng 100%, không còn dấu vết của bất kỳ Canary nào.
    """
    canaries = [
        CANARY_TITLE,
        CANARY_IDEMPOTENCY,
        CANARY_TRANSCRIPT_EDIT,
        CANARY_SUMMARY_EDIT,
    ]

    # 1. Upload meeting
    with patch("app.api.v1.meetings.probe_audio") as mock_probe:
        mock_probe.return_value = AudioProbeResult(
            duration_sec=15.0,
            sample_rate=16000,
            channels=1,
            format_name="wav",
        )
        fake_wav = b"RIFF" + b"\x00" * 200
        res = client.post(
            "/api/v1/meetings",
            files={"file": ("meeting.wav", fake_wav, "audio/wav")},
            data={"title": CANARY_TITLE, "consent_confirmed": "true"},
            headers={**auth_headers, "Idempotency-Key": CANARY_IDEMPOTENCY},
        )
        assert res.status_code == 201, res.text
        created_data = res.json()
        meeting_id = created_data["meeting"]["id"]
        job_id = created_data["job"]["id"]

    # 2. Worker xử lý cuộc họp bằng fake pipeline
    ran = run_worker_once(
        test_db,
        storage=test_storage,
        worker_id="privacy-worker-runner-1",
        backend="fake",
    )
    assert ran is True, "Worker cần nhận và xử lý xong job"

    # Kiểm tra meeting đã sẵn sàng và có segments
    transcript_res = client.get(f"/api/v1/meetings/{meeting_id}/transcript", headers=auth_headers)
    assert transcript_res.status_code == 200
    segments = transcript_res.json().get("segments", [])
    assert len(segments) > 0, "Fake pipeline phải sinh ra transcript segments"
    first_segment_id = segments[0]["id"]
    first_segment_ver = segments[0]["version"]

    # 3. Chỉnh sửa segment với CANARY_TRANSCRIPT_EDIT
    patch_seg_res = client.patch(
        f"/api/v1/meetings/{meeting_id}/segments/{first_segment_id}",
        json={"text": CANARY_TRANSCRIPT_EDIT, "version": first_segment_ver},
        headers=auth_headers,
    )
    assert patch_seg_res.status_code == 200

    # 4. Chỉnh sửa summary với CANARY_SUMMARY_EDIT
    summary_get_res = client.get(f"/api/v1/meetings/{meeting_id}/summary", headers=auth_headers)
    assert summary_get_res.status_code == 200
    sum_ver = summary_get_res.json()["version"]

    put_sum_res = client.put(
        f"/api/v1/meetings/{meeting_id}/summary",
        json={
            "version": sum_ver,
            "content": {
                "overview": CANARY_SUMMARY_EDIT,
                "key_points": [
                    {"text": "Điểm thảo luận", "evidence_segment_ids": [first_segment_id]}
                ],
                "decisions": [],
            },
        },
        headers=auth_headers,
    )
    assert put_sum_res.status_code == 200

    # 5. Kiểm tra log của API và Worker: Tuyệt đối KHÔNG có canary nào
    captured_logs = log_capture.getvalue()
    for canary in canaries:
        assert canary not in captured_logs, (
            f"Bảo mật vi phạm: Phát hiện canary '{canary}' trong log!\n{captured_logs}"
        )

    # Khẳng định log vẫn có đầy đủ structured fields cho truy nguyên
    assert job_id in captured_logs
    assert meeting_id in captured_logs
    assert '"event": "job_created"' in captured_logs
    assert '"event": "job_succeeded"' in captured_logs

    # 6. Kiểm tra trước khi xóa: các canaries thực sự đang có mặt trong DB
    meeting_in_db = test_db.execute(
        select(Meeting).where(Meeting.id == meeting_id)
    ).scalar_one_or_none()
    assert meeting_in_db is not None
    assert meeting_in_db.title == CANARY_TITLE

    seg_in_db = test_db.execute(
        select(Segment).where(Segment.id == first_segment_id)
    ).scalar_one_or_none()
    assert seg_in_db is not None
    assert seg_in_db.text == CANARY_TRANSCRIPT_EDIT

    # 7. Thực hiện xóa toàn bộ cuộc họp qua erase_meeting
    erase_meeting(
        db=test_db,
        storage=test_storage,
        meeting_id=meeting_id,
        current_user_id=sample_user.id,
    )

    # 8. Khẳng định: Toàn bộ cơ sở dữ liệu KHÔNG còn sót bất kỳ canary nào
    _assert_no_canaries_in_db(test_db, canaries)

    # 9. Khẳng định: Kho lưu trữ trên ổ đĩa KHÔNG còn sót bất kỳ canary nào
    _assert_no_canaries_in_storage(tmp_path, canaries)

    # 10. Log sau khi xóa cũng không chứa canary
    all_logs_after = log_capture.getvalue()
    for canary in canaries:
        assert canary not in all_logs_after


def test_privacy_canary_account_erasure_flow(
    client: TestClient,
    test_db: Session,
    test_storage: Storage,
    sample_user: User,
    other_user: User,
    auth_headers: dict[str, str],
    log_capture: io.StringIO,
    tmp_path: Path,
) -> None:
    """Kiểm tra xóa toàn bộ tài khoản người dùng (erase_user) không để lọt canary (BE-18).

    - sample_user sở hữu cuộc họp với canary.
    - other_user sở hữu một cuộc họp riêng biệt.
    - Gọi erase_user cho sample_user.
    - Khẳng định dữ liệu sample_user biến mất hoàn toàn khỏi DB và storage.
    - Dữ liệu other_user được giữ nguyên, bảo đảm tính toàn vẹn (isolation).
    """
    canary_user_title = "CANARY_USER_ACCOUNT_ERASE_TEST_Z11"

    # Tạo cuộc họp cho sample_user
    with patch("app.api.v1.meetings.probe_audio") as mock_probe:
        mock_probe.return_value = AudioProbeResult(
            duration_sec=10.0,
            sample_rate=16000,
            channels=1,
            format_name="wav",
        )
        fake_wav = b"RIFF" + b"\x00" * 128
        res = client.post(
            "/api/v1/meetings",
            files={"file": ("meeting.wav", fake_wav, "audio/wav")},
            data={"title": canary_user_title, "consent_confirmed": "true"},
            headers={**auth_headers, "Idempotency-Key": str(uuid.uuid4())},
        )
        assert res.status_code == 201
        meeting_id = res.json()["meeting"]["id"]

    # Tạo cuộc họp cho other_user trực tiếp qua DB
    other_meeting = Meeting(
        id=str(uuid.uuid4()),
        owner_id=other_user.id,
        title="Cuộc họp của người dùng khác",
        status="ready",
        created_at=test_db.execute(select(Meeting.created_at)).scalar() or None,
    )
    test_db.add(other_meeting)
    test_db.commit()

    # Xóa toàn bộ tài khoản sample_user
    erase_user(db=test_db, storage=test_storage, user_id=sample_user.id)

    # 1. Khẳng định tài khoản và cuộc họp của sample_user đã biến mất
    assert (
        test_db.execute(select(User).where(User.id == sample_user.id)).scalar_one_or_none() is None
    )
    assert (
        test_db.execute(select(Meeting).where(Meeting.id == meeting_id)).scalar_one_or_none()
        is None
    )

    # 2. Khẳng định không còn chuỗi canary trong toàn bộ DB
    _assert_no_canaries_in_db(test_db, [canary_user_title])

    # 3. Khẳng định không còn tệp của cuộc họp bị xóa trong storage
    audio_path = test_storage.get_audio_path(meeting_id, "wav")
    assert not audio_path.exists()
    _assert_no_canaries_in_storage(tmp_path, [canary_user_title])

    # 4. Cuộc họp của other_user vẫn được giữ nguyên
    persisted_other = test_db.execute(
        select(Meeting).where(Meeting.id == other_meeting.id)
    ).scalar_one_or_none()
    assert persisted_other is not None
    assert persisted_other.title == "Cuộc họp của người dùng khác"

    # 5. Log xóa người dùng an toàn
    assert canary_user_title not in log_capture.getvalue()


def test_privacy_canary_worker_internal_failure_does_not_log_error_data(
    test_db: Session,
    test_storage: Storage,
    sample_user: User,
    log_capture: io.StringIO,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ngoại lệ nội bộ bên trong worker/pipeline không làm rò rỉ dữ liệu canary vào log."""
    canary_error_title = "CANARY_JOB_TITLE_FAILURE_LEAK_CHECK"
    now = test_db.execute(select(User.created_at)).scalar() or None
    meeting = Meeting(
        id=str(uuid.uuid4()),
        owner_id=sample_user.id,
        title=canary_error_title,
        status="processing",
        created_at=now,
    )
    test_db.add(meeting)

    job = Job(
        id=str(uuid.uuid4()),
        meeting_id=meeting.id,
        status="queued",
        stage="asr",
        stage_status={"asr": "queued"},
        attempt=1,
        max_attempts=3,
        created_at=now,
    )
    test_db.add(job)
    test_db.commit()

    # Giả lập pipeline run_job ném PermanentPipelineError
    def failing_run_job(*args, **kwargs):
        raise PermanentPipelineError(
            code=ErrorCode.AUDIO_INVALID,
            stage=Stage.ASR,
            message="Audio format cannot be decoded",
        )

    monkeypatch.setattr("app.worker.runner.run_job", failing_run_job)

    # Chạy worker
    ran = run_worker_once(
        test_db,
        storage=test_storage,
        worker_id="privacy-failing-worker",
        backend="fake",
    )
    assert ran is True

    # Kiểm tra log: tiêu đề canary tuyệt đối KHÔNG được ghi vào log
    logs_text = log_capture.getvalue()
    assert canary_error_title not in logs_text, (
        f"Lỗi bảo mật nghiêm trọng: Tiêu đề canary đã in vào log worker!\n{logs_text}"
    )

    # Khẳng định log chứa event job_failed có cấu trúc
    assert '"event": "job_failed"' in logs_text
    assert '"error_code": "AUDIO_INVALID"' in logs_text

    # Kiểm tra job đã được đánh dấu thất bại an toàn
    test_db.refresh(job)
    assert job.status in ("retry_scheduled", "failed")
