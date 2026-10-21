"""Test hậu xử lý output của engine ASR (AI-06)."""

import math
from collections import Counter

from hypothesis import given, settings
from hypothesis import strategies as st

from meeting_pipeline.schemas import AsrOutput
from meeting_pipeline.stages.asr_post import RawSegment, RawWord, normalize_segments


def asr(segments) -> AsrOutput:
    return AsrOutput(model="test", language="vi", segments=segments)


def test_valid_segment_is_kept_as_is():
    raw = RawSegment(
        1.0,
        3.5,
        " Xin chào mọi người. ",
        -0.2,
        0.01,
        1.3,
        (RawWord(" Xin", 1.0, 1.4, 0.9), RawWord("chào", 1.4, 1.9, 0.8)),
    )
    [seg] = normalize_segments([raw], duration=10)
    assert (seg.start_sec, seg.end_sec, seg.text) == (1.0, 3.5, "Xin chào mọi người.")
    assert [(w.w, w.s, w.e, w.p) for w in seg.words] == [
        ("Xin", 1.0, 1.4, 0.9),
        ("chào", 1.4, 1.9, 0.8),
    ]
    assert (seg.avg_logprob, seg.no_speech_prob, seg.compression_ratio) == (-0.2, 0.01, 1.3)


def test_times_are_clamped_rounded_and_ordered():
    raw = [
        RawSegment(8.0, 12.0, "cuối", words=(RawWord("cuối", 9.5, 12.5),)),
        RawSegment(-0.5, 0.123456, "đầu"),
        RawSegment(4.0, 3.0, "ngược"),
    ]
    segs = normalize_segments(raw, duration=10)
    assert [(s.text, s.start_sec, s.end_sec) for s in segs] == [
        ("đầu", 0.0, 0.123),
        ("ngược", 4.0, 4.001),
        ("cuối", 8.0, 10.0),
    ]
    assert (segs[2].words[0].s, segs[2].words[0].e) == (9.5, 10.0)


def test_segment_grows_to_cover_its_words():
    raw = RawSegment(2.0, 3.0, "a b", words=(RawWord("a", 1.8, 2.2), RawWord("b", 2.9, 3.4)))
    [seg] = normalize_segments([raw], duration=10)
    assert (seg.start_sec, seg.end_sec) == (1.8, 3.4)


def test_empty_text_and_words_are_dropped_or_rebuilt():
    raw = [
        RawSegment(0, 1, "   "),
        RawSegment(
            1,
            2,
            "",
            words=(RawWord("chỉ", 1.1, 1.3), RawWord(" ", 1.3, 1.4), RawWord("word", 1.4, 1.8)),
        ),
    ]
    [seg] = normalize_segments(raw, duration=10)
    assert seg.text == "chỉ word"
    assert [w.w for w in seg.words] == ["chỉ", "word"]


def test_bad_probabilities_become_none():
    raw = RawSegment(
        0,
        1,
        "x",
        avg_logprob=math.nan,
        no_speech_prob=1.7,
        compression_ratio=-1,
        words=(RawWord("x", 0, 1, math.inf),),
    )
    [seg] = normalize_segments([raw], duration=10)
    assert (seg.avg_logprob, seg.no_speech_prob, seg.compression_ratio) == (None, None, None)
    assert seg.words[0].p is None


def test_zero_length_segment_at_end_of_audio():
    [seg] = normalize_segments([RawSegment(10.0, 10.0, "hết")], duration=10)
    assert (seg.start_sec, seg.end_sec) == (9.999, 10.0)


times = st.floats(-5, 130, allow_nan=False)
tokens = st.sampled_from(["một", "hai", " ", "", "Ba.", "API", "ừ"])
probs = st.none() | st.floats(allow_nan=True, allow_infinity=True)


@st.composite
def raw_segments(draw):
    segs = []
    for _ in range(draw(st.integers(0, 8))):
        words = tuple(
            RawWord(draw(tokens), draw(times), draw(times), draw(probs))
            for _ in range(draw(st.integers(0, 6)))
        )
        segs.append(
            RawSegment(
                draw(times), draw(times), draw(tokens), draw(probs), draw(probs), draw(probs), words
            )
        )
    return segs


