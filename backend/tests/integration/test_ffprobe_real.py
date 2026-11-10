"""Đường ffprobe thật, không mock (VT-018, BE-15).

Các test API upload khác luôn mock `probe_audio` để kết quả không phụ thuộc máy.
Trước 2026-11-10, chúng chỉ mock khi máy KHÔNG có ffprobe và gửi `RIFF` + byte 0:
CI (không có ffprobe) xanh, máy có ffprobe đỏ 5 test (`docs/evidence/vt-018/04-red-ffprobe.log`).
File này giữ đường thật: WAV hợp lệ sinh tại chỗ thì qua, `RIFF` giả thì bị từ chối.
"""

import io
import shutil
import uuid
import wave
from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import get_current_user
from app.core.errors import APIError
from app.db.base import Base
from app.db.models.idempotency import IdempotencyKey
from app.db.models.job import Job
from app.db.models.meeting import Meeting
from app.db.models.user import User
from app.db.session import get_db
from app.main import create_app
from app.services.audio_validator import probe_audio
from app.services.storage import LocalStorage, get_storage

pytestmark = pytest.mark.skipif(
    shutil.which("ffprobe") is None, reason="máy không có ffprobe; CI cài ffmpeg"
)


def wav_bytes(seconds: float = 1.0, rate: int = 16000) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"\x00\x00" * int(rate * seconds))
    return buf.getvalue()


def test_real_probe_reads_a_valid_wav(tmp_path: Path) -> None:
    path = tmp_path / "ok.wav"
    path.write_bytes(wav_bytes(1.0))
    result = probe_audio(file_path=path)
    assert result.duration_sec == pytest.approx(1.0, abs=0.05)
    assert result.sample_rate == 16000
    assert result.channels == 1


def test_real_probe_rejects_the_fake_riff_old_tests_sent(tmp_path: Path) -> None:
    path = tmp_path / "fake.wav"
    path.write_bytes(b"RIFF" + b"\x00" * 100)
    with pytest.raises(APIError) as exc:
        probe_audio(file_path=path)
    assert exc.value.code == "AUDIO_INVALID"


@pytest.fixture
def client(tmp_path: Path) -> Generator[tuple[TestClient, Session], None, None]:
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    tables = [User.__table__, Meeting.__table__, Job.__table__, IdempotencyKey.__table__]
    Base.metadata.create_all(bind=engine, tables=tables)
    session = sessionmaker(autocommit=False, autoflush=False, bind=engine)()
    user = User(
        id=str(uuid.uuid4()),
        email="ffprobe@example.com",
        display_name="Probe",
        password_hash="x",
    )
    session.add(user)
    session.commit()

    app = create_app()
    app.dependency_overrides[get_db] = lambda: session
    app.dependency_overrides[get_storage] = lambda: LocalStorage(base_dir=tmp_path)
    app.dependency_overrides[get_current_user] = lambda: user
    try:
        with TestClient(app) as c:
            yield c, session
    finally:
        session.close()
        engine.dispose()


def test_upload_with_real_probe_stores_the_measured_duration(
    client: tuple[TestClient, Session],
) -> None:
    c, session = client
    response = c.post(
        "/api/v1/meetings",
        data={"title": "Probe thật", "consent_confirmed": "true"},
        files={"file": ("ok.wav", wav_bytes(2.0), "audio/wav")},
        headers={"Idempotency-Key": str(uuid.uuid4())},
    )
    assert response.status_code == 201, response.text
    meeting = session.get(Meeting, response.json()["meeting"]["id"])
    assert meeting is not None
    assert meeting.duration_sec == pytest.approx(2.0, abs=0.05)


def test_upload_with_real_probe_rejects_fake_riff(client: tuple[TestClient, Session]) -> None:
    c, _ = client
    response = c.post(
        "/api/v1/meetings",
        data={"title": "RIFF giả", "consent_confirmed": "true"},
        files={"file": ("fake.wav", b"RIFF" + b"\x00" * 100, "audio/wav")},
        headers={"Idempotency-Key": str(uuid.uuid4())},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "AUDIO_INVALID"
