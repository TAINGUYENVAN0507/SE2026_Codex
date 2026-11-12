# Vietnamese Meeting Minutes Assistant

Hệ thống hỗ trợ ghi âm hoặc tải lên tệp âm thanh cuộc họp tiếng Việt, tự động nhận dạng giọng nói kèm timestamp và phân tách người nói (diarization), tạo bản tóm tắt có cấu trúc và danh sách công việc (action items). Người dùng có thể nghe lại audio, hiệu chỉnh trực tiếp nội dung trên giao diện web và xuất kết quả ra các định dạng TXT, Markdown, JSON.

Dự án môn học **SE2026 – Phát triển phần mềm với AI & Kỹ nghệ Kiểm thử**, nhóm 3 thành viên (SE2026-T05).

---

## 1. Đọc trước khi code

Mọi thành viên và AI coding assistant bắt buộc đọc các tài liệu sau trước khi thực hiện thay đổi:

1. [`structure/`](structure/README.md): Cấu trúc repository, kiến trúc hệ thống, ranh giới module và contracts trao đổi dữ liệu.
2. [`rules/`](rules/README.md): Checklist trước khi commit/mở PR, quy ước nhánh Git, chuẩn code, kiểm thử và bảo vệ quyền riêng tư (`privacy-security.md`).
3. [`tasks/`](tasks/README.md): Nhiệm vụ phân công trong ngày (`tasks/<YYYY-MM-DD>/member-<a|b|c>.md`) và kế hoạch triển khai tổng thể ([`tasks/ROADMAP.md`](tasks/ROADMAP.md)).
4. README chi tiết của từng module: [`frontend/`](frontend/README.md), [`backend/`](backend/README.md), [`pipeline/`](pipeline/README.md).

---

## 2. Thành viên và Phân công

| Thành viên | Vai trò & Phần việc chính | Thư mục phụ trách | GitHub | Nhánh làm việc |
|---|---|---|---|---|
| **A** | Frontend SPA, UX, audio player, trình biên tập transcript/summary/action items, giao diện export | `frontend/`, `backend/app/services/export/` | `@mactuongmvt` | `vantuong` |
| **B** | Backend API (FastAPI), cơ sở dữ liệu (PostgreSQL/SQLAlchemy), worker orchestration, erasure, retention, JSON logging, metrics, tìm kiếm & phân trang | `backend/`, `contracts/openapi.json`, `tests/`, Docker, CI | `@minhquangha` | `haquang` |
| **C** *(Nhóm trưởng)* | AI/Speech pipeline (VAD, ASR, Diarization, LLM Summarization), evaluation datasets (WER/RTF), review & merge mọi PR | `pipeline/`, `contracts/pipeline/`, `evaluation/` | `@TAINGUYENVAN0507` | `tainguyen` |

---

## 3. Trạng thái Hiện tại của Dự án

Toàn bộ 3 module chính đã được triển khai đầy đủ và tích hợp thông qua hợp đồng dữ liệu chuẩn:

- **AI/Speech Pipeline (`pipeline/`):**
  - Đầy đủ 6 stage: `preprocess` → `vad` → `asr` → `diarize` → `merge` → `summarize`.
  - Hỗ trợ cả 2 chế độ: `PIPELINE_BACKEND=real` (mô hình AI thật: Silero VAD, faster-whisper `large-v3-turbo`, pyannote diarization hỗ trợ GPU/CUDA, Claude API cho LLM summarization) và `PIPELINE_BACKEND=fake` (chạy giả lập nhanh cho dev, CI, test mà không cần GPU hay API key).
  - Đã hiệu chỉnh timeout động theo RTF đo đạc thực tế; bộ đánh giá độ chính xác WER và hiệu năng RTF.

