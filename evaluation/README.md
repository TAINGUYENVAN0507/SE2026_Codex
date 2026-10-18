# evaluation

Dữ liệu và công cụ đánh giá chất lượng AI. Owner: member C. A và B cùng gõ transcript tham chiếu, gán nhãn speaker và chấm rubric.

> Mọi số liệu trong thư mục này phải đến từ một lần chạy thật, kèm script để chạy lại và `env.json` ghi model, tham số, phần cứng, git SHA. Không ghi số ước lượng.

## Cài đặt và chạy test

```bash
cd evaluation
uv sync
uv run pytest
```

## Chuẩn hóa text cho WER

```python
import sys

sys.path.insert(0, "evaluation/normalizer")
from vi_normalize import normalize, strip_diacritics

normalize("Hoà chốt 25% lúc 9h30, ờ, ngày 15/10.")
# 'hòa chốt hai mươi lăm phần trăm lúc chín giờ ba mươi ngày mười lăm tháng mười'
```

Quy tắc đầy đủ và các giới hạn đã biết nằm ở `normalizer/RULES.md`.

## Cấu trúc

| Thư mục | Nội dung | Task |
|---|---|---|
| `datasets/` | Manifest, license, quy ước gán nhãn, mẫu consent, script tải dữ liệu | AI-10, SH-01, SH-02 |
| `normalizer/` | Chuẩn hóa text tiếng Việt trước khi tính WER | AI-11 |
| `spikes/` | Thử nghiệm chọn model ASR và diarization | AI-01, AI-02 |
| `wer/`, `noisy_audio/`, `diarization/`, `performance/`, `summary_rubric/` | Các bộ đánh giá | AI-11 đến AI-14 |

Thư mục nào chưa có nghĩa là task đó chưa bắt đầu.