@settings(max_examples=300, deadline=None)
@given(raw_segments(), st.floats(1, 120))
def test_output_always_valid_and_keeps_every_word(raw, duration):
    segs = normalize_segments(raw, duration)
    out = asr(segs)
    assert AsrOutput.model_validate(out.model_dump()) == out
    for s in segs:
        assert 0 <= s.start_sec < s.end_sec <= round(duration, 3)
        assert s.text.strip()
        assert all(0 <= w.s <= w.e for w in s.words)
    expected = Counter(w.w.strip() for r in raw for w in r.words if w.w.strip())
    assert Counter(w.w for s in segs for w in s.words) == expected


# ---------------------------------------------------------- hallucination

from meeting_pipeline.schemas import AsrSegment, Word  # noqa: E402
from meeting_pipeline.stages.asr_post import (  # noqa: E402
    HALLUCINATION_FILTERED,
    filter_hallucinations,
)


def seg(text, start=0.0, end=2.0, *, nsp=0.01, logprob=-0.2, ratio=1.3, words=()):
    return AsrSegment(
        start_sec=start,
        end_sec=end,
        text=text,
        avg_logprob=logprob,
        no_speech_prob=nsp,
        compression_ratio=ratio,
        words=list(words),
    )


def test_normal_segments_are_untouched():
    segs = [seg("Hôm nay mình chốt phạm vi sprint."), seg("Được, được.", 2, 3)]
    assert filter_hallucinations(segs) == (segs, [])


def test_blacklisted_phrase_is_dropped():
    segs = [
        seg("Hãy subscribe cho kênh Ghiền Mì Gõ để không bỏ lỡ những video hấp dẫn."),
        seg("Bắt đầu họp nhé.", 2, 4),
    ]
    kept, warnings = filter_hallucinations(segs)
    assert [s.text for s in kept] == ["Bắt đầu họp nhé."]
    assert [(w.code, w.message) for w in warnings] == [
        (HALLUCINATION_FILTERED, "bỏ 1 segment nghi là hallucination, cắt lặp ở 0 segment")
    ]


def test_silence_needs_both_high_no_speech_and_low_logprob():
    silent = seg("Cảm ơn.", nsp=0.9, logprob=-1.5)
    unsure_but_spoken = seg("Cảm ơn.", nsp=0.9, logprob=-0.3)
    quiet_speech = seg("Cảm ơn.", nsp=0.2, logprob=-1.5)
    kept, _ = filter_hallucinations([silent, unsure_but_spoken, quiet_speech])
    assert kept == [unsure_but_spoken, quiet_speech]


def test_repeated_ngrams_are_cut_to_the_limit():
    looped = seg("vâng " * 10 + "ok", ratio=4.0)
    phrase = seg("đúng rồi " * 6)
    three = seg("không không không")  # 3 lần vẫn có thể là lời nói thật
    kept, warnings = filter_hallucinations([looped, phrase, three])
    assert [s.text for s in kept] == [
        "vâng vâng vâng ok",
        "đúng rồi đúng rồi đúng rồi",
        "không không không",
    ]
    assert warnings[0].message == "bỏ 0 segment nghi là hallucination, cắt lặp ở 2 segment"


def test_repeats_are_cut_on_words_with_their_timestamps():
    words = [
        Word(w=w, s=i * 0.2, e=i * 0.2 + 0.2, p=0.9) for i, w in enumerate(["chào,"] + ["ok"] * 6)
    ]
    [cut], _ = filter_hallucinations([seg("chào, ok ok ok ok ok ok", words=words)])
    assert cut.text == "chào, ok ok ok"
    assert [w.s for w in cut.words] == [0.0, 0.2, 0.4, 0.6]


def test_high_compression_without_visible_loop_is_dropped():
    kept, warnings = filter_hallucinations([seg("lalala lalala lalalala", ratio=3.1)])
    assert kept == [] and len(warnings) == 1


@settings(max_examples=300, deadline=None)
@given(st.lists(st.sampled_from(["a", "b", "a,"]), max_size=40))
def test_repeat_collapse_terminates_and_respects_the_limit(tokens):
    from meeting_pipeline.stages.asr_post import MAX_NGRAM, REPEAT_LIMIT, _kept_indices

    kept = _kept_indices(tokens)
    assert kept == sorted(set(kept)) and all(0 <= i < len(tokens) for i in kept)
    if tokens:
        assert kept  # luôn giữ ít nhất một token
    out = [tokens[i].rstrip(",") for i in kept]
    for n in range(1, MAX_NGRAM + 1):
        for i in range(len(out) - n * (REPEAT_LIMIT + 1) + 1):
            grams = [out[i + k * n : i + (k + 1) * n] for k in range(REPEAT_LIMIT + 1)]
            assert not all(g == grams[0] for g in grams), (tokens, out)