- **Backend (`backend/`):**
  - REST API trên nền FastAPI + PostgreSQL 16 (Alembic migrations, cookie session auth, optimistic locking với `version`).
  - Đầy đủ các luồng nghiệp vụ: upload file kiểm tra MIME/kích thước và SHA-256; ghi âm có consent; chỉnh sửa transcript, speaker, summary, action items; lịch sử chỉnh sửa (audit events).
  - Xuất dữ liệu đa định dạng (TXT, Markdown, JSON schema 1.0) dựng từ database.
  - Dịch vụ xóa (BE-18) xóa cuộc họp hoặc cả tài khoản (`DELETE /auth/me`) khỏi DB, `idempotency_keys`, audio và artifact ([ADR 0002](docs/adr/0002-adapter-boundary-and-erasure.md)); Retention Reaper (BE-14) dọn dẹp file audio và dữ liệu vận hành quá hạn.
  - JSON structured logging kèm `job_id`, `stage`, `attempt` (BE-19); endpoint Prometheus `/metrics` theo dõi request, độ trễ và trạng thái hàng đợi job.
  - Tính năng tìm kiếm, lọc và phân trang có thứ tự ổn định (VT-017) với tie-breaker `Meeting.id`, đảm bảo tương thích ngược 100% với client cũ.
  - Hơn 300 test backend, CI xanh, không drift hợp đồng OpenAPI (`contracts/openapi.json`). Kết quả giống nhau dù máy có hay không có `ffprobe`; CI cài ffmpeg và đặt `REQUIRE_FFPROBE=1` để test ffprobe thật (`backend/tests/integration/test_ffprobe_real.py`) không bị skip.
  - Bằng chứng kiểm thử và đo tải: [`docs/evidence/`](docs/evidence/) (chạy lại: `docs/evidence/vt-018/README.md`). Số đo là một lần chạy trên một máy với pipeline giả, không phải cam kết hiệu năng.

- **Frontend (`frontend/`):**
  - Ứng dụng React 18 SPA (Vite + TypeScript strict + Tailwind CSS + TanStack Query).
  - Giao diện hoàn chỉnh: `/login`, danh sách cuộc họp `/meetings` (hỗ trợ tìm kiếm, lọc, phân trang), upload file mới `/meetings/new`, màn hình chi tiết `/meetings/:meetingId` và trang mẫu `/meetings/sprint-42`.
  - Audio player đồng bộ timeline transcript; trình biên tập trực tiếp speaker, segment text, tóm tắt và action items; menu export TXT/MD/JSON theo bản chỉnh sửa hoặc bản gốc AI.
  - Hỗ trợ chạy với Backend thật (`VITE_API_MOCK=0`) hoặc chế độ Mock Service Worker (`VITE_API_MOCK=1`). Kiểm thử E2E trên stack thật với Playwright.

---

## 4. Hướng dẫn Khởi chạy Nhanh (Quick Start)

