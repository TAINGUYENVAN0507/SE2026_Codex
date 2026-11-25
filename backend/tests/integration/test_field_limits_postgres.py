"""Mỗi trường chữ API nhận phải trả 4xx khi quá giới hạn, không được 500 (BE-05, AD-018).

SQLite không kiểm độ dài `VARCHAR(n)`, nên lỗi này chỉ lộ trên PostgreSQL. Mỗi ca gửi giá trị
dài hơn cột trong DB (hoặc giới hạn của schema) đúng 1 ký tự, hoặc sai định dạng với cột
ngắn, và chỉ đòi status < 500.
Ca nào hiện còn 500 thì đánh `xfail(strict=True)` kèm việc được giao. Khi sửa xong, ca đó chuyển
sang XPASS và làm suite đỏ, nên người sửa phải bỏ dấu xfail.
"""

import io
import uuid
import wave
from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.models.meeting import Meeting
from app.db.models.transcript import Segment, Speaker
from app.db.models.user import User
from app.db.session import get_db
from app.main import create_app
from app.services.storage import get_storage
from app.services.storage.local import LocalStorage


def _wav() -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(b"\0" * 32000)
    return buf.getvalue()


@pytest.fixture
def seeded(db_session: Session) -> dict[str, str]:
    user = User(
        id=str(uuid.uuid4()),
        email="field-limits@example.com",
        display_name="Field Limits",
        password_hash="x",
    )
    meeting = Meeting(
        id=str(uuid.uuid4()),
        owner_id=user.id,
        title="Họp kiểm giới hạn",
        source="upload",
        status="ready",
        version=1,
    )
    speaker = Speaker(
        id=str(uuid.uuid4()),
        meeting_id=meeting.id,
        label="spk_0",
        default_name="Người nói 1",
        display_name="Người nói 1",
        version=1,
    )
    segment = Segment(
        id=str(uuid.uuid4()),
        meeting_id=meeting.id,
        speaker_id=speaker.id,
        idx=0,
        start_sec=0.0,
        end_sec=1.0,
        text="xin chào",
        ai_text="xin chào",
        version=1,
    )
    db_session.add(user)
    db_session.commit()
    db_session.add(meeting)
    db_session.commit()
    db_session.add_all([speaker, segment])
    db_session.commit()
    return {"user": user.id, "meeting": meeting.id, "speaker": speaker.id, "segment": segment.id}


@pytest.fixture
def client(
    db_session: Session, seeded: dict[str, str], tmp_path: Path
) -> Generator[TestClient, None, None]:
    app = create_app()
    user = db_session.get(User, seeded["user"])
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_storage] = lambda: LocalStorage(base_dir=tmp_path)
    # raise_server_exceptions=False: lỗi 500 phải về thành response để test đọc được status.
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
    app.dependency_overrides.clear()


def _create(c: TestClient, *, key: str | None = None, **form: str):
    return c.post(
        "/api/v1/meetings",
        data={"consent_confirmed": "true", **form},
        files={"file": ("a.wav", _wav(), "audio/wav")},
        headers={"Idempotency-Key": key or str(uuid.uuid4())},
    )


CREATE_CASES = [
    pytest.param({"title": "a" * 200}, None, 201, id="create-title-200-ok"),
    pytest.param({"title": f"  {'a' * 200}  "}, None, 201, id="create-title-200-stripped-ok"),
    pytest.param({"title": "   "}, None, 422, id="create-title-whitespace-only"),
    pytest.param({"title": "a" * 201}, None, 422, id="create-title-201"),
    pytest.param({"meeting_date": "2026-11-24T09"}, None, 422, id="create-meeting-date-13-chars"),
    pytest.param({"meeting_date": "2026-02-30"}, None, 422, id="create-meeting-date-invalid-cal"),
    pytest.param({}, "k" * 100, 201, id="create-idempotency-key-100-ok"),
    pytest.param({}, "k" * 101, 422, id="create-idempotency-key-101"),
]


@pytest.mark.parametrize(("form", "key", "expected"), CREATE_CASES)
def test_create_meeting_fields_past_the_limit_answer_4xx(
    client: TestClient, form: dict, key: str | None, expected: int
) -> None:
    r = _create(client, key=key, **form)
    assert r.status_code == expected, f"{r.status_code}: {r.text[:300]}"
    if key and len(key) > 100:
        assert r.json()["error"]["code"] == "IDEMPOTENCY_KEY_TOO_LONG"


def _patch_cases(ids: dict[str, str]) -> list[tuple[str, str, dict]]:
    m, sp, sg = ids["meeting"], ids["speaker"], ids["segment"]
    return [
        ("PATCH", f"/api/v1/meetings/{m}", {"title": "a" * 201, "version": 1}),
        ("PATCH", f"/api/v1/meetings/{m}/speakers/{sp}", {"display_name": "a" * 101, "version": 1}),
        ("PATCH", f"/api/v1/meetings/{m}/segments/{sg}", {"text": "a" * 5001, "version": 1}),
        (
            "POST",
            f"/api/v1/meetings/{m}/action-items",
            {"description": "việc", "assignee_name": "a" * 101},
        ),
        ("POST", f"/api/v1/meetings/{m}/action-items", {"description": "việc", "status": "a" * 21}),
        (
            "POST",
            f"/api/v1/meetings/{m}/action-items",
            {"description": "việc", "due_date": "2026-11-24T09"},
        ),
        (
            "POST",
            f"/api/v1/meetings/{m}/action-items",
            {"description": "việc", "due_date": "2026-02-30"},
        ),
        (
            "POST",
            f"/api/v1/meetings/{m}/action-items",
            {"description": "việc", "assignee_speaker_id": "a" * 37},
        ),
    ]


JSON_CASE_IDS = [
    "patch-meeting-title-201",
    "patch-speaker-name-101",
    "patch-segment-text-5001",
    "action-item-assignee-101",
    "action-item-status-21",
    "action-item-due-date-13-chars",
    "action-item-due-date-invalid-cal",
    "action-item-speaker-id-37",
]


JSON_PARAMS = [pytest.param(i, id=name) for i, name in enumerate(JSON_CASE_IDS)]


@pytest.mark.parametrize("index", JSON_PARAMS)
def test_json_fields_past_the_limit_answer_4xx(
    client: TestClient, seeded: dict[str, str], index: int
) -> None:
    method, url, body = _patch_cases(seeded)[index]
    r = client.request(method, url, json=body)
    assert 400 <= r.status_code < 500, f"{method} {url}: {r.status_code}: {r.text[:300]}"
