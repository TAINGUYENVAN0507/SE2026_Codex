# Cấu trúc repository

> Trạng thái ngày 2026-10-19. ✓ đã có trong `main` · ◐ đang ở nhánh cá nhân, chưa vào `main` · ○ chưa có, sẽ làm theo kế hoạch.

## Cây thư mục cấp cao

```text
.
├── README.md             ✓ giới thiệu dự án, thành viên, link tới structure/ và rules/
├── AGENTS.md             ✓ hướng dẫn cho AI coding assistant: đọc structure/ và rules/ trước
├── structure/            ✓ cấu trúc chung (thư mục này)
├── rules/                ✓ quy tắc làm việc chung
├── docs/                 ✓ tài liệu chung theo khu vực (docs/README.md)
├── contracts/            ✓ contract giữa các module (contracts.md)
├── frontend/             ◐ A, nhánh vantuong
├── backend/              ○ B
├── pipeline/             ✓ C
├── evaluation/           ✓ C
├── tests/                ○ B: test liên module (integration, audit, reliability, privacy)
├── infra/                ○ B: nginx.conf, Dockerfile của api/worker/web
├── scripts/              ○ B, C: create_user.py, seed.py, download_models.py
├── docker-compose.yml    ○ B: db, api, worker, web (+ docker-compose.gpu.yml)
├── Makefile              ○ B: up, down, test, seed, contract-check, eval-*
├── .env.example          ○ B: chỉ chứa placeholder
├── .github/              ✓ workflows/pipeline.yml, evaluation.yml · ◐ workflows/frontend.yml
└── reports/              ✗ ghi chú cá nhân của nhóm trưởng, nằm trong .gitignore
```

Thêm thư mục cấp 1 mới: hỏi nhóm trưởng trước và cập nhật file này trong cùng PR.

## Owner

Owner chịu trách nhiệm về nội dung và quyết định cấu trúc bên trong thư mục. Mọi PR vẫn do nhóm trưởng review và merge ([git-workflow.md](../rules/git-workflow.md)).

| Thư mục | Owner | Ghi chú |
|---|---|---|
| `frontend/` | A | |
| `backend/` | B | Riêng `backend/app/services/export/` do A viết (FE-15), B review cách gọi |
| `contracts/openapi.json`, `contracts/fixtures/api/`, `contracts/error_codes.md` | B | A là consumer |
| `contracts/pipeline/`, `contracts/fixtures/pipeline/` | C | B là consumer |
| `contracts/export.schema.json` | A | |
| `pipeline/`, `evaluation/` | C | A và B cùng gõ transcript tham chiếu, chấm rubric |
| `tests/` | B | C viết phần stage timeout/transient trong `tests/reliability/` |
| `docs/<khu vực>/` | Owner của khu vực | `docs/adr/`: người đề xuất quyết định |
| `infra/`, `docker-compose*.yml`, `Makefile` | B | C viết Dockerfile của worker (AI-16) |
| `.github/workflows/<module>.yml` | Owner của module | |
| `structure/`, `rules/`, `README.md`, `AGENTS.md`, `.github/` (ngoài workflows) | Nhóm trưởng (C) | Ai cũng được đề xuất sửa qua PR |

Sửa file trong thư mục của người khác: báo owner trước, ghi rõ trong mô tả PR để owner đọc lại.

## Bên trong từng module

### `frontend/` (A)

Theo code hiện có ở nhánh `vantuong`:

```text
frontend/
├── src/
│   ├── main.tsx, App.tsx    # entry và khai báo route
│   ├── app/                 # provider dùng chung: router, TanStack Query
│   ├── components/          # component dùng ở nhiều màn hình: AppShell, Topbar...
│   ├── pages/               # mỗi route một file: LoginPage, MeetingListPage...
│   ├── features/<feature>/  # logic và component theo tính năng: audio/, meetings/...
│   ├── api/                 ○ client và type sinh từ contracts/openapi.json (FE-02)
│   ├── mocks/               ○ MSW đọc contracts/fixtures/api/ (FE-02)
│   └── test/setup.ts        # cấu hình Vitest
├── e2e/                     ○ Playwright: flows/, privacy/ (FE-17)
├── public/
└── package.json, package-lock.json, .nvmrc
```

Quy ước riêng của frontend nằm ở `frontend/README.md`.

### `backend/` (B)

Theo kế hoạch. B chốt khi làm BE-01 rồi cập nhật mục này.

```text
backend/
├── app/
│   ├── core/          # cấu hình (pydantic-settings), logging, security
│   ├── db/models/     # SQLAlchemy models
│   ├── schemas/       # Pydantic: <Entity>Out, <Entity>Create, <Entity>Patch
│   ├── api/v1/        # router theo resource: meetings.py, jobs.py...
│   ├── services/      # <domain>_service.py; export/ (A), audit/, storage/, idempotency/
│   └── worker/        # claim job, lease, retry, persist, runner_adapter.py
├── alembic/
└── tests/{unit,api}/
```

