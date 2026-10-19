"""Test stage merge (AI-08): gán speaker cho word, dựng segment, bất biến của transcript."""

import math
import random

import pytest

from meeting_pipeline.fallbacks import DIARIZATION_FALLBACK, diarization_fallback
from meeting_pipeline.schemas import (
    AsrOutput,
    AsrSegment,
    AudioInfo,
    DiarizeOutput,
    PipelineWarning,
    SegmentFlag,
    SpeakerTurn,
    Stage,
    Word,
)
from meeting_pipeline.stages.merge import (
    MAX_TEXT_CHARS,
    TEXT_TRUNCATED,
    Crosstalk,
    MergeConfig,
    TurnIndex,
    label_words,
    merge,
)

A, B, C = "SPEAKER_00", "SPEAKER_01", "SPEAKER_02"


def turn(start: float, end: float, label: str) -> SpeakerTurn:
    return SpeakerTurn(start_sec=start, end_sec=end, speaker_label=label)


def word(start: float, end: float, w: str = "x", p: float | None = 0.9) -> Word:
    return Word(w=w, s=start, e=end, p=p)


# ------------------------------------------------------------------ TurnIndex


@pytest.mark.parametrize(
    ("start", "end", "expected"),
    [
        (1.0, 2.0, A),  # nằm gọn trong turn của A
        (4.0, 5.6, A),  # A 1.0 s, B 0.6 s
        (4.6, 6.0, B),  # A 0.4 s, B 1.0 s
        (4.5, 5.5, A),  # hòa 0.5 s: lấy label nhỏ hơn
        (10.2, 10.8, None),  # khoảng lặng sau turn cuối
        (10.0, 10.5, None),  # chỉ chạm biên, overlap 0
    ],
)
def test_speaker_for_takes_largest_overlap(start, end, expected):
    index = TurnIndex([turn(0, 5, A), turn(5, 10, B)])
    assert index.speaker_for(start, end) == expected


def test_tie_does_not_depend_on_label_order():
    index = TurnIndex([turn(0, 5, B), turn(5, 10, A)])
    assert index.speaker_for(4.5, 5.5) == A


def test_overlap_is_summed_per_speaker():
    index = TurnIndex([turn(0, 2, A), turn(1, 4, B), turn(3, 5, A)])
    assert index.speaker_for(1, 4) == B  # A 1 + 1 = 2 s, B 3 s
    assert index.speaker_for(0, 5) == A  # A 2 + 2 = 4 s, B 3 s


@pytest.mark.parametrize(
    ("at", "expected"),
    [(1.0, A), (3.0, B), (2.0, A), (5.0, None)],
)
def test_zero_length_word_takes_containing_turn(at, expected):
    index = TurnIndex([turn(0, 2, A), turn(2, 4, B)])
    assert index.speaker_for(at, at) == expected


def test_long_early_turn_is_still_found():
    # Turn dài của A bắt đầu trước nhiều turn ngắn của B: không được dừng quét quá sớm.
    turns = [turn(0, 100, A)] + [turn(t, t + 1, B) for t in range(10, 40, 10)]
    index = TurnIndex(turns)
    assert index.speaker_for(50, 51) == A
    assert index.touching(50, 51) == [turns[0]]
    assert index.touching(20.5, 20.6) == [turns[0], turns[2]]


def test_turn_order_does_not_matter():
    turns = [turn(t, t + 1.5, [A, B, C][t % 3]) for t in range(0, 30)]
    shuffled = turns[:]
    random.Random(7).shuffle(shuffled)
    sorted_index, shuffled_index = TurnIndex(turns), TurnIndex(shuffled)
    for t in range(0, 300):
        start = t / 10
        assert sorted_index.speaker_for(start, start + 0.4) == shuffled_index.speaker_for(
            start, start + 0.4
        )


def test_empty_index_has_no_speaker():
    index = TurnIndex([])
    assert len(index) == 0
    assert index.speaker_for(0, 1) is None


