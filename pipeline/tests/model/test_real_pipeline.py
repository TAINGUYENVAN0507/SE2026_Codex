"""Pipeline thật qua `run_job()`, đúng đường worker của B gọi (AI-04, AI-07).

Cần `uv sync --extra asr --extra diarize`, GPU CUDA cho ASR, FLEURS đã tải.

    uv run pytest -m model tests/model/test_real_pipeline.py

`summarize` chưa có bản thật (AI-09), nên runner phải dừng ở đó với lỗi
`STAGE_NOT_IMPLEMENTED`, sau khi `transcript.json` đã được ghi và worker đã được báo.
"""

import pytest

pytest.importorskip("faster_whisper")
pytest.importorskip("pyannote.audio")
pytestmark = pytest.mark.model

from meeting_pipeline.errors import ErrorCode, PermanentPipelineError  # noqa: E402
from meeting_pipeline.runner import run_job  # noqa: E402
from meeting_pipeline.schemas import STAGES, JobSpec, Stage, Transcript  # noqa: E402
from meeting_pipeline.workdir import artifact_path  # noqa: E402


def cuda_available() -> bool:
    import ctranslate2

    from meeting_pipeline.engines.whisper import preload_cuda_libs

    preload_cuda_libs()
    return ctranslate2.get_cuda_device_count() > 0


def test_real_run_job_produces_transcript_then_stops_at_summarize(tmp_path, two_voices):
    if not cuda_available():
        pytest.skip("không có GPU CUDA cho ASR")
    workdir = tmp_path / "work"
    done: list[Stage] = []
    spec = JobSpec(meeting_id="m", job_id="j", audio_path=str(two_voices))

    with pytest.raises(PermanentPipelineError) as exc:
        run_job(spec, workdir=workdir, on_stage_done=lambda s, p: done.append(s), backend="real")

    assert (exc.value.code, exc.value.stage) == (ErrorCode.STAGE_NOT_IMPLEMENTED, Stage.SUMMARIZE)
    assert done == list(STAGES[:-1])
    transcript = Transcript.model_validate_json(
        artifact_path(workdir, Stage.MERGE).read_text(encoding="utf-8")
    )
    assert transcript.diarization_status == "ok"
    assert [s.label for s in transcript.speakers] == ["SPEAKER_00", "SPEAKER_01"]
    assert [s.speaker_label for s in transcript.segments] == ["SPEAKER_00", "SPEAKER_01"]
    assert all("giao thông" in s.text.lower() for s in transcript.segments)
