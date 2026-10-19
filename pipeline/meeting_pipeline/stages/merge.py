"""Stage merge (AI-08): ghép output ASR với diarization thành transcript có speaker.

Gán speaker cho từng word theo phần overlap lớn nhất với các turn của diarization.
Word rơi vào khoảng lặng giữa các turn (timestamp của ASR thường lệch vài trăm ms)
lấy speaker của word gần nhất trong cùng segment ASR. Cả segment ASR không chạm turn
nào thì speaker là null: người dùng gán tay trên UI.

Mọi hàm ở đây là pure function và deterministic: không đọc môi trường, không gọi model.
"""

from __future__ import annotations

import bisect
from collections import Counter
from collections.abc import Sequence
from itertools import accumulate

from meeting_pipeline.schemas import SpeakerTurn, Word


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
