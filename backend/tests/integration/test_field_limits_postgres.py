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


# 11-25 (C): các endpoint ghi còn lại. Mỗi ca cần một bản ghi có sẵn (công việc, tóm tắt).
def _summary(db_session: Session, meeting_id: str) -> None:
    from app.db.models.summary import Summary

    db_session.add(
        Summary(
            id=str(uuid.uuid4()),
            meeting_id=meeting_id,
            status="ready",
            content={"overview": "Tổng quan", "key_points": [], "decisions": []},
            version=1,
        )
    )
    db_session.commit()


def _summary_body(**content) -> dict:
    return {
        "content": {"overview": "Tổng quan", "key_points": [], "decisions": [], **content},
        "version": 1,
    }


MORE_CASE_IDS = [
    "patch-action-item-assignee-101",
    "patch-action-item-due-date-invalid",
    "patch-action-item-status-21",
    "patch-speaker-name-51",
    "patch-segment-speaker-id-37",
    "patch-segment-speaker-id-unknown-uuid",
    "put-summary-overview-5001",
    "put-summary-51-key-points",
    "put-summary-evidence-id-unknown",
    "login-email-300",
    "login-password-100k",
]


def _more_cases(ids: dict[str, str], item_id: str) -> list[tuple[str, str, dict]]:
    m, sp, sg = ids["meeting"], ids["speaker"], ids["segment"]
    item = f"/api/v1/meetings/{m}/action-items/{item_id}"
    point = {"text": "ý", "evidence_segment_ids": []}
    return [
        ("PATCH", item, {"assignee_name": "a" * 101, "version": 1}),
        ("PATCH", item, {"due_date": "2026-13-01", "version": 1}),
        ("PATCH", item, {"status": "a" * 21, "version": 1}),
        ("PATCH", f"/api/v1/meetings/{m}/speakers/{sp}", {"display_name": "a" * 51, "version": 1}),
        ("PATCH", f"/api/v1/meetings/{m}/segments/{sg}", {"speaker_id": "a" * 37, "version": 1}),
        (
            "PATCH",
            f"/api/v1/meetings/{m}/segments/{sg}",
            {"speaker_id": str(uuid.uuid4()), "version": 1},
        ),
        ("PUT", f"/api/v1/meetings/{m}/summary", _summary_body(overview="a" * 5001)),
        ("PUT", f"/api/v1/meetings/{m}/summary", _summary_body(key_points=[point] * 51)),
        (
            "PUT",
            f"/api/v1/meetings/{m}/summary",
            _summary_body(key_points=[{"text": "ý", "evidence_segment_ids": [str(uuid.uuid4())]}]),
        ),
        ("POST", "/api/v1/auth/login", {"email": "a" * 290 + "@example.com", "password": "x"}),
        ("POST", "/api/v1/auth/login", {"email": "khong@example.com", "password": "x" * 100_000}),
    ]


MORE_PARAMS = [pytest.param(i, id=name) for i, name in enumerate(MORE_CASE_IDS)]


@pytest.mark.parametrize("index", MORE_PARAMS)
def test_more_write_endpoints_past_the_limit_answer_4xx(
    client: TestClient, db_session: Session, seeded: dict[str, str], index: int
) -> None:
    _summary(db_session, seeded["meeting"])
    created = client.post(
        f"/api/v1/meetings/{seeded['meeting']}/action-items", json={"description": "việc"}
    )
    assert created.status_code == 201, created.text[:300]
    method, url, body = _more_cases(seeded, created.json()["id"])[index]
    r = client.request(method, url, json=body)
    assert 400 <= r.status_code < 500, f"{method} {url}: {r.status_code}: {r.text[:300]}"
    if MORE_CASE_IDS[index] == "put-summary-evidence-id-unknown":
        assert r.status_code == 422
        assert r.json()["error"]["code"] == "EVIDENCE_SEGMENT_NOT_IN_MEETING"


def test_put_summary_rejects_evidence_from_other_meeting_and_accepts_same_meeting(
    client: TestClient, db_session: Session, seeded: dict[str, str]
) -> None:
    """PUT /summary phải từ chối segment của cuộc họp khác (cả key_points và decisions)."""
    _summary(db_session, seeded["meeting"])

    other_meeting = Meeting(
        id=str(uuid.uuid4()),
        owner_id=seeded["user"],
        title="Cuộc họp khác",
        source="upload",
        status="ready",
        version=1,
    )
    other_segment = Segment(
        id=str(uuid.uuid4()),
        meeting_id=other_meeting.id,
        idx=0,
        start_sec=0.0,
        end_sec=1.0,
        text="đoạn của cuộc họp khác",
        ai_text="đoạn của cuộc họp khác",
        version=1,
    )
    db_session.add(other_meeting)
    db_session.commit()
    db_session.add(other_segment)
    db_session.commit()

    url = f"/api/v1/meetings/{seeded['meeting']}/summary"

    # Segment thuộc cuộc họp khác trong key_points -> 422 EVIDENCE_SEGMENT_NOT_IN_MEETING
    r_kp = client.put(
        url,
        json=_summary_body(key_points=[{"text": "ý", "evidence_segment_ids": [other_segment.id]}]),
    )
    assert r_kp.status_code == 422, r_kp.text[:300]
    assert r_kp.json()["error"]["code"] == "EVIDENCE_SEGMENT_NOT_IN_MEETING"

    # Segment thuộc cuộc họp khác trong decisions -> 422 EVIDENCE_SEGMENT_NOT_IN_MEETING
    r_dec = client.put(
        url,
        json=_summary_body(
            decisions=[{"text": "chốt", "evidence_segment_ids": [other_segment.id]}]
        ),
    )
    assert r_dec.status_code == 422, r_dec.text[:300]
    assert r_dec.json()["error"]["code"] == "EVIDENCE_SEGMENT_NOT_IN_MEETING"

    # Segment thuộc chính cuộc họp -> 200 OK
    r_ok = client.put(
        url,
        json=_summary_body(
            key_points=[{"text": "ý đúng", "evidence_segment_ids": [seeded["segment"]]}],
            decisions=[{"text": "chốt đúng", "evidence_segment_ids": [seeded["segment"]]}],
        ),
    )
    assert r_ok.status_code == 200, r_ok.text[:300]


