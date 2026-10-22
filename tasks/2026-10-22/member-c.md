# 2026-10-22 · Member C: pipeline, evaluation, nhóm trưởng

- **Người làm:** C (`@TAINGUYENVAN0507`), nhánh `tainguyen`.
- **Số commit:** 5.
- **Trạng thái:** đã xong 5 commit. Pipeline M2 chạy thật từ preprocess tới transcript; diarization trên CPU là nút cổ chai (`docs/pipeline/AI-07.md`).
- **Mục tiêu:** diarization thật bằng pyannote `community-1` (AI-07). Sau AI-07, phần pipeline cho M2 (`preprocess → vad → asr → diarize → merge`) chạy thật hết. Thêm bộ chấm DER (AI-13) để sẵn sàng khi có RTTM của SH-02.

Đọc trước: `pipeline/README.md`, `pipeline/meeting_pipeline/engines/`, mục AI-07 và AI-13 của kế hoạch.

Lệnh kiểm tra cho mọi commit:

```bash
cd pipeline && uv run ruff check . && uv run ruff format --check . && uv run pytest -m "not model"
cd evaluation && uv run ruff check . && uv run ruff format --check . && uv run pytest
```

## 5 commit

### 1. [x] Adapter diarization: pyannote và bản fake (AI-07)

- **Việc:** `engines/` thêm interface `DiarizeEngine`, `PyannoteDiarizer` (import trong hàm, đọc `audio.wav` thành waveform rồi đưa vào pipeline, không để pyannote tự decode file; truyền gợi ý `num_speakers`; token lấy từ `HF_TOKEN` hoặc HF cache) và `FakeDiarizer`. Model gated hoặc thiếu token là lỗi permanent `MODEL_UNAVAILABLE`, OOM là lỗi transient.
- **Xong khi:** unit test với pipeline giả: chuyển đổi turn, map lỗi, thông điệp lỗi không lộ token.
- **Message:** `feat(pipeline): diarization engine adapter with pyannote and fake (AI-07)`
- **Hash:** `f7ec2b1`

### 2. [x] Stage `diarize` thật (AI-07)

- **Việc:** `stages/diarize.py`: gọi engine, chuẩn hóa turn (clamp, làm tròn ms, bỏ turn rỗng, sắp xếp), đổi nhãn sang dạng `SPEAKER_00`, ghi `diarization.json` và `diarization.rttm`. Lỗi thì runner đã có cơ chế fallback 1 speaker.
- **Xong khi:** test với engine giả: output hợp lệ, RTTM đúng định dạng `SPEAKER <id> 1 <start> <dur> <NA> <NA> <spk> <NA> <NA>`, `num_speakers` khớp số nhãn, có test cho lỗi.
- **Message:** `feat(pipeline): real diarize stage with RTTM output (AI-07)`
- **Hash:** `9808ef3`

### 3. [x] Extra `diarize` và test với model thật (AI-07)

- **Việc:** extra `diarize` gồm pyannote.audio 4.x và torch bản CPU (index của PyTorch; bản GPU để dành cho Docker ở AI-16). Test `@pytest.mark.model` chạy pyannote thật trên audio ghép từ 2 clip FLEURS.
- **Xong khi:** test model thật pass. Chạy CLI `preprocess → vad → asr → diarize → merge` thật ra `transcript.json` hợp lệ.
- **Message:** `feat(pipeline): diarize extra with CPU torch and a real-model test (AI-07)`
- **Hash:** `4fef9d0`

### 4. [x] Bộ chấm DER (AI-13)

- **Việc:** `evaluation/diarization/run_der.py`: đọc RTTM tham chiếu theo `rttm_path` trong manifest và RTTM của hệ thống, tính DER bằng pyannote.metrics (collar 0.25 s) cả khi bỏ qua và khi tính vùng nói chồng, kèm sai số về số speaker; ghi `results/<ngày>_<tag>/` theo cùng quy tắc với `wer/` (`env.json`, không chứa text).
- **Xong khi:** test với RTTM tự viết có DER biết trước.
- **Message:** `feat(eval): run_der.py scores diarization against reference RTTM (AI-13)`
- **Hash:** `bf96999`

### 5. [x] Test pipeline thật qua `run_job()` tới transcript (AI-04, AI-07)

- **Việc:** test `@pytest.mark.model` gọi `run_job(backend="real")` trên audio ghép, chạy từ `preprocess` tới `merge`; `summarize` chưa có nên phải báo `STAGE_NOT_IMPLEMENTED` sau khi `transcript.json` đã được ghi và `on_stage_done(merge)` đã được gọi. Ghi thời gian từng stage vào `docs/pipeline/AI-07.md`.
- **Xong khi:** test pass trên máy C; tài liệu có số đo thật kèm lệnh chạy lại.
- **Message:** `test(pipeline): real run_job from preprocess to transcript (AI-04, AI-07)`
- **Hash:** `2444100`

## Việc của nhóm trưởng (không phải commit)

- [ ] Review và merge PR của A và B hôm nay.
- [ ] SH-01: tổ chức buổi ghi âm pilot (vẫn chưa có). Đây là việc chặn AI-02 và việc chốt G1.
