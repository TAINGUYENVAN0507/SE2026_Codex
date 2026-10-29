# Docker image (AI-16)

## Worker

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

**Bản `cpu`** bỏ các gói CUDA mà extra `asr` kéo theo trên Linux: cuBLAS, cuDNN, NVRTC. Kích thước đo trên CI: bản `cpu` 2.57 GB, bản `cuda` 4.87 GB.

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
