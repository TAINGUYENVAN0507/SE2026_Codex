"""Kiểm thử persist transcript sau stage merge (BE-07).

Bao gồm:
- Lưu trữ transcript vào DB: ai_outputs, speakers, segments trong 1 transaction.
- RT-12: Chạy persist 2 lần không tạo bản trùng (Idempotent theo job_id và stage).
- Fixture sai schema hoặc schema_version không hỗ trợ thì báo lỗi PIPELINE_OUTPUT_INVALID.
"""

import json
import uuid
from collections.abc import Generator
from pathlib import Path

import pytest
from meeting_pipeline.errors import ErrorCode, PermanentPipelineError
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.models.ai_output import AIOutput
from app.db.models.job import Job
from app.db.models.meeting import Meeting
from app.db.models.transcript import Segment, Speaker
from app.db.models.user import User
from app.worker.persister import persist_transcript


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
        email="persist_user@example.com",
        display_name="Persist User",
        password_hash="hash",
    )
    test_db.add(user)
    test_db.commit()
    return user


@pytest.fixture
def sample_meeting_and_job(test_db: Session, sample_user: User) -> tuple[Meeting, Job]:
    """Tạo meeting và job mẫu."""
    meeting = Meeting(
        id=str(uuid.uuid4()),
        owner_id=sample_user.id,
        title="Cuộc họp kiểm thử persist",
        source="upload",
        status="running",
    )
    test_db.add(meeting)
    test_db.commit()

    job = Job(
        id=str(uuid.uuid4()),
        meeting_id=meeting.id,
        status="running",
        stage="merge",
    )
    test_db.add(job)
    test_db.commit()
    return meeting, job


@pytest.fixture
def valid_transcript_file(tmp_path: Path) -> Path:
    """Tạo tệp transcript.json hợp lệ theo đúng schema pipeline."""
    data = {
        "schema_version": "1.0",
        "audio": {
            "duration_sec": 120.5,
            "sample_rate": 16000,
            "channels": 1,
        },
        "models": {
            "asr": "faster-whisper-large-v3",
            "diarization": "pyannote-3.1",
        },
        "diarization_status": "ok",
        "speakers": [
            {"label": "SPEAKER_00", "first_start_sec": 0.5},
            {"label": "SPEAKER_01", "first_start_sec": 4.5},
        ],
        "segments": [
            {
                "index": 0,
                "start_sec": 0.5,
                "end_sec": 4.2,
                "text": "Xin chào mọi người, chúng ta bắt đầu cuộc họp.",
                "speaker_label": "SPEAKER_00",
                "confidence": 0.95,
                "words": [],
                "flags": [],
            },
            {
                "index": 1,
                "start_sec": 4.5,
                "end_sec": 8.0,
                "text": "Vâng chào anh, tôi đã chuẩn bị xong báo cáo tuần.",
                "speaker_label": "SPEAKER_01",
                "confidence": 0.92,
                "words": [],
                "flags": [],
            },
        ],
        "warnings": [],
    }
    file_path = tmp_path / "transcript.json"
    file_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return file_path


