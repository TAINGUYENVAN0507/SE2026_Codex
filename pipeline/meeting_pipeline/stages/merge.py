"""Stage merge (AI-08): ghép output ASR với diarization thành transcript có speaker.

1. Gán speaker cho từng word theo phần overlap lớn nhất với các turn của diarization.
   Word rơi vào khoảng lặng giữa các turn (timestamp của ASR thường lệch vài trăm ms)
   lấy speaker của word gần nhất trong cùng segment ASR. Cả segment ASR không chạm turn
   nào thì speaker là null: người dùng gán tay trên UI.
2. Tách segment ASR khi đổi speaker giữa câu.
3. Gộp các đoạn ngắn liền nhau của cùng một speaker.
4. Gắn cờ `overlap` khi đoạn có nhiều người nói cùng lúc (hoặc chồng lên đoạn trước do
   timestamp của ASR lệch), `low_confidence` khi confidence thấp.
5. Đánh số lại speaker theo thứ tự xuất hiện: người nói đầu tiên là `SPEAKER_00`.

Diarization fallback (hoặc không có turn nào) thì gộp toàn bộ thành 1 speaker.

Mọi hàm ở đây là pure function và deterministic: không đọc môi trường, không gọi model.
Thời gian được clamp vào `[0, duration_sec]` và làm tròn ms, nên output luôn thỏa các
bất biến của `Transcript` dù ASR trả timestamp lệch.
"""

from __future__ import annotations

import bisect
import math
import unicodedata
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, field
from itertools import accumulate, groupby

from meeting_pipeline.fallbacks import DIARIZATION_FALLBACK
from meeting_pipeline.schemas import (
    AsrOutput,
    AsrSegment,
    AudioInfo,
    DiarizeOutput,
    ModelInfo,
    PipelineWarning,
    PreprocessOutput,
    SegmentFlag,
    SpeakerTurn,
    Stage,
    Transcript,
    TranscriptSegment,
    TranscriptSpeaker,
    Word,
)
from meeting_pipeline.stages.base import StageContext

MAX_TEXT_CHARS = 5000  # giới hạn `text` của TranscriptSegment
TEXT_TRUNCATED = "SEGMENT_TEXT_TRUNCATED"
_ONE_SPEAKER = "SPEAKER_00"


@dataclass(frozen=True)
class MergeConfig:
    """Giá trị khởi tạo, chưa đo trên audio họp thật. Hiệu chỉnh ở AI-13."""

    # Chỉ gộp hai đoạn cùng speaker khi cách nhau không quá max_gap_sec, một trong hai
    # ngắn hơn short_segment_sec, và đoạn sau khi gộp không dài quá max_segment_sec.
    max_gap_sec: float = 1.0
    short_segment_sec: float = 1.5
    max_segment_sec: float = 30.0
    # Gắn cờ overlap khi thời gian nói chồng trong đoạn đạt mức này (hoặc nửa đoạn).
    crosstalk_min_sec: float = 0.3
    low_confidence: float = 0.5


def _overlap(a_start: float, a_end: float, b_start: float, b_end: float) -> float:
    return max(0.0, min(a_end, b_end) - max(a_start, b_start))


class TurnIndex:
    """Tra cứu nhanh các turn chạm vào một khoảng thời gian.

    Turn được sắp theo `start_sec`. `_max_end[i]` là `end_sec` lớn nhất trong
    `turns[0..i]`, nên khi quét ngược từ turn cuối cùng bắt đầu trước khoảng cần tìm,
    có thể dừng ngay khi `_max_end` không còn với tới đầu khoảng. Một cuộc họp 60' có
    khoảng chục nghìn word, quét toàn bộ turn cho mỗi word sẽ quá chậm.
    """

    def __init__(self, turns: Sequence[SpeakerTurn]) -> None:
        self._turns = sorted(turns, key=lambda t: (t.start_sec, t.end_sec, t.speaker_label))
        self._starts = [t.start_sec for t in self._turns]
        self._max_end = list(accumulate((t.end_sec for t in self._turns), max))

    def __len__(self) -> int:
        return len(self._turns)

    def touching(self, start: float, end: float) -> list[SpeakerTurn]:
        """Các turn giao với đoạn `[start, end]`, kể cả chỉ chạm ở biên."""
        found = []
        for i in range(bisect.bisect_right(self._starts, end) - 1, -1, -1):
            if self._max_end[i] < start:
                break
            if self._turns[i].end_sec >= start:
                found.append(self._turns[i])
        found.reverse()
        return found

    def speaker_for(self, start: float, end: float) -> str | None:
        """Speaker có tổng thời gian overlap với `[start, end]` lớn nhất, hoặc None.

        Hòa thì lấy label nhỏ hơn, để kết quả không phụ thuộc thứ tự turn. Word dài 0 s
        (ASR đôi khi trả về) được gán cho turn chứa nó.
        """
        totals: dict[str, float] = {}
        for t in self.touching(start, end):
            amount = _overlap(start, end, t.start_sec, t.end_sec)
            totals[t.speaker_label] = totals.get(t.speaker_label, 0.0) + amount
        if end > start:
            totals = {label: amount for label, amount in totals.items() if amount > 0}
        if not totals:
            return None
        return min(totals, key=lambda label: (-totals[label], label))