# ---------------------------------------------------------------- label_words


def test_gap_word_takes_speaker_of_nearest_word_in_time():
    index = TurnIndex([turn(0, 2, A), turn(3, 5, B)])
    words = [word(0.5, 1.5), word(2.1, 2.3), word(2.6, 2.9), word(3.1, 4.0)]
    # word 2 cách word trước 0.6 s, word sau 0.8 s; word 3 cách word sau 0.2 s.
    assert label_words(words, index) == [A, A, B, B]


def test_gap_word_equally_far_goes_to_previous_word():
    index = TurnIndex([turn(0, 1, A), turn(3, 4, B)])
    words = [word(0, 1), word(1.5, 2.5), word(3, 4)]
    assert label_words(words, index) == [A, A, B]


def test_segment_outside_every_turn_stays_unassigned():
    index = TurnIndex([turn(0, 2, A), turn(8, 9, B)])
    assert label_words([word(3, 4), word(4, 5)], index) == [None, None]


def test_speaker_change_mid_segment_is_kept():
    index = TurnIndex([turn(0, 3, A), turn(3, 6, B)])
    words = [word(0.2, 1.0), word(1.1, 2.9), word(3.1, 4.0), word(4.1, 5.0)]
    assert label_words(words, index) == [A, A, B, B]


# ------------------------------------------------------------------ Crosstalk


@pytest.mark.parametrize(
    ("turns", "regions"),
    [
        ([turn(0, 5, A), turn(5, 8, B)], []),  # chỉ chạm nhau ở biên
        ([turn(0, 5, A), turn(4, 8, B)], [(4, 5)]),
        ([turn(0, 5, A), turn(4, 8, A)], []),  # cùng một người
        ([turn(0, 10, A), turn(2, 4, B), turn(3, 6, C)], [(2, 6)]),
        ([turn(0, 3, A), turn(1, 2, B), turn(2.5, 4, B)], [(1, 2), (2.5, 3)]),
        ([], []),
    ],
)
def test_crosstalk_regions(turns, regions):
    assert Crosstalk(turns).regions == regions


def test_crosstalk_seconds_within():
    crosstalk = Crosstalk([turn(0, 10, A), turn(2, 4, B), turn(6, 7, B)])
    assert crosstalk.regions == [(2, 4), (6, 7)]
    assert crosstalk.seconds_within(3, 6.5) == pytest.approx(1.5)
    assert crosstalk.seconds_within(4, 6) == 0
    assert crosstalk.seconds_within(0, 10) == pytest.approx(3)


# --------------------------------------------------------------------- merge()

AUDIO = AudioInfo(duration_sec=60.0, sample_rate=16000, channels=1)


def words_of(text: str, start: float, end: float, p: float | None = 0.9) -> list[Word]:
    """Chia đều thời gian của đoạn cho từng token."""
    tokens = text.split()
    step = (end - start) / len(tokens)
    return [word(start + i * step, start + (i + 1) * step, tok, p) for i, tok in enumerate(tokens)]


def seg(
    start: float,
    end: float,
    text: str,
    *,
    words: list[Word] | None = None,
    avg_logprob: float | None = -0.1,
) -> AsrSegment:
    return AsrSegment(
        start_sec=start,
        end_sec=end,
        text=text,
        avg_logprob=avg_logprob,
        no_speech_prob=0.01,
        compression_ratio=1.2,
        words=words_of(text, start, end) if words is None else words,
    )


def asr(*segments: AsrSegment, warnings: list[PipelineWarning] | None = None) -> AsrOutput:
    return AsrOutput(
        model="test-asr", language="vi", segments=list(segments), warnings=warnings or []
    )


def diar(*turns: SpeakerTurn) -> DiarizeOutput:
    ordered = sorted(turns, key=lambda t: (t.start_sec, t.end_sec))
    return DiarizeOutput(
        model="test-diarization",
        status="ok",
        num_speakers=len({t.speaker_label for t in turns}),
        turns=ordered,
    )