def test_persist_transcript_happy_path(
    test_db: Session,
    sample_meeting_and_job: tuple[Meeting, Job],
    valid_transcript_file: Path,
) -> None:
    """Lưu trữ transcript thành công vào ai_outputs, speakers và segments."""
    meeting, job = sample_meeting_and_job

    persist_transcript(
        test_db,
        meeting_id=meeting.id,
        job_id=job.id,
        artifact_path=valid_transcript_file,
    )

    # 1. Kiểm tra ai_outputs
    ai_out = test_db.execute(
        select(AIOutput).where(AIOutput.job_id == job.id, AIOutput.stage == "merge")
    ).scalar_one_or_none()
    assert ai_out is not None
    assert ai_out.meeting_id == meeting.id
    assert ai_out.model == "faster-whisper-large-v3"
    assert ai_out.payload["audio"]["duration_sec"] == 120.5

    # 2. Kiểm tra speakers
    speakers = (
        test_db.execute(
            select(Speaker).where(Speaker.meeting_id == meeting.id).order_by(Speaker.label.asc())
        )
        .scalars()
        .all()
    )
    assert len(speakers) == 2
    assert speakers[0].label == "SPEAKER_00"
    assert speakers[0].display_name == "Speaker 1"
    assert speakers[1].label == "SPEAKER_01"
    assert speakers[1].display_name == "Speaker 2"

    # 3. Kiểm tra segments
    segments = (
        test_db.execute(
            select(Segment).where(Segment.meeting_id == meeting.id).order_by(Segment.idx.asc())
        )
        .scalars()
        .all()
    )
    assert len(segments) == 2

    assert segments[0].idx == 0
    assert segments[0].start_sec == 0.5
    assert segments[0].end_sec == 4.2
    assert segments[0].text == "Xin chào mọi người, chúng ta bắt đầu cuộc họp."
    assert segments[0].ai_text == "Xin chào mọi người, chúng ta bắt đầu cuộc họp."
    assert segments[0].speaker_id == speakers[0].id
    assert segments[0].ai_speaker_id == speakers[0].id

    assert segments[1].idx == 1
    assert segments[1].text == "Vâng chào anh, tôi đã chuẩn bị xong báo cáo tuần."
    assert segments[1].speaker_id == speakers[1].id


def test_persist_transcript_idempotent_rt12(
    test_db: Session,
    sample_meeting_and_job: tuple[Meeting, Job],
    valid_transcript_file: Path,
) -> None:
    """RT-12: Gọi persist 2 lần liên tiếp không tạo bản trùng lặp trong DB."""
    meeting, job = sample_meeting_and_job

    # Lần 1
    persist_transcript(
        test_db,
        meeting_id=meeting.id,
        job_id=job.id,
        artifact_path=valid_transcript_file,
    )

    count_ai_1 = len(test_db.execute(select(AIOutput)).scalars().all())
    count_speakers_1 = len(test_db.execute(select(Speaker)).scalars().all())
    count_segments_1 = len(test_db.execute(select(Segment)).scalars().all())

    # Lần 2 (chạy lại do retry hoặc duplicate callback)
    persist_transcript(
        test_db,
        meeting_id=meeting.id,
        job_id=job.id,
        artifact_path=valid_transcript_file,
    )

    count_ai_2 = len(test_db.execute(select(AIOutput)).scalars().all())
    count_speakers_2 = len(test_db.execute(select(Speaker)).scalars().all())
    count_segments_2 = len(test_db.execute(select(Segment)).scalars().all())

    assert count_ai_2 == count_ai_1 == 1
    assert count_speakers_2 == count_speakers_1 == 2
    assert count_segments_2 == count_segments_1 == 2


def test_persist_transcript_unsupported_schema_version(
    test_db: Session,
    sample_meeting_and_job: tuple[Meeting, Job],
    tmp_path: Path,
) -> None:
    """schema_version không hỗ trợ (vd 2.0) phải raise PIPELINE_OUTPUT_INVALID."""
    meeting, job = sample_meeting_and_job
    bad_file = tmp_path / "transcript_v2.json"
    bad_data = {
        "schema_version": "2.0",
        "audio": {"duration_sec": 10.0, "sample_rate": 16000, "channels": 1},
        "models": {"asr": "whisper", "diarization": "pyannote"},
        "diarization_status": "ok",
        "speakers": [],
        "segments": [],
        "warnings": [],
    }
    bad_file.write_text(json.dumps(bad_data), encoding="utf-8")

    with pytest.raises(PermanentPipelineError) as exc_info:
        persist_transcript(
            test_db,
            meeting_id=meeting.id,
            job_id=job.id,
            artifact_path=bad_file,
        )

    assert exc_info.value.code == ErrorCode.PIPELINE_OUTPUT_INVALID