### `pipeline/` (C)

```text
pipeline/
├── meeting_pipeline/
│   ├── schemas.py     # schema I/O của các stage, nguồn sinh ra contracts/pipeline/
│   ├── errors.py      # mã lỗi; permanent, transient, timeout; exit code
│   ├── runner.py      # run_job(): API công khai cho worker của B
│   ├── cli.py         # python -m meeting_pipeline run-stage ...
│   ├── registry.py    # chọn stage thật hay fake theo PIPELINE_BACKEND
│   ├── stages/        # mỗi stage một file: preprocess.py, merge.py...
│   ├── fake/          # fake pipeline và dữ liệu mẫu cho test, dev của A và B
│   └── llm/           ○ LLMProvider: anthropic, fake (AI-09)
└── tests/{unit,edge,model}/
```

### `evaluation/` (C)

```text
evaluation/
├── datasets/      # manifest.csv, LICENSES.md, CONVENTIONS.md, refs/ (chỉ dữ liệu public)
│   ├── raw/       # dữ liệu tải về, không commit
│   └── private/   # dữ liệu họp nội bộ theo consent, không commit
├── normalizer/    # chuẩn hóa text tiếng Việt cho WER
├── wer/           # run_wer.py, make_report.py, results/<YYYY-MM-DD>_<tag>/
├── spikes/        ○ chọn model ASR, diarization (AI-01, AI-02)
└── noisy_audio/, diarization/, performance/, summary_rubric/   ○ AI-12 đến AI-14
```

## File mới đặt ở đâu

| Muốn thêm | Đặt ở | Kèm theo trong cùng PR |
|---|---|---|
| Màn hình (route) mới | `frontend/src/pages/`, logic ở `frontend/src/features/<feature>/` | Route trong `App.tsx`, test cạnh file |
| Component dùng ở nhiều màn hình | `frontend/src/components/` | Test |
| API endpoint | `backend/app/api/v1/<resource>.py`, schema ở `backend/app/schemas/` | Test ở `backend/tests/api/`, sinh lại `contracts/openapi.json`, fixture ở `contracts/fixtures/api/` |
| Bảng hoặc cột DB | `backend/app/db/models/` và migration trong `backend/alembic/` | Migration có downgrade |
| Stage hoặc thuật toán AI | `pipeline/meeting_pipeline/stages/` | Test ở `pipeline/tests/unit/` hoặc `edge/`; sinh lại `contracts/pipeline/` nếu đổi schema |
| Test liên module (API + worker + pipeline + DB) | `tests/<integration\|audit\|reliability\|privacy>/` | Tên test theo ID kịch bản, ví dụ `test_rt06_...`, `test_aud03_...` |
| Bộ đánh giá, kết quả đo | `evaluation/<bộ>/`, kết quả ở `evaluation/<bộ>/results/<YYYY-MM-DD>_<tag>/` | `env.json` và lệnh chạy lại |
| Quyết định kiến trúc | `docs/adr/NNNN-<slug>.md` | |
| Tài liệu nghiệm thu task | `docs/<khu vực>/<TaskID>.md` | |
| Biến môi trường mới | Đọc qua module config của từng phần | Placeholder trong `.env.example`, mô tả trong README của module |
| Workflow CI | `.github/workflows/<module>.yml` | Lọc `paths` theo module |
| Thư viện mới | `pyproject.toml` + `uv.lock`, hoặc `package.json` + `package-lock.json` | Ghi lý do và license trong commit body |

## Không commit

| Loại | Ví dụ | Thay bằng |
|---|---|---|
| Secret | `.env`, API key, HF token | `.env.example` chỉ có placeholder |
| Audio, video | `*.wav`, `*.mp3`, `*.m4a`, `*.webm`… | Sinh lúc chạy test bằng ffmpeg, hoặc tải bằng script có sha256 |
| Dữ liệu họp nội bộ | Audio, transcript tham chiếu, RTTM của `meet-*`, `noisy-*` | Để trong `evaluation/datasets/private/`, chia sẻ qua kênh riêng của nhóm |
| Dữ liệu tải về | `evaluation/datasets/raw/` | `evaluation/datasets/download.py` |
| Model, artifact của pipeline | `models/`, `artifacts/` | Script tải model (`scripts/download_models.py`, chưa có) |
| Môi trường, cache, build | `.venv/`, `node_modules/`, `__pycache__/`, `dist/` | Lockfile: `uv.lock`, `package-lock.json` |
| Ghi chú cá nhân | `reports/`, `CLAUDE.md` | |
