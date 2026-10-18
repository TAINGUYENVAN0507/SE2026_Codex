import re

import pytest

from meeting_pipeline.errors import (
    EXIT_PERMANENT,
    EXIT_TRANSIENT,
    ErrorCode,
    ErrorKind,
    ErrorReport,
    PermanentPipelineError,
    PipelineCancelledError,
    PipelineError,
    StageTimeoutError,
    TransientPipelineError,
)
from meeting_pipeline.schemas import Stage


def test_error_codes_are_upper_snake_and_match_value():
    for code in ErrorCode:
        assert re.fullmatch(r"[A-Z][A-Z0-9_]*", code.value)
        assert code.name == code.value


@pytest.mark.parametrize(
    ("err", "kind", "exit_code", "retryable"),
    [
        (PermanentPipelineError(ErrorCode.AUDIO_INVALID, Stage.PREPROCESS), "permanent", 10, False),
        (TransientPipelineError(ErrorCode.LLM_UNAVAILABLE, Stage.SUMMARIZE), "transient", 20, True),
        (StageTimeoutError(Stage.ASR, timeout_sec=120), "timeout", 20, True),
        (PipelineCancelledError(Stage.VAD), "cancelled", 10, False),
    ],
)
def test_error_classification(err, kind, exit_code, retryable):
    assert err.kind == kind
    assert err.exit_code == exit_code
    assert err.retryable is retryable


def test_timeout_is_a_transient_error():
    err = StageTimeoutError(Stage.ASR, timeout_sec=90)
    assert isinstance(err, TransientPipelineError)
    assert err.code is ErrorCode.STAGE_TIMEOUT
    assert "90" in err.message
    assert EXIT_TRANSIENT == err.exit_code != EXIT_PERMANENT


def test_str_contains_code_and_stage():
    err = PermanentPipelineError(ErrorCode.AUDIO_TOO_LONG, Stage.PREPROCESS, "7300 s > 3600 s")
    assert str(err) == "AUDIO_TOO_LONG at preprocess: 7300 s > 3600 s"
    assert str(PermanentPipelineError(ErrorCode.INTERNAL_ERROR)) == "INTERNAL_ERROR at pipeline"


@pytest.mark.parametrize(
    "err",
    [
        PermanentPipelineError(
            ErrorCode.AUDIO_TOO_SHORT, Stage.PREPROCESS, "0.3 s", {"duration_sec": 0.3}
        ),
        TransientPipelineError(ErrorCode.OUT_OF_MEMORY, Stage.ASR, "CUDA OOM"),
        StageTimeoutError(Stage.DIARIZE, timeout_sec=300.0),
    ],
)
def test_report_round_trip_restores_same_class(err):
    report = ErrorReport.model_validate_json(err.to_report().model_dump_json())
    back = PipelineError.from_report(report)
    assert type(back) is type(err)
    assert (back.code, back.stage, back.message, back.details) == (
        err.code,
        err.stage,
        err.message,
        err.details,
    )


def test_report_fields():
    report = StageTimeoutError(Stage.ASR, timeout_sec=60).to_report()
    assert report.kind is ErrorKind.TIMEOUT
    assert report.retryable is True
    assert report.details == {"timeout_sec": 60}
    assert report.schema_version == "1.0"


def test_long_message_is_truncated_in_report():
    err = PermanentPipelineError(ErrorCode.INTERNAL_ERROR, Stage.MERGE, "x" * 5000)
    assert len(err.to_report().message) == 2000
