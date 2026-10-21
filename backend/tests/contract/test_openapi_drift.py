"""Kiểm thử OpenAPI contract drift và kiểm tra tính hợp lệ của fixtures."""

import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app
from app.schemas.common import ErrorResponse
from app.schemas.job import JobOut
from app.schemas.meeting import (
    MeetingCreateOut,
    MeetingDetailOut,
    MeetingListOut,
    MeetingOut,
    SpeakerOut,
)
from app.schemas.transcript import (
    TranscriptOut,
    TranscriptSegmentOut,
)


def get_contracts_root() -> Path:
    """Trả về thư mục contracts/ ở gốc repository."""
    return Path(__file__).resolve().parents[3] / "contracts"


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
