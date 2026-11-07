"""AI-18: pipeline ghi sự kiện stage có cấu trúc để lần ra nguyên nhân một job lỗi."""

import logging
from pathlib import Path

import pytest

from meeting_pipeline.errors import PermanentPipelineError
from meeting_pipeline.runner import run_job
from meeting_pipeline.schemas import STAGES, JobSpec

CANARY = "CANARY_TRANSCRIPT_7f3a"
FIELDS = ("event", "job_id", "meeting_id", "stage", "attempt")


def run(spec: JobSpec, wd: Path, scenario: str = "ok"):
    return run_job(spec, workdir=wd, backend="fake", env={"FAKE_SCENARIO": scenario})


def events(caplog) -> list[dict]:
    out = []
    for rec in caplog.records:
        if rec.name == "meeting_pipeline.runner" and hasattr(rec, "event"):
            out.append(
                {
                    k: getattr(rec, k)
                    for k in (*FIELDS, "status", "error_code", "duration_sec")
                    if hasattr(rec, k)
                }
            )
    return out


def test_ok_run_logs_start_and_finish_for_all_stages(job_spec, tmp_path, caplog):
    caplog.set_level(logging.INFO, logger="meeting_pipeline.runner")
    run(job_spec, tmp_path / "wd")
    evs = events(caplog)
    for stage in STAGES:
        started = [e for e in evs if e["event"] == "stage_started" and e["stage"] == stage.value]
        finished = [e for e in evs if e["event"] == "stage_finished" and e["stage"] == stage.value]
        assert len(started) == 1 and len(finished) == 1, stage
        assert finished[0]["status"] == "succeeded"
        assert finished[0]["duration_sec"] >= 0
    assert {e["job_id"] for e in evs} == {job_spec.job_id}
    assert {e["meeting_id"] for e in evs} == {job_spec.meeting_id}
    assert all(e["attempt"] == 1 for e in evs)


def test_permanent_failure_logs_stage_failed_with_error_code(job_spec, tmp_path, caplog):
    caplog.set_level(logging.INFO, logger="meeting_pipeline.runner")
    with pytest.raises(PermanentPipelineError):
        run(job_spec, tmp_path / "wd", "permanent")
    failed = [e for e in events(caplog) if e["event"] == "stage_failed"]
    assert len(failed) == 1
    assert failed[0]["stage"] == "preprocess"
    assert failed[0]["error_code"] == "AUDIO_INVALID"
    assert failed[0]["status"] == "failed"
    assert not [e for e in events(caplog) if e["event"] == "stage_finished"]


def test_diarize_fallback_logs_stage_fallback(job_spec, tmp_path, caplog):
    caplog.set_level(logging.INFO, logger="meeting_pipeline.runner")
    last = job_spec.model_copy(update={"attempt": job_spec.max_attempts})
    run(last, tmp_path / "wd", "diarize_fail")
    evs = events(caplog)
    fb = [e for e in evs if e["event"] == "stage_fallback"]
    assert len(fb) == 1 and fb[0]["stage"] == "diarize" and fb[0]["error_code"]
    done = [e for e in evs if e["event"] == "stage_finished" and e["stage"] == "diarize"]
    assert done[0]["status"] == "fallback"


def test_resume_logs_stage_skipped(job_spec, tmp_path, caplog):
    wd = tmp_path / "wd"
    run(job_spec, wd)
    caplog.clear()
    caplog.set_level(logging.INFO, logger="meeting_pipeline.runner")
    run(job_spec, wd)
    evs = events(caplog)
    assert {e["event"] for e in evs} == {"stage_skipped"}
    assert len(evs) == len(STAGES)


def test_logs_never_contain_transcript_text_or_paths(job_spec, tmp_path, caplog):
    """PRIV-10: không text transcript, không tên file, không đường dẫn tuyệt đối."""
    audio = tmp_path / "upload" / f"{CANARY}.webm"
    audio.write_bytes(Path(job_spec.audio_path).read_bytes())
    spec = job_spec.model_copy(update={"audio_path": str(audio)})
    caplog.set_level(logging.DEBUG)
    run(spec, tmp_path / "wd")
    run(spec.model_copy(update={"attempt": spec.max_attempts}), tmp_path / "wd2", "diarize_fail")
    with pytest.raises(PermanentPipelineError):
        run(spec, tmp_path / "wd3", "permanent")

    blob = "\n".join(
        r.getMessage() + " " + " ".join(f"{k}={v}" for k, v in vars(r).items() if k != "args")
        for r in caplog.records
        if r.name.startswith("meeting_pipeline")
    )
    assert blob, "phải có log để kiểm"
    assert CANARY not in blob
    assert str(tmp_path) not in blob
    assert "Chào mọi người" not in blob  # câu đầu của transcript mẫu
