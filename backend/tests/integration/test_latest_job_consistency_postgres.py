"""Kiểm thử chọn job mới nhất nhất quán khi trùng created_at trên Postgres (BE-05)."""

import uuid
from collections.abc import Generator
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.models.job import Job
from app.db.models.meeting import Meeting
from app.db.models.user import User
from app.db.session import get_db
from app.main import create_app


@pytest.fixture
def client_with_postgres(db_session: Session) -> Generator[tuple[TestClient, User], None, None]:
    """Khởi tạo TestClient với session PostgreSQL thật."""
    user = User(
        id=str(uuid.uuid4()),
        email="latest-job-tie@example.com",
        display_name="Latest Job Tie",
        password_hash="x",
    )
    db_session.add(user)
    db_session.commit()

    app = create_app()
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_user] = lambda: user
    with TestClient(app) as client:
        yield client, user
    app.dependency_overrides.clear()


def test_list_detail_and_retry_pick_same_latest_job_when_created_at_ties(
    client_with_postgres: tuple[TestClient, User],
    db_session: Session,
) -> None:
    """Khi hai job có cùng created_at trên Postgres, mọi endpoint đều chọn cùng một job mới nhất."""
    client, user = client_with_postgres
    tied_created_at = datetime(2026, 11, 25, 10, 0, 0, tzinfo=UTC)

    meeting = Meeting(
        id=str(uuid.uuid4()),
        owner_id=user.id,
        title="Cuộc họp kiểm tra trùng created_at của job",
        source="upload",
        status="ready",
        version=1,
        created_at=tied_created_at,
        updated_at=tied_created_at,
    )
    db_session.add(meeting)
    db_session.commit()

    # Chèn ...001 trước (failed) rồi ...002 sau (succeeded) với cùng created_at
    # để tái hiện thứ tự bất định của PostgreSQL khi trùng created_at.
    job_001 = Job(
        id="00000000-0000-4000-8000-000000000001",
        meeting_id=meeting.id,
        status="failed",
        stage="summarize",
        progress=0.8,
        created_at=tied_created_at,
    )
    job_002 = Job(
        id="00000000-0000-4000-8000-000000000002",
        meeting_id=meeting.id,
        status="succeeded",
        stage="summarize",
        progress=1.0,
        created_at=tied_created_at,
    )
    db_session.add(job_001)
    db_session.commit()
    db_session.add(job_002)
    db_session.commit()

    list_res = client.get("/api/v1/meetings?page=1&page_size=10")
    assert list_res.status_code == 200
    list_latest_id = list_res.json()["items"][0]["latest_job_id"]

    detail_res = client.get(f"/api/v1/meetings/{meeting.id}")
    assert detail_res.status_code == 200
    detail_data = detail_res.json()
    detail_latest_id = detail_data["latest_job_id"]
    assert detail_data["latest_job"]["id"] == detail_latest_id

    assert list_latest_id == detail_latest_id, (
        f"Danh sách chọn {list_latest_id} nhưng chi tiết chọn {detail_latest_id}"
    )

    job_res = client.get(f"/api/v1/jobs/{list_latest_id}")
    assert job_res.status_code == 200
    assert job_res.json()["id"] == list_latest_id

    # retry_meeting_job cũng phải thấy cùng job mới nhất (job_002 -> 409 JOB_ALREADY_SUCCEEDED)
    retry_res = client.post(f"/api/v1/meetings/{meeting.id}/jobs", json={})
    assert retry_res.status_code == 409
    assert retry_res.json()["error"]["code"] == "JOB_ALREADY_SUCCEEDED"
