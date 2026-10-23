"""Kiểm thử OpenAPI contract drift và kiểm tra tính hợp lệ của fixtures."""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.schemas.action_item import ActionItemListOut, ActionItemOut
from app.schemas.auth import LoginResponse, UserMeOut
from app.schemas.common import ErrorResponse
from app.schemas.config import ConfigOut
from app.schemas.edit import EditListOut
from app.schemas.job import JobOut
from app.schemas.meeting import (
    MeetingCreateOut,
    MeetingDetailOut,
    MeetingListOut,
    MeetingOut,
    SpeakerOut,
)
from app.schemas.summary import SummaryOut
from app.schemas.transcript import (
    TranscriptOut,
    TranscriptSegmentOut,
)


def get_contracts_root() -> Path:
    """Trả về thư mục contracts/ ở gốc repository."""
    return Path(__file__).resolve().parents[3] / "contracts"


@pytest.fixture(autouse=True)
def auto_auth_for_contract_tests(monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest):
    """Tự động mock current_user cho các contract stub tests."""
    if request.node.name.startswith("test_auth_") or request.node.name == "test_openapi_json_drift":
        return

    import shutil

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    from app import main as app_main
    from app.api.deps import get_current_user
    from app.db.base import Base
    from app.db.models.idempotency import IdempotencyKey
    from app.db.models.job import Job
    from app.db.models.meeting import Meeting
    from app.db.models.transcript import Segment, Speaker
    from app.db.models.user import User
    from app.db.session import get_db
    from app.services.audio_validator import AudioProbeResult

    if shutil.which("ffprobe") is None:

        def _mock_probe(file_path, timeout_sec=10.0, ffprobe_bin=None):
            return AudioProbeResult(
                duration_sec=120.0,
                format_name="wav",
                sample_rate=16000,
                channels=1,
            )

        monkeypatch.setattr("app.api.v1.meetings.probe_audio", _mock_probe)

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
    ]
    Base.metadata.create_all(bind=engine, tables=tables)
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = session_factory()

    fake_user = User(
        id="u-03a1b2c3-d4e5-4f6a-8b9c-0d1e2f3a4b5c",
        email="user@example.com",
        display_name="Nguyễn Văn A",
        password_hash="mock",
    )
    session.add(fake_user)
    session.flush()

    fake_meeting = Meeting(
        id="test-meeting-uuid-12345",
        owner_id=fake_user.id,
        title="Họp sprint planning tuần 42",
        source="recording",
        status="processing",
        meeting_date="2026-10-15",
        duration_sec=1834.52,
        num_speakers_hint=3,
        audio_path="audio/test-meeting-uuid-12345/original.webm",
        audio_sha256="mock_sha256",
        version=1,
    )
    session.add(fake_meeting)

    fake_job = Job(
        id="test-job-uuid-67890",
        meeting_id=fake_meeting.id,
        status="retry_scheduled",
        stage="summarize",
        from_stage=None,
        progress=0.9,
        stage_status={
            "preprocess": "succeeded",
            "vad": "succeeded",
            "asr": "succeeded",
            "diarize": "succeeded",
            "merge": "succeeded",
            "summarize": "retry_scheduled",
        },
        attempt=2,
        max_attempts=3,
        error_code="LLM_UNAVAILABLE",
        error_message="Dịch vụ tóm tắt tạm thời không phản hồi. Hệ thống sẽ tự thử lại.",
    )
    session.add(fake_job)

    meeting_ready = Meeting(
        id="test-meeting-1",
        owner_id=fake_user.id,
        title="Họp thử nghiệm 1",
        source="upload",
        status="ready",
        version=1,
    )
    meeting_pending = Meeting(
        id="meeting-pending-123",
        owner_id=fake_user.id,
        title="Họp chờ xử lý",
        source="upload",
        status="queued",
        version=1,
    )
    session.add_all([meeting_ready, meeting_pending])

    seg1 = Segment(
        id="5b1e7c2a-b2c3-4d4e-8f9a-0b1c2d3e4f5a",
        meeting_id="test-meeting-1",
        idx=0,
        start_sec=0.0,
        end_sec=5.0,
        text="Xin chào mọi người",
        ai_text="Xin chào mọi người",
        version=2,
    )
    session.add(seg1)
    session.commit()

    orig_create_app = app_main.create_app

    def patched_create_app():
        application = orig_create_app()
        application.dependency_overrides[get_current_user] = lambda: fake_user

        def _get_db():
            yield session

        application.dependency_overrides[get_db] = _get_db
        return application

    monkeypatch.setattr("tests.contract.test_openapi_drift.create_app", patched_create_app)


