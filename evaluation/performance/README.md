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
- **Diarization trên CPU chiếm 76–88 % tổng thời gian** (RTF 0.71–0.75), khớp với số đo AI-07 (khoảng 0.77). Ngoại suy tuyến tính, audio 60' mất khoảng 43' chỉ riêng diarize, vượt mục tiêu 30' (S6 của kế hoạch). Cần torch GPU cho pyannote (AI-16). Đã đo trên GPU ở mục `2026-10-29_gtx1650ti-gpu-diarize` bên dưới.
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

### `2026-10-29_gtx1650ti-gpu-diarize` và `..._gpu-diarize-60m`

Cùng máy; ASR `large-v3-turbo` int8_float16 trên GPU, **diarization trên GPU** (extra `diarize-gpu`, torch 2.14.1+cu126). Tóm tắt `disabled`.

| Audio | asr | diarize | Tổng | RTF tổng | RSS đỉnh | VRAM đỉnh asr | VRAM đỉnh diarize |
|---|---|---|---|---|---|---|---|
| 5' | 53.4 s | 35.2 s | 93.9 s | 0.313 | 1877 MB | 1252 MB | 2800 MB |
| 15' | 84.7 s | 73.7 s | 162.1 s | 0.180 | 1848 MB | 1254 MB | 2796 MB |
| 30' | 152.0 s | 126.0 s | 283.9 s | 0.158 | 1914 MB | 1254 MB | 2796 MB |
| **60'** | 356.4 s | 240.9 s | **607.9 s (~10 phút)** | **0.169** | 3920 MB | 1254 MB | 2798 MB |

**So với diarization trên CPU (cùng GPU cho ASR):**
- RTF của diarize giảm từ 0.71–0.99 xuống 0.067–0.117 (khoảng 7–10 lần).
- Tổng RTF của job giảm từ 0.81 xuống 0.16–0.17.
- 60' mất 608 s thay vì khoảng 2 giờ.

**Mục tiêu S6 (audio 60' xong trong khoảng 30') đạt theo số đo thật**, không theo ngoại suy: 608 s so với 1800 s.

**Nhận xét:**
- **VRAM:** `nvidia-smi` thấy tiến trình diarize dùng khoảng **2.8 GB** (allocator của torch đo 1.63 GB trong test; phần còn lại là CUDA context và cache). Trên GPU 4 GB còn dư khoảng 1.2 GB, đủ vì `asr` và `diarize` chạy ở hai process khác nhau, lần lượt. Chạy cả hai cùng lúc trên GPU 4 GB sẽ không đủ.
- **RAM:** RSS đỉnh của job 60' là 3.9 GB, ở stage `asr` (30' là 1.9 GB), nên bộ nhớ tăng theo độ dài audio. Máy chạy worker cần ít nhất 4 GB RAM trống cho audio 60'.
- **RTF theo độ dài audio:** ASR 0.178 ở 5', 0.084 ở 30', 0.099 ở 60'. Phần cố định (nạp model) làm RTF cao ở audio ngắn; RTF ở 60' hơi cao hơn 30' (chưa rõ nguyên nhân, có thể do tăng RAM và swap; chỉ có 1 lần đo mỗi độ dài).
- Máy không bị nghẽn khi đo: IO PSI avg60 từ 0.7 % đến 10.5 % (`pressure` trong `env.json`).
- Mỗi độ dài chỉ đo 1 lần, chưa có khoảng tin cậy.

**Chưa đo:**
- 15', 30', 60' với diarization trên CPU (đã có GPU ở trên). 60' trên CPU thuần chưa đo, chỉ ngoại suy khoảng 2 giờ.
- Audio họp thật (cần SH-01).
- Tỉ lệ job thành công trên nhiều lần chạy.
