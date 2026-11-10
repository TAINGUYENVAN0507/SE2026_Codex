# Docker image (AI-16, BE-16)

Tài liệu hướng dẫn xây dựng và triển khai các Docker image cho hệ thống Vietnamese Meeting Minutes Assistant, bao gồm: API (kèm worker), Worker chuyên dụng cho mô hình AI, và Web Frontend phục vụ qua Nginx reverse proxy.

---

## 1. API (kèm Worker) (BE-16)

`api.Dockerfile` đóng gói toàn bộ backend FastAPI và worker loop phục vụ xử lý công việc. Build từ gốc repo:

```bash
docker build -f infra/docker/api.Dockerfile -t meeting-api .
```

### Đặc điểm kỹ thuật:
- **Base image:** `python:3.12-slim-bookworm` tối ưu dung lượng, tích hợp sẵn `ffmpeg` cho xử lý âm thanh.
- **Quản lý gói:** Dùng `uv` với cache layer độc lập, không cài dev dependencies hay GPU runtime nặng (Torch/CUDA).
- **Đa dụng (kèm worker):**
  - Mặc định chạy API server: `uvicorn app.main:create_app --factory --host 0.0.0.0 --port 8000`.
  - Có thể chạy worker loop bằng cách ghi đè lệnh: `python -m app.worker.runner`.
- **Bảo mật và Phân quyền:**
  - Chạy dưới user không phải root: `app` (UID `10001`).
  - Không nhúng secret, file `.env` hay thông tin xác thực vào image.
- **Kích thước image:** ~420 MB (tối ưu đáng kể so với worker có model nặng).

---

## 2. Web Frontend & Nginx Proxy (BE-16)

`web.Dockerfile` thực hiện multi-stage build: biên dịch mã nguồn React qua Vite và phục vụ tệp tĩnh qua Nginx reverse proxy. Build từ gốc repo:

```bash
docker build -f infra/docker/web.Dockerfile -t meeting-web .
```

Builder giữ cấu trúc `/app/frontend` và `/app/contracts/openapi.json` để Vite
đọc capability của API đúng như khi chạy từ repo. Contract chỉ nằm ở builder;
image Nginx cuối chỉ nhận `dist/`. Workflow Docker chạy lại khi OpenAPI đổi.

### Đặc điểm kỹ thuật:
- **Giai đoạn Build:** `node:24-bookworm-slim`, cài đặt dependencies bằng `npm ci --legacy-peer-deps` và biên dịch qua `vite build` ra thư mục `dist/`.
- **Giai đoạn Serve:** `nginx:1.27-alpine` siêu nhẹ.
- **Cấu hình Nginx (`infra/docker/nginx.conf`):**
  - Phục vụ Single Page Application (SPA) với fallback `try_files $uri $uri/ /index.html`.
  - Giới hạn tải lên `client_max_body_size 250M` đáp ứng kích thước file ghi âm.
  - Proxy an toàn: chuyển tiếp `/api/` và `/health` tới service backend `api:8000`.
  - **Bảo vệ dữ liệu vận hành (PRIV-10):** Chặn hoàn toàn `/metrics` ở cấp proxy (trả HTTP 404), ngăn chặn lộ thông tin giám sát ra mạng công cộng.
- **Bảo mật và Phân quyền:**
  - Chạy dưới user không phải root: `nginx` (UID `101`), lắng nghe trên cổng unprivileged `8080`.
- **Kích thước image:** ~48 MB.

---

## 3. Worker (AI-16)

`worker.Dockerfile` đóng gói worker (`python -m app.worker.runner`) cùng pipeline thật. Build từ gốc repo:

```bash
docker build -f infra/docker/worker.Dockerfile -t meeting-worker:cpu .
docker build -f infra/docker/worker.Dockerfile --build-arg VARIANT=cuda -t meeting-worker:cuda .
```

**Hai bản image:**
- **`cuda`** giữ cuBLAS và cuDNN từ wheel `nvidia-*-cu12`, không cần base image CUDA. Chạy bằng `docker run --gpus all ...`; host cần driver NVIDIA và nvidia-container-toolkit.
- **Mặc định của ASR do `worker-entrypoint.sh` đặt theo bản image:**
  - `cpu`: `ASR_DEVICE=cpu`, `ASR_COMPUTE_TYPE=int8`;
  - `cuda`: `ASR_DEVICE=cuda`, `ASR_COMPUTE_TYPE=int8_float16`.

  Muốn đổi thì truyền `-e` khi `docker run`.
