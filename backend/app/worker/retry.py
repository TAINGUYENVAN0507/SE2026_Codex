"""Chính sách retry và tính toán thời gian backoff cho worker (BE-08).

Quy ước:
- Backoff delays: 30 s -> 2' (120 s) -> 8' (480 s)
- Jitter: ±20% (nhân với hệ số ngẫu nhiên từ 0.8 đến 1.2)
- Tối đa 3 lượt thử (max_attempts = 3)
"""

import random

BACKOFF_DELAYS_SEC = (30, 120, 480)


def compute_backoff_delay(attempt: int, with_jitter: bool = True) -> float:
    """Tính toán thời gian chờ backoff tính theo giây.

    Args:
        attempt: Số lần đã thử (1-indexed). Lần 1 thất bại -> chờ theo mốc 30s.
        with_jitter: Nếu True, áp dụng jitter ngẫu nhiên ±20%.

    Returns:
        Số giây cần chờ trước lần chạy tiếp theo.
    """
    idx = min(max(0, attempt - 1), len(BACKOFF_DELAYS_SEC) - 1)
    base = float(BACKOFF_DELAYS_SEC[idx])
    if with_jitter:
        factor = random.uniform(0.8, 1.2)
        return round(base * factor, 2)
    return base