def texts(transcript) -> list[tuple[str | None, str]]:
    return [(s.speaker_label, s.text) for s in transcript.segments]


def test_one_segment_per_speaker_turn():
    t = merge(
        asr(seg(0.5, 5.0, "Chào mọi người, mình bắt đầu nhé."), seg(6.0, 9.0, "Dạ, em nghe rõ.")),
        diar(turn(0.4, 5.2, A), turn(5.8, 9.2, B)),
        AUDIO,
    )
    assert texts(t) == [(A, "Chào mọi người, mình bắt đầu nhé."), (B, "Dạ, em nghe rõ.")]
    assert [(s.label, s.first_start_sec) for s in t.speakers] == [(A, 0.5), (B, 6.0)]
    assert t.diarization_status == "ok"
    assert (t.models.asr, t.models.diarization) == ("test-asr", "test-diarization")
    assert [s.flags for s in t.segments] == [[], []]


def test_speaker_change_mid_sentence_splits_segment():
    words = [
        word(0.2, 0.6, "Xin"),
        word(0.7, 1.2, "chào"),
        word(1.2, 1.25, "."),
        word(3.1, 3.6, "Vâng"),
        word(3.7, 4.4, "ạ."),
    ]
    t = merge(
        asr(seg(0.2, 4.4, "Xin chào. Vâng ạ.", words=words)),
        diar(turn(0, 3, A), turn(3, 6, B)),
        AUDIO,
    )
    assert texts(t) == [(A, "Xin chào."), (B, "Vâng ạ.")]
    first, second = t.segments
    assert (first.start_sec, first.end_sec) == (0.2, 1.25)
    assert (second.start_sec, second.end_sec) == (3.1, 4.4)
    assert [w.w for w in first.words] == ["Xin", "chào", "."]
    assert [w.w for w in second.words] == ["Vâng", "ạ."]


def test_speakers_are_renumbered_by_first_appearance():
    # pyannote đặt nhãn tùy ý: ở đây người nói đầu tiên là SPEAKER_02.
    t = merge(
        asr(seg(0, 4, "một hai ba"), seg(5, 9, "bốn năm sáu"), seg(10, 14, "bảy tám")),
        diar(turn(0, 4.5, C), turn(4.5, 9.5, A), turn(9.5, 15, C)),
        AUDIO,
    )
    assert [s.speaker_label for s in t.segments] == [A, B, A]
    assert [(s.label, s.first_start_sec) for s in t.speakers] == [(A, 0.0), (B, 5.0)]


def test_short_segments_of_same_speaker_are_joined():
    t = merge(
        asr(seg(0.0, 0.8, "Đồng ý."), seg(1.2, 4.0, "Anh Minh làm phần upload.")),
        diar(turn(0, 5, A)),
        AUDIO,
    )
    assert texts(t) == [(A, "Đồng ý. Anh Minh làm phần upload.")]
    only = t.segments[0]
    assert (only.start_sec, only.end_sec) == (0.0, 4.0)
    assert [w.w for w in only.words] == ["Đồng", "ý.", "Anh", "Minh", "làm", "phần", "upload."]


@pytest.mark.parametrize(
    "segments",
    [
        # Cả hai đoạn đều dài hơn short_segment_sec.
        [seg(0, 5, "đoạn một"), seg(5.2, 10, "đoạn hai")],
        # Đoạn ngắn nhưng cách quá max_gap_sec.
        [seg(0, 5, "đoạn một"), seg(6.5, 7, "ừ")],
        # Gộp vào thì dài quá max_segment_sec.
        [seg(0, 29.5, "đoạn rất dài"), seg(29.8, 30.6, "nhé")],
    ],
)
def test_segments_are_not_joined_beyond_limits(segments):
    t = merge(asr(*segments), diar(turn(0, 40, A)), AUDIO)
    assert len(t.segments) == 2


