"""Kiểm thử persist summary và action items sau stage summarize (BE-07).

Bao gồm:
- Lưu trữ summary và action items từ fixture contracts/fixtures/pipeline/summary*.json.
- Chuyển đổi evidence_segment_indices sang evidence_segment_ids (UUID của segment).
- Xử lý evidence trỏ tới index không tồn tại: loại bỏ evidence đó và đánh dấu needs_review=True.
- Trạng thái status="disabled" và status="insufficient_content" được lưu đúng.
- Idempotent theo (job_id, stage).
"""

import json
import uuid
from collections.abc import Generator
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.models.action_item import ActionItem
from app.db.models.ai_output import AIOutput
from app.db.models.job import Job
from app.db.models.meeting import Meeting
from app.db.models.summary import Summary
from app.db.models.transcript import Segment, Speaker
from app.db.models.user import User
from app.worker.persister import persist_summary

CONTRACT_FIXTURES_DIR = (
    Path(__file__).resolve().parent.parent.parent.parent / "contracts" / "fixtures" / "pipeline"
)


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
        AIOutput.__table__,
        Speaker.__table__,
        Segment.__table__,
        Summary.__table__,
        ActionItem.__table__,
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
    """Tạo user mẫu."""
    user = User(
        id=str(uuid.uuid4()),
        email="summary_user@example.com",
        display_name="Summary User",
        password_hash="hash",
    )
    test_db.add(user)
    test_db.commit()
    return user


@pytest.fixture
def sample_meeting_and_job(test_db: Session, sample_user: User) -> tuple[Meeting, Job]:
    """Tạo meeting và job mẫu kèm các segment tương ứng trong transcript."""
    meeting = Meeting(
        id=str(uuid.uuid4()),
        owner_id=sample_user.id,
        title="Cuộc họp kiểm thử persist summary",
        source="upload",
        status="running",
    )
    test_db.add(meeting)
    test_db.commit()

    job = Job(
        id=str(uuid.uuid4()),
        meeting_id=meeting.id,
        status="running",
        stage="summarize",
    )
    test_db.add(job)
    test_db.commit()

    # Tạo các segment tương ứng với index 0, 1, 2, 3, 4, 5
    for idx in range(6):
        seg = Segment(
            id=str(uuid.uuid4()),
            meeting_id=meeting.id,
            idx=idx,
            start_sec=float(idx * 5),
            end_sec=float(idx * 5 + 4),
            text=f"Nội dung phân đoạn {idx}",
            ai_text=f"Nội dung phân đoạn {idx}",
            version=1,
        )
        test_db.add(seg)
    test_db.commit()

    return meeting, job


def test_persist_summary_happy_path(
    test_db: Session,
    sample_meeting_and_job: tuple[Meeting, Job],
) -> None:
    """Lưu trữ summary.json hợp lệ và đổi evidence_segment_indices sang evidence_segment_ids."""
    meeting, job = sample_meeting_and_job
    fixture_path = CONTRACT_FIXTURES_DIR / "summary.json"
    assert fixture_path.is_file()

    persist_summary(
        test_db,
        meeting_id=meeting.id,
        job_id=job.id,
        artifact_path=fixture_path,
    )

    # 1. Kiểm tra ai_outputs
    ai_out = test_db.execute(
        select(AIOutput).where(AIOutput.job_id == job.id, AIOutput.stage == "summarize")
    ).scalar_one_or_none()
    assert ai_out is not None
    assert ai_out.model == "fake-llm"

    # 2. Kiểm tra summary
    sum_record = test_db.execute(
        select(Summary).where(Summary.meeting_id == meeting.id)
    ).scalar_one_or_none()
    assert sum_record is not None
    assert sum_record.status == "ready"
    assert sum_record.content is not None
    assert "Nhóm chốt phạm vi" in sum_record.content["overview"]

    # Kiểm tra evidence_segment_ids trong key_points
    key_points = sum_record.content["key_points"]
    assert len(key_points) == 1
    # Segment index 1
    seg_1 = test_db.execute(
        select(Segment).where(Segment.meeting_id == meeting.id, Segment.idx == 1)
    ).scalar_one()
    assert key_points[0]["evidence_segment_ids"] == [seg_1.id]

    # 3. Kiểm tra action items
    action_items = (
        test_db.execute(
            select(ActionItem)
            .where(ActionItem.meeting_id == meeting.id)
            .order_by(ActionItem.description.asc())
        )
        .scalars()
        .all()
    )
    assert len(action_items) == 2

    # Tìm action item có due date
    dated_item = next(item for item in action_items if item.due_date is not None)
    assert dated_item.assignee_name == "Anh Minh"
    assert dated_item.due_date == "2026-10-16"
    assert dated_item.source == "ai"
    assert dated_item.ai_original is not None

    seg_2 = test_db.execute(
        select(Segment).where(Segment.meeting_id == meeting.id, Segment.idx == 2)
    ).scalar_one()
    assert dated_item.evidence_segment_ids == [seg_2.id]