def test_persist_transcript_invalid_schema_content(
    test_db: Session,
    sample_meeting_and_job: tuple[Meeting, Job],
    tmp_path: Path,
) -> None:
    """Nội dung JSON vi phạm ràng buộc schema (start_sec >= end_sec) phải raise lỗi."""
    meeting, job = sample_meeting_and_job
    invalid_file = tmp_path / "transcript_invalid.json"
    invalid_data = {
        "schema_version": "1.0",
        "audio": {"duration_sec": 10.0, "sample_rate": 16000, "channels": 1},
        "models": {"asr": "whisper", "diarization": "pyannote"},
        "diarization_status": "ok",
        "speakers": [{"label": "SPEAKER_00"}],
        "segments": [
            {
                "index": 0,
                "start_sec": 5.0,
                "end_sec": 2.0,  # Lỗi start_sec >= end_sec
                "text": "Lỗi thời gian",
                "speaker_label": "SPEAKER_00",
                "words": [],
                "flags": [],
            }
        ],
        "warnings": [],
    }
    invalid_file.write_text(json.dumps(invalid_data), encoding="utf-8")

    with pytest.raises(PermanentPipelineError) as exc_info:
        persist_transcript(
            test_db,
            meeting_id=meeting.id,
            job_id=job.id,
            artifact_path=invalid_file,
        )

    assert exc_info.value.code == ErrorCode.PIPELINE_OUTPUT_INVALID


def test_persist_transcript_errors_never_echo_canary_content(
    test_db: Session,
    sample_meeting_and_job: tuple[Meeting, Job],
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Kiểm tra lỗi persist không lộ chuỗi canary vào job.error_message, response API hay log."""
    import logging
    from unittest.mock import patch

    from fastapi.testclient import TestClient
    from meeting_pipeline.runner import Stage

    from app.api.deps import get_current_user
    from app.db.session import get_db
    from app.main import create_app
    from app.services.storage.local import LocalStorage
    from app.worker.runner import process_job

    meeting, job = sample_meeting_and_job
    canary = "CANARY_7f3a_secret_meeting_text"

    bad_file = tmp_path / "transcript.json"
    bad_data = {
        "schema_version": "1.0",
        "audio": {"duration_sec": 10.0, "sample_rate": 16000, "channels": 1},
        "models": {"asr": "whisper", "diarization": "pyannote"},
        "diarization_status": "ok",
        "speakers": [{"label": "SPEAKER_00"}],
        "segments": [
            {
                "index": 0,
                "start_sec": 10.0,
                "end_sec": 2.0,  # Invalid: start > end
                "text": f"Nội dung nhạy cảm {canary}",
                "speaker_label": "SPEAKER_00",
                "words": [],
                "flags": [],
            }
        ],
        "warnings": [],
    }
    bad_file.write_text(json.dumps(bad_data), encoding="utf-8")

    # 1. Gọi trực tiếp persist_transcript
    with pytest.raises(PermanentPipelineError) as exc_info:
        persist_transcript(
            test_db,
            meeting_id=meeting.id,
            job_id=job.id,
            artifact_path=bad_file,
        )

    assert canary not in exc_info.value.message
    assert str(tmp_path) not in exc_info.value.message
    assert exc_info.value.code == ErrorCode.PIPELINE_OUTPUT_INVALID

    # 2. Chạy qua process_job với caplog
    caplog.set_level(logging.INFO)
    storage = LocalStorage(base_dir=tmp_path)

    def mock_run_job(*args, **kwargs):
        on_done = kwargs.get("on_stage_done")
        if on_done:
            on_done(Stage.MERGE, bad_file)
        raise exc_info.value

    with patch("app.worker.runner.run_job", mock_run_job):
        process_job(
            test_db,
            job,
            storage=storage,
            backend="fake",
        )

    test_db.refresh(job)
    assert job.status == "failed"
    assert job.error_message is not None
    assert canary not in job.error_message
    assert str(tmp_path) not in job.error_message
    assert canary not in caplog.text

    # 3. Kiểm tra phản hồi API GET /jobs/{id}
    app = create_app()
    owner = test_db.get(User, meeting.owner_id)
    app.dependency_overrides[get_db] = lambda: test_db
    app.dependency_overrides[get_current_user] = lambda: owner

    client = TestClient(app)
    response = client.get(f"/api/v1/jobs/{job.id}")
    assert response.status_code == 200
    assert canary not in response.text
    assert str(tmp_path) not in response.text
