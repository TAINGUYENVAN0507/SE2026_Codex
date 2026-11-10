"""Kiểm tra oracle phân vị của thực nghiệm hiệu năng VT-017."""

import pytest

from scripts.run_load_test import percentile


@pytest.mark.parametrize("probability, expected", [(0.5, 50), (0.95, 95), (0.99, 99)])
def test_nearest_rank_100_samples(probability, expected):
    """TC27: Bắt sai lệch một vị trí khi lấy phân vị trên đúng 100 mẫu."""
    assert percentile(list(reversed(range(1, 101))), probability) == expected


@pytest.mark.parametrize("values, probability", [([], 0.95), ([1], 0), ([1], 1.1)])
def test_invalid_percentile_input_is_rejected(values, probability):
    """TC28: Không công bố một phân vị khi dữ liệu hoặc xác suất không hợp lệ."""
    with pytest.raises(ValueError):
        percentile(values, probability)
