# Bộ đánh giá ồn (AI-12)

ASR chịu được nhiễu tới mức nào. Phần **synthetic** tự sinh từ clip FLEURS. Phần **thu thật** (quạt hoặc điều hòa, quán cà phê, micro laptop đặt xa, điện thoại) chờ buổi ghi âm SH-01. Hai phần được tách bằng cột `source` trong `per_condition.csv`.

| File | Việc |
|---|---|
| `conditions.yaml` | Danh sách điều kiện và seed |
| `make_noisy.py` | Áp điều kiện lên một clip; cùng seed thì ra cùng byte |
| `run_noisy.py` | `transcribe`: tạo bộ ồn, chạy VAD và ASR như pipeline. `score`: chấm WER theo điều kiện |
| `runs/<tag>/` | `hyp.jsonl` (text của ASR trên FLEURS, dữ liệu công khai) và `meta.json` |
| `results/<ngày>_<tag>/` | `per_condition.csv`, `report.md`, `env.json`. Không chứa text |

```bash
cd pipeline     # môi trường có faster-whisper
uv run python ../evaluation/noisy_audio/run_noisy.py transcribe --clips 10 --tag turbo-int8-float16
cd ../evaluation
uv run python noisy_audio/run_noisy.py score noisy_audio/runs/turbo-int8-float16
```

Cách đo:
- **SNR** tính trên chính tín hiệu (công suất trung bình trên toàn clip) và được đo lại sau khi trộn (cột `snr_measured_db`).
- **Vọng** dùng impulse response tổng hợp, có RT60 và DRR (tỉ lệ năng lượng trực tiếp / vọng) đặt tường minh.
- **Đường chạy** giống pipeline: VAD từ chối thì tính như pipeline báo `NO_SPEECH_DETECTED`; ASR xong thì qua `normalize_segments` và `filter_hallucinations`.

## Kết quả

### `2026-10-25_turbo-int8-float16` (synthetic)

- **ASR:** `large-v3-turbo` int8_float16 trên GTX 1650 Ti.
- **Dữ liệu:** 10 clip FLEURS đầu tiên của manifest, 120.5 s audio, 333 từ tham chiếu. Babble lấy từ 8 clip FLEURS khác.
- **Seed:** 2026.

| Điều kiện | WER | Δ so với clean |
|---|---|---|
| `clean` | 0.033 | |
| Ồn hồng SNR 20 / 10 / 5 / 0 dB | 0.054 / 0.078 / 0.105 / 0.222 | +0.021 / +0.045 / +0.072 / +0.189 |
| Ồn trắng SNR 20 / 10 / 5 / 0 dB | 0.063 / 0.090 / 0.141 / 0.345 | +0.030 / +0.057 / +0.108 / +0.312 |
| Ồn nâu (quạt) SNR 10 dB | 0.045 | +0.012 |
| Babble 4 giọng SNR 10 / 5 dB | 0.054 / 0.204 | +0.021 / +0.171 |
| Vọng RT60 0.4 s DRR 3 dB / 0.8 s DRR 0 dB | 0.054 / 0.108 | +0.021 / +0.075 |
| Micro đặt xa (lọc 4 kHz, vọng, DRR −3 dB, −15 dB) | 0.195 | +0.162 |
| Opus 16 kbps | 0.057 | +0.024 |

Không có file nào bị VAD từ chối, kể cả ở SNR 0 dB. Bảng đầy đủ (CER, SNR đo lại) nằm trong `results/2026-10-25_turbo-int8-float16/report.md`.

**Nhận xét:**
- Ba điều kiện làm ASR kém nhất:
  - ồn trắng hoặc hồng ở SNR 0 dB;
  - babble ở SNR 5 dB (người nói chen phía sau nghe như lời thật);
  - micro đặt xa.
- **Micro đặt xa giống cách dùng thật nhất** (laptop giữa bàn), và WER tăng gấp khoảng 6 lần. Đây là điều kiện cần đo trên bản ghi thật đầu tiên.
- Nén Opus 16 kbps (WebM từ trình duyệt) và ồn tần thấp gần như không ảnh hưởng.

**Giới hạn:**
- Mẫu nhỏ: 333 từ, nên mỗi từ sai là 0.3 điểm WER. Chênh lệch dưới khoảng 0.03 (khoảng 10 từ) chưa đủ để kết luận điều kiện nào tốt hơn.
- Giọng đọc, mỗi clip một người, không có nói chồng. Không đại diện cho cuộc họp thật.
- Vọng là tổng hợp, không phải đo trong phòng thật.