def test_unassigned_segments_are_never_joined():
    t = merge(
        asr(seg(10.0, 10.5, "ừ"), seg(10.6, 11.0, "được")),
        diar(turn(0, 5, A)),
        AUDIO,
    )
    assert texts(t) == [(None, "ừ"), (None, "được")]
    assert [s.label for s in t.speakers] == []


def test_segment_outside_every_turn_has_null_speaker():
    t = merge(
        asr(seg(0, 4, "câu thứ nhất"), seg(20, 22, "câu không ai nhận")),
        diar(turn(0, 5, A)),
        AUDIO,
    )
    assert texts(t) == [(A, "câu thứ nhất"), (None, "câu không ai nhận")]
    assert [s.label for s in t.speakers] == [A]


def test_crosstalk_sets_overlap_flag():
    # B nói chen "ừ" trong lúc A đang nói: ASR chỉ ra lời của A.
    t = merge(
        asr(seg(0, 6, "Mình cần chốt phạm vi sprint trong hôm nay"), seg(8, 12, "Tiếp theo nhé")),
        diar(turn(0, 6, A), turn(4, 5, B), turn(7.5, 12.5, A)),
        AUDIO,
    )
    assert [s.speaker_label for s in t.segments] == [A, A]
    assert t.segments[0].flags == [SegmentFlag.OVERLAP]
    assert t.segments[1].flags == []


def test_brief_crosstalk_below_threshold_is_not_flagged():
    t = merge(
        asr(seg(0, 6, "Mình cần chốt phạm vi sprint trong hôm nay")),
        diar(turn(0, 6, A), turn(5.9, 7, B)),
        AUDIO,
    )
    assert t.segments[0].flags == []


def test_asr_segments_overlapping_in_time_are_flagged():
    # Timestamp của ASR lệch: đoạn sau bắt đầu trước khi đoạn trước kết thúc.
    t = merge(
        asr(seg(0, 3.2, "đoạn của A"), seg(3.0, 6, "đoạn của B")),
        diar(turn(0, 3.1, A), turn(3.1, 6, B)),
        AUDIO,
    )
    assert [s.flags for s in t.segments] == [[SegmentFlag.OVERLAP], [SegmentFlag.OVERLAP]]


@pytest.mark.parametrize(
    ("words", "avg_logprob", "confidence", "flags"),
    [
        (words_of("nghe không rõ", 0, 3, p=0.3), -0.1, 0.3, [SegmentFlag.LOW_CONFIDENCE]),
        (words_of("nghe rất rõ", 0, 3, p=0.95), -2.0, 0.95, []),
        # Word thiếu xác suất: dùng exp(avg_logprob) của segment.
        (words_of("không có xác suất", 0, 3, p=None), -0.1, round(math.exp(-0.1), 3), []),
        ([], -1.2, round(math.exp(-1.2), 3), [SegmentFlag.LOW_CONFIDENCE]),
        ([], None, None, []),
    ],
)
def test_confidence_and_low_confidence_flag(words, avg_logprob, confidence, flags):
    t = merge(
        asr(seg(0, 3, "câu thử", words=words, avg_logprob=avg_logprob)),
        diar(turn(0, 3, A)),
        AUDIO,
    )
    assert t.segments[0].confidence == confidence
    assert t.segments[0].flags == flags


def test_joined_segment_confidence_is_weighted_by_duration():
    t = merge(
        asr(
            seg(0, 1, "ừ", words=words_of("ừ", 0, 1, p=0.4)),
            seg(1, 4, "để mình xem", words=words_of("để mình xem", 1, 4, p=0.8)),
        ),
        diar(turn(0, 5, A)),
        AUDIO,
    )
    assert len(t.segments) == 1
    assert t.segments[0].confidence == pytest.approx((0.4 * 1 + 0.8 * 3) / 4, abs=1e-3)


