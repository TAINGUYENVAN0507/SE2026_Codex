from datetime import date
from pathlib import Path

import pytest

from meeting_pipeline.errors import (
    ErrorCode,
    PermanentPipelineError,
    PipelineError,
    TransientPipelineError,
)
from meeting_pipeline.fake import data
from meeting_pipeline.registry import get_stage
from meeting_pipeline.schemas import (
    STAGES,
    PreprocessOutput,
    Stage,
    SummaryOutput,
    Transcript,
)
from meeting_pipeline.stages.base import execute_stage
from meeting_pipeline.workdir import (
    artifact_path,
    has_valid_artifact,
    read_artifact,
    read_job,
    write_job,
    write_json_atomic,
)


def run(workdir: Path, stage: Stage) -> Path:
    return execute_stage(stage, workdir, get_stage(stage, "fake"))


def run_all(workdir: Path) -> None:
    for stage in STAGES:
        run(workdir, stage)


def test_ok_scenario_produces_valid_artifacts(workdir):
    run_all(workdir)
    for stage in STAGES:
        assert has_valid_artifact(workdir, stage), stage

    pre = read_artifact(workdir, Stage.PREPROCESS)
    assert isinstance(pre, PreprocessOutput)
    assert pre.playback.mime_type == "audio/webm"
    assert pre.source.size_bytes == 64

    transcript = read_artifact(workdir, Stage.MERGE)
    assert isinstance(transcript, Transcript)
    assert transcript.diarization_status == "ok"
    assert [s.label for s in transcript.speakers] == ["SPEAKER_00", "SPEAKER_01"]
    assert transcript.segments[4].speaker_label is None

    summary = read_artifact(workdir, Stage.SUMMARIZE)
    assert isinstance(summary, SummaryOutput)
    assert summary.status == "ready"
    # 2026-10-15 là thứ Năm, "thứ Sáu tuần này" là 2026-10-16.
    assert summary.action_items[0].due_date == date(2026, 10, 16)
    assert summary.action_items[1].due_date is None


def test_evidence_indices_point_to_existing_segments():
    transcript = data.transcript()
    summary = data.summary_output()
    n = len(transcript.segments)
    items = [*summary.key_points, *summary.decisions, *summary.action_items]
    for item in items:
        assert all(0 <= i < n for i in item.evidence_segment_indices)


def test_permanent_scenario_fails_preprocess_without_artifact(workdir, monkeypatch):
    monkeypatch.setenv("FAKE_SCENARIO", "permanent")
    with pytest.raises(PermanentPipelineError) as exc:
        run(workdir, Stage.PREPROCESS)
    assert exc.value.code is ErrorCode.AUDIO_INVALID
    assert not artifact_path(workdir, Stage.PREPROCESS).exists()


def test_no_speech_scenario(workdir, monkeypatch):
    run(workdir, Stage.PREPROCESS)
    monkeypatch.setenv("FAKE_SCENARIO", "no_speech")
    with pytest.raises(PermanentPipelineError) as exc:
        run(workdir, Stage.VAD)
    assert exc.value.code is ErrorCode.NO_SPEECH_DETECTED


def test_transient_once_fails_then_succeeds(workdir, monkeypatch):
    monkeypatch.setenv("FAKE_SCENARIO", "transient_once")
    run(workdir, Stage.PREPROCESS)
    run(workdir, Stage.VAD)
    with pytest.raises(TransientPipelineError) as exc:
        run(workdir, Stage.ASR)
    assert exc.value.code is ErrorCode.OUT_OF_MEMORY
    run(workdir, Stage.ASR)
    assert has_valid_artifact(workdir, Stage.ASR)


def test_diarize_fail_is_transient(workdir, monkeypatch):
    run(workdir, Stage.PREPROCESS)
    monkeypatch.setenv("FAKE_SCENARIO", "diarize_fail")
    with pytest.raises(TransientPipelineError) as exc:
        run(workdir, Stage.DIARIZE)
    assert exc.value.code is ErrorCode.DIARIZATION_FAILED


def test_merge_with_fallback_diarization_uses_one_speaker(workdir):
    for stage in (Stage.PREPROCESS, Stage.VAD, Stage.ASR):
        run(workdir, stage)
    write_json_atomic(artifact_path(workdir, Stage.DIARIZE), data.diarize_fallback_output())
    run(workdir, Stage.MERGE)
    transcript = read_artifact(workdir, Stage.MERGE)
    assert isinstance(transcript, Transcript)
    assert transcript.diarization_status == "fallback"
    assert {s.speaker_label for s in transcript.segments} == {"SPEAKER_00"}
    assert [w.code for w in transcript.warnings] == ["DIARIZATION_FALLBACK"]