- **Diarization:** bản `cpu` dùng extra `diarize` (torch CPU); bản `cuda` dùng `diarize-gpu` (torch CUDA 12.6, chung cuDNN và cuBLAS với CTranslate2), `DIARIZATION_DEVICE=auto`.

Yêu cầu phần cứng và số đo: [`docs/pipeline/AI-16.md`](../../docs/pipeline/AI-16.md).

**Image gồm 2 venv**, mỗi venv dựng từ lock của chính nó, nên không phải trộn 2 lock:

| Venv | Nội dung | Dùng để |
|---|---|---|
| `/app/backend/.venv` | backend, `meeting_pipeline` (không có model) | worker loop, `run_job()` |
| `/app/pipeline/.venv` | pipeline với extra `asr` và `diarize` (bản cpu) hoặc `diarize-gpu` (bản cuda) | subprocess của từng stage, qua `PIPELINE_PYTHON` |

**Bản `cpu`** bỏ các gói CUDA mà extra `asr` kéo theo trên Linux: cuBLAS, cuDNN, NVRTC. Kích thước đo trên CI: bản `cpu` 2.57 GB, bản `cuda` 8.38 GB (gồm torch CUDA cho diarization).

**Volume:**
- `/models`: cache Hugging Face (`HF_HOME`). Model không nằm trong image.
- `/app/backend/appdata`: file upload và artifact của job (storage của backend).

**Biến môi trường:**
- Đặt sẵn trong image: `PIPELINE_BACKEND=real`, `DIARIZATION_DEVICE=auto`, `WORKER_VARIANT`. Mặc định của ASR như ở trên.
- Truyền lúc chạy: `DATABASE_URL`, `HF_TOKEN` (model diarization là model gated), và `LLM_PROVIDER`, `ANTHROPIC_API_KEY` nếu bật tóm tắt.
- Không đặt secret trong image.

```bash
docker run --rm \
  -e DATABASE_URL=... -e HF_TOKEN=... \
  -v models:/models -v appdata:/app/backend/appdata \
  meeting-worker:cpu
```

Worker chạy bằng user không phải root (uid 10001). `.dockerignore` loại `.env`, `evaluation/`, `reports/`, audio và venv của máy dev khỏi build context.

## Kiểm tra

Workflow `worker-image` trên CI chạy hadolint, build cả 2 bản, rồi chạy `smoke_worker.sh` trong container với `--network none`. CI không có GPU. Script kiểm:
1. có ffmpeg;
2. venv pipeline có faster-whisper, pyannote; bản `cpu` có torch CPU và không có cuBLAS; bản `cuda` có torch CUDA 12, cuDNN 9.x, cuBLAS 12.x và mặc định `ASR_DEVICE=cuda`;
3. venv backend không có runtime của model;
4. `run_job()` từ venv backend chạy đủ 6 stage fake bằng venv pipeline;
5. stage `preprocess` thật chạy được;
6. image không có `.env`, dữ liệu đánh giá hay audio, và không chạy bằng root.

```bash
docker run --rm -v "$PWD/infra/docker/smoke_worker.sh:/smoke.sh:ro" meeting-worker:cpu sh /smoke.sh
```

## Kiểm chứng Web ngày 08/11/2026

- Trước sửa: Docker build lỗi ENOENT tại /contracts/openapi.json; sau khi bổ sung contract, nginx -t còn lỗi quyền ghi /run/nginx.pid.
- Sau sửa: Docker build đạt; nginx -t đạt dưới user nginx; container QA trả HTTP 200 cho /settings và 404 cho /metrics.
- Sửa phát sinh do tích hợp FE-19 với BE-16. PR cần B review Dockerfile và bộ lọc workflow; không đổi API hay contract.

## Smoke Web trong CI — 09/11/2026

Sau `build-web`, workflow chạy `sh infra/docker/smoke_web.sh meeting-web:latest`.
Script giữ user mặc định non-root, kiểm `nginx -t`, khởi động container trên cổng
host ngẫu nhiên, chờ HTTP 200 cho `/` và `/settings`, kiểm `/metrics` trả 404.
Container kiểm tra được dọn cả khi đạt lẫn lỗi; API được resolve qua
`--add-host api:127.0.0.1`, không yêu cầu API thật cho các route SPA.

Chạy lại local sau khi build image bằng đúng lệnh trên (cần Docker, sh và curl).
Negative control: nhánh tạm cố tình đưa PID về `/var/run/nginx.pid`; bước smoke
phải fail vì nginx không có quyền ghi. Không đưa mutation vào nhánh nộp.
Bằng chứng run đỏ/xanh được ghi ở FE-19 và file phân công, không coi build image
đạt là bằng chứng container khởi động được.
