"""Kiểm thử tính toán segment_count và speaking_time_sec của người nói (BE-05).

Xác nhận tính nhất quán giữa 3 endpoint:
1. GET /api/v1/meetings/{id}/transcript
2. GET /api/v1/meetings/{id}
3. PATCH /api/v1/speakers/{id}
"""

import uuid
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import get_current_user
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


@pytest.fixture
def test_db() -> Generator[Session, None, None]:
    """Tạo database SQLite in-memory dùng cho test."""
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
def user_a(test_db: Session) -> User:
    """Tạo người dùng sở hữu cuộc họp."""
    user = User(
        id=str(uuid.uuid4()),
        email="speaker_stats_user@example.com",
        display_name="Speaker Stats User",
        password_hash="mock_hash",
    )
    test_db.add(user)
    test_db.commit()
    return user


@pytest.fixture
def client_a(test_db: Session, user_a: User) -> Generator[TestClient, None, None]:
    """TestClient xác thực với User A."""
    app = create_app()
    app.dependency_overrides[get_db] = lambda: test_db
    app.dependency_overrides[get_current_user] = lambda: user_a
    token = create_access_token(user_a.id)
    with TestClient(app, cookies={"session_token": token}) as client:
        yield client
    app.dependency_overrides.clear()


def test_speaker_segment_count_and_speaking_time_consistent(
    client_a: TestClient,
    test_db: Session,
    user_a: User,
) -> None:
    """Meeting ready có 3 segments cho speaker 1 và 1 segment cho speaker 2.

    Cả GET transcript, GET meeting detail và PATCH speaker đều phải trả đúng số liệu (BE-05).
    """
    meeting_id = str(uuid.uuid4())
    spk1_id = str(uuid.uuid4())
    spk2_id = str(uuid.uuid4())

    meeting = Meeting(
        id=meeting_id,
        owner_id=user_a.id,
        title="Cuộc họp kiểm tra thống kê người nói",
        source="upload",
        status="ready",
        version=1,
    )
    spk1 = Speaker(
        id=spk1_id,
        meeting_id=meeting_id,
        label="spk_0",
        default_name="Người nói 1",
        display_name="Người nói 1",
        version=1,
    )
    spk2 = Speaker(
        id=spk2_id,
        meeting_id=meeting_id,
        label="spk_1",
        default_name="Người nói 2",
        display_name="Người nói 2",
        version=1,
    )

    # Speaker 1: 3 segments, tổng thời gian = 2.5 + 2.25 + 2.0 = 6.75s
    seg1 = Segment(
        id=str(uuid.uuid4()),
        meeting_id=meeting_id,
        speaker_id=spk1_id,
        start_sec=0.0,
        end_sec=2.5,
        text="Đoạn 1 của spk 1",
        ai_text="Đoạn 1 của spk 1",
        idx=0,
    )
    seg2 = Segment(
        id=str(uuid.uuid4()),
        meeting_id=meeting_id,
        speaker_id=spk1_id,
        start_sec=3.0,
        end_sec=5.25,
        text="Đoạn 2 của spk 1",
        ai_text="Đoạn 2 của spk 1",
        idx=1,
    )
    seg3 = Segment(
        id=str(uuid.uuid4()),
        meeting_id=meeting_id,
        speaker_id=spk1_id,
        start_sec=6.0,
        end_sec=8.0,
        text="Đoạn 3 của spk 1",
        ai_text="Đoạn 3 của spk 1",
        idx=2,
    )

    # Speaker 2: 1 segment, thời gian = 12.42 - 9.0 = 3.42s
    seg4 = Segment(
        id=str(uuid.uuid4()),
        meeting_id=meeting_id,
        speaker_id=spk2_id,
        start_sec=9.0,
        end_sec=12.42,
        text="Đoạn 1 của spk 2",
        ai_text="Đoạn 1 của spk 2",
        idx=3,
    )

    test_db.add_all([meeting, spk1, spk2, seg1, seg2, seg3, seg4])
    test_db.commit()

    # 1. Kiểm tra GET /api/v1/meetings/{id}/transcript
    res_transcript = client_a.get(f"/api/v1/meetings/{meeting_id}/transcript")
    assert res_transcript.status_code == 200
    t_speakers = {s["id"]: s for s in res_transcript.json()["speakers"]}

    assert t_speakers[spk1_id]["segment_count"] == 3
    assert t_speakers[spk1_id]["speaking_time_sec"] == 6.75
    assert t_speakers[spk2_id]["segment_count"] == 1
    assert t_speakers[spk2_id]["speaking_time_sec"] == 3.42

    # 2. Kiểm tra GET /api/v1/meetings/{id} (meeting detail)
    res_detail = client_a.get(f"/api/v1/meetings/{meeting_id}")
    assert res_detail.status_code == 200
    d_speakers = {s["id"]: s for s in res_detail.json()["speakers"]}

    assert d_speakers[spk1_id]["segment_count"] == 3
    assert d_speakers[spk1_id]["speaking_time_sec"] == 6.75
    assert d_speakers[spk2_id]["segment_count"] == 1
    assert d_speakers[spk2_id]["speaking_time_sec"] == 3.42

    # 3. Kiểm tra PATCH /api/v1/meetings/{meeting_id}/speakers/{id}
    res_patch = client_a.patch(
        f"/api/v1/meetings/{meeting_id}/speakers/{spk1_id}",
        json={"display_name": "Nguyễn Văn Một", "version": 1},
    )
    assert res_patch.status_code == 200
    p_spk1 = res_patch.json()
    assert p_spk1["segment_count"] == 3
    assert p_spk1["speaking_time_sec"] == 6.75

    # Khẳng định cả 3 nơi trả dữ liệu giống hệt nhau
    assert (
        t_speakers[spk1_id]["segment_count"]
        == d_speakers[spk1_id]["segment_count"]
        == p_spk1["segment_count"]
    )
    assert (
        t_speakers[spk1_id]["speaking_time_sec"]
        == d_speakers[spk1_id]["speaking_time_sec"]
        == p_spk1["speaking_time_sec"]
    )
