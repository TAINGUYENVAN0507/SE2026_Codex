"""Test stage merge (AI-08): gán speaker cho word, dựng segment, bất biến của transcript."""

import random

import pytest

from meeting_pipeline.schemas import SpeakerTurn, Word
from meeting_pipeline.stages.merge import Crosstalk, TurnIndex, label_words

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