def test_openapi_json_drift() -> None:
    """Kiểm tra contracts/openapi.json khớp hoàn toàn với OpenAPI schema sinh từ code."""
    app = create_app()
    current_spec = app.openapi()
    expected_content = json.dumps(current_spec, indent=2, ensure_ascii=False) + "\n"

    openapi_file = get_contracts_root() / "openapi.json"
    assert openapi_file.is_file(), f"File {openapi_file} không tồn tại!"

    with open(openapi_file, encoding="utf-8") as f:
        file_content = f.read()

    assert file_content == expected_content, (
        f"Phát hiện OpenAPI drift tại {openapi_file}! "
        "Hãy chạy `uv run python scripts/generate_openapi.py` để đồng bộ lại file contract."
    )


def test_meeting_processing_fixture_validates() -> None:
    """Kiểm tra fixture meeting_processing.json hợp lệ theo MeetingOut và MeetingDetailOut."""
    fixture_file = get_contracts_root() / "fixtures" / "api" / "meeting_processing.json"
    assert fixture_file.is_file(), f"Không tìm thấy fixture {fixture_file}"

    with open(fixture_file, encoding="utf-8") as f:
        data = json.load(f)

    # Validate schema
    meeting = MeetingOut.model_validate(data)
    assert meeting.id == "8f6c2a1e-b2c3-4d4e-8f9a-0b1c2d3e4f5a"
    assert meeting.status == "processing"
    assert meeting.audio.available is True


def test_job_retry_scheduled_fixture_validates() -> None:
    """Kiểm tra fixture job_retry_scheduled.json hợp lệ theo JobOut."""
    fixture_file = get_contracts_root() / "fixtures" / "api" / "job_retry_scheduled.json"
    assert fixture_file.is_file(), f"Không tìm thấy fixture {fixture_file}"

    with open(fixture_file, encoding="utf-8") as f:
        data = json.load(f)

    job = JobOut.model_validate(data)
    assert job.id == "c1d2e3f4-a5b6-4c7d-8e9f-0a1b2c3d4e5f"
    assert job.status == "retry_scheduled"
    assert job.stage == "summarize"
    assert job.progress == 0.9
    assert job.error is not None
    assert job.error.code == "LLM_UNAVAILABLE"


def test_get_meeting_endpoint_stub() -> None:
    """Kiểm tra endpoint GET /api/v1/meetings/{id} trả về dữ liệu đúng schema."""
    app = create_app()
    with TestClient(app) as client:
        test_id = "test-meeting-uuid-12345"
        response = client.get(f"/api/v1/meetings/{test_id}")
        assert response.status_code == 200

        data = response.json()
        meeting = MeetingDetailOut.model_validate(data)
        assert meeting.id == test_id
        assert meeting.status == "processing"


def test_get_job_endpoint_stub() -> None:
    """Kiểm tra endpoint GET /api/v1/jobs/{id} trả về dữ liệu đúng schema."""
    app = create_app()
    with TestClient(app) as client:
        test_id = "test-job-uuid-67890"
        response = client.get(f"/api/v1/jobs/{test_id}")
        assert response.status_code == 200

        data = response.json()
        job = JobOut.model_validate(data)
        assert job.id == test_id
        assert job.status == "retry_scheduled"


def test_meeting_list_fixture_validates() -> None:
    """Kiểm tra fixture meeting_list.json hợp lệ theo MeetingListOut."""
    fixture_file = get_contracts_root() / "fixtures" / "api" / "meeting_list.json"
    assert fixture_file.is_file(), f"Không tìm thấy fixture {fixture_file}"

    with open(fixture_file, encoding="utf-8") as f:
        data = json.load(f)

    result = MeetingListOut.model_validate(data)
    assert len(result.items) == 1
    assert result.page == 1
    assert result.total == 1


