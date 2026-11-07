"""VT-018: pairwise cho POST /meetings/{id}/jobs.

Bốn tham số, tổ hợp đầy đủ là 5 x 4 x 2 x 3 = 120 ca. `allpairspy` chọn tập nhỏ phủ mọi cặp
giá trị của hai tham số bất kỳ. Bảng sinh ra được commit ở docs/evidence/vt-018/pairwise.md
và test `test_pairwise_table_is_current` báo lỗi nếu bảng lệch khỏi bộ sinh.

Oracle viết từ hợp đồng nghiệp vụ (BE-13), không đọc ngược từ code:
1. đang có job active -> 409 JOB_ALREADY_ACTIVE
2. job gần nhất đã thành công và yêu cầu trùng nó -> 409 JOB_ALREADY_SUCCEEDED
3. chạy lại từ đầu hoặc từ asr/diarize/merge khi đã có chỉnh sửa -> 409 HAS_USER_EDITS
4. còn lại -> 202
5. gửi lại cùng Idempotency-Key: 202 được replay (header Idempotent-Replayed), 409 thì không
"""

import uuid
from collections.abc import Generator
from pathlib import Path

import pytest
from allpairspy import AllPairs
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import create_access_token
from app.db.base import Base
from app.db.models.edit_event import EditEvent
from app.db.models.idempotency import IdempotencyKey
from app.db.models.job import Job
from app.db.models.meeting import Meeting
from app.db.models.transcript import Segment, Speaker
from app.db.models.user import User
from app.db.session import get_db
from app.main import create_app

PARAMS = [
    ("from_stage", [None, "asr", "diarize", "merge", "summarize"]),
    ("prev_job", ["failed", "succeeded", "queued", "cancelled"]),
    ("user_edits", [False, True]),
    ("idem", ["absent", "fresh", "replayed"]),
]
NAMES = [n for n, _ in PARAMS]
CASES = [dict(zip(NAMES, row, strict=True)) for row in AllPairs([v for _, v in PARAMS])]
TABLE = Path(__file__).resolve().parents[3] / "docs" / "evidence" / "vt-018" / "pairwise.md"


def expected(case: dict) -> tuple[int, str | None]:
    if case["prev_job"] == "queued":
        return 409, "JOB_ALREADY_ACTIVE"
    if case["prev_job"] == "succeeded" and case["from_stage"] is None:
        return 409, "JOB_ALREADY_SUCCEEDED"
    if case["from_stage"] in (None, "asr", "diarize", "merge") and case["user_edits"]:
        return 409, "HAS_USER_EDITS"
    return 202, None


def render_table() -> str:
    lines = [
        "# VT-018 · Bảng pairwise cho `POST /meetings/{id}/jobs`",
        "",
        "Sinh bằng `allpairspy` từ `tests/unit/test_vt018_pairwise.py`; không sửa tay.",
        f"{len(CASES)} ca thay cho 120 tổ hợp đầy đủ.",
        "",
        "| # | from_stage | job trước | có chỉnh sửa | Idempotency-Key | Kỳ vọng |",
        "|---|---|---|---|---|---|",
    ]
    for i, c in enumerate(CASES, 1):
        code, err = expected(c)
        lines.append(
            f"| {i} | {c['from_stage']} | {c['prev_job']} | {c['user_edits']} | {c['idem']} | "
            f"{code}{' ' + err if err else ''} |"
        )
    return "\n".join(lines) + "\n"


def test_pairwise_table_is_current() -> None:
    assert TABLE.read_text(encoding="utf-8") == render_table(), (
        "Bảng lệch. Chạy: uv run python -m tests.unit.test_vt018_pairwise"
    )


def test_pairwise_covers_every_pair() -> None:
    seen = set()
    for c in CASES:
        for i, a in enumerate(NAMES):
            for b in NAMES[i + 1 :]:
                seen.add((a, c[a], b, c[b]))
    want = {
        (a, va, b, vb)
        for i, (a, vs_a) in enumerate(PARAMS)
        for b, vs_b in PARAMS[i + 1 :]
        for va in vs_a
        for vb in vs_b
    }
    assert seen == want


@pytest.fixture
def db() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    tables = [
        User.__table__,
        Meeting.__table__,
        Job.__table__,
        IdempotencyKey.__table__,
        Speaker.__table__,
        Segment.__table__,
        EditEvent.__table__,
    ]
    Base.metadata.create_all(bind=engine, tables=tables)
    session = sessionmaker(autocommit=False, autoflush=False, bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def build(db: Session, case: dict) -> tuple[TestClient, str]:
    user = User(id=str(uuid.uuid4()), email="pw@example.com", display_name="PW", password_hash="x")
    meeting = Meeting(
        id=str(uuid.uuid4()), owner_id=user.id, title="PW", source="upload", status="ready"
    )
    db.add_all([user, meeting])
    db.commit()
    db.add(
        Job(
            id=str(uuid.uuid4()),
            meeting_id=meeting.id,
            status=case["prev_job"],
            stage="summarize",
            from_stage=None,
            stage_status={},
            progress=1.0 if case["prev_job"] == "succeeded" else 0.2,
            attempt=1,
            max_attempts=3,
        )
    )
    edited = case["user_edits"]
    db.add(
        Segment(
            id=str(uuid.uuid4()),
            meeting_id=meeting.id,
            idx=0,
            start_sec=0.0,
            end_sec=1.0,
            text="đã sửa" if edited else "gốc",
            ai_text="gốc",
            version=2 if edited else 1,
        )
    )
    db.commit()
    app = create_app()

    def _db() -> Generator[Session, None, None]:
        yield db

    app.dependency_overrides[get_db] = _db
    client = TestClient(app)
    client.cookies.set("session_token", create_access_token(user.id))
    return client, meeting.id


@pytest.mark.parametrize("case", CASES, ids=[f"case{i}" for i in range(1, len(CASES) + 1)])
def test_pairwise_retry_endpoint(db: Session, case: dict) -> None:
    client, meeting_id = build(db, case)
    code, err = expected(case)
    url = f"/api/v1/meetings/{meeting_id}/jobs"
    key = {"absent": None, "fresh": str(uuid.uuid4()), "replayed": str(uuid.uuid4())}[case["idem"]]
    headers = {"Idempotency-Key": key} if key else {}

    res = client.post(url, json={"from_stage": case["from_stage"]}, headers=headers)
    assert res.status_code == code, res.text
    if err:
        assert res.json()["error"]["code"] == err

    jobs = db.execute(select(func.count()).select_from(Job)).scalar_one()
    assert jobs == (2 if code == 202 else 1), "chỉ ca 202 mới tạo job"

    if case["idem"] == "replayed":
        again = client.post(url, json={"from_stage": case["from_stage"]}, headers=headers)
        assert again.status_code == code
        # Chỉ phản hồi 202 được lưu để replay; 409 giải phóng key để người dùng thử lại.
        assert (again.headers.get("Idempotent-Replayed") == "true") == (code == 202)
        assert db.execute(select(func.count()).select_from(Job)).scalar_one() == jobs


if __name__ == "__main__":
    TABLE.parent.mkdir(parents=True, exist_ok=True)
    TABLE.write_text(render_table(), encoding="utf-8")
    print(f"ghi {TABLE} ({len(CASES)} ca)")
