# 2026-10-24 · Member C: pipeline, evaluation, nhóm trưởng

- **Người làm:** C (`@TAINGUYENVAN0507`), nhánh `tainguyen`.
- **Số commit:** 5.
- **Trạng thái:** đã xong 5 commit. AI-04 merge sớm qua PR #22 (`dbfb2b0`) để B dùng. Benchmark: diarize trên CPU chiếm 76–88 % thời gian (`evaluation/performance/README.md`).
- **Mục tiêu:**
  - Bổ sung cho `run_job()` hai thứ worker cần: heartbeat trong lúc stage chạy, và hủy stage đang chạy (AI-04). Commit 1 của B hôm nay phụ thuộc phần này, nên **merge PR này trước**.
  - Edge case qua VAD/ASR thật (AI-15).
  - Bộ benchmark hiệu năng (AI-13).
  - Rubric chấm tóm tắt (AI-14), để A và B chấm khi có dữ liệu họp.

Đọc trước:
- `pipeline/meeting_pipeline/runner.py`.
- Mục AI-04, AI-13, AI-14, AI-15 và mục 10.4 (RT-09, RT-15) của kế hoạch.
- `evaluation/README.md`: quy tắc `results/` và `env.json`, không ghi số ước lượng.

Lệnh kiểm tra cho mọi commit:

```bash
cd pipeline && uv run ruff check . && uv run ruff format --check . && uv run pytest -m "not model"
uv run python -m meeting_pipeline export-contracts --check
cd ../evaluation && uv run ruff check . && uv run ruff format --check . && uv run pytest
```

## 5 commit

### 1. [x] Callback `on_heartbeat` trong lúc stage chạy (AI-04)

- **Việc:**
  - `run_job(..., on_heartbeat=..., heartbeat_sec=15)` gọi `on_heartbeat()` ngay khi bắt đầu, sau đó ít nhất mỗi `heartbeat_sec`. Callback vẫn được gọi khi một stage chạy nhiều phút mà không báo progress.
  - Callback chạy trên thread của người gọi `run_job()`, như các callback khác, nên worker dùng được session DB của mình.
  - Callback ném lỗi thì kill stage đang chạy, không để process mồ côi.
- **Xong khi:** test:
  - stage fake ngủ 3 s, `heartbeat_sec=0.5` thì callback được gọi ít nhất 5 lần;
  - callback ném lỗi thì process group bị kill;
  - stage được bỏ qua nhờ checkpoint vẫn có heartbeat.
- **Message:** `feat(pipeline): heartbeat callback while stages run (AI-04)`
- **Hash:** `d8efb0c`

### 2. [x] Hủy stage đang chạy (AI-04)

- **Việc:**
  - `is_cancelled()` giờ được kiểm cả trong lúc stage chạy (tối đa mỗi giây một lần), không chỉ giữa các stage.
  - Bị hủy thì kill cả process group, raise `PipelineCancelledError(stage)`.
  - Không để lại artifact dở dang. Lần chạy sau làm lại stage đó từ đầu.
- **Xong khi:** test: hủy giữa stage thì kết thúc trong khoảng 1 s, không có artifact của stage đó, `on_stage_done` không được gọi; chạy lại cùng workdir thì tiếp tục từ checkpoint (RT-15).
- **Message:** `feat(pipeline): cancel a running stage within a second (AI-04)`
- **Hash:** `e74ded6`

### 3. [x] Edge case qua VAD và ASR thật (AI-15)

- **Việc:** test `@pytest.mark.model` chạy `vad` và `asr` thật trên audio sinh bằng ffmpeg và clip FLEURS:
  - im lặng 10 s và tiếng ồn trắng 10 s thì `NO_SPEECH_DETECTED`;
  - lời nói lấy mẫu 8 kHz (kiểu điện thoại) và lời nói bị clipping vẫn ra text;
  - lời nói chen giữa hai khoảng im lặng dài thì timestamp vẫn nằm trong khoảng nói.
  - Ghi kết quả từng case vào `pipeline/tests/edge/README.md`.
- **Xong khi:** mỗi case có output hoặc mã lỗi mong đợi; test model pass trên máy GPU.
- **Message:** `test(pipeline): edge cases through real VAD and ASR (AI-15)`
- **Hash:** `a21147f`

### 4. [x] Bộ benchmark hiệu năng (AI-13)

- **Việc:**
  - `evaluation/performance/bench.py` chạy `run_job(backend="real")` trên audio có thời lượng cho trước, ghép từ clip FLEURS.
  - Ghi: thời gian từng stage, RTF, RAM đỉnh của subprocess, VRAM đỉnh (đọc từ `nvidia-smi` nếu có), job thành công hay không.
  - Kết quả vào `evaluation/performance/results/<ngày>_<tag>/` (`bench.csv`, `env.json`), không chứa text.
  - Chạy thật với audio 1' và 5'. Chạy 15/30/60' sau khi có torch GPU (AI-16).
- **Xong khi:** test đơn vị cho phần ghép audio và tính RTF; có kết quả chạy thật 1' và 5'.
- **Message:** `feat(eval): pipeline benchmark with per-stage time, RTF and peak memory (AI-13)`
- **Hash:** `9e9839e`

### 5. [x] Rubric chấm tóm tắt và độ đồng thuận (AI-14)

- **Việc:**
  - `evaluation/summary_rubric/rubric.md`: các tiêu chí điểm 1–5 (đầy đủ, đúng sự thật/không bịa, quyết định, action item gồm người nhận và hạn, evidence, tiếng Việt), mỗi mức có mô tả và ví dụ.
  - `ratings.csv` mẫu.
  - `agreement.py`: tính tỉ lệ trùng điểm, tỉ lệ lệch không quá 1 điểm và độ lệch trung bình theo từng tiêu chí, xuất `report.md`.
- **Xong khi:** test với 2 bộ điểm tự tạo có kết quả tính tay.
- **Message:** `feat(eval): summary rubric and rater agreement report (AI-14)`
- **Hash:** `127718d`

## Việc của nhóm trưởng (không phải commit)

- [x] Review và merge PR của A (#19) và B (#20) từ hôm qua. PR của hôm nay: chờ A và B mở.
- [ ] SH-01: tổ chức buổi ghi âm pilot (vẫn chưa có). AI-12, AI-14 và phần dữ liệu họp của AI-13 đang chờ dữ liệu này.
- [ ] Quyết định cho nhóm: có dùng Claude API với audio họp thật không (cần consent theo phiếu) và ngân sách API.