def label_words(words: Sequence[Word], index: TurnIndex) -> list[str | None]:
    """Speaker của từng word trong một segment ASR, theo thứ tự của `words`.

    Word không chạm turn nào lấy speaker của word gần nhất về thời gian đã gán được
    trong cùng segment; cách đều hai bên thì lấy word đứng trước. Không word nào chạm
    turn thì cả segment là None.
    """
    labels = [index.speaker_for(w.s, w.e) for w in words]
    known = [i for i, label in enumerate(labels) if label is not None]
    if not known:
        return labels

    result: list[str | None] = []
    for i, label in enumerate(labels):
        if label is None:
            pos = bisect.bisect_left(known, i)
            # (khoảng cách, phía, vị trí): phía 0 là word đứng trước, thắng khi hòa.
            candidates: list[tuple[float, int, int]] = []
            if pos > 0:
                j = known[pos - 1]
                candidates.append((words[i].s - words[j].e, 0, j))
            if pos < len(known):
                j = known[pos]
                candidates.append((words[j].s - words[i].e, 1, j))
            label = labels[min(candidates)[2]]
        result.append(label)
    return result


class Crosstalk:
    """Các khoảng có từ 2 speaker khác nhau cùng nói.

    pyannote cho phép turn của các speaker chồng lấn nhau. ASR chỉ ra một luồng chữ,
    nên đoạn transcript nằm trong khoảng này dễ lẫn lời của hai người: merge gắn cờ
    `overlap` để người dùng biết cần kiểm tra.
    """

    def __init__(self, turns: Sequence[SpeakerTurn]) -> None:
        # Tại cùng một thời điểm, xử lý turn kết thúc trước turn bắt đầu: hai turn chỉ
        # chạm nhau ở biên không tạo ra khoảng nói chồng.
        events = sorted(
            [(t.start_sec, 1, t.speaker_label) for t in turns]
            + [(t.end_sec, -1, t.speaker_label) for t in turns],
            key=lambda e: (e[0], e[1]),
        )
        active: Counter[str] = Counter()
        regions: list[tuple[float, float]] = []
        opened: float | None = None
        for time, delta, label in events:
            active[label] += delta
            if active[label] == 0:
                del active[label]
            if len(active) >= 2 and opened is None:
                opened = time
            elif len(active) < 2 and opened is not None:
                if time > opened:
                    regions.append((opened, time))
                opened = None
        self.regions = regions
        self._starts = [start for start, _ in regions]

    def seconds_within(self, start: float, end: float) -> float:
        """Tổng thời gian nói chồng nằm trong `[start, end]`."""
        total = 0.0
        # Các khoảng không giao nhau và đã sắp xếp, nên `end` của chúng cũng tăng dần.
        for i in range(bisect.bisect_left(self._starts, end) - 1, -1, -1):
            r_start, r_end = self.regions[i]
            if r_end <= start:
                break
            total += _overlap(start, end, r_start, r_end)
        return total


# ------------------------------------------------------------------ transcript


