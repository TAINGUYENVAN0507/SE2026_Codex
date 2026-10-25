# Benchmark hiệu năng pipeline (AI-13)

`bench.py` chạy pipeline thật qua `run_job(backend="real")`, đúng đường worker gọi, rồi ghi:
- thời gian từng stage và RTF (thời gian / thời lượng audio);
- RSS đỉnh của subprocess từng stage, cộng cả process con;
- VRAM đỉnh lấy từ `nvidia-smi`.

Cách chạy và định nghĩa từng cột: xem docstring đầu file `bench.py`.

```bash
cd pipeline   # môi trường của pipeline: uv sync --extra asr --extra diarize
uv run python ../evaluation/performance/bench.py --minutes 1 5 --tag gtx1650ti-cpu-diarize
```

Audio được ghép từ clip FLEURS (`datasets/raw/fleurs_vi_test_audio/test/`) theo thứ tự tên file. Mỗi clip là một người đọc khác nhau, nên số speaker cao hơn cuộc họp thật. Bộ này đo **tốc độ**, không đo chất lượng.

## Kết quả

### `2026-10-24_gtx1650ti-cpu-diarize`

**Máy chạy:**
- CPU: i7-10750H (12 luồng), RAM 15 GB.
- GPU: GTX 1650 Ti 4 GB.
- Phần mềm: faster-whisper 1.2.1 với `large-v3-turbo` int8_float16 trên GPU; pyannote.audio 4.0.7 với torch 2.14.1+cpu.
- Tóm tắt: `LLM_PROVIDER` không đặt, nên `disabled`.

Lần chạy dùng code của commit chứa thư mục này (`git.dirty=true` trong `env.json` vì lúc chạy `bench.py` chưa được commit).

| Audio | preprocess | vad | asr | diarize | merge | summarize | Tổng | RTF tổng |
|---|---|---|---|---|---|---|---|---|
| 1' | 0.7 s | 1.5 s | 11.0 s | 44.7 s | 0.6 s | 0.3 s | 58.8 s | 0.98 |
| 5' | 0.4 s | 1.1 s | 27.6 s | 213.2 s | 0.4 s | 0.3 s | 243.0 s | 0.81 |

| Audio | RSS đỉnh asr | VRAM đỉnh asr | RSS đỉnh diarize |
|---|---|---|---|
| 1' | 1821 MB | 1254 MB | 2235 MB |
| 5' | 1801 MB | 1252 MB | 2278 MB |

**Nhận xét:**
- **Diarization trên CPU chiếm 76–88 % tổng thời gian** (RTF 0.71–0.75), khớp với số đo AI-07 (khoảng 0.77). Ngoại suy tuyến tính, audio 60' mất khoảng 43' chỉ riêng diarize, vượt mục tiêu 30' (S6 của kế hoạch). Cần torch GPU cho pyannote (AI-16). Chưa đo trên GPU vì 4 GB VRAM phải chia với ASR.
- ASR có RTF 0.18 ở 1' và 0.09 ở 5'. Số này gồm cả thời gian nạp model, nên audio càng dài thì RTF càng thấp. VRAM đỉnh 1.25 GB, còn dư so với 4 GB.
- Stage ngắn hơn chu kỳ lấy mẫu 0.5 s (preprocess, merge, summarize) có thể không có số RSS, hoặc số thấp hơn thực tế.
- Lúc chạy máy không bị nghẽn: IO PSI avg60 khoảng 13 % trước lần 1', dưới 6 % ở các lúc đo sau (xem `pressure` trong `env.json`). Trước đó trong ngày, IO PSI từng lên khoảng 75 % (trình duyệt đang swap); `bench.py` ghi PSI để phân biệt được lần đo nào bị ảnh hưởng.

### `2026-10-25_i7-10750h-cpu-only`

Cùng máy, cùng audio 1'. ASR chạy trên CPU: `ASR_DEVICE=cpu`, `ASR_COMPUTE_TYPE=int8`, giống image worker bản CPU (AI-16).

| Audio | preprocess | vad | asr | diarize | merge | summarize | Tổng | RTF tổng | RSS đỉnh |
|---|---|---|---|---|---|---|---|---|---|
| 1' | 0.4 s | 0.9 s | 55.6 s | 59.3 s | 0.4 s | 0.3 s | 116.9 s | 1.95 | 2219 MB |

- ASR trên CPU có RTF 0.93, chậm khoảng 5 lần so với GPU (0.18 ở lần đo 1' bên trên). Cả hai số đều gồm thời gian nạp model.
- Diarize của cùng audio mất 59.3 s ở lần này và 44.7 s ở lần trước. Đây là dao động giữa các lần chạy trên laptop; cần chạy lặp lại để có khoảng tin cậy.
- IO PSI avg60 là 1 % trước khi chạy và 7.7 % sau khi chạy.

**Chưa đo:**
- 15', 30', 60' (cần chạy khi có torch GPU, hoặc chấp nhận khoảng 45' cho mỗi lần 60').
- Audio họp thật (cần SH-01).
- Tỉ lệ job thành công trên nhiều lần chạy.