### 4.1. Yêu cầu hệ thống
- Python 3.12+ và [uv](https://docs.astral.sh/uv/)
- Node.js 24+ và npm
- Docker & Docker Compose (cho PostgreSQL 16)
- `ffmpeg` và `ffprobe` trong `PATH` hệ thống

### 4.2. Khởi chạy từng bước

#### Bước 1: Khởi động Cơ sở dữ liệu PostgreSQL
Từ thư mục gốc dự án:
```bash
# Sao chép cấu hình môi trường mẫu nếu chưa có
cp .env.example .env

# Khởi chạy container PostgreSQL 16
docker compose up -d db
```

#### Bước 2: Chạy migration và Khởi động Backend API Server
Mở terminal 1:
```bash
cd backend
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --port 8000
```
- API Server: `http://localhost:8000`
- Tài liệu API tương tác: `http://localhost:8000/docs` hoặc `http://localhost:8000/redoc`
- Cấu hình mở rộng (`.env`): `WEB_CONCURRENCY` (số uvicorn worker, mặc định `1`), `DB_RESERVED_CONNECTIONS` (kết nối dự phòng cho worker/migration, mặc định `20`), `PROMETHEUS_MULTIPROC_DIR` (thư mục chia sẻ gom metric đa tiến trình cho Prometheus).

#### Bước 3: Khởi động Background Worker
Mở terminal 2:
```bash
cd backend
# Chạy worker với pipeline giả lập (không cần GPU hay API key LLM)
PIPELINE_BACKEND=fake uv run python -m app.worker.runner

# Hoặc chạy với pipeline AI thật (yêu cầu cài đặt thêm extras của pipeline)
# PIPELINE_BACKEND=real uv run python -m app.worker.runner
```

#### Bước 4: Khởi động Frontend Web App
Mở terminal 3:
```bash
cd frontend
npm ci
npm run dev
```
- Mở trình duyệt tại: `http://localhost:5173`
- Khi chạy dev, frontend mặc định dùng MSW để xem thử độc lập: `user@example.com` / `demo-password`. Để gọi backend thật, đặt `VITE_API_MOCK=0` (PowerShell: `$env:VITE_API_MOCK='0'`) trước `npm run dev`; proxy mặc định tới `http://localhost:8000`. Hướng dẫn tài khoản, migration và kiểm thử nằm trong [frontend/README.md](frontend/README.md).

### 4.3. Khởi chạy Trọn gói Bằng Docker Compose (BE-16)

Hệ thống hỗ trợ đóng gói và khởi chạy toàn bộ 4 service chỉ với một lệnh Docker Compose duy nhất (hoặc qua `make up` / `make down`):

```bash
# Xây dựng và khởi chạy cả 4 service ở chế độ nền (hoặc: make up)
docker compose up --build -d
```

#### Kiến trúc 4 service trong Compose:
| Service | Image / Build | Vai trò & Cấu hình | Healthcheck |
|---|---|---|---|
| `db` | `postgres:16` | Cơ sở dữ liệu chính, cổng 5432, lưu trữ persistent trên volume `pgdata`. | `pg_isready -U postgres` |
| `api` | `infra/docker/api.Dockerfile` | FastAPI backend, tự động chạy migration `alembic upgrade head` khi khởi động, cổng 8000. | `curl -f http://localhost:8000/ready` |
| `worker` | `infra/docker/api.Dockerfile` | Background worker xử lý audio qua pipeline, chia sẻ volume `appdata` với `api`. | DB query `SELECT 1` |
| `web` | `infra/docker/web.Dockerfile` | Nginx reverse proxy phục vụ frontend SPA trên cổng 80. Proxy `/api/` và `/health` về `api:8000`, **chặn hoàn toàn `/metrics`** để bảo mật hệ thống. | `wget http://127.0.0.1:8080/` |

#### Smoke Test Luồng Xử lý Hoàn chỉnh (Upload → Transcript):
Sau khi các container đều ở trạng thái `healthy`:
```bash
# 1. Kiểm tra trạng thái các service
docker compose ps

# 2. Thực hiện smoke test nhanh qua API (hoặc truy cập http://localhost trên trình duyệt):
# Đăng nhập lấy phiên:
curl -c cookies.txt -X POST http://localhost/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"demo@example.com","password":"demopassword123"}'

# Tải lên tệp âm thanh WAV (có gắn cờ consent):
curl -b cookies.txt -X POST http://localhost/api/v1/meetings \
  -F "title=Smoke Test Cuộc Họp" \
  -F "consent=true" \
  -F "audio=@contracts/fixtures/pipeline/sample.wav"

# Worker tự động nhận job từ hàng đợi, hoàn thành các stage và chuyển meeting sang ready!

# Chạy kiểm thử khói End-to-End tự động trên Compose:
make smoke

# Dừng cụm service (hoặc: make down):
docker compose down
```

---

## 5. Quy chuẩn Kiểm tra Chất lượng (Quality Gates)

Dự án cung cấp `Makefile` tại thư mục gốc để thuận tiện chạy kiểm tra nhanh cho toàn bộ hệ thống:

```bash
# Kiểm tra lint và định dạng cho toàn bộ module (backend, frontend, pipeline):
make lint

# Chạy test suites của toàn bộ module:
make test
```

Trước khi commit mã nguồn hoặc mở Pull Request, mỗi thành viên phải bảo đảm toàn bộ lệnh lint và test của module phụ trách đều xanh (có thể chạy qua `make lint` / `make test` hoặc các lệnh trực tiếp của từng module bên dưới):

### Backend (`backend/`)
```bash
cd backend
uv run ruff check .
uv run ruff format --check .
uv run pytest
```
*Lưu ý:* Kiểm tra OpenAPI drift trước khi commit:
```bash
uv run python scripts/generate_openapi.py --check
```

### Frontend (`frontend/`)
```bash
cd frontend
npm run lint
npm run format:check
npm run typecheck
npm test
npm run build
```

### Pipeline (`pipeline/`)
```bash
cd pipeline
uv run pytest
```

---

## 6. Cấu trúc Thư mục Tổng quan

```text
SE2026_Codex/
├── backend/            # FastAPI application, database models, worker runner, REST API routes
├── contracts/          # Hợp đồng dữ liệu chung: openapi.json, schemas, fixtures, error codes
├── docs/               # Tài liệu kiến trúc, ADRs, hướng dẫn kỹ thuật và chính sách dữ liệu
├── evaluation/         # Bộ công cụ đánh giá pipeline: WER, RTF benchmark, test datasets
├── frontend/           # Ứng dụng React SPA, audio player, editing UI, mock handlers
├── pipeline/           # AI/Speech pipeline (preprocess, vad, asr, diarize, merge, summarize)
├── rules/              # Quy tắc làm việc của nhóm: git-workflow, coding, testing, privacy
├── structure/          # Quy định cấu trúc: repository, architecture, contracts
└── tasks/              # Phân công công việc hàng ngày và roadmap tiến độ MVP
```