@dataclass
class _Piece:
    """Một đoạn liên tục của cùng một speaker, trước khi thành TranscriptSegment."""

    start: float
    end: float
    label: str | None
    text: str
    words: list[Word]
    # (confidence, trọng số theo thời lượng) của từng phần đã gộp vào đoạn này.
    scores: list[tuple[float, float]] = field(default_factory=list)

    @property
    def duration(self) -> float:
        return self.end - self.start

    def confidence(self) -> float | None:
        total = sum(weight for _, weight in self.scores)
        if total <= 0:
            return None
        return round(sum(c * weight for c, weight in self.scores) / total, 3)


def _span(start: float, end: float, duration: float) -> tuple[float, float]:
    """Clamp vào `[0, duration]`, làm tròn ms và bảo đảm `start < end`."""
    start = round(min(max(start, 0.0), duration), 3)
    end = round(min(max(end, start), duration), 3)
    if end <= start:
        if round(start + 0.001, 3) <= duration:
            end = round(start + 0.001, 3)
        else:
            start, end = round(duration - 0.001, 3), duration
    return start, end


def _clean_words(words: Sequence[Word], duration: float) -> list[Word]:
    cleaned = []
    for w in words:
        token = w.w.strip()
        if not token:
            continue
        s = min(max(w.s, 0.0), duration)
        cleaned.append(Word(w=token, s=s, e=min(max(w.e, s), duration), p=w.p))
    return sorted(cleaned, key=lambda w: (w.s, w.e))


def _is_punct(token: str) -> bool:
    return all(unicodedata.category(ch).startswith("P") for ch in token)


def _join(words: Sequence[Word]) -> str:
    """Ghép word thành câu. Token chỉ gồm dấu câu dính vào token trước, không cách."""
    text = ""
    for w in words:
        text += w.w if not text or _is_punct(w.w) else f" {w.w}"
    return text


def _confidence(words: Sequence[Word], seg: AsrSegment) -> float | None:
    """Trung bình xác suất của word; thiếu thì lấy exp(avg_logprob) của segment ASR."""
    probs = [w.p for w in words if w.p is not None]
    if words and len(probs) == len(words):
        return sum(probs) / len(probs)
    if seg.avg_logprob is not None:
        return min(1.0, math.exp(seg.avg_logprob))
    return None


def _pieces(seg: AsrSegment, index: TurnIndex, one_speaker: bool, duration: float) -> list[_Piece]:
    """Tách một segment ASR thành các đoạn, mỗi đoạn một speaker."""

    def piece(start: float, end: float, label: str | None, text: str, words: list[Word]):
        start, end = _span(start, end, duration)
        conf = _confidence(words, seg)
        scores = [] if conf is None else [(conf, max(end - start, 0.001))]
        return _Piece(start, end, label, text, words, scores)

    words = _clean_words(seg.words, duration)
    text = seg.text.strip()
    if not words:
        if not text:
            return []
        start, end = _span(seg.start_sec, seg.end_sec, duration)
        label = _ONE_SPEAKER if one_speaker else index.speaker_for(start, end)
        return [piece(start, end, label, text, [])]

    labels = [_ONE_SPEAKER] * len(words) if one_speaker else label_words(words, index)
    runs = [
        (label, [w for _, w in group])
        for label, group in groupby(zip(labels, words, strict=True), key=lambda lw: lw[0])
    ]
    return [
        # Không phải tách thì giữ nguyên text của ASR (dấu câu, khoảng trắng).
        piece(
            run[0].s,
            max(w.e for w in run),
            label,
            text if len(runs) == 1 and text else _join(run),
            run,
        )
        for label, run in runs
    ]


def _can_join(a: _Piece, b: _Piece, config: MergeConfig) -> bool:
    return (
        a.label is not None
        and a.label == b.label
        and b.start - a.end <= config.max_gap_sec
        and min(a.duration, b.duration) < config.short_segment_sec
        and max(a.end, b.end) - a.start <= config.max_segment_sec
        and len(a.text) + 1 + len(b.text) <= MAX_TEXT_CHARS
    )


def _join_short(pieces: Sequence[_Piece], config: MergeConfig) -> list[_Piece]:
    joined: list[_Piece] = []
    for p in pieces:
        if joined and _can_join(joined[-1], p, config):
            last = joined[-1]
            last.end = max(last.end, p.end)
            last.text = f"{last.text} {p.text}"
            last.words = sorted([*last.words, *p.words], key=lambda w: (w.s, w.e))
            last.scores.extend(p.scores)
        else:
            joined.append(p)
    return joined


