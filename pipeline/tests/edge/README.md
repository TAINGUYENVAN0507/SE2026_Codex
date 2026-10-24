# Edge case của audio (AI-05, AI-15)

Audio được sinh bằng ffmpeg lúc chạy test, không commit file audio.

| File | Stage | Cần | Chạy trên CI |
|---|---|---|---|
| `test_preprocess.py` | `preprocess` | ffmpeg | Có |
| `test_real_vad_asr.py` | `vad`, `asr` thật | `uv sync --extra asr`, GPU CUDA, FLEURS đã tải | Không (marker `model`) |

```bash
uv run pytest tests/edge                                    # preprocess
uv run pytest -m model tests/edge/test_real_vad_asr.py      # VAD + ASR thật
```

## `preprocess`

Định dạng phát được trên trình duyệt (giữ file gốc), codec không phát được (chuyển sang AAC), WebM/Opus từ recorder, WebM thiếu duration trong header (lấy độ dài sau khi decode), duration trong header lệch, stereo 48 kHz. Các lỗi: file quá ngắn (`AUDIO_TOO_SHORT`), quá dài (`AUDIO_TOO_LONG`), bytes ngẫu nhiên, file text đổi đuôi `.mp3`, video không có audio (`AUDIO_INVALID`), file không tồn tại.

## `vad` và `asr` thật

Mọi case dùng clip FLEURS `fleurs-1661-13695736044714235367` (11.2 s, một giọng nam đọc). Kết quả lần chạy dưới đây:
- **Thời gian chạy:** 2026-10-24.
- **Code:** commit `e74ded6` cộng thêm file test này.
- **Phần cứng:** GTX 1650 Ti 4 GB.
- **Phần mềm:** faster-whisper 1.2.1, CTranslate2 4.8.3, `large-v3-turbo` int8_float16, ffmpeg 4.4.

Không có lời nói, nên phải dừng ở VAD trước khi chạy ASR:

| Case | Kết quả |
|---|---|
| Im lặng 10 s | `NO_SPEECH_DETECTED` |
| Ồn trắng 10 s (amplitude 0.1) | `NO_SPEECH_DETECTED` |
| Ồn hồng 10 s (amplitude 0.3) | `NO_SPEECH_DETECTED` |

Lời nói bị làm hỏng. Test kiểm tra có cụm "Trung Quốc" trong text và mọi segment có word timestamp. WER tính bằng `evaluation/wer/edge_wer.py`, cùng normalizer với `run_wer.py`:

| Case | WER | CER | S/D/I |
|---|---|---|---|
| `clean` (gốc) | 0.103 | 0.067 | 2/1/0 |
| `phone_8khz` (lọc 300–3400 Hz, 8 kHz) | 0.103 | 0.067 | 2/1/0 |
| `clipped_plus_20db` (+20 dB, bị clipping) | 0.069 | 0.050 | 1/1/0 |
| `quiet_minus_30db` (−30 dB) | 0.103 | 0.067 | 2/1/0 |
| `stereo_48khz_one_side` (lời chỉ ở kênh trái) | 0.103 | 0.067 | 2/1/0 |
| `silence_20s_both_sides` (20 s lặng trước và sau) | 0.103 | 0.067 | 2/1/0 |
| `pink_noise_snr_5db` | 0.138 | 0.101 | 3/1/0 |
| `pink_noise_snr_0db` (chỉ đo, không kiểm cụm từ khóa) | 0.310 | 0.235 | 8/1/0 |

- SNR tính theo RMS của cả clip, gồm cả phần ngắt nghỉ: lời nói −28.5 dBFS, ồn hồng amplitude 0.05 là −40.4 dBFS. Đo bằng `astats` của ffmpeg.
- Với 20 s lặng hai đầu, VAD bắt đầu từ 20.66 s, segment ASR nằm trong 20.46–30.4 s, không có chữ bịa trong khoảng lặng.
- Tới SNR 5 dB, WER gần như không đổi. Ở 0 dB, WER tăng gấp 3 và có từ sai nghĩa ("kết quả Đuổi mình chưa tới Trung Quốc").
- **Giới hạn:** chỉ có một clip đọc của một người, không đại diện cho cuộc họp thật. Đánh giá theo điều kiện ồn trên bản ghi thật là việc của AI-12 (cần SH-01).

Chạy lại bảng WER:

```bash
cd pipeline
EDGE_HYP_OUT=/tmp/edge.jsonl uv run pytest -m model tests/edge/test_real_vad_asr.py
cd ../evaluation && uv run python wer/edge_wer.py /tmp/edge.jsonl
```