def test_meeting_created_fixture_validates() -> None:
    """Kiểm tra fixture meeting_created.json hợp lệ theo MeetingCreateOut."""
    fixture_file = get_contracts_root() / "fixtures" / "api" / "meeting_created.json"
    assert fixture_file.is_file(), f"Không tìm thấy fixture {fixture_file}"

    with open(fixture_file, encoding="utf-8") as f:
        data = json.load(f)

    result = MeetingCreateOut.model_validate(data)
    assert result.meeting.status == "queued"
    assert result.job.status == "queued"


def test_list_meetings_endpoint_stub() -> None:
    """Kiểm tra endpoint GET /api/v1/meetings trả về danh sách cuộc họp đúng schema."""
    app = create_app()
    with TestClient(app) as client:
        response = client.get("/api/v1/meetings?page=1&page_size=10")
        assert response.status_code == 200

        data = response.json()
        result = MeetingListOut.model_validate(data)
        assert result.page == 1
        assert len(result.items) >= 1


def test_create_meeting_missing_idempotency_key() -> None:
    """Kiểm tra POST /api/v1/meetings thiếu Idempotency-Key trả về 400."""
    app = create_app()
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/meetings",
            files={"file": ("sample.wav", b"fake audio bytes", "audio/wav")},
            data={"consent_confirmed": "true"},
        )
        assert response.status_code == 400
        error = response.json().get("error", {})
        assert error.get("code") == "IDEMPOTENCY_KEY_REQUIRED"


def test_create_meeting_missing_consent() -> None:
    """Kiểm tra POST /api/v1/meetings thiếu consent_confirmed trả về 422."""
    app = create_app()
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/meetings",
            headers={"Idempotency-Key": "test-key-123"},
            files={"file": ("sample.wav", b"fake audio bytes", "audio/wav")},
            data={"consent_confirmed": "false"},
        )
        assert response.status_code == 422
        error = response.json().get("error", {})
        assert error.get("code") == "CONSENT_REQUIRED"


def test_create_meeting_success() -> None:
    """Kiểm tra POST /api/v1/meetings hợp lệ trả về 201 kèm meeting và job."""
    app = create_app()
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/meetings",
            headers={"Idempotency-Key": "test-key-123"},
            files={"file": ("sample.wav", b"fake audio bytes", "audio/wav")},
            data={"consent_confirmed": "true", "title": "Họp thảo luận sprint mới"},
        )
        assert response.status_code == 201
        data = response.json()
        result = MeetingCreateOut.model_validate(data)
        assert result.meeting.title == "Họp thảo luận sprint mới"
        assert result.job.status == "queued"


def test_transcript_ready_fixture_validates() -> None:
    """Kiểm tra transcript_ready.json hợp lệ: 2 speaker và 1 segment có speaker_id: null."""
    fixture_file = get_contracts_root() / "fixtures" / "api" / "transcript_ready.json"
    assert fixture_file.is_file(), f"Không tìm thấy fixture {fixture_file}"

    with open(fixture_file, encoding="utf-8") as f:
        data = json.load(f)

    result = TranscriptOut.model_validate(data)
    assert result.status == "ready"
    assert result.diarization_status == "ok"
    assert len(result.speakers) == 2
    # Ít nhất 1 segment có speaker_id là None
    null_speakers = [s for s in result.segments if s.speaker_id is None]
    assert len(null_speakers) >= 1


def test_transcript_pending_fixture_validates() -> None:
    """Kiểm tra transcript_pending.json hợp lệ: pending thì segments rỗng."""
    fixture_file = get_contracts_root() / "fixtures" / "api" / "transcript_pending.json"
    assert fixture_file.is_file(), f"Không tìm thấy fixture {fixture_file}"

    with open(fixture_file, encoding="utf-8") as f:
        data = json.load(f)

    result = TranscriptOut.model_validate(data)
    assert result.status == "pending"
    assert result.segments == []


