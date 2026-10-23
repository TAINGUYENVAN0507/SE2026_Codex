from datetime import date
from pathlib import Path

import pytest

from meeting_pipeline.schemas import JobSpec
from meeting_pipeline.workdir import write_job


@pytest.fixture
def job_spec(tmp_path: Path) -> JobSpec:
    audio = tmp_path / "upload" / "meeting.webm"
    audio.parent.mkdir()
    audio.write_bytes(b"\x1a\x45\xdf\xa3" + b"\0" * 60)
    return JobSpec(
        meeting_id="11111111-1111-4111-8111-111111111111",
        job_id="22222222-2222-4222-8222-222222222222",
        audio_path=str(audio),
        meeting_date=date(2026, 10, 15),
    )


@pytest.fixture
def workdir(tmp_path: Path, job_spec: JobSpec) -> Path:
    wd = tmp_path / "work"
    write_job(wd, job_spec)
    return wd


@pytest.fixture(autouse=True)
def _clean_pipeline_env(monkeypatch):
    for var in (
        "FAKE_SCENARIO",
        "PIPELINE_BACKEND",
        "FAKE_STAGE_SLEEP_SEC",
        "FAKE_HANG_SEC",
        "LLM_PROVIDER",
    ):
        monkeypatch.delenv(var, raising=False)
