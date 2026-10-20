import random
import time
import unicodedata

import pytest
from metrics import Counts, char_counts, corpus, score, word_counts


@pytest.mark.parametrize(
    ("ref", "hyp", "expected"),
    [
        ("a b c d", "a b c d", Counts(4, hits=4)),
        ("a b c d", "a x c e f", Counts(4, hits=2, substitutions=2, insertions=1)),
        ("a b c d", "a c d", Counts(4, hits=3, deletions=1)),
        ("a b c", "", Counts(3, deletions=3)),
        ("", "a b", Counts(0, insertions=2)),
        ("", "", Counts(0)),
        ("  a   b ", "a b", Counts(2, hits=2)),
    ],
)
def test_word_counts(ref, hyp, expected):
    assert word_counts(ref, hyp) == expected


def test_rate():
    assert Counts(4, hits=2, substitutions=2, insertions=1).rate == pytest.approx(0.75)
    assert Counts(3, deletions=3).rate == 1.0
    # Reference rỗng: WER không định nghĩa được, không báo thành 0 hay vô cực.
    assert Counts(0, insertions=2).rate is None


def test_char_counts_include_spaces_between_tokens():
    c = char_counts("ab cd", "ab ce")
    assert c == Counts(5, hits=4, substitutions=1)
    assert char_counts("ab  cd", "abcd") == Counts(5, hits=4, deletions=1)


def test_hits_substitutions_deletions_cover_reference():
    rng = random.Random(42)
    vocab = ["một", "hai", "ba", "bốn", "năm"]
    for _ in range(200):
        ref = " ".join(rng.choices(vocab, k=rng.randint(1, 15)))
        hyp = " ".join(rng.choices(vocab, k=rng.randint(0, 15)))
        for c in (word_counts(ref, hyp), char_counts(ref, hyp)):
            assert c.hits + c.substitutions + c.deletions == c.ref_len


def test_score_normalizes_both_sides():
    s = score("Hoà chốt 25%, ờ, lúc 9h30.", "hòa chốt hai mươi lăm phần trăm lúc chín giờ ba mươi")
    assert s.words.errors == 0 and s.chars.errors == 0
    nfd = unicodedata.normalize("NFD", "Thủy điện")
    assert score(nfd, "thủy điện").words.errors == 0


def test_wer_without_diacritics_separates_tone_errors():
    s = score("bán hàng online", "bàn hàng online")
    assert s.words == Counts(3, hits=2, substitutions=1)
    assert s.words_nodiac == Counts(3, hits=3)


def test_corpus_wer_sums_errors_before_dividing():
    long_ok = score("một hai ba bốn", "một hai ba năm")  # 1/4
    short_bad = score("vâng", "")  # 1/1
    c = corpus([long_ok, short_bad])
    assert c.samples == 2
    assert c.words == Counts(5, hits=3, substitutions=1, deletions=1)
    assert c.words.rate == pytest.approx(2 / 5)
    assert c.mean_sample_wer == pytest.approx((0.25 + 1.0) / 2)


def test_corpus_skips_empty_reference_in_mean_but_counts_its_errors():
    c = corpus([score("một hai", "một hai"), score("", "ừ thêm")])
    assert c.words.insertions == 2
    assert c.words.rate == pytest.approx(1.0)
    assert c.mean_sample_wer == 0.0


def test_empty_corpus():
    c = corpus([])
    assert c.samples == 0 and c.words.rate is None and c.mean_sample_wer is None


def test_long_meeting_transcript_is_fast():
    # Cuộc họp 60' vào khoảng 10-15 nghìn token: căn chỉnh không được chậm như DP Python.
    rng = random.Random(0)
    vocab = [f"t{i}" for i in range(300)]
    ref = rng.choices(vocab, k=20_000)
    hyp = [w if rng.random() > 0.15 else rng.choice(vocab) for w in ref]
    started = time.perf_counter()
    c = word_counts(" ".join(ref), " ".join(hyp))
    assert time.perf_counter() - started < 5
    assert c.ref_len == 20_000 and 0 < c.rate < 0.2