def test_error_version_conflict_fixture_validates() -> None:
    """Kiểm tra fixture error_version_conflict.json hợp lệ theo ErrorResponse."""
    fixture_file = get_contracts_root() / "fixtures" / "api" / "error_version_conflict.json"
    assert fixture_file.is_file(), f"Không tìm thấy fixture {fixture_file}"

    with open(fixture_file, encoding="utf-8") as f:
        data = json.load(f)

    err = ErrorResponse.model_validate(data)
    assert err.error.code == "VERSION_CONFLICT"
    assert "current" in err.error.details


def test_get_transcript_endpoint_ready() -> None:
    """Kiểm tra GET /api/v1/meetings/{id}/transcript trả về dữ liệu transcript."""
    app = create_app()
    with TestClient(app) as client:
        response = client.get("/api/v1/meetings/test-meeting-1/transcript")
        assert response.status_code == 200

        data = response.json()
        result = TranscriptOut.model_validate(data)
        assert result.status == "ready"
        assert len(result.segments) > 0


def test_get_transcript_endpoint_pending() -> None:
    """Kiểm tra GET /api/v1/meetings/{id}/transcript khi pending trả về segments rỗng."""
    app = create_app()
    with TestClient(app) as client:
        response = client.get("/api/v1/meetings/meeting-pending-123/transcript")
        assert response.status_code == 200

        data = response.json()
        result = TranscriptOut.model_validate(data)
        assert result.status == "pending"
        assert result.segments == []


def test_patch_segment_version_conflict() -> None:
    """Kiểm tra PATCH /meetings/{id}/segments/{id} lệch version trả về 409 VERSION_CONFLICT."""
    app = create_app()
    with TestClient(app) as client:
        response = client.patch(
            "/api/v1/meetings/test-meeting-1/segments/5b1e7c2a-b2c3-4d4e-8f9a-0b1c2d3e4f5a",
            json={"text": "Văn bản mới", "version": 1},
        )
        assert response.status_code == 409
        data = response.json()
        assert data["error"]["code"] == "VERSION_CONFLICT"
        assert data["error"]["details"]["current"]["version"] == 3


def test_patch_segment_success() -> None:
    """Kiểm tra PATCH /meetings/{id}/segments/{id} đúng version trả về 200."""
    app = create_app()
    with TestClient(app) as client:
        response = client.patch(
            "/api/v1/meetings/test-meeting-1/segments/5b1e7c2a-b2c3-4d4e-8f9a-0b1c2d3e4f5a",
            json={"text": "Nội dung cập nhật thành công", "version": 2},
        )
        assert response.status_code == 200
        data = response.json()
        seg = TranscriptSegmentOut.model_validate(data)
        assert seg.text == "Nội dung cập nhật thành công"
        assert seg.version == 3
        assert seg.is_edited is True


def test_patch_speaker_version_conflict() -> None:
    """Kiểm tra PATCH /meetings/{id}/speakers/{id} lệch version trả về 409."""
    app = create_app()
    with TestClient(app) as client:
        response = client.patch(
            "/api/v1/meetings/test-meeting-1/speakers/speaker-1",
            json={"display_name": "Tên mới", "version": 99},
        )
        assert response.status_code == 409
        data = response.json()
        assert data["error"]["code"] == "VERSION_CONFLICT"


def test_patch_speaker_success() -> None:
    """Kiểm tra PATCH /meetings/{id}/speakers/{id} đúng version trả về 200."""
    app = create_app()
    with TestClient(app) as client:
        response = client.patch(
            "/api/v1/meetings/test-meeting-1/speakers/2c7a9d10-a1b2-4c3d-8e4f-5a6b7c8d9e0f",
            json={"display_name": "Chị Lan (Lead PM)", "version": 2},
        )
        assert response.status_code == 200
        data = response.json()
        spk = SpeakerOut.model_validate(data)
        assert spk.display_name == "Chị Lan (Lead PM)"
        assert spk.version == 3
        assert spk.is_edited is True


def test_summary_ready_fixture_validates() -> None:
    """Kiểm tra summary_ready.json hợp lệ theo SummaryOut."""
    fixture_file = get_contracts_root() / "fixtures" / "api" / "summary_ready.json"
    assert fixture_file.is_file(), f"Không tìm thấy fixture {fixture_file}"

    with open(fixture_file, encoding="utf-8") as f:
        data = json.load(f)

    result = SummaryOut.model_validate(data)
    assert result.status == "ready"
    assert result.content is not None
    assert len(result.content.key_points) > 0


