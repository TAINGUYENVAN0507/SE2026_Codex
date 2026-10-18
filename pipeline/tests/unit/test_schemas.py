import copy

import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError

from meeting_pipeline.schemas import (
    ARTIFACT_FILES,
    STAGE_OUTPUT_MODELS,
    STAGES,
    DiarizeOutput,
    JobSpec,
    PlaybackInfo,
    Stage,
    SummaryOutput,
    TimeSpan,
    Transcript,
    VadOutput,
    error_file,
)


def transcript_dict() -> dict:
    return {
        "schema_version": "1.0",
        "audio": {"duration_sec": 20.0, "sample_rate": 16000, "channels": 1},
        "models": {"asr": "fake-asr", "diarization": "fake-diarization"},
        "diarization_status": "ok",
        "speakers": [
            {"label": "SPEAKER_00", "first_start_sec": 0.5, "display_name": None},
            {"label": "SPEAKER_01", "first_start_sec": 6.0, "display_name": None},
        ],
        "segments": [
            {
                "index": 0,
                "start_sec": 0.5,
                "end_sec": 5.8,
                "speaker_label": "SPEAKER_00",
                "text": "Chào mọi người, mình bắt đầu họp nhé.",
                "confidence": 0.9,
                "flags": [],
                "words": [{"w": "Chào", "s": 0.5, "e": 0.8, "p": 0.97}],
            },
            {
                "index": 1,
                "start_sec": 6.0,
                "end_sec": 9.0,
                "speaker_label": "SPEAKER_01",
                "text": "Ừ, được.",
                "confidence": None,
                "flags": [],
                "words": [],
            },
            {
                "index": 2,
                "start_sec": 9.0,
                "end_sec": 10.0,
                "speaker_label": None,
                "text": "Vâng.",
                "confidence": 0.4,
                "flags": ["low_confidence"],
                "words": [],
            },
        ],
        "warnings": [],
    }


def test_every_stage_has_artifact_file_and_model():
    assert set(ARTIFACT_FILES) == set(STAGES) == set(STAGE_OUTPUT_MODELS)
    assert len(set(ARTIFACT_FILES.values())) == len(STAGES)
    assert [s.value for s in STAGES] == [
        "preprocess",
        "vad",
        "asr",
        "diarize",
        "merge",
        "summarize",
    ]
    assert error_file(Stage.ASR) == "asr.error.json"


def test_transcript_round_trip_keeps_null_fields():
    t = Transcript.model_validate(transcript_dict())
    dumped = t.model_dump(mode="json")
    assert dumped["segments"][2]["speaker_label"] is None
    assert dumped["segments"][1]["confidence"] is None
    assert Transcript.model_validate_json(t.model_dump_json()) == t


def test_timespan_rounds_to_milliseconds():
    span = TimeSpan(start_sec=1.23456, end_sec=2.0004)
    assert (span.start_sec, span.end_sec) == (1.235, 2.0)


@pytest.mark.parametrize(("start", "end"), [(2.0, 2.0), (3.0, 2.0), (-0.1, 1.0)])
def test_timespan_rejects_invalid(start, end):
    with pytest.raises(ValidationError):
        TimeSpan(start_sec=start, end_sec=end)


def mutate(fn) -> dict:
    data = copy.deepcopy(transcript_dict())
    fn(data)
    return data


@pytest.mark.parametrize(
    "broken",
    [
        pytest.param(mutate(lambda d: d["segments"][1].update(index=5)), id="index-gap"),
        pytest.param(
            mutate(lambda d: d["segments"][2].update(end_sec=25.0)), id="end-after-duration"
        ),
        pytest.param(
            mutate(lambda d: d["segments"][1].update(speaker_label="SPEAKER_07")),
            id="unknown-speaker",
        ),
        pytest.param(
            mutate(lambda d: d["segments"][1].update(start_sec=5.0)), id="overlap-without-flag"
        ),
        pytest.param(
            mutate(lambda d: d["segments"][0].update(start_sec=12.0, end_sec=13.0)),
            id="unsorted-segments",
        ),
        pytest.param(mutate(lambda d: d["segments"][0].update(text="")), id="empty-text"),
        pytest.param(mutate(lambda d: d.update(extra_field=1)), id="extra-field"),
        pytest.param(mutate(lambda d: d.update(schema_version="2.0")), id="major-2"),
        pytest.param(
            mutate(lambda d: d["speakers"].append(dict(d["speakers"][0]))), id="dup-speaker"
        ),
        pytest.param(mutate(lambda d: d["speakers"][0].update(label="spk0")), id="bad-label"),
    ],
)
def test_transcript_rejects_broken_invariants(broken):
    with pytest.raises(ValidationError):
        Transcript.model_validate(broken)


def test_transcript_allows_overlap_when_flagged():
    def overlap(d):
        d["segments"][1].update(start_sec=5.0, flags=["overlap"])

    Transcript.model_validate(mutate(overlap))


def test_minor_schema_version_is_accepted():
    Transcript.model_validate(mutate(lambda d: d.update(schema_version="1.3")))


def test_vad_regions_must_not_overlap():
    with pytest.raises(ValidationError):
        VadOutput(
            model="silero",
            speech_ratio=0.5,
            speech_regions=[
                TimeSpan(start_sec=0, end_sec=2),
                TimeSpan(start_sec=1.5, end_sec=3),
            ],
        )


def test_diarize_ok_requires_matching_speaker_count():
    turns = [
        {"start_sec": 0, "end_sec": 1, "speaker_label": "SPEAKER_00"},
        {"start_sec": 1, "end_sec": 2, "speaker_label": "SPEAKER_01"},
    ]
    DiarizeOutput(model="pyannote", status="ok", num_speakers=2, turns=turns)
    with pytest.raises(ValidationError):
        DiarizeOutput(model="pyannote", status="ok", num_speakers=3, turns=turns)


def test_summary_without_content_unless_ready():
    SummaryOutput(status="disabled", model=None, prompt_version=None, overview=None)
    with pytest.raises(ValidationError):
        SummaryOutput(status="disabled", model=None, prompt_version=None, overview="x")
    with pytest.raises(ValidationError):
        SummaryOutput(status="ready", model="m", prompt_version="v1", overview=None)


def test_playback_file_only_when_transcoded():
    PlaybackInfo(source="original", file=None, mime_type="audio/webm")
    PlaybackInfo(source="transcoded", file="playback.m4a", mime_type="audio/mp4")
    with pytest.raises(ValidationError):
        PlaybackInfo(source="original", file="playback.m4a", mime_type="audio/mp4")


def test_job_spec_defaults_and_bounds():
    spec = JobSpec(meeting_id="m1", job_id="j1", audio_path="/data/a.webm")
    assert spec.from_stage is None and spec.language == "vi"
    assert not spec.is_last_attempt
    assert JobSpec(meeting_id="m", job_id="j", audio_path="/a", attempt=3).is_last_attempt
    with pytest.raises(ValidationError):
        JobSpec(meeting_id="m", job_id="j", audio_path="/a", num_speakers_hint=11)


@given(
    start=st.floats(min_value=0, max_value=7200, allow_nan=False),
    length=st.floats(min_value=0.01, max_value=60, allow_nan=False),
)
def test_valid_timespans_round_trip(start, length):
    span = TimeSpan(start_sec=start, end_sec=start + length)
    assert 0 <= span.start_sec < span.end_sec
    assert TimeSpan.model_validate_json(span.model_dump_json()) == span