def test_fallback_diarization_uses_one_speaker():
    t = merge(
        asr(seg(0, 4, "câu một"), seg(10, 14, "câu hai")),
        diarization_fallback("diarization lỗi"),
        AUDIO,
    )
    assert [s.speaker_label for s in t.segments] == [A, A]
    assert [s.label for s in t.speakers] == [A]
    assert t.diarization_status == "fallback"
    assert t.models.diarization is None
    assert [w.code for w in t.warnings] == [DIARIZATION_FALLBACK]


def test_diarization_without_turns_falls_back_with_warning():
    empty = DiarizeOutput(model="test-diarization", status="ok", num_speakers=0, turns=[])
    t = merge(asr(seg(0, 4, "câu một")), empty, AUDIO)
    assert [s.speaker_label for s in t.segments] == [A]
    assert t.diarization_status == "fallback"
    assert [(w.code, w.stage) for w in t.warnings] == [(DIARIZATION_FALLBACK, Stage.MERGE)]


def test_times_are_clamped_to_audio_duration():
    audio = AudioInfo(duration_sec=10.0, sample_rate=16000, channels=1)
    words = [word(8.0, 9.0, "gần"), word(9.5, 12.0, "hết"), word(12.0, 12.0, "giờ")]
    t = merge(asr(seg(8.0, 12.0, "gần hết giờ", words=words)), diar(turn(7, 12, A)), audio)
    only = t.segments[0]
    assert (only.start_sec, only.end_sec) == (8.0, 10.0)
    assert [(w.s, w.e) for w in only.words] == [(8.0, 9.0), (9.5, 10.0), (10.0, 10.0)]


def test_zero_length_segment_gets_one_millisecond():
    t = merge(
        asr(seg(2.0, 2.5, "à", words=[word(2.0, 2.0, "à")])),
        diar(turn(0, 5, A)),
        AUDIO,
    )
    assert (t.segments[0].start_sec, t.segments[0].end_sec) == (2.0, 2.001)


def test_blank_text_and_words_are_dropped():
    t = merge(
        asr(
            seg(0, 1, "   ", words=[]),
            seg(2, 3, "có chữ", words=[word(2, 2.4, " "), *words_of("có chữ", 2.4, 3)]),
        ),
        diar(turn(0, 5, A)),
        AUDIO,
    )
    assert texts(t) == [(A, "có chữ")]
    assert [w.w for w in t.segments[0].words] == ["có", "chữ"]


def test_empty_asr_gives_empty_transcript():
    t = merge(asr(), diar(turn(0, 5, A)), AUDIO)
    assert t.segments == [] and t.speakers == []


def test_overlong_text_is_truncated_with_warning():
    garbage = "lặp " * 2000  # hallucination: một segment ASR rất dài
    t = merge(asr(seg(0, 30, garbage, words=[])), diar(turn(0, 30, A)), AUDIO)
    assert len(t.segments[0].text) <= MAX_TEXT_CHARS
    assert t.segments[0].text.endswith("lặp")
    assert [w.code for w in t.warnings] == [TEXT_TRUNCATED]


def test_warnings_are_kept_and_deduplicated():
    asr_warning = PipelineWarning(code="HALLUCINATION_FILTERED", stage=Stage.ASR, message="x")
    t = merge(
        asr(seg(0, 4, "câu một"), warnings=[asr_warning, asr_warning]),
        diar(turn(0, 5, A)),
        AUDIO,
    )
    assert t.warnings == [asr_warning]


def test_merge_is_deterministic():
    inputs = (
        asr(seg(0, 4, "một hai ba bốn"), seg(4.2, 4.8, "ừ"), seg(5, 9, "năm sáu bảy")),
        diar(turn(0, 4.1, B), turn(3.5, 5, A), turn(5, 9, B)),
        AUDIO,
    )
    assert merge(*inputs) == merge(*inputs)
    assert merge(*inputs, MergeConfig()) == merge(*inputs)
