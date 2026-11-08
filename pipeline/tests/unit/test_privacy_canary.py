"""AI-18, PRIV-10: dữ liệu người dùng (canary) không lọt vào log hay file lỗi của pipeline.

`test_stage_events.py` đã kiểm log sự kiện của runner. File này kiểm hai đường còn lại:
exception không lường trước trong stage, và stderr của subprocess.
"""

import json
import logging
import sys

from meeting_pipeline import cli
from meeting_pipeline.runner import run_process
from meeting_pipeline.schemas import Stage, error_file

CANARY = "CANARY_TRANSCRIPT_9c1e"


def _all_text(caplog, capsys) -> str:
    out = capsys.readouterr()
    records = "\n".join(
        r.getMessage() + " " + " ".join(f"{k}={v}" for k, v in vars(r).items() if k != "args")
        for r in caplog.records
    )
    return records + out.out + out.err


def test_unexpected_exception_message_is_not_logged_or_stored(workdir, monkeypatch, caplog, capsys):
    def boom(*_a, **_k):
        raise ValueError(f"không đọc được đoạn: {CANARY}")

    monkeypatch.setattr(cli, "get_stage", lambda *_a, **_k: lambda ctx: None)
    monkeypatch.setattr(cli, "execute_stage", boom)
    caplog.set_level(logging.DEBUG)

    rc = cli.run_stage(Stage.ASR, workdir, "fake")

    assert rc != 0
    report = (workdir / error_file(Stage.ASR)).read_text(encoding="utf-8")
    assert json.loads(report)["code"] == "INTERNAL_ERROR"
    assert CANARY not in report
    assert CANARY not in _all_text(caplog, capsys)


def test_subprocess_stderr_with_user_data_is_not_logged(caplog):
    """stderr của stage có thể chứa traceback kèm text của thư viện; log không được chép lại."""
    caplog.set_level(logging.DEBUG, logger="meeting_pipeline")
    code = f"import sys; sys.stderr.write({CANARY!r} + '\\n'); sys.exit(1)"

    rc = run_process([sys.executable, "-c", code], stage=Stage.ASR, timeout_sec=30)

    assert rc == 1
    blob = "\n".join(r.getMessage() for r in caplog.records)
    assert CANARY not in blob
