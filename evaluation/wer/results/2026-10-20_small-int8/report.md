# Kết quả WER: small-int8

> Sinh tự động bởi `wer/make_report.py` từ `summary.json`, `per_sample.csv` và `env.json` trong cùng thư mục. Không sửa tay.

## Kết quả theo loại dữ liệu

| Loại | Sample | Thiếu hyp | Token ref | S | D | I | WER | WER TB mỗi sample | CER | WER không dấu |
|---|---|---|---|---|---|---|---|---|---|---|
| `read_speech` | 40 | 0 | 1322 | 230 | 8 | 16 | 19.21 % | 20.21 % | 8.75 % | 15.88 % |

- WER cấp corpus: tổng số lỗi chia cho tổng số token của reference. WER TB mỗi sample chỉ để tham khảo.
- WER không dấu chỉ dùng để chẩn đoán lỗi thanh điệu, không thay cho WER.
- Quy tắc chuẩn hóa: `normalizer/RULES.md`.
- `read_speech` là giọng đọc (FLEURS, Common Voice, VIVOS), không đại diện cho hội thoại cuộc họp. Các loại dữ liệu được báo cáo riêng, không cộng gộp.

## 10 sample nhiều lỗi nhất

| id | Loại | Token ref | Lỗi | WER |
|---|---|---|---|---|
| `fleurs-1835-12248278775709569896` | `read_speech` | 39 | 19 | 48.72 % |
| `fleurs-1824-5714031489489416595` | `read_speech` | 45 | 17 | 37.78 % |
| `fleurs-1865-10684685439757401963` | `read_speech` | 29 | 14 | 48.28 % |
| `fleurs-1896-16804968178539575670` | `read_speech` | 57 | 14 | 24.56 % |
| `fleurs-1913-6766457086612963634` | `read_speech` | 24 | 11 | 45.83 % |
| `fleurs-1924-4982844084427427570` | `read_speech` | 45 | 10 | 22.22 % |
| `fleurs-1946-3770458745111860265` | `read_speech` | 48 | 10 | 20.83 % |
| `fleurs-1993-4866221185440118393` | `read_speech` | 24 | 10 | 41.67 % |
| `fleurs-1702-5552194812226333079` | `read_speech` | 30 | 8 | 26.67 % |
| `fleurs-1810-1620655904537315737` | `read_speech` | 23 | 8 | 34.78 % |

## Môi trường

| | |
|---|---|
| Thời điểm chạy | 2026-10-20T14:06:25Z |
| Git | `3f0edb89d7d5` |
| Normalizer | `b5db08c5fab9` |
| jiwer | 4.0.0 |
| Input `manifest` | `evaluation/datasets/manifest.csv` (sha256 `d6dc0d4b65e0`) |
| Input `hyp` | `evaluation/spikes/asr/runs/small-int8/hyp.jsonl` (sha256 `247487ee05be`) |
| ASR `model` | small |
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
| ASR `proc_sec` | 33.983 |
| ASR `rtf` | 0.0632 |
| ASR `model_load_sec` | 1.052 |
| ASR `vram_peak_mib` | 487 |

## Chạy lại

```bash
cd evaluation
uv run python wer/run_wer.py --hyp spikes/asr/runs/small-int8/hyp.jsonl --tag small-int8 --source fleurs
```

Bảng Môi trường ghi đường dẫn tính từ gốc repo, lệnh trên tính từ `evaluation/`. File nằm ngoài repo chỉ được ghi tên. Kiểm tra sha256 trước khi so sánh hai lần chạy.
