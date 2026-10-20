# Spike ASR (AI-01)

Chọn cấu hình ASR cho Gate G1 bằng số liệu đo thật: WER, CER, RTF, VRAM. Kiểm chứng giả định S1 của kế hoạch: có ít nhất một cấu hình ASR đạt chất lượng chấp nhận được trên tiếng Việt.

## Chạy

```bash
cd evaluation
uv sync --group asr-spike                     # faster-whisper, cuBLAS, cuDNN; CI không cài
uv run python datasets/download.py fleurs_vi_test_audio

uv run python spikes/asr/run_asr.py --model small --compute-type int8 --tag small-int8
uv run python wer/run_wer.py --hyp spikes/asr/runs/small-int8/hyp.jsonl --tag small-int8 \
  --asr-meta spikes/asr/runs/small-int8/meta.json --source fleurs
```

`--limit 3` để thử nhanh, `--device cpu` để chạy trên CPU, `--no-vad` để tắt lọc VAD.

## Kết quả ngày 2026-10-20

40 câu FLEURS `vi_vn` test, GTX 1650 Ti 4 GB. Phân tích và đề xuất ở [`docs/adr/0001-asr.md`](../../../docs/adr/0001-asr.md).

| Cấu hình (`--tag`) | WER | CER | WER không dấu | RTF | Kết quả |
|---|---|---|---|---|---|
| `small-int8` | 19.21 % | 8.75 % | 15.89 % | 0.063 | `wer/results/2026-10-20_small-int8/` |
| `medium-int8` | 9.46 % | 4.58 % | 7.87 % | 0.137 | `wer/results/2026-10-20_medium-int8/` |
| `large-v3-turbo-int8-float16` | 6.66 % | 3.26 % | 5.45 % | 0.134 | `wer/results/2026-10-20_large-v3-turbo-int8-float16/` |

## Cách đo

| Đại lượng | Cách đo |
|---|---|
| WER, CER, WER không dấu | `wer/run_wer.py`, chuẩn hóa theo `normalizer/RULES.md` |
| RTF | Tổng thời gian transcribe chia tổng thời lượng audio. Không tính thời gian load model. |
| Thời gian load model | Đo riêng, ghi trong `meta.json` |
| VRAM đỉnh | `nvidia-smi` mỗi 0.2 s, trừ mức đang dùng trước khi load model. GPU dùng chung với màn hình nên chỉ là xấp xỉ. |

Tham số giải mã giống nhau cho mọi cấu hình: `language="vi"`, `beam_size=5`, lọc VAD (Silero, có sẵn trong faster-whisper), `condition_on_previous_text=False`, các ngưỡng `no_speech`, `compression_ratio`, `log_prob` để mặc định.

## File

| Đường dẫn | Nội dung |
|---|---|
| `run_asr.py` | Chạy một cấu hình, ghi `runs/<tag>/hyp.jsonl` và `meta.json` |
| `runs/<tag>/` | Output của ASR trên FLEURS (dữ liệu public, được commit) |
| `../../wer/results/<ngày>_<tag>/` | Kết quả chấm WER của từng cấu hình |

## Giới hạn

- Dữ liệu là 40 câu FLEURS `vi_vn` test, giọng đọc, toàn giọng nam. WER trên tập này **không đại diện** cho cuộc họp. Cần chạy lại khi có audio họp pilot (SH-01, SH-02).
- Phần cứng: GTX 1650 Ti 4 GB. Whisper large-v3 đầy đủ có thể không vừa VRAM.
- Chưa thử PhoWhisper: cần convert sang CTranslate2 bằng transformers và torch.
- Chưa đánh giá chất lượng timestamps (giả định S2).