# Chữ của từng ý chính và quyết định (C, 2026-11-26). `SummaryPointOut.text` chưa có giới hạn,
# và API không giới hạn dung lượng body JSON, nên `PUT /summary` lưu một ý dài tùy ý. Giới hạn
# cần đặt là 1..1000 ký tự sau khi bỏ khoảng trắng hai đầu; frontend dùng cùng số. Tổng quan
# chỉ có khoảng trắng cũng đang được lưu.
SUMMARY_POINT_TEXT_MAX = 1000
POINT_B_2026_11_26 = (
    "PUT summary nhận ý chính hoặc quyết định quá 1000 ký tự hoặc rỗng, và tổng quan chỉ có "
    "khoảng trắng (trả 200); giao B ngày 11-26, việc 1 (tasks/2026-11-26/member-b.md)"
)
POINT_CASES = {
    "put-summary-key-point-text-1001": {
        "key_points": [{"text": "a" * (SUMMARY_POINT_TEXT_MAX + 1), "evidence_segment_ids": []}]
    },
    "put-summary-decision-text-1001": {
        "decisions": [{"text": "a" * (SUMMARY_POINT_TEXT_MAX + 1), "evidence_segment_ids": []}]
    },
    "put-summary-key-point-text-empty": {"key_points": [{"text": "", "evidence_segment_ids": []}]},
    "put-summary-decision-text-blank": {"decisions": [{"text": "   ", "evidence_segment_ids": []}]},
    "put-summary-overview-blank": {"overview": "   "},
}


@pytest.mark.parametrize(
    "name",
    [
        pytest.param(
            name,
            id=name,
            marks=pytest.mark.xfail(strict=True, raises=AssertionError, reason=POINT_B_2026_11_26),
        )
        for name in POINT_CASES
    ],
)
def test_put_summary_point_text_outside_1_to_1000_answers_422(
    client: TestClient, db_session: Session, seeded: dict[str, str], name: str
) -> None:
    _summary(db_session, seeded["meeting"])
    r = client.put(
        f"/api/v1/meetings/{seeded['meeting']}/summary", json=_summary_body(**POINT_CASES[name])
    )
    assert r.status_code == 422, f"{name}: {r.status_code}: {r.text[:200]}"


def test_put_summary_point_text_at_1000_is_saved(
    client: TestClient, db_session: Session, seeded: dict[str, str]
) -> None:
    """Đúng 1000 ký tự thì vẫn lưu được (biên trên của giới hạn trên)."""
    _summary(db_session, seeded["meeting"])
    text = "a" * SUMMARY_POINT_TEXT_MAX
    r = client.put(
        f"/api/v1/meetings/{seeded['meeting']}/summary",
        json=_summary_body(
            key_points=[{"text": text, "evidence_segment_ids": []}],
            decisions=[{"text": text, "evidence_segment_ids": []}],
        ),
    )
    assert r.status_code == 200, r.text[:300]
    assert r.json()["content"]["key_points"][0]["text"] == text


def test_get_summary_still_answers_200_for_stored_points_longer_than_the_input_limit(
    client: TestClient, db_session: Session, seeded: dict[str, str]
) -> None:
    """Giới hạn mới chỉ áp cho dữ liệu gửi lên. Tóm tắt đã lưu từ trước (hoặc do AI sinh) có ý
    dài hơn 1000 ký tự thì `GET /summary` và `GET /meetings/{id}` vẫn phải trả 200, không 500.
    `SummaryContentOut` dùng cho cả đầu vào và đầu ra, nên đặt `max_length` thẳng vào đó sẽ làm
    test này đỏ."""
    from app.db.models.summary import Summary

    long_text = "b" * (SUMMARY_POINT_TEXT_MAX * 5)
    db_session.add(
        Summary(
            id=str(uuid.uuid4()),
            meeting_id=seeded["meeting"],
            status="ready",
            content={
                "overview": "Tổng quan",
                "key_points": [{"text": long_text, "evidence_segment_ids": []}],
                "decisions": [{"text": long_text, "evidence_segment_ids": []}],
            },
            version=1,
        )
    )
    db_session.commit()

    r = client.get(f"/api/v1/meetings/{seeded['meeting']}/summary")
    assert r.status_code == 200, r.text[:300]
    assert r.json()["content"]["key_points"][0]["text"] == long_text
    assert client.get(f"/api/v1/meetings/{seeded['meeting']}").status_code == 200