@pytest.mark.parametrize(
    ("scenario", "error_cls", "code"),
    [
        ("summary_fail", PermanentPipelineError, ErrorCode.LLM_REQUEST_INVALID),
        ("summary_flaky", TransientPipelineError, ErrorCode.LLM_UNAVAILABLE),
    ],
)
def test_summary_failures(workdir, monkeypatch, scenario, error_cls, code):
    run_all_but_summary(workdir)
    monkeypatch.setenv("FAKE_SCENARIO", scenario)
    with pytest.raises(error_cls) as exc:
        run(workdir, Stage.SUMMARIZE)
    assert exc.value.code is code


def run_all_but_summary(workdir: Path) -> None:
    for stage in STAGES[:-1]:
        run(workdir, stage)


def test_summary_flaky_succeeds_on_third_run(workdir, monkeypatch):
    run_all_but_summary(workdir)
    monkeypatch.setenv("FAKE_SCENARIO", "summary_flaky")
    for _ in range(2):
        with pytest.raises(TransientPipelineError):
            run(workdir, Stage.SUMMARIZE)
    run(workdir, Stage.SUMMARIZE)
    assert read_artifact(workdir, Stage.SUMMARIZE).status == "ready"


def test_summary_disabled(workdir, monkeypatch):
    run_all_but_summary(workdir)
    monkeypatch.setenv("FAKE_SCENARIO", "summary_disabled")
    run(workdir, Stage.SUMMARIZE)
    assert read_artifact(workdir, Stage.SUMMARIZE).status == "disabled"


def test_summarize_reads_transcript_override(workdir, tmp_path):
    short = data.transcript().model_copy(update={"segments": data.transcript().segments[:1]})
    override = write_json_atomic(tmp_path / "edited.json", short)
    spec = read_job(workdir).model_copy(update={"transcript_override_path": str(override)})
    write_job(workdir, spec)
    # Không có transcript.json trong workdir: summarize chỉ dùng bản override.
    run(workdir, Stage.SUMMARIZE)
    assert read_artifact(workdir, Stage.SUMMARIZE).status == "insufficient_content"


def test_missing_input_is_permanent(workdir):
    with pytest.raises(PermanentPipelineError) as exc:
        run(workdir, Stage.VAD)
    assert exc.value.code is ErrorCode.MISSING_INPUT


def test_corrupt_input_is_permanent(workdir):
    artifact_path(workdir, Stage.PREPROCESS).write_text('{"schema_version": "1.0"}')
    with pytest.raises(PermanentPipelineError) as exc:
        run(workdir, Stage.VAD)
    assert exc.value.code is ErrorCode.PIPELINE_OUTPUT_INVALID


def test_unknown_scenario_is_rejected(workdir, monkeypatch):
    monkeypatch.setenv("FAKE_SCENARIO", "nope")
    with pytest.raises(PipelineError) as exc:
        run(workdir, Stage.PREPROCESS)
    assert exc.value.code is ErrorCode.INTERNAL_ERROR


def test_wrong_output_type_is_rejected(workdir):
    with pytest.raises(PermanentPipelineError) as exc:
        execute_stage(Stage.VAD, workdir, lambda ctx: data.asr_output())
    assert exc.value.code is ErrorCode.PIPELINE_OUTPUT_INVALID


def test_real_backend_reports_not_implemented(workdir):
    with pytest.raises(PermanentPipelineError) as exc:
        execute_stage(Stage.ASR, workdir, get_stage(Stage.ASR, "real"))
    assert exc.value.code is ErrorCode.STAGE_NOT_IMPLEMENTED


def test_invalid_backend_env(monkeypatch):
    monkeypatch.setenv("PIPELINE_BACKEND", "gpu")
    with pytest.raises(PipelineError):
        get_stage(Stage.ASR)


def test_atomic_write_leaves_no_temp_files(tmp_path):
    path = write_json_atomic(tmp_path / "out" / "vad.json", data.vad_output())
    write_json_atomic(path, data.vad_output())
    assert [p.name for p in path.parent.iterdir()] == ["vad.json"]