def test_summary_disabled_fixture_validates() -> None:
    """Kiểm tra summary_disabled.json hợp lệ theo SummaryOut."""
    fixture_file = get_contracts_root() / "fixtures" / "api" / "summary_disabled.json"
    assert fixture_file.is_file(), f"Không tìm thấy fixture {fixture_file}"

    with open(fixture_file, encoding="utf-8") as f:
        data = json.load(f)

    result = SummaryOut.model_validate(data)
    assert result.status == "disabled"
    assert result.content is None


def test_action_items_fixture_validates() -> None:
    """Kiểm tra action_items.json: một item có hạn và một item không có hạn."""
    fixture_file = get_contracts_root() / "fixtures" / "api" / "action_items.json"
    assert fixture_file.is_file(), f"Không tìm thấy fixture {fixture_file}"

    with open(fixture_file, encoding="utf-8") as f:
        data = json.load(f)

    result = ActionItemListOut.model_validate(data)
    assert len(result.items) == 2

    with_due = [item for item in result.items if item.due_date is not None]
    without_due = [item for item in result.items if item.due_date is None]
    assert len(with_due) >= 1
    assert len(without_due) >= 1


def test_get_summary_ready() -> None:
    """Kiểm tra GET /api/v1/meetings/{id}/summary trả về 200 trạng thái ready."""
    app = create_app()
    with TestClient(app) as client:
        response = client.get("/api/v1/meetings/meeting-1/summary")
        assert response.status_code == 200
        data = response.json()
        result = SummaryOut.model_validate(data)
        assert result.status == "ready"


def test_get_summary_disabled() -> None:
    """Kiểm tra GET /api/v1/meetings/{id}/summary khi disabled trả về 200 trạng thái disabled."""
    app = create_app()
    with TestClient(app) as client:
        response = client.get("/api/v1/meetings/meeting-disabled-1/summary")
        assert response.status_code == 200
        data = response.json()
        result = SummaryOut.model_validate(data)
        assert result.status == "disabled"


def test_put_summary_success() -> None:
    """Kiểm tra PUT /api/v1/meetings/{id}/summary với đúng version trả về 200."""
    app = create_app()
    with TestClient(app) as client:
        payload = {
            "content": {
                "overview": "Tổng quan cuộc họp sau khi chỉnh sửa.",
                "key_points": [
                    {
                        "text": "Đã thống nhất hoàn thiện upload audio.",
                        "evidence_segment_ids": ["5b1e7c2a-b2c3-4d4e-8f9a-0b1c2d3e4f5a"],
                    }
                ],
                "decisions": [],
            },
            "version": 2,
        }
        response = client.put("/api/v1/meetings/meeting-1/summary", json=payload)
        assert response.status_code == 200
        data = response.json()
        result = SummaryOut.model_validate(data)
        assert result.version == 3
        assert result.is_edited is True


def test_put_summary_version_conflict() -> None:
    """Kiểm tra PUT /api/v1/meetings/{id}/summary với version sai trả về 409."""
    app = create_app()
    with TestClient(app) as client:
        payload = {
            "content": {
                "overview": "Nội dung mới",
                "key_points": [],
                "decisions": [],
            },
            "version": 1,
        }
        response = client.put("/api/v1/meetings/meeting-1/summary", json=payload)
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "VERSION_CONFLICT"


def test_get_action_items() -> None:
    """Kiểm tra GET /api/v1/meetings/{id}/action-items trả về danh sách items."""
    app = create_app()
    with TestClient(app) as client:
        response = client.get("/api/v1/meetings/meeting-1/action-items")
        assert response.status_code == 200
        data = response.json()
        result = ActionItemListOut.model_validate(data)
        assert len(result.items) == 2


