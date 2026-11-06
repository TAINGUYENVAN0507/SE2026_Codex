"""Kiểm thử API xuất biên bản cuộc họp GET /api/v1/meetings/{id}/export (BE-05, FE-15).

Bao gồm:
- 3 định dạng (txt, json, md) × 2 biến thể (current, ai_original).
- RT-13: Gọi 3 lần cùng tham số ra cùng byte và không ghi gì vào DB.
- PRIV-12: Người dùng khác truy cập cuộc họp không thuộc sở hữu trả về 404.
- Transcript chưa sẵn sàng (queued/processing/failed) trả về 409 TRANSCRIPT_NOT_READY.
- Định dạng không hỗ trợ (docx, pdf) trả về 422 FORMAT_NOT_SUPPORTED.
- Chưa xác thực trả về 401.
"""

import json
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
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


@pytest.fixture
def test_db() -> Generator[Session, None, None]:
    """Tạo database SQLite in-memory dùng cho test API export."""
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
        id="user-owner-uuid-1234",
        email="owner@example.com",
        display_name="Chủ Cuộc Họp",
        password_hash="mock_hash",
    )
    test_db.add(user)
    test_db.commit()
    test_db.refresh(user)
    return user


@pytest.fixture
def other_user(test_db: Session) -> User:
    """Tạo người dùng khác để kiểm tra PRIV-12."""
    user = User(
        id="user-other-uuid-5678",
        email="other@example.com",
        display_name="Người Dùng Khác",
        password_hash="mock_hash",
    )
    test_db.add(user)
    test_db.commit()
    test_db.refresh(user)
    return user


@pytest.fixture
def ready_meeting(test_db: Session, test_user: User) -> Meeting:
    """Tạo cuộc họp ở trạng thái ready đầy đủ dữ liệu người nói, transcript, summary."""
    meeting = Meeting(
        id="meeting-export-ready-uuid",
        owner_id=test_user.id,
        title="Họp Tổng Kết Quý 3",
        source="upload",
        status="ready",
        meeting_date="2026-10-15",
        duration_sec=300.0,
        version=1,
    )
    test_db.add(meeting)
    test_db.flush()

    spk1 = Speaker(
        id="speaker-uuid-001",
        meeting_id=meeting.id,
        label="SPEAKER_00",
        default_name="Speaker 1",
        display_name="Chị Hương",
        version=1,
    )
    spk2 = Speaker(
        id="speaker-uuid-002",
        meeting_id=meeting.id,
        label="SPEAKER_01",
        default_name="Speaker 2",
        display_name="Anh Tuấn",
        version=1,
    )
    test_db.add_all([spk1, spk2])
    test_db.flush()

    seg1 = Segment(
        id="segment-uuid-001",
        meeting_id=meeting.id,
        idx=0,
        start_sec=0.0,
        end_sec=5.0,
        speaker_id=spk1.id,
        ai_speaker_id=spk1.id,
        text="Chào mọi người, chúng ta bắt đầu họp.",
        ai_text="Chào mọi người, chúng ta bắt đầu.",
        version=1,
    )
    seg2 = Segment(
        id="segment-uuid-002",
        meeting_id=meeting.id,
        idx=1,
        start_sec=6.0,
        end_sec=12.0,
        speaker_id=spk2.id,
        ai_speaker_id=spk2.id,
        text="Tôi đồng ý với phương án triển khai này.",
        ai_text="Tôi đồng ý phương án này.",
        version=1,
    )
    test_db.add_all([seg1, seg2])
    test_db.flush()

    summary = Summary(
        id="summary-uuid-001",
        meeting_id=meeting.id,
        status="ready",
        content={
            "overview": "Tổng quan cuộc họp quý 3 đã chỉnh sửa.",
            "key_points": [
                {
                    "text": "Điểm chính đã sửa",
                    "evidence_segment_ids": [seg1.id],
                }
            ],
            "decisions": [
                {
                    "text": "Quyết định đã sửa",
                    "evidence_segment_ids": [seg2.id],
                }
            ],
        },
        ai_content={
            "overview": "Tổng quan cuộc họp quý 3 từ AI gốc.",
            "key_points": [
                {
                    "text": "Điểm chính từ AI",
                    "evidence_segment_ids": [seg1.id],
                }
            ],
            "decisions": [
                {
                    "text": "Quyết định từ AI",
                    "evidence_segment_ids": [seg2.id],
                }
            ],
        },
        version=1,
    )
    test_db.add(summary)

    action1 = ActionItem(
        id="action-uuid-001",
        meeting_id=meeting.id,
        description="Nhiệm vụ đã được cập nhật mô tả",
        assignee_name="Anh Tuấn",
        due_date="2026-10-30",
        due_date_text="cuối tháng 10",
        status="open",
        source="ai",
        needs_review=False,
        evidence_segment_ids=[seg2.id],
        ai_original={
            "description": "Nhiệm vụ gốc từ AI",
            "assignee_name": "Speaker 2",
            "due_date": "2026-10-25",
            "due_date_text": "sau 10 ngày",
        },
        version=1,
    )
    test_db.add(action1)
    test_db.commit()
    test_db.refresh(meeting)
    return meeting


