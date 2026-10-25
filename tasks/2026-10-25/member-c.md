# 2026-10-25 · Member C: pipeline, evaluation, nhóm trưởng

- **Người làm:** C (`@TAINGUYENVAN0507`), nhánh `tainguyen`.
- **Số commit:** 5.
- **Trạng thái:** đã xong 5 commit, cộng `6a75fd4` sửa số kích thước image cho đúng số đo của CI.
- **Khác với phân công:** bản CUDA (commit 5) là `--build-arg VARIANT=cuda` của cùng `worker.Dockerfile`, không phải file riêng, và không dùng base image CUDA. Lý do: cuBLAS và cuDNN đã có trong wheel `nvidia-*-cu12` của extra `asr`, được `preload_cuda_libs()` nạp; hai Dockerfile riêng sẽ lặp lại toàn bộ các bước cài đặt.
- **Mục tiêu:**
  - Phần synthetic của bộ đánh giá ồn (AI-12): sinh audio theo `conditions.yaml` có seed, chạy ASR, tính WER theo từng điều kiện. Phần audio thu thật chờ SH-01.
  - Docker image cho worker (AI-16): bản CPU (build và smoke test trên CI), script kiểm tra model, bản CUDA.

Đọc trước:
- Mục AI-12, AI-16 của kế hoạch.
- `evaluation/README.md`: quy tắc `results/` và `env.json`.
- `pipeline/tests/edge/README.md`: cách đo SNR đã dùng hôm qua.
- `pipeline/README.md`, phần extra `asr`, `diarize` và token Hugging Face.

Lệnh kiểm tra cho mọi commit:

```bash
cd pipeline && uv run ruff check . && uv run ruff format --check . && uv run pytest -m "not model"
cd ../evaluation && uv run ruff check . && uv run ruff format --check . && uv run pytest
```

## 5 commit

### 1. [x] Sinh audio ồn theo `conditions.yaml` có seed (AI-12)

- **Việc:**
  - `evaluation/noisy_audio/conditions.yaml` gồm các điều kiện:
    - ồn hồng và ồn trắng ở SNR 20, 10, 5, 0 dB;
    - babble (trộn giọng FLEURS khác);
    - vọng phòng;
    - micro đặt xa (lọc tần thấp, vọng, nhỏ tiếng);
    - nén Opus 16 kbps.
  - `make_noisy.py` áp điều kiện lên một clip.
  - SNR được tính trên chính tín hiệu, không phải ước lượng theo amplitude.
  - Cùng seed thì ra cùng byte.
- **Xong khi:** test: SNR đo lại khớp mục tiêu ±0.5 dB; chạy 2 lần cùng seed ra file giống hệt; điều kiện sai trong YAML thì báo lỗi rõ.
- **Message:** `feat(eval): seeded noisy audio generator from conditions.yaml (AI-12)`
- **Hash:** `8001a87`

### 2. [x] Chạy ASR trên bộ ồn, WER theo điều kiện (AI-12)

- **Việc:**
  - `run_noisy.py` (chạy bằng môi trường của pipeline) lấy N clip FLEURS, áp mọi điều kiện, chạy ASR thật (nạp model một lần), ghi hypothesis.
  - Chấm WER theo điều kiện bằng `metrics.score`.
  - Kết quả vào `noisy_audio/results/<ngày>_<tag>/`: `per_condition.csv`, `report.md`, `env.json`. Có cột `source=synthetic` để sau này tách với bản ghi thật.
- **Xong khi:** test đơn vị cho phần gom WER; có kết quả thật cho ít nhất 10 clip × mọi điều kiện.
- **Message:** `feat(eval): noisy suite runner with per-condition WER (AI-12)`
- **Hash:** `220690a`

### 3. [x] Docker image CPU cho worker (AI-16)

- **Việc:**
  - `infra/docker/worker.Dockerfile`: Python 3.12 slim, ffmpeg, `uv sync --locked --extra asr --extra diarize` cho `pipeline/`.
  - User không phải root. Model cache nằm trong volume (`HF_HOME`), không đóng gói vào image.
  - Workflow CI build image và chạy smoke test trong container: fake pipeline chạy hết 6 stage.
- **Xong khi:** CI build được image; smoke test pass; image không chứa `.env`, audio hay dữ liệu trong `evaluation/datasets/`.
- **Message:** `feat(infra): CPU worker image with ffmpeg and a model cache volume (AI-16)`
- **Hash:** `00e030e`

### 4. [x] `scripts/download_models.py` kiểm tra token và điều kiện model (AI-16)

- **Việc:**
  - Tải trước model ASR và diarization vào cache.
  - Kiểm tra `HF_TOKEN` và quyền vào model gated `pyannote/speaker-diarization-community-1`.
  - Thiếu token hoặc chưa chấp nhận điều kiện thì báo lỗi rõ kèm link, exit code khác 0, và không in token ra log.
- **Xong khi:** test với Hub giả: thiếu token, token sai, chưa chấp nhận điều kiện, thành công; trong output không có token.
- **Message:** `feat(scripts): download_models.py checks the HF token and gated model terms (AI-16)`
- **Hash:** `78b8005`

### 5. [x] Bản CUDA của worker và yêu cầu phần cứng (AI-16)

- **Việc:**
  - `infra/docker/worker.cuda.Dockerfile` (base CUDA 12, cuDNN 9), cho ASR chạy GPU.
  - `docs/pipeline/AI-16.md` ghi yêu cầu phần cứng dựa trên số đo thật của AI-13 (VRAM 1.25 GB cho ASR, RAM 2.3 GB cho diarize), cách chạy với `--gpus all`, và giới hạn hiện tại: diarize vẫn chạy CPU.
- **Xong khi:** Dockerfile qua hadolint; tài liệu chỉ dùng số đã đo.
- **Message:** `feat(infra): CUDA worker variant and hardware requirements (AI-16)`
- **Hash:** `27fdd0a`

## Việc của nhóm trưởng (không phải commit)

- [x] Review và merge PR của A (#24) và B (#25) từ hôm qua.
- [ ] SH-01: tổ chức buổi ghi âm pilot (vẫn chưa có).
- [ ] Quyết định cho nhóm: có dùng Claude API với audio họp thật không (cần consent theo phiếu) và ngân sách API.
