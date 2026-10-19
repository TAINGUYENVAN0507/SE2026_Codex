"""WER, CER và WER không dấu cho từng cặp reference/hypothesis và cho cả corpus (AI-11).

Cả hai bên đều qua `vi_normalize.normalize()` trước khi so (quy tắc trong
`normalizer/RULES.md`). Căn chỉnh dùng jiwer (Levenshtein của rapidfuzz), đủ nhanh cho
transcript cuộc họp dài hàng chục nghìn token.

- WER: số lỗi (S + D + I) chia cho số token của reference. Token là chuỗi tách bởi
  khoảng trắng, xấp xỉ âm tiết.
- CER: như WER nhưng trên từng ký tự của text đã chuẩn hóa, kể cả khoảng trắng giữa
  các token (cùng định nghĩa với jiwer).
- WER không dấu: WER sau khi `strip_diacritics()` cả hai bên. Chỉ dùng để chẩn đoán lỗi
  thanh điệu, không thay cho WER chính.

Cấp corpus cộng dồn số lỗi và số token của mọi sample rồi mới chia, không lấy trung
bình WER của từng sample (trung bình đó được báo cáo riêng).

    >>> s = score("Hoà chốt 25%.", "hòa chốt hai mươi năm phần trăm")
    >>> s.words.substitutions, s.words.ref_len
    (1, 7)
    >>> round(s.words.rate, 3)
    0.143
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

import jiwer
from vi_normalize import normalize, strip_diacritics


@dataclass(frozen=True)
class Counts:
    """Kết quả căn chỉnh. `ref_len` là số token (hoặc ký tự) của reference."""

    ref_len: int
    hits: int = 0
    substitutions: int = 0
    deletions: int = 0
    insertions: int = 0

    @property
    def errors(self) -> int:
        return self.substitutions + self.deletions + self.insertions

    @property
    def rate(self) -> float | None:
        """`errors / ref_len`, hoặc None khi reference rỗng (không định nghĩa được)."""
        return self.errors / self.ref_len if self.ref_len else None

    def __add__(self, other: Counts) -> Counts:
        return Counts(
            ref_len=self.ref_len + other.ref_len,
            hits=self.hits + other.hits,
            substitutions=self.substitutions + other.substitutions,
            deletions=self.deletions + other.deletions,
            insertions=self.insertions + other.insertions,
        )


def _from_jiwer(out: jiwer.WordOutput | jiwer.CharacterOutput, ref_len: int) -> Counts:
    return Counts(ref_len, out.hits, out.substitutions, out.deletions, out.insertions)


def _one_side_empty(ref_len: int, hyp_len: int) -> Counts:
    # Không cần căn chỉnh; jiwer cũng không định nghĩa WER cho reference rỗng.
    return Counts(ref_len=ref_len, deletions=ref_len, insertions=hyp_len)


def word_counts(ref: str, hyp: str) -> Counts:
    """Căn chỉnh theo token tách bởi khoảng trắng. Input nên đã được chuẩn hóa."""
    r, h = ref.split(), hyp.split()
    if not r or not h:
        return _one_side_empty(len(r), len(h))
    return _from_jiwer(jiwer.process_words(" ".join(r), " ".join(h)), len(r))


def char_counts(ref: str, hyp: str) -> Counts:
    """Căn chỉnh theo ký tự; khoảng trắng liên tiếp được gộp làm một."""
    r, h = " ".join(ref.split()), " ".join(hyp.split())
    if not r or not h:
        return _one_side_empty(len(r), len(h))
    return _from_jiwer(jiwer.process_characters(r, h), len(r))


@dataclass(frozen=True)
class SampleScore:
    words: Counts
    chars: Counts
    words_nodiac: Counts


def score(reference: str, hypothesis: str) -> SampleScore:
    """Chuẩn hóa cả hai bên rồi tính WER, CER, WER không dấu."""
    ref, hyp = normalize(reference), normalize(hypothesis)
    return SampleScore(
        words=word_counts(ref, hyp),
        chars=char_counts(ref, hyp),
        words_nodiac=word_counts(strip_diacritics(ref), strip_diacritics(hyp)),
    )


@dataclass(frozen=True)
class CorpusScore:
    samples: int
    words: Counts
    chars: Counts
    words_nodiac: Counts
    # Trung bình WER của từng sample, bỏ qua sample có reference rỗng.
    mean_sample_wer: float | None


def corpus(scores: Iterable[SampleScore]) -> CorpusScore:
    scores = list(scores)
    words, chars, nodiac = Counts(0), Counts(0), Counts(0)
    for s in scores:
        words, chars, nodiac = words + s.words, chars + s.chars, nodiac + s.words_nodiac
    rates = [s.words.rate for s in scores if s.words.rate is not None]
    return CorpusScore(
        samples=len(scores),
        words=words,
        chars=chars,
        words_nodiac=nodiac,
        mean_sample_wer=sum(rates) / len(rates) if rates else None,
    )