@pytest.fixture
def auth_client(test_db: Session, test_user: User) -> Generator[TestClient, None, None]:
    """TestClient có xác thực của test_user."""
    app = create_app()
    app.dependency_overrides[get_db] = lambda: test_db
    app.dependency_overrides[get_current_user] = lambda: test_user
    with TestClient(app) as client:
        token = create_access_token(test_user.id)
        client.headers.update({"Authorization": f"Bearer {token}"})
        yield client
    app.dependency_overrides.clear()


@pytest.fixture
def other_auth_client(test_db: Session, other_user: User) -> Generator[TestClient, None, None]:
    """TestClient có xác thực của other_user."""
    app = create_app()
    app.dependency_overrides[get_db] = lambda: test_db
    app.dependency_overrides[get_current_user] = lambda: other_user
    with TestClient(app) as client:
        token = create_access_token(other_user.id)
        client.headers.update({"Authorization": f"Bearer {token}"})
        yield client
    app.dependency_overrides.clear()


@pytest.mark.parametrize("fmt", ["txt", "json", "md"])
@pytest.mark.parametrize("variant", ["current", "ai_original"])
def test_export_meeting_all_formats_and_variants(
    auth_client: TestClient,
    ready_meeting: Meeting,
    fmt: str,
    variant: str,
) -> None:
    """Kiểm tra 3 định dạng × 2 biến thể trả về 200 và dữ liệu phù hợp."""
    response = auth_client.get(
        f"/api/v1/meetings/{ready_meeting.id}/export?format={fmt}&variant={variant}"
    )
    assert response.status_code == 200
    assert "attachment;" in response.headers.get("content-disposition", "")
    assert f".{fmt}" in response.headers.get("content-disposition", "")

    content_str = response.content.decode("utf-8")

    if fmt == "json":
        data = json.loads(content_str)
        assert data["variant"] == variant
        assert data["meeting"]["id"] == ready_meeting.id
        if variant == "current":
            assert data["speakers"][0]["name"] == "Chị Hương"
            assert data["segments"][0]["text"] == "Chào mọi người, chúng ta bắt đầu họp."
            assert data["summary"]["overview"] == "Tổng quan cuộc họp quý 3 đã chỉnh sửa."
            assert data["action_items"][0]["description"] == "Nhiệm vụ đã được cập nhật mô tả"
        else:
            assert data["speakers"][0]["name"] == "Speaker 1"
            assert data["segments"][0]["text"] == "Chào mọi người, chúng ta bắt đầu."
            assert data["summary"]["overview"] == "Tổng quan cuộc họp quý 3 từ AI gốc."
            assert data["action_items"][0]["description"] == "Nhiệm vụ gốc từ AI"

    elif fmt == "txt":
        if variant == "current":
            assert "Chị Hương" in content_str
            assert "Chào mọi người, chúng ta bắt đầu họp." in content_str
        else:
            assert "Speaker 1" in content_str
            assert "Chào mọi người, chúng ta bắt đầu." in content_str

    elif fmt == "md":
        assert ready_meeting.title in content_str
        if variant == "current":
            assert "Chị Hương" in content_str
            assert "Tổng quan cuộc họp quý 3 đã chỉnh sửa." in content_str
            assert "Nhiệm vụ đã được cập nhật mô tả" in content_str
        else:
            assert "Speaker 1" in content_str
            assert "Tổng quan cuộc họp quý 3 từ AI gốc." in content_str
            assert "Nhiệm vụ gốc từ AI" in content_str


