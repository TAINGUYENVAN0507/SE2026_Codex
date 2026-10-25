# Docker image (AI-16)

## Worker bản CPU

`worker.Dockerfile` đóng gói worker (`python -m app.worker.runner`) cùng pipeline thật. Build từ gốc repo:

```bash
docker build -f infra/docker/worker.Dockerfile -t meeting-worker:cpu .
```

**Image gồm 2 venv**, mỗi venv dựng từ lock của chính nó, nên không phải trộn 2 lock:

| Venv | Nội dung | Dùng để |
|---|---|---|
| `/app/backend/.venv` | backend, `meeting_pipeline` (không có model) | worker loop, `run_job()` |
| `/app/pipeline/.venv` | pipeline với extra `asr`, `diarize` (faster-whisper, pyannote, torch CPU) | subprocess của từng stage, qua `PIPELINE_PYTHON` |

**Bản CPU** bỏ các gói CUDA mà extra `asr` kéo theo trên Linux:
- bỏ: cuBLAS, cuDNN, NVRTC (khoảng 1 GB);
- ASR chạy `int8` trên CPU, diarization cũng chạy CPU.

**Volume:**
- `/models`: cache Hugging Face (`HF_HOME`). Model không nằm trong image.
- `/app/backend/appdata`: file upload và artifact của job (storage của backend).

**Biến môi trường:**
- Đặt sẵn trong image: `PIPELINE_BACKEND=real`, `ASR_DEVICE=cpu`, `ASR_COMPUTE_TYPE=int8`, `DIARIZATION_DEVICE=cpu`.
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

Workflow `worker-image` trên CI build image, rồi chạy `smoke_worker.sh` trong container với `--network none`. Script kiểm:
1. có ffmpeg;
2. venv pipeline có faster-whisper, pyannote, torch CPU;
3. venv backend không có runtime của model;
4. `run_job()` từ venv backend chạy đủ 6 stage fake bằng venv pipeline;
5. stage `preprocess` thật chạy được;
6. image không có `.env`, dữ liệu đánh giá hay audio, và không chạy bằng root.

```bash
docker run --rm -v "$PWD/infra/docker/smoke_worker.sh:/smoke.sh:ro" meeting-worker:cpu sh /smoke.sh
```
