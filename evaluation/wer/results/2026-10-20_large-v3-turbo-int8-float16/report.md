# Kết quả WER: large-v3-turbo-int8-float16

> Sinh tự động bởi `wer/make_report.py` từ `summary.json`, `per_sample.csv` và `env.json` trong cùng thư mục. Không sửa tay.

## Kết quả theo loại dữ liệu

| Loại | Sample | Thiếu hyp | Token ref | S | D | I | WER | WER TB mỗi sample | CER | WER không dấu |
|---|---|---|---|---|---|---|---|---|---|---|
| `read_speech` | 40 | 0 | 1322 | 79 | 4 | 5 | 6.66 % | 7.04 % | 3.26 % | 5.45 % |

- WER cấp corpus: tổng số lỗi chia cho tổng số token của reference. WER TB mỗi sample chỉ để tham khảo.
- WER không dấu chỉ dùng để chẩn đoán lỗi thanh điệu, không thay cho WER.
- Quy tắc chuẩn hóa: `normalizer/RULES.md`.
- `read_speech` là giọng đọc (FLEURS, Common Voice, VIVOS), không đại diện cho hội thoại cuộc họp. Các loại dữ liệu được báo cáo riêng, không cộng gộp.

## 10 sample nhiều lỗi nhất

| id | Loại | Token ref | Lỗi | WER |
|---|---|---|---|---|
| `fleurs-1835-12248278775709569896` | `read_speech` | 39 | 9 | 23.08 % |
| `fleurs-1865-10684685439757401963` | `read_speech` | 29 | 9 | 31.03 % |
| `fleurs-1824-5714031489489416595` | `read_speech` | 45 | 6 | 13.33 % |
| `fleurs-1924-4982844084427427570` | `read_speech` | 45 | 6 | 13.33 % |
| `fleurs-1877-13530171061020944210` | `read_speech` | 42 | 4 | 9.52 % |
| `fleurs-1993-4866221185440118393` | `read_speech` | 24 | 4 | 16.67 % |
| `fleurs-1661-13695736044714235367` | `read_speech` | 29 | 3 | 10.34 % |
| `fleurs-1721-12740622559749389835` | `read_speech` | 32 | 3 | 9.38 % |
| `fleurs-1810-1620655904537315737` | `read_speech` | 23 | 3 | 13.04 % |
| `fleurs-1853-4608094309958540492` | `read_speech` | 20 | 3 | 15.00 % |

## Môi trường

| | |
|---|---|
| Thời điểm chạy | 2026-10-20T14:06:26Z |
| Git | `3f0edb89d7d5` |
| Normalizer | `b5db08c5fab9` |
| jiwer | 4.0.0 |
| Input `manifest` | `evaluation/datasets/manifest.csv` (sha256 `d6dc0d4b65e0`) |
| Input `hyp` | `evaluation/spikes/asr/runs/large-v3-turbo-int8-float16/hyp.jsonl` (sha256 `48ccc9194379`) |
| ASR `model` | large-v3-turbo |
| ASR `compute_type` | int8_float16 |
| ASR `device` | cuda |
| ASR `gpu` | NVIDIA GeForce GTX 1650 Ti, 4096 MiB, 580.178.04 |
| ASR `params` | {"beam_size": 5, "vad_filter": true, "condition_on_previous_text": false, "language": "vi", "no_speech_threshold": 0.6, "compression_ratio_threshold": 2.4, "log_prob_threshold": -1.0} |
| ASR `faster_whisper` | 1.2.1 |
| ASR `ctranslate2` | 4.8.3 |
| ASR `python` | 3.13.9 |
| ASR `samples` | 40 |
| ASR `errors` | 0 |
| ASR `audio_sec` | 537.36 |
| ASR `proc_sec` | 71.735 |
| ASR `rtf` | 0.1335 |
| ASR `model_load_sec` | 9.203 |
| ASR `vram_peak_mib` | 1255 |

## Chạy lại

```bash
cd evaluation
uv run python wer/run_wer.py --hyp spikes/asr/runs/large-v3-turbo-int8-float16/hyp.jsonl --tag large-v3-turbo-int8-float16 --source fleurs
```

Bảng Môi trường ghi đường dẫn tính từ gốc repo, lệnh trên tính từ `evaluation/`. File nằm ngoài repo chỉ được ghi tên. Kiểm tra sha256 trước khi so sánh hai lần chạy.