def test_persist_summary_disabled_fixture(
    test_db: Session,
    sample_meeting_and_job: tuple[Meeting, Job],
) -> None:
    """Lưu trữ summary_disabled.json hợp lệ với status='disabled'."""
    meeting, job = sample_meeting_and_job
    fixture_path = CONTRACT_FIXTURES_DIR / "summary_disabled.json"
    assert fixture_path.is_file()

    persist_summary(
        test_db,
        meeting_id=meeting.id,
        job_id=job.id,
        artifact_path=fixture_path,
    )

    sum_record = test_db.execute(
        select(Summary).where(Summary.meeting_id == meeting.id)
    ).scalar_one_or_none()
    assert sum_record is not None
    assert sum_record.status == "disabled"
    assert sum_record.content is None


def test_persist_summary_insufficient_content_fixture(
    test_db: Session,
    sample_meeting_and_job: tuple[Meeting, Job],
) -> None:
    """Lưu trữ summary_insufficient.json với status='insufficient_content'."""
    meeting, job = sample_meeting_and_job
    fixture_path = CONTRACT_FIXTURES_DIR / "summary_insufficient.json"
    assert fixture_path.is_file()

    persist_summary(
        test_db,
        meeting_id=meeting.id,
        job_id=job.id,
        artifact_path=fixture_path,
    )

    sum_record = test_db.execute(
        select(Summary).where(Summary.meeting_id == meeting.id)
    ).scalar_one_or_none()
    assert sum_record is not None
    assert sum_record.status == "insufficient_content"
    assert sum_record.content is None


def test_persist_summary_nonexistent_evidence_sets_needs_review(
    test_db: Session,
    sample_meeting_and_job: tuple[Meeting, Job],
    tmp_path: Path,
) -> None:
    """Evidence trỏ tới index segment không tồn tại thì bỏ evidence đó và đặt needs_review=True."""
    meeting, job = sample_meeting_and_job

    bad_summary_data = {
        "schema_version": "1.0",
        "status": "ready",
        "model": "fake-llm",
        "prompt_version": "v1",
        "overview": "Tóm tắt mẫu có evidence sai index.",
        "key_points": [
            {
                "text": "Điểm chính với index 999 không tồn tại",
                "evidence_segment_indices": [999],
            }
        ],
        "decisions": [],
        "action_items": [
            {
                "description": "Nhiệm vụ với index không tồn tại",
                "assignee_name": "Người thực hiện",
                "assignee_speaker_label": None,
                "due_date": None,
                "due_date_text": None,
                "evidence_segment_indices": [999],
                "needs_review": False,
            }
        ],
        "warnings": [],
    }
    file_path = tmp_path / "summary_bad_evidence.json"
    file_path.write_text(json.dumps(bad_summary_data, ensure_ascii=False), encoding="utf-8")

    persist_summary(
        test_db,
        meeting_id=meeting.id,
        job_id=job.id,
        artifact_path=file_path,
    )

    sum_record = test_db.execute(
        select(Summary).where(Summary.meeting_id == meeting.id)
    ).scalar_one()
    # Key point bị loại bỏ evidence không tồn tại
    assert sum_record.content["key_points"][0]["evidence_segment_ids"] == []

    # Action item bị loại bỏ evidence và needs_review thành True
    act = test_db.execute(
        select(ActionItem).where(ActionItem.meeting_id == meeting.id)
    ).scalar_one()
    assert act.evidence_segment_ids == []
    assert act.needs_review is True
    assert act.ai_original["needs_review"] is True


def test_persist_summary_idempotent(
    test_db: Session,
    sample_meeting_and_job: tuple[Meeting, Job],
) -> None:
    """Gọi persist_summary 2 lần không tạo bản ghi trùng lặp."""
    meeting, job = sample_meeting_and_job
    fixture_path = CONTRACT_FIXTURES_DIR / "summary.json"

    # Lần 1
    persist_summary(
        test_db,
        meeting_id=meeting.id,
        job_id=job.id,
        artifact_path=fixture_path,
    )
    ai_count_1 = len(test_db.execute(select(AIOutput)).scalars().all())
    sum_count_1 = len(test_db.execute(select(Summary)).scalars().all())
    act_count_1 = len(test_db.execute(select(ActionItem)).scalars().all())

    # Lần 2
    persist_summary(
        test_db,
        meeting_id=meeting.id,
        job_id=job.id,
        artifact_path=fixture_path,
    )
    ai_count_2 = len(test_db.execute(select(AIOutput)).scalars().all())
    sum_count_2 = len(test_db.execute(select(Summary)).scalars().all())
    act_count_2 = len(test_db.execute(select(ActionItem)).scalars().all())

    assert ai_count_2 == ai_count_1 == 1
    assert sum_count_2 == sum_count_1 == 1
    assert act_count_2 == act_count_1 == 2
