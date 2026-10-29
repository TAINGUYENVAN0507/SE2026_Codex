# 2026-10-29 · Member C: pipeline, evaluation, nhóm trưởng

- **Người làm:** C (`@TAINGUYENVAN0507`), nhánh `tainguyen`.
- **Số commit:** 5.
- **Mục tiêu:** đưa diarization lên GPU (AI-16). Diarization trên CPU chiếm 76–88 % thời gian xử lý (RTF 0.71–0.75); ngoại suy cho audio 60' thì riêng bước này mất khoảng 43', vượt mục tiêu 30'. Sau đó benchmark lại (AI-13) và hiệu chỉnh timeout theo số đo.

Đọc trước:
- `docs/pipeline/AI-16.md`, mục "Còn lại".
- `evaluation/performance/README.md`: số đo hiện tại.
- `pipeline/pyproject.toml`: ghi chú vì sao extra `diarize` dùng torch CPU.
- `pipeline/meeting_pipeline/engines/pyannote.py`: `DIARIZATION_DEVICE=auto`.
- `pipeline/meeting_pipeline/runner.py`: `TimeoutPolicy`, ghi "hiệu chỉnh thành 2 × p95 sau benchmark AI-13".
- Mục AI-13, AI-16 và S6 của kế hoạch.

Lệnh kiểm tra cho mọi commit:

```bash
cd pipeline && uv run ruff check . && uv run ruff format --check . && uv run pytest -m "not model"
uv run python -m meeting_pipeline export-contracts --check
cd ../evaluation && uv run ruff check . && uv run ruff format --check . && uv run pytest
```

## Bước 0 (không tính vào số commit)

```bash
git checkout tainguyen
git fetch origin
git merge origin/main
```

## 5 commit

### 1. [ ] Extra `diarize-gpu` với torch CUDA 12 (AI-16)

- **Việc:**
  - Thêm extra `diarize-gpu`: pyannote.audio cùng torch và torchaudio từ index CUDA 12 của PyTorch (`[[tool.uv.index]]` explicit).
  - Khai báo xung đột với extra `diarize` (`[tool.uv] conflicts`).
  - Torch CUDA 12 và CTranslate2 (extra `asr`) phải dùng chung **một** bản `nvidia-cudnn-cu12` 9.x và `nvidia-cublas-cu12`: kiểm trong `uv.lock`.
  - Lỗi cũ là torch trên PyPI kèm CUDA 13 và cuDNN cho CUDA 13, ghi đè thư viện mà CTranslate2 cần.
- **Xong khi:** `uv sync --extra asr --extra diarize-gpu` cài được; trong cùng venv, cả `ctranslate2.get_cuda_device_count()` và `torch.cuda.is_available()` đều thấy GPU; CI (không cài extra) vẫn xanh.
- **Message:** `feat(pipeline): diarize-gpu extra with CUDA 12 torch sharing cuDNN with CTranslate2 (AI-16)`
- **Hash:**

### 2. [ ] Test diarization thật trên GPU, đo VRAM (AI-07, AI-16)

- **Việc:**
  - Test `@pytest.mark.model` chạy stage `diarize` trên GPU (`DIARIZATION_DEVICE=auto`) với audio ghép 2 giọng FLEURS có sẵn trong `tests/model/conftest.py`.
  - Kết quả phải giống bản CPU: 2 speaker, ranh giới đúng.
  - Ghi VRAM đỉnh (máy demo có 4 GB, ASR chạy ở stage khác nên không cộng dồn).
  - GPU hết bộ nhớ thì lỗi transient như ASR; ở lượt cuối thì runner fallback 1 speaker như hiện tại.
- **Xong khi:** test model pass trên GPU; số VRAM ghi vào `docs/pipeline/AI-16.md`.
- **Message:** `test(pipeline): real diarization on GPU with peak VRAM (AI-07, AI-16)`
- **Hash:**

### 3. [ ] Image worker bản CUDA dùng diarization GPU (AI-16)

- **Việc:**
  - `worker.Dockerfile` với `VARIANT=cuda` cài `--extra diarize-gpu` thay cho `--extra diarize`, đặt `DIARIZATION_DEVICE=auto`.
  - `smoke_worker.sh`: bản cuda có `torch.version.cuda` bắt đầu bằng `12`, bản cpu vẫn là torch CPU.
  - Cập nhật kích thước image đo trên CI vào `docs/pipeline/AI-16.md` và `infra/docker/README.md`.
- **Xong khi:** workflow `worker-image` xanh cả 2 bản (hadolint, build, smoke test).
- **Message:** `feat(infra): CUDA worker image runs diarization on the GPU (AI-16)`
- **Hash:**

### 4. [ ] Benchmark 5/15/30' với diarization GPU (AI-13)

- **Việc:**
  - Chạy `evaluation/performance/bench.py --minutes 5 15 30` với `--extra asr --extra diarize-gpu`.
  - Nếu tổng RTF cho thấy 60' xong trong khoảng 30' thì chạy thêm 60'.
  - So với lần đo diarization CPU, ghi vào `evaluation/performance/README.md`.
  - Ghi PSI của máy như các lần trước. Lần đo bị nghẽn IO thì chạy lại, không dùng số đó.
- **Xong khi:** có `results/<ngày>_<tag>/` thật; README nói rõ mục tiêu S6 (60' trong 30') đạt hay chưa, theo số đo chứ không theo ngoại suy.
- **Message:** `perf(eval): benchmark 5 to 30 minute audio with GPU diarization (AI-13)`
- **Hash:**

### 5. [ ] Hiệu chỉnh timeout của stage theo số đo (AI-13)

- **Việc:**
  - `TimeoutPolicy` trong `runner.py`: `per_audio_sec` của từng stage bằng khoảng 2 × RTF p95 đo được, `base_sec` đủ cho việc nạp model.
  - Worker bản CPU chậm hơn nhiều (ASR RTF 0.93 trên CPU so với khoảng 0.1 trên GPU): cho chọn hệ số theo thiết bị, hoặc đọc từ biến môi trường. Không để timeout quá chặt làm job trên CPU bị kill nhầm.
  - Ghi nguồn số liệu ngay cạnh giá trị trong code.
- **Xong khi:** test: audio 60' trên GPU và trên CPU đều có timeout lớn hơn thời gian đo nhân 1.5; giá trị lấy từ số đo, có comment trỏ tới thư mục kết quả.
- **Message:** `feat(pipeline): stage timeouts calibrated from measured RTF (AI-13)`
- **Hash:**

## Việc của nhóm trưởng (không phải commit)

- [ ] Review và merge PR #28 (B) và #29 (A) của ngày 2026-10-25.
- [ ] SH-01: tổ chức buổi ghi âm pilot (vẫn chưa có). AI-12 (phần thu thật), AI-14 (chấm điểm) và benchmark trên audio họp đang chờ dữ liệu này.
- [ ] Quyết định cho nhóm: có dùng Claude API với audio họp thật không (cần consent theo phiếu) và ngân sách API.