def test_post_action_item() -> None:
    """Kiểm tra POST /api/v1/meetings/{id}/action-items trả về 201 với source='user'."""
    app = create_app()
    with TestClient(app) as client:
        payload = {
            "description": "Thêm kiểm thử tự động cho action items",
            "assignee_name": "Quang Ha",
            "due_date": "2026-10-25",
            "status": "open",
        }
        response = client.post("/api/v1/meetings/meeting-1/action-items", json=payload)
        assert response.status_code == 201
        data = response.json()
        result = ActionItemOut.model_validate(data)
        assert result.source == "user"
        assert result.description == "Thêm kiểm thử tự động cho action items"


def test_patch_action_item_success() -> None:
    """Kiểm tra PATCH /api/v1/meetings/{id}/action-items/{id} đúng version trả về 200."""
    app = create_app()
    with TestClient(app) as client:
        payload = {
            "description": "Cập nhật mô tả công việc",
            "status": "done",
            "version": 1,
        }
        response = client.patch(
            "/api/v1/meetings/meeting-1/action-items/a1f0a2b3-c4d5-4e6f-8a9b-0c1d2e3f4a5b",
            json=payload,
        )
        assert response.status_code == 200
        data = response.json()
        result = ActionItemOut.model_validate(data)
        assert result.version == 2
        assert result.is_edited is True


def test_patch_action_item_conflict() -> None:
    """Kiểm tra PATCH /api/v1/meetings/{id}/action-items/{id} sai version trả về 409."""
    app = create_app()
    with TestClient(app) as client:
        payload = {
            "description": "Mô tả mới",
            "version": 99,
        }
        response = client.patch(
            "/api/v1/meetings/meeting-1/action-items/a1f0a2b3-c4d5-4e6f-8a9b-0c1d2e3f4a5b",
            json=payload,
        )
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "VERSION_CONFLICT"


def test_delete_action_item() -> None:
    """Kiểm tra DELETE /api/v1/meetings/{id}/action-items/{id} trả về 204."""
    app = create_app()
    with TestClient(app) as client:
        response = client.delete(
            "/api/v1/meetings/meeting-1/action-items/a1f0a2b3-c4d5-4e6f-8a9b-0c1d2e3f4a5b?version=1"
        )
        assert response.status_code == 204


def test_config_fixture_validates() -> None:
    """Kiểm tra fixture config.json hợp lệ theo ConfigOut."""
    fixture_file = get_contracts_root() / "fixtures" / "api" / "config.json"
    assert fixture_file.is_file(), f"Không tìm thấy fixture {fixture_file}"

    with open(fixture_file, encoding="utf-8") as f:
        data = json.load(f)

    result = ConfigOut.model_validate(data)
    assert result.max_upload_mb == 200
    assert result.llm_enabled is True
    assert "txt" in result.export_formats


def test_user_me_fixture_validates() -> None:
    """Kiểm tra fixture user_me.json hợp lệ theo UserMeOut."""
    fixture_file = get_contracts_root() / "fixtures" / "api" / "user_me.json"
    assert fixture_file.is_file(), f"Không tìm thấy fixture {fixture_file}"

    with open(fixture_file, encoding="utf-8") as f:
        data = json.load(f)

    result = UserMeOut.model_validate(data)
    assert result.user.email == "user@example.com"


def test_edits_fixture_validates() -> None:
    """Kiểm tra fixture edits.json hợp lệ theo EditListOut."""
    fixture_file = get_contracts_root() / "fixtures" / "api" / "edits.json"
    assert fixture_file.is_file(), f"Không tìm thấy fixture {fixture_file}"

    with open(fixture_file, encoding="utf-8") as f:
        data = json.load(f)

    result = EditListOut.model_validate(data)
    assert result.total == 1
    assert len(result.items) == 1
    assert result.items[0].entity_type == "segment"


def test_get_config_endpoint() -> None:
    """Kiểm tra GET /api/v1/config trả về 200."""
    app = create_app()
    with TestClient(app) as client:
        response = client.get("/api/v1/config")
        assert response.status_code == 200
        data = response.json()
        result = ConfigOut.model_validate(data)
        assert result.max_upload_mb == 200