def _truncate(text: str) -> str:
    cut = text[:MAX_TEXT_CHARS]
    space = cut.rfind(" ")
    return (cut[:space] if space > 0 else cut).rstrip()


def _dedupe(warnings: Sequence[PipelineWarning]) -> list[PipelineWarning]:
    seen: set[tuple[str, Stage]] = set()
    result = []
    for w in warnings:
        if (w.code, w.stage) not in seen:
            seen.add((w.code, w.stage))
            result.append(w)
    return result


def merge(
    asr: AsrOutput,
    diarization: DiarizeOutput,
    audio: AudioInfo,
    config: MergeConfig | None = None,
) -> Transcript:
    """Ghép `asr` và `diarization` thành `Transcript`. Pure function."""
    config = config or MergeConfig()
    duration = round(audio.duration_sec, 3)
    warnings = [*asr.warnings, *diarization.warnings]

    one_speaker = diarization.status == "fallback" or not diarization.turns
    if diarization.status == "ok" and not diarization.turns:
        warnings.append(
            PipelineWarning(
                code=DIARIZATION_FALLBACK,
                stage=Stage.MERGE,
                message="diarization không tìm thấy lượt nói nào, gộp thành 1 speaker",
            )
        )
    index = TurnIndex(diarization.turns)
    crosstalk = Crosstalk(diarization.turns)

    pieces = [p for seg in asr.segments for p in _pieces(seg, index, one_speaker, duration)]
    pieces.sort(key=lambda p: (p.start, p.end))
    pieces = _join_short(pieces, config)

    flags: list[set[SegmentFlag]] = [set() for _ in pieces]
    reach = 0  # vị trí của đoạn có end lớn nhất tính tới đoạn đang xét
    for i, p in enumerate(pieces):
        conf = p.confidence()
        if conf is not None and conf < config.low_confidence:
            flags[i].add(SegmentFlag.LOW_CONFIDENCE)
        if crosstalk.seconds_within(p.start, p.end) >= min(
            config.crosstalk_min_sec, p.duration / 2
        ):
            flags[i].add(SegmentFlag.OVERLAP)
        if i > 0 and p.start < pieces[reach].end:
            flags[i].add(SegmentFlag.OVERLAP)
            flags[reach].add(SegmentFlag.OVERLAP)
        if p.end > pieces[reach].end:
            reach = i

    names: dict[str, str] = {}
    speakers: list[TranscriptSpeaker] = []
    for p in pieces:
        if p.label is not None and p.label not in names:
            names[p.label] = f"SPEAKER_{len(names):02d}"
            speakers.append(TranscriptSpeaker(label=names[p.label], first_start_sec=p.start))

    truncated = sum(len(p.text) > MAX_TEXT_CHARS for p in pieces)
    if truncated:
        warnings.append(
            PipelineWarning(
                code=TEXT_TRUNCATED,
                stage=Stage.MERGE,
                message=f"{truncated} đoạn dài quá {MAX_TEXT_CHARS} ký tự, đã cắt bớt",
            )
        )

    return Transcript(
        audio=audio,
        models=ModelInfo(asr=asr.model, diarization=diarization.model),
        diarization_status="fallback" if one_speaker else "ok",
        speakers=speakers,
        segments=[
            TranscriptSegment(
                index=i,
                start_sec=p.start,
                end_sec=p.end,
                speaker_label=names[p.label] if p.label is not None else None,
                text=_truncate(p.text) if len(p.text) > MAX_TEXT_CHARS else p.text,
                confidence=p.confidence(),
                flags=[f for f in SegmentFlag if f in flags[i]],
                words=p.words,
            )
            for i, p in enumerate(pieces)
        ],
        warnings=_dedupe(warnings),
    )


def run(ctx: StageContext) -> Transcript:
    pre = ctx.input(Stage.PREPROCESS)
    asr = ctx.input(Stage.ASR)
    diarization = ctx.input(Stage.DIARIZE)
    assert isinstance(pre, PreprocessOutput)
    assert isinstance(asr, AsrOutput)
    assert isinstance(diarization, DiarizeOutput)
    ctx.progress(0.1)
    audio = AudioInfo(
        duration_sec=pre.duration_sec, sample_rate=pre.sample_rate, channels=pre.channels
    )
    return merge(asr, diarization, audio)
