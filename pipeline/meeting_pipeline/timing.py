"""Tiện ích thời gian dùng chung cho các stage: clamp, làm tròn ms, bảo đảm start < end."""

from __future__ import annotations


def clamp(value: float, duration: float) -> float:
    """Đưa `value` vào `[0, duration]`."""
    return min(max(value, 0.0), duration)


def span_within(start: float, end: float, duration: float) -> tuple[float, float]:
    """Clamp vào `[0, duration]`, làm tròn ms và bảo đảm `start < end`.

    Khoảng dài 0 (ASR đôi khi trả về) được nới thành 1 ms, lùi về trước nếu chạm cuối audio.
    """
    duration = round(duration, 3)
    start = round(clamp(start, duration), 3)
    end = round(min(max(end, start), duration), 3)
    if end <= start:
        if round(start + 0.001, 3) <= duration:
            end = round(start + 0.001, 3)
        else:
            start, end = round(duration - 0.001, 3), duration
    return start, end
