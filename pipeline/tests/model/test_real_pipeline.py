"""Pipeline thật qua `run_job()`, đúng đường worker của B gọi (AI-04, AI-07, AI-09).

Cần `uv sync --extra asr --extra diarize`, GPU CUDA cho ASR, FLEURS đã tải.

    uv run pytest -m model tests/model/test_real_pipeline.py

Cả 6 stage chạy bản thật. `summarize` dùng `LLM_PROVIDER=fake` để test không gọi Claude API
(không tốn tiền, không gửi audio của FLEURS ra ngoài).
"""

import pytest

pytest.importorskip("faster_whisper")
pytest.importorskip("pyannote.audio")
pytestmark = pytest.mark.model

from meeting_pipeline.llm.fake import FAKE_MODEL  # noqa: E402
from meeting_pipeline.llm.postcheck import is_insufficient  # noqa: E402
from meeting_pipeline.runner import run_job  # noqa: E402
from meeting_pipeline.schemas import STAGES, JobSpec, Stage, SummaryOutput, Transcript  # noqa: E402
from meeting_pipeline.workdir import artifact_path  # noqa: E402


def cuda_available() -> bool:
    import ctranslate2

    from meeting_pipeline.engines.whisper import preload_cuda_libs

    preload_cuda_libs()
    return ctranslate2.get_cuda_device_count() > 0


def test_real_run_job_runs_all_six_stages(tmp_path, two_voices):
    if not cuda_available():
        pytest.skip("không có GPU CUDA cho ASR")
    workdir = tmp_path / "work"
    done: list[Stage] = []
    spec = JobSpec(meeting_id="m", job_id="j", audio_path=str(two_voices))

    outcome = run_job(
        spec,
        workdir=workdir,
        on_stage_done=lambda s, p: done.append(s),
        backend="real",
        env={"LLM_PROVIDER": "fake"},
    )

    assert done == list(STAGES)
    assert set(outcome.stage_status.values()) == {"succeeded"}
    transcript = Transcript.model_validate_json(
        artifact_path(workdir, Stage.MERGE).read_text(encoding="utf-8")
    )
    assert transcript.diarization_status == "ok"
    assert [s.label for s in transcript.speakers] == ["SPEAKER_00", "SPEAKER_01"]
    assert [s.speaker_label for s in transcript.segments] == ["SPEAKER_00", "SPEAKER_01"]
    assert all("giao thông" in s.text.lower() for s in transcript.segments)
    summary = SummaryOutput.model_validate_json(
        artifact_path(workdir, Stage.SUMMARIZE).read_text(encoding="utf-8")
    )
    # Hai câu ngắn của FLEURS có thể dưới ngưỡng MIN_WORDS: khi đó LLM không được gọi.
    expected = "insufficient_content" if is_insufficient(transcript) else "ready"
    assert (summary.status, summary.model) == (expected, FAKE_MODEL)
