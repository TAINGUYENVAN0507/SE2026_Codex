# Kết quả WER: medium-int8

> Sinh tự động bởi `wer/make_report.py` từ `summary.json`, `per_sample.csv` và `env.json` trong cùng thư mục. Không sửa tay.

## Kết quả theo loại dữ liệu

| Loại | Sample | Thiếu hyp | Token ref | S | D | I | WER | WER TB mỗi sample | CER | WER không dấu |
|---|---|---|---|---|---|---|---|---|---|---|
| `read_speech` | 40 | 0 | 1322 | 115 | 4 | 6 | 9.46 % | 9.93 % | 4.58 % | 7.87 % |

- WER cấp corpus: tổng số lỗi chia cho tổng số token của reference. WER TB mỗi sample chỉ để tham khảo.
- WER không dấu chỉ dùng để chẩn đoán lỗi thanh điệu, không thay cho WER.
- Quy tắc chuẩn hóa: `normalizer/RULES.md`.
- `read_speech` là giọng đọc (FLEURS, Common Voice, VIVOS), không đại diện cho hội thoại cuộc họp. Các loại dữ liệu được báo cáo riêng, không cộng gộp.

## 10 sample nhiều lỗi nhất

| id | Loại | Token ref | Lỗi | WER |
|---|---|---|---|---|
| `fleurs-1835-12248278775709569896` | `read_speech` | 39 | 15 | 38.46 % |
| `fleurs-1824-5714031489489416595` | `read_speech` | 45 | 9 | 20.00 % |
| `fleurs-1810-1620655904537315737` | `read_speech` | 23 | 7 | 30.43 % |
| `fleurs-1865-10684685439757401963` | `read_speech` | 29 | 7 | 24.14 % |
| `fleurs-1946-3770458745111860265` | `read_speech` | 48 | 6 | 12.50 % |
| `fleurs-1947-13645053621181699022` | `read_speech` | 25 | 6 | 24.00 % |
| `fleurs-1993-4866221185440118393` | `read_speech` | 24 | 6 | 25.00 % |
| `fleurs-1877-13530171061020944210` | `read_speech` | 42 | 5 | 11.90 % |
| `fleurs-1913-6766457086612963634` | `read_speech` | 24 | 5 | 20.83 % |
| `fleurs-1919-8482216785041033031` | `read_speech` | 28 | 5 | 17.86 % |

## Môi trường

| | |
|---|---|
| Thời điểm chạy | 2026-10-20T14:06:25Z |
| Git | `3f0edb89d7d5` |
| Normalizer | `b5db08c5fab9` |
| jiwer | 4.0.0 |
| Input `manifest` | `evaluation/datasets/manifest.csv` (sha256 `d6dc0d4b65e0`) |
| Input `hyp` | `evaluation/spikes/asr/runs/medium-int8/hyp.jsonl` (sha256 `668f79d6cda6`) |
| ASR `model` | medium |
| ASR `compute_type` | int8 |
| ASR `device` | cuda |
| ASR `gpu` | NVIDIA GeForce GTX 1650 Ti, 4096 MiB, 580.178.04 |
| ASR `params` | {"beam_size": 5, "vad_filter": true, "condition_on_previous_text": false, "language": "vi", "no_speech_threshold": 0.6, "compression_ratio_threshold": 2.4, "log_prob_threshold": -1.0} |
| ASR `faster_whisper` | 1.2.1 |
| ASR `ctranslate2` | 4.8.3 |
| ASR `python` | 3.13.9 |
| ASR `samples` | 40 |
| ASR `errors` | 0 |
| ASR `audio_sec` | 537.36 |
| ASR `proc_sec` | 73.473 |
| ASR `rtf` | 0.1367 |
| ASR `model_load_sec` | 2.205 |
| ASR `vram_peak_mib` | 1255 |

## Chạy lại

```bash
cd evaluation
uv run python wer/run_wer.py --hyp spikes/asr/runs/medium-int8/hyp.jsonl --tag medium-int8 --source fleurs
```

Bảng Môi trường ghi đường dẫn tính từ gốc repo, lệnh trên tính từ `evaluation/`. File nằm ngoài repo chỉ được ghi tên. Kiểm tra sha256 trước khi so sánh hai lần chạy.
