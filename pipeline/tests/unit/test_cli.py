import json
import os
import subprocess
import sys

import pytest

from meeting_pipeline import cli
from meeting_pipeline.errors import ErrorReport
from meeting_pipeline.schemas import JOB_FILE, Stage, error_file
from meeting_pipeline.workdir import has_valid_artifact


def events(stdout: str) -> list[dict]:
    return [json.loads(line) for line in stdout.splitlines() if line.strip()]


def run_cli(workdir, stage, **env):
    """Chạy CLI trong subprocess, giống cách runner gọi."""
    return subprocess.run(
        [sys.executable, "-m", "meeting_pipeline", "run-stage", stage, "--workdir", str(workdir)],
        env={**os.environ, "PIPELINE_BACKEND": "fake", **env},
        capture_output=True,
        text=True,
        timeout=60,
    )


def read_error(workdir, stage: Stage) -> ErrorReport:
    return ErrorReport.model_validate_json((workdir / error_file(stage)).read_text())


def test_subprocess_ok_writes_artifact_and_done_event(workdir):
    proc = run_cli(workdir, "preprocess")
    assert proc.returncode == 0, proc.stderr
    assert events(proc.stdout)[-1] == {
        "event": "done",
        "stage": "preprocess",
        "artifact": "preprocess.json",
    }
    assert has_valid_artifact(workdir, Stage.PREPROCESS)


def test_subprocess_permanent_exit_10_with_error_file(workdir):
    proc = run_cli(workdir, "preprocess", FAKE_SCENARIO="permanent")
    assert proc.returncode == 10
    report = read_error(workdir, Stage.PREPROCESS)
    assert (report.code, report.kind, report.retryable) == ("AUDIO_INVALID", "permanent", False)
    assert not (workdir / "preprocess.json").exists()


def test_transient_exit_20_then_success_clears_error_file(workdir, monkeypatch):
    monkeypatch.setenv("PIPELINE_BACKEND", "fake")
    monkeypatch.setenv("FAKE_SCENARIO", "transient_once")
    assert cli.main(["run-stage", "preprocess", "--workdir", str(workdir)]) == 0
    assert cli.main(["run-stage", "vad", "--workdir", str(workdir)]) == 0
    assert cli.main(["run-stage", "asr", "--workdir", str(workdir)]) == 20
    assert read_error(workdir, Stage.ASR).kind == "transient"
    assert cli.main(["run-stage", "asr", "--workdir", str(workdir)]) == 0
    assert not (workdir / error_file(Stage.ASR)).exists()


def test_progress_events_in_slow_scenario(workdir, monkeypatch, capsys):
    monkeypatch.setenv("FAKE_SCENARIO", "slow")
    monkeypatch.setenv("FAKE_STAGE_SLEEP_SEC", "0.04")
    code = cli.main(["run-stage", "preprocess", "--workdir", str(workdir), "--backend", "fake"])
    assert code == 0
    progress = [e["value"] for e in events(capsys.readouterr().out) if e["event"] == "progress"]
    assert progress == [0.25, 0.5, 0.75, 1.0, 1.0]


def test_missing_job_file_is_permanent(tmp_path):
    assert cli.main(["run-stage", "vad", "--workdir", str(tmp_path), "--backend", "fake"]) == 10
    report = read_error(tmp_path, Stage.VAD)
    assert report.code == "MISSING_INPUT"
    assert JOB_FILE in report.message


def test_unexpected_exception_does_not_leak_message(workdir, monkeypatch, capsys):
    secret = "CANARY_TRANSCRIPT_7f3a"

    def boom(ctx):
        raise ValueError(f"không parse được câu: {secret}")

    monkeypatch.setattr(cli, "get_stage", lambda stage, backend: boom)
    assert cli.main(["run-stage", "merge", "--workdir", str(workdir)]) == 10
    report = read_error(workdir, Stage.MERGE)
    assert report.code == "INTERNAL_ERROR"
    assert report.message.startswith("ValueError tại test_cli.py:")
    captured = capsys.readouterr()
    error_json = (workdir / error_file(Stage.MERGE)).read_text()
    assert secret not in captured.out + captured.err + error_json


def test_stage_without_explicit_stage_gets_it_filled(workdir, monkeypatch):
    monkeypatch.setenv("FAKE_SCENARIO", "nope")
    assert cli.main(["run-stage", "vad", "--workdir", str(workdir), "--backend", "fake"]) == 10
    assert read_error(workdir, Stage.VAD).stage == Stage.VAD


def test_rejects_unknown_stage(workdir):
    with pytest.raises(SystemExit) as exc:
        cli.main(["run-stage", "translate", "--workdir", str(workdir)])
    assert exc.value.code == 2


def test_export_contracts_check(tmp_path):
    assert cli.main(["export-contracts", "--root", str(tmp_path), "--check"]) == 1
    assert cli.main(["export-contracts", "--root", str(tmp_path)]) == 0
    assert cli.main(["export-contracts", "--root", str(tmp_path), "--check"]) == 0
