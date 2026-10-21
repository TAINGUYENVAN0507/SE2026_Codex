"""Hậu xử lý output của engine ASR trước khi ghi `asr.json` (AI-06).

Engine (faster-whisper hay bản fake) trả về `RawSegment`, chưa được kiểm tra gì: timestamp
có thể âm, vượt thời lượng audio, `end < start`, word lệch ra ngoài segment, xác suất là
NaN. `normalize_segments()` đưa chúng về dạng luôn hợp lệ theo `AsrOutput`:

- Clamp mọi thời điểm vào `[0, duration]`, làm tròn ms, bảo đảm `start < end`.
- Word: bỏ khoảng trắng thừa, bỏ word rỗng, sắp theo thời gian, `e >= s`.
- Segment nới ra để chứa hết word của nó. Segment không có chữ và không có word thì bỏ.
- Xác suất ngoài `[0, 1]` hoặc NaN thì thành `None`.
- Segment sắp theo `(start_sec, end_sec)`.

Hàm thuần, deterministic, không gọi model.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass, field

from meeting_pipeline.schemas import AsrSegment, Word
from meeting_pipeline.timing import clamp, span_within


@dataclass(frozen=True)
class RawWord:
    w: str
    s: float
    e: float
    p: float | None = None


@dataclass(frozen=True)
class RawSegment:
    start: float
    end: float
    text: str
    avg_logprob: float | None = None
    no_speech_prob: float | None = None
    compression_ratio: float | None = None
    words: Sequence[RawWord] = field(default_factory=tuple)


def _finite(value: float | None) -> float | None:
    return value if value is not None and math.isfinite(value) else None


def _probability(value: float | None) -> float | None:
    value = _finite(value)
    return value if value is not None and 0.0 <= value <= 1.0 else None


def _words(raw: Sequence[RawWord], duration: float) -> list[Word]:
    words = []
    for w in raw:
        token = w.w.strip()
        if not token or not math.isfinite(w.s) or not math.isfinite(w.e):
            continue
        s = round(clamp(w.s, duration), 3)
        e = round(clamp(max(w.e, w.s), duration), 3)
        words.append(Word(w=token, s=s, e=max(e, s), p=_probability(w.p)))
    return sorted(words, key=lambda w: (w.s, w.e))


def normalize_segment(raw: RawSegment, duration: float) -> AsrSegment | None:
    """Một segment thô thành `AsrSegment` hợp lệ, hoặc None nếu không còn chữ."""
    words = _words(raw.words, duration)
    text = " ".join(raw.text.split())
    if not text:
        if not words:
            return None
        text = " ".join(w.w for w in words)

    start = raw.start if math.isfinite(raw.start) else 0.0
    end = raw.end if math.isfinite(raw.end) else start
    if words:
        start, end = min(start, words[0].s), max(end, max(w.e for w in words))
    start, end = span_within(start, end, duration)

    ratio = _finite(raw.compression_ratio)
    return AsrSegment(
        start_sec=start,
        end_sec=end,
        text=text,
        avg_logprob=_finite(raw.avg_logprob),
        no_speech_prob=_probability(raw.no_speech_prob),
        compression_ratio=ratio if ratio is not None and ratio >= 0 else None,
        words=words,
    )


def normalize_segments(raw: Sequence[RawSegment], duration: float) -> list[AsrSegment]:
    segments = [s for r in raw if (s := normalize_segment(r, duration)) is not None]
    return sorted(segments, key=lambda s: (s.start_sec, s.end_sec))
