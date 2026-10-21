"""Hậu xử lý output của engine ASR trước khi ghi `asr.json` (AI-06).

Engine (faster-whisper hay bản fake) trả về `RawSegment`, chưa được kiểm tra gì: timestamp
có thể âm, vượt thời lượng audio, `end < start`, word lệch ra ngoài segment, xác suất là
NaN. `normalize_segments()` đưa chúng về dạng luôn hợp lệ theo `AsrOutput`:

- Clamp mọi thời điểm vào `[0, duration]`, làm tròn ms, bảo đảm `start < end`.
- Word: bỏ khoảng trắng thừa, bỏ word rỗng, sắp theo thời gian, `e >= s`.
- Segment nới ra để chứa hết word của nó. Segment không có chữ và không có word thì bỏ.
- Xác suất ngoài `[0, 1]` hoặc NaN thì thành `None`.
- Segment sắp theo `(start_sec, end_sec)`.

`filter_hallucinations()` bỏ hoặc cắt các đoạn Whisper hay "bịa" ra trên khoảng lặng, nhạc
hoặc nhiễu (xem các hằng số bên dưới). Các ngưỡng là giá trị khởi tạo, lấy theo mặc định
của faster-whisper; hiệu chỉnh khi có audio họp thật (AI-13).

Hàm thuần, deterministic, không gọi model.
"""

from __future__ import annotations

import math
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass, field

from meeting_pipeline.schemas import AsrSegment, PipelineWarning, Stage, Word
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


# ------------------------------------------------------------ hallucination

HALLUCINATION_FILTERED = "HALLUCINATION_FILTERED"

# Đoạn im lặng: Whisper vẫn sinh chữ nhưng tự đánh giá là không có lời nói.
NO_SPEECH_PROB = 0.6
LOW_AVG_LOGPROB = -1.0
# Text lặp nhiều nén được rất tốt: dấu hiệu của vòng lặp giải mã.
MAX_COMPRESSION_RATIO = 2.4
# Một n-gram (1 đến MAX_NGRAM token) lặp liên tiếp quá REPEAT_LIMIT lần thì cắt bớt.
MAX_NGRAM = 4
REPEAT_LIMIT = 3
# Câu Whisper hay bịa trên nhạc nền hoặc khoảng lặng, học từ phụ đề video tiếng Việt.
# So khớp sau khi chữ thường, bỏ dấu câu. Không thêm câu có thể xuất hiện trong cuộc họp.
BLACKLIST = (
    "hãy subscribe cho kênh",
    "subscribe cho kênh",
    "đăng ký kênh",
    "ghiền mì gõ",
    "để không bỏ lỡ những video hấp dẫn",
    "cảm ơn các bạn đã theo dõi",
    "cảm ơn các bạn đã xem video",
    "hẹn gặp lại các bạn trong những video tiếp theo",
    "like share và subscribe",
)


def _key(text: str) -> str:
    """Chữ thường, bỏ dấu câu, gộp khoảng trắng: dùng để so khớp."""
    text = unicodedata.normalize("NFC", text).lower()
    text = "".join(" " if unicodedata.category(ch).startswith("P") else ch for ch in text)
    return " ".join(text.split())


def _collapse_pass(keys: Sequence[str]) -> list[int]:
    """Một lượt quét trái sang phải, trả về vị trí được giữ."""
    kept: list[int] = []
    i = 0
    while i < len(keys):
        step = 0
        # Không xét n-gram vượt quá cuối danh sách: thiếu điều kiện này thì vòng lặp
        # đứng yên ở token cuối.
        for n in range(1, min(MAX_NGRAM, len(keys) - i) + 1):
            gram = keys[i : i + n]
            repeats = 1
            while keys[i + repeats * n : i + (repeats + 1) * n] == gram:
                repeats += 1
            if repeats > REPEAT_LIMIT:
                kept.extend(range(i, i + REPEAT_LIMIT * n))
                step = repeats * n
                break
        if step:
            i += step
        else:
            kept.append(i)
            i += 1
    return kept


def _kept_indices(tokens: Sequence[str]) -> list[int]:
    """Vị trí token được giữ sau khi cắt các n-gram lặp liên tiếp quá REPEAT_LIMIT lần.

    Một lượt quét tham lam có thể để lộ ra vòng lặp mới (cắt "a" lặp ở đầu làm lộ ra
    "a a a b" lặp phía sau), nên quét lại tới khi không còn gì để cắt. Mỗi lượt có cắt
    đều làm danh sách ngắn đi, nên chắc chắn dừng.
    """
    keys = [_key(t) for t in tokens]
    indices = list(range(len(keys)))
    while True:
        kept = _collapse_pass([keys[i] for i in indices])
        if len(kept) == len(indices):
            return indices
        indices = [indices[k] for k in kept]


def _collapse_repeats(seg: AsrSegment) -> AsrSegment | None:
    """Segment đã cắt lặp, hoặc None nếu không có gì để cắt."""
    if seg.words:
        kept = _kept_indices([w.w for w in seg.words])
        if len(kept) == len(seg.words):
            return None
        words = [seg.words[i] for i in kept]
        text = " ".join(w.w for w in words)
        return seg.model_copy(update={"text": text, "words": words})
    tokens = seg.text.split()
    kept = _kept_indices(tokens)
    if len(kept) == len(tokens):
        return None
    return seg.model_copy(update={"text": " ".join(tokens[i] for i in kept)})


def _is_silence(seg: AsrSegment) -> bool:
    return (
        seg.no_speech_prob is not None
        and seg.avg_logprob is not None
        and seg.no_speech_prob > NO_SPEECH_PROB
        and seg.avg_logprob < LOW_AVG_LOGPROB
    )


def filter_hallucinations(
    segments: Sequence[AsrSegment],
) -> tuple[list[AsrSegment], list[PipelineWarning]]:
    """Bỏ hoặc cắt segment nghi là hallucination. Warning chỉ ghi số lượng, không ghi text."""
    kept: list[AsrSegment] = []
    dropped = trimmed = 0
    for seg in segments:
        key = _key(seg.text)
        if any(phrase in key for phrase in BLACKLIST) or _is_silence(seg):
            dropped += 1
            continue
        collapsed = _collapse_repeats(seg)
        if collapsed is not None:
            trimmed += 1
            kept.append(collapsed)
        elif seg.compression_ratio is not None and seg.compression_ratio > MAX_COMPRESSION_RATIO:
            dropped += 1
        else:
            kept.append(seg)

    warnings = []
    if dropped or trimmed:
        warnings.append(
            PipelineWarning(
                code=HALLUCINATION_FILTERED,
                stage=Stage.ASR,
                message=f"bỏ {dropped} segment nghi là hallucination, cắt lặp ở {trimmed} segment",
            )
        )
    return kept, warnings