def test_rt13_export_deterministic_and_no_db_write(
    auth_client: TestClient,
    test_db: Session,
    ready_meeting: Meeting,
) -> None:
    """RT-13: Gọi export 3 lần cùng tham số ra cùng byte chính xác và không ghi gì vào DB."""
    # Đếm số lượng bản ghi ban đầu của các bảng
    initial_counts = {
        "meetings": test_db.execute(select(func.count(Meeting.id))).scalar_one(),
        "segments": test_db.execute(select(func.count(Segment.id))).scalar_one(),
        "speakers": test_db.execute(select(func.count(Speaker.id))).scalar_one(),
        "summaries": test_db.execute(select(func.count(Summary.id))).scalar_one(),
        "action_items": test_db.execute(select(func.count(ActionItem.id))).scalar_one(),
        "edit_events": test_db.execute(select(func.count(EditEvent.id))).scalar_one(),
    }

    resp1 = auth_client.get(
        f"/api/v1/meetings/{ready_meeting.id}/export?format=json&variant=current"
    )
    resp2 = auth_client.get(
        f"/api/v1/meetings/{ready_meeting.id}/export?format=json&variant=current"
    )
    resp3 = auth_client.get(
        f"/api/v1/meetings/{ready_meeting.id}/export?format=json&variant=current"
    )

    assert resp1.status_code == 200
    assert resp2.status_code == 200
    assert resp3.status_code == 200

    # Khẳng định trả về byte giống hệt nhau
    assert resp1.content == resp2.content == resp3.content

    # Kiểm tra database không có bất kỳ bản ghi nào bị ghi thêm
    after_counts = {
        "meetings": test_db.execute(select(func.count(Meeting.id))).scalar_one(),
        "segments": test_db.execute(select(func.count(Segment.id))).scalar_one(),
        "speakers": test_db.execute(select(func.count(Speaker.id))).scalar_one(),
        "summaries": test_db.execute(select(func.count(Summary.id))).scalar_one(),
        "action_items": test_db.execute(select(func.count(ActionItem.id))).scalar_one(),
        "edit_events": test_db.execute(select(func.count(EditEvent.id))).scalar_one(),
    }
    assert initial_counts == after_counts


def test_priv12_other_user_gets_404(
    other_auth_client: TestClient,
    ready_meeting: Meeting,
) -> None:
    """PRIV-12: Người dùng khác truy cập export cuộc họp không phải của mình nhận 404."""
    response = other_auth_client.get(f"/api/v1/meetings/{ready_meeting.id}/export?format=txt")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "MEETING_NOT_FOUND"


def test_export_meeting_not_ready_returns_409(
    auth_client: TestClient,
    test_db: Session,
    test_user: User,
) -> None:
    """Cuộc họp chưa ở trạng thái ready/partial trả về 409 TRANSCRIPT_NOT_READY."""
    meeting = Meeting(
        id="meeting-processing-uuid",
        owner_id=test_user.id,
        title="Họp đang xử lý",
        source="upload",
        status="processing",
        version=1,
    )
    test_db.add(meeting)
    test_db.commit()

    response = auth_client.get(f"/api/v1/meetings/{meeting.id}/export?format=txt")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "TRANSCRIPT_NOT_READY"


def test_export_unsupported_format_returns_422(
    auth_client: TestClient,
    ready_meeting: Meeting,
) -> None:
    """Định dạng không hỗ trợ (docx, pdf) trả về 422 FORMAT_NOT_SUPPORTED."""
    for bad_fmt in ["docx", "pdf", "xlsx", "unknown"]:
        response = auth_client.get(f"/api/v1/meetings/{ready_meeting.id}/export?format={bad_fmt}")
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "FORMAT_NOT_SUPPORTED"


def test_export_unauthenticated_returns_401(
    ready_meeting: Meeting,
) -> None:
    """Chưa đăng nhập trả về 401."""
    app = create_app()
    with TestClient(app) as client:
        response = client.get(f"/api/v1/meetings/{ready_meeting.id}/export?format=txt")
        assert response.status_code == 401