def _setup_openapi_auth_app():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    from app.core.security import hash_password
    from app.db.base import Base
    from app.db.models.user import User
    from app.db.session import get_db

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine, tables=[User.__table__])
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = session_factory()
    user = User(
        id="u-03a1b2c3-d4e5-4f6a-8b9c-0d1e2f3a4b5c",
        email="user@example.com",
        display_name="Nguyễn Văn A",
        password_hash=hash_password("valid-password"),
    )
    session.add(user)
    session.commit()

    app = create_app()

    def _override_get_db():
        yield session

    app.dependency_overrides[get_db] = _override_get_db
    return app


def test_auth_login_success() -> None:
    """Kiểm tra POST /api/v1/auth/login thành công trả về 200 và set cookie."""
    app = _setup_openapi_auth_app()
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/auth/login",
            json={"email": "user@example.com", "password": "valid-password"},
        )
        assert response.status_code == 200
        data = response.json()
        result = LoginResponse.model_validate(data)
        assert result.user.email == "user@example.com"
        assert "session_token" in response.cookies


def test_auth_login_invalid() -> None:
    """Kiểm tra POST /api/v1/auth/login sai thông tin trả về 401."""
    app = _setup_openapi_auth_app()
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/auth/login",
            json={"email": "invalid@example.com", "password": "wrong"},
        )
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "INVALID_CREDENTIALS"


def test_auth_logout() -> None:
    """Kiểm tra POST /api/v1/auth/logout trả về 204."""
    app = _setup_openapi_auth_app()
    with TestClient(app) as client:
        response = client.post("/api/v1/auth/logout")
        assert response.status_code == 204


def test_auth_me() -> None:
    """Kiểm tra GET /api/v1/auth/me trả về thông tin user khi đã đăng nhập."""
    app = _setup_openapi_auth_app()
    with TestClient(app) as client:
        # Đăng nhập để nhận cookie
        login_res = client.post(
            "/api/v1/auth/login",
            json={"email": "user@example.com", "password": "valid-password"},
        )
        assert login_res.status_code == 200
        response = client.get("/api/v1/auth/me")
        assert response.status_code == 200
        data = response.json()
        result = UserMeOut.model_validate(data)
        assert result.user.email == "user@example.com"


def test_retry_meeting_job_success() -> None:
    """Kiểm tra POST /api/v1/meetings/{id}/jobs trả về 202."""
    app = create_app()
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/meetings/meeting-1/jobs",
            json={"from_stage": "summarize"},
        )
        assert response.status_code == 202
        data = response.json()
        job = JobOut.model_validate(data)
        assert job.from_stage == "summarize"


def test_retry_meeting_job_already_active() -> None:
    """Kiểm tra POST /api/v1/meetings/{id}/jobs khi job đang chạy trả về 409."""
    app = create_app()
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/meetings/active-meeting-1/jobs",
            json={"from_stage": None},
        )
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "JOB_ALREADY_ACTIVE"


def test_list_meeting_edits() -> None:
    """Kiểm tra GET /api/v1/meetings/{id}/edits trả về lịch sử sửa."""
    app = create_app()
    with TestClient(app) as client:
        response = client.get("/api/v1/meetings/meeting-1/edits")
        assert response.status_code == 200
        data = response.json()
        edits = EditListOut.model_validate(data)
        assert edits.total == 1


def test_export_meeting_success() -> None:
    """Kiểm tra GET /api/v1/meetings/{id}/export định dạng txt trả về 200."""
    app = create_app()
    with TestClient(app) as client:
        response = client.get("/api/v1/meetings/meeting-1/export?format=txt&variant=current")
        assert response.status_code == 200
        assert "attachment;" in response.headers.get("content-disposition", "")
        assert "Biên bản cuộc họp".encode() in response.content


def test_export_meeting_unsupported_format() -> None:
    """Kiểm tra GET /api/v1/meetings/{id}/export định dạng không hỗ trợ trả về 422."""
    app = create_app()
    with TestClient(app) as client:
        response = client.get("/api/v1/meetings/meeting-1/export?format=pdf")
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "FORMAT_NOT_SUPPORTED"


def test_export_meeting_not_ready() -> None:
    """Kiểm tra GET /api/v1/meetings/{id}/export khi chưa ready trả về 409."""
    app = create_app()
    with TestClient(app) as client:
        response = client.get("/api/v1/meetings/not-ready-meeting/export?format=txt")
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "TRANSCRIPT_NOT_READY"
