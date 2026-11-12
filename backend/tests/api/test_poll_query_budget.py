"""Kiểm thử ngân sách truy vấn (Query Budget) cho các tuyến đọc và polling (AD-018, BE-12).

Mỗi client trong kịch bản 247 clients thực hiện poll GET /jobs/{id} (khoảng 5 lần)
và đọc GET /meetings/{id}.
Kiểm tra số lượng truy vấn SQL không vượt quá ngân sách (<= 6 truy vấn mỗi request)
và loại bỏ hoàn toàn hiện tượng N+1 query theo số lượng speakers hoặc segments.
"""

import uuid
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import create_access_token
from app.db.base import Base
from app.db.models.job import Job
from app.db.models.meeting import Meeting
from app.db.models.transcript import Segment, Speaker
from app.db.models.user import User
from app.db.session import get_db
from app.main import create_app


@pytest.fixture
def test_db() -> Generator[Session, None, None]:
    """Tạo database SQLite in-memory cho kiểm thử query budget."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    tables = [
        User.__table__,
        Meeting.__table__,
        Job.__table__,
        Speaker.__table__,
        Segment.__table__,
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
def auth_headers_and_user(test_db: Session) -> tuple[dict[str, str], User]:
    """Tạo user và auth cookie session_token cho kiểm thử."""
    user = User(
        id=str(uuid.uuid4()),
        email="budget_test@example.local",
        display_name="Budget Tester",
        password_hash="fakehash",
    )
    test_db.add(user)
    test_db.commit()
    token = create_access_token(user.id)
    return {"session_token": token}, user


@pytest.fixture
def sample_meeting_with_transcript(
    test_db: Session, auth_headers_and_user: tuple[dict[str, str], User]
) -> tuple[Meeting, Job]:
    """Tạo một meeting kèm job, nhiều speakers và nhiều segments để kiểm tra N+1 query."""
    _, user = auth_headers_and_user
    meeting = Meeting(
        id=str(uuid.uuid4()),
        owner_id=user.id,
        title="Cuộc họp kiểm tra Query Budget",
        source="upload",
        status="ready",
        duration_sec=120.0,
    )
    job = Job(
        id=str(uuid.uuid4()),
        meeting_id=meeting.id,
        status="succeeded",
        stage="summarize",
        progress=1.0,
    )
    test_db.add_all([meeting, job])

    # Tạo 5 speakers và 10 segments
    speakers = []
    for i in range(5):
        spk = Speaker(
            id=str(uuid.uuid4()),
            meeting_id=meeting.id,
            label=f"spk_{i}",
            default_name=f"Người nói {i}",
            display_name=f"Người nói {i}",
        )
        speakers.append(spk)
        test_db.add(spk)

    for i in range(10):
        spk = speakers[i % len(speakers)]
        seg = Segment(
            id=str(uuid.uuid4()),
            meeting_id=meeting.id,
            speaker_id=spk.id,
            start_sec=float(i * 10),
            end_sec=float((i + 1) * 10),
            text=f"Đoạn hội thoại số {i}",
            ai_text=f"Đoạn hội thoại số {i}",
            idx=i,
        )
        test_db.add(seg)

    test_db.commit()
    return meeting, job


@pytest.fixture
def client_with_db(test_db: Session) -> Generator[TestClient, None, None]:
    """TestClient FastAPI với dependency override get_db."""
    app = create_app()
    app.dependency_overrides[get_db] = lambda: test_db
    with TestClient(app) as c:
        yield c


def test_get_job_query_budget(
    client_with_db: TestClient,
    test_db: Session,
    auth_headers_and_user: tuple[dict[str, str], User],
    sample_meeting_with_transcript: tuple[Meeting, Job],
) -> None:
    """GET /jobs/{id} không được vượt quá 2 truy vấn SQL (<= 6) và O(1) khi poll nhiều lần."""
    cookies, _ = auth_headers_and_user
    _, job = sample_meeting_with_transcript
    job_id = str(job.id)

    client_with_db.cookies.update(cookies)
    engine = test_db.bind

    queries: list[str] = []

    def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        queries.append(statement)

    event.listen(engine, "before_cursor_execute", before_cursor_execute)
    try:
        # 1. Đo lượt poll đơn lẻ: 1 auth + 1 job (join meeting check owner) = 2 queries
        queries.clear()
        res = client_with_db.get(f"/api/v1/jobs/{job_id}")
        assert res.status_code == 200
        single_count = len(queries)
        assert single_count <= 2, (
            f"GET /jobs/{{id}} thực hiện {single_count} truy vấn, vượt ngưỡng ngân sách 2"
        )

        # 2. Kiểm tra mô hình client poll 5 lần liên tiếp
        queries.clear()
        for _poll_idx in range(5):
            res_poll = client_with_db.get(f"/api/v1/jobs/{job_id}")
            assert res_poll.status_code == 200

        total_poll_queries = len(queries)
        assert total_poll_queries == single_count * 5, (
            f"5 lần poll thực hiện {total_poll_queries} queries (kỳ vọng đúng {single_count * 5})"
        )
    finally:
        event.remove(engine, "before_cursor_execute", before_cursor_execute)


def test_get_meeting_detail_query_budget_and_no_n_plus_one(
    client_with_db: TestClient,
    test_db: Session,
    auth_headers_and_user: tuple[dict[str, str], User],
    sample_meeting_with_transcript: tuple[Meeting, Job],
) -> None:
    """GET /meetings/{id} không vượt quá 4 queries (<= 6) và không bị N+1 theo speakers/segments."""
    cookies, _ = auth_headers_and_user
    meeting, _ = sample_meeting_with_transcript
    meeting_id = str(meeting.id)

    client_with_db.cookies.update(cookies)
    engine = test_db.bind

    queries: list[str] = []

    def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        queries.append(statement)

    event.listen(engine, "before_cursor_execute", before_cursor_execute)
    try:
        # Lần 1: Với 5 speakers và 10 segments
        queries.clear()
        res1 = client_with_db.get(f"/api/v1/meetings/{meeting_id}")
        assert res1.status_code == 200
        count_baseline = len(queries)
        assert count_baseline <= 4, (
            f"GET /meetings/{{id}} thực hiện {count_baseline} truy vấn, vượt ngưỡng ngân sách 4"
        )

        # Thêm 10 speakers và 20 segments nữa vào meeting
        speakers_extra = []
        for i in range(5, 15):
            spk = Speaker(
                id=str(uuid.uuid4()),
                meeting_id=meeting.id,
                label=f"spk_{i}",
                default_name=f"Người nói {i}",
                display_name=f"Người nói {i}",
            )
            speakers_extra.append(spk)
            test_db.add(spk)

        for i in range(10, 30):
            spk = speakers_extra[i % len(speakers_extra)]
            seg = Segment(
                id=str(uuid.uuid4()),
                meeting_id=meeting.id,
                speaker_id=spk.id,
                start_sec=float(i * 10),
                end_sec=float((i + 1) * 10),
                text=f"Đoạn hội thoại mở rộng {i}",
                ai_text=f"Đoạn hội thoại mở rộng {i}",
                idx=i,
            )
            test_db.add(seg)
        test_db.commit()

        # Lần 2: Sau khi tăng gấp 3 số lượng dữ liệu (15 speakers, 30 segments)
        queries.clear()
        res2 = client_with_db.get(f"/api/v1/meetings/{meeting_id}")
        assert res2.status_code == 200
        count_expanded = len(queries)

        assert count_expanded == count_baseline, (
            f"Phát hiện N+1 query: số truy vấn tăng từ {count_baseline} lên {count_expanded} "
            f"khi số lượng speakers và segments tăng"
        )
    finally:
        event.remove(engine, "before_cursor_execute", before_cursor_execute)
