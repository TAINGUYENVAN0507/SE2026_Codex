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

## Chấm WER cho một lần chạy ASR

```bash
uv run python wer/run_wer.py --hyp hyp.jsonl --tag whisper-small-int8 --asr-meta meta.json
```

`hyp.jsonl` có mỗi dòng `{"id": "<id trong manifest>", "text": "..."}`. Kết quả (`per_sample.csv`, `summary.json`, `env.json`, `report.md`) nằm ở `wer/results/<ngày>_<tag>/`. Định nghĩa metric và quy tắc báo cáo ở `wer/README.md`.

## Cấu trúc

| Thư mục | Nội dung | Task |
|---|---|---|
| `datasets/` | Manifest, license, quy ước gán nhãn, mẫu consent, script tải dữ liệu | AI-10, SH-01, SH-02 |
| `normalizer/` | Chuẩn hóa text tiếng Việt trước khi tính WER | AI-11 |
| `wer/` | Chấm WER, CER, WER không dấu cho một lần chạy ASR, sinh report | AI-11 |
| `spikes/asr/` | Spike chọn cấu hình ASR: chạy faster-whisper trên manifest, đo RTF và VRAM | AI-01 |
| `spikes/diarization/` | Spike diarization (chưa có) | AI-02 |
| `noisy_audio/`, `diarization/`, `performance/`, `summary_rubric/` | Các bộ đánh giá còn lại | AI-12 đến AI-14 |

Thư mục nào chưa có nghĩa là task đó chưa bắt đầu.
