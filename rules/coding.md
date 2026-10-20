# Quy ước viết code

## Ngôn ngữ

| Nội dung | Ngôn ngữ |
|---|---|
| Tên biến, hàm, class, file, mã lỗi; tiêu đề commit | Tiếng Anh |
| Comment, docstring, README, `docs/`, thân commit, mô tả PR | Tiếng Việt có dấu, giữ nguyên thuật ngữ kỹ thuật tiếng Anh |
| Text cho người dùng: UI, thông điệp lỗi của API | Tiếng Việt |
| Log kỹ thuật | Tiếng Việt hoặc tiếng Anh, không chứa dữ liệu người dùng ([privacy-security.md](privacy-security.md)) |

## Đặt tên

| Đối tượng | Quy ước | Ví dụ |
|---|---|---|
| Python: module, hàm, biến | `snake_case` | `run_job`, `edit_service.py` |
| Python: class | `PascalCase` | `TranscriptSegment` |
| Hằng số | `UPPER_SNAKE` | `MAX_TEXT_CHARS` |
| Pydantic schema của API | `<Entity>Out`, `<Entity>Create`, `<Entity>Patch` | `SegmentPatch` |
| Service và router của backend | `<domain>_service.py`; router đặt theo resource số nhiều | `edit_service.py`, `api/v1/meetings.py` |
| Bảng DB | Số nhiều, `snake_case` | `segments`, `action_items` |
| Cột DB | `*_at`: timestamptz UTC. `*_sec`: giây, kiểu float. `ai_*`: bản AI gốc, không bao giờ UPDATE. | `segments.ai_text` |
| API path | `/api/v1/<resource số nhiều>`, nhiều từ thì dùng kebab-case | `/api/v1/meetings/{id}/action-items` |
| Field JSON | `snake_case` | `start_sec` |
| Mã lỗi | `UPPER_SNAKE`, liệt kê trong `contracts/error_codes.md` | `AUDIO_TOO_LONG` |
| React component | `PascalCase`, file `.tsx` cùng tên | `TranscriptSegment.tsx` |
| React hook | `useXxx`. Hook gọi API: `useXxxQuery`, `useXxxMutation`. | `useRecorder` |
| Test frontend | Đặt cạnh file được test, đuôi `.test.ts` hoặc `.test.tsx` | `model.test.ts` |
| Test Python | `tests/.../test_<module>.py`, hàm `test_<hành vi>`. Kịch bản evidence mang ID. | `test_rt01_stage_timeout_kills_subprocess` |
| Stage của pipeline | Tên cố định | `preprocess`, `vad`, `asr`, `diarize`, `merge`, `summarize` |
| Biến môi trường | `UPPER_SNAKE`. Biến riêng của một phần có tiền tố. | `PIPELINE_BACKEND`, `FAKE_SCENARIO`, `DATABASE_URL`, `ANTHROPIC_API_KEY` |

## Công cụ và lệnh kiểm tra

Chạy lệnh của module trước khi push. CI chạy đúng các lệnh này.

| Module | Runtime | Quản lý gói | Lint, format | Test | Lệnh (chạy trong thư mục module) |
|---|---|---|---|---|---|
| `frontend/` | Node.js 24 (`.nvmrc`), TypeScript strict | npm, commit `package-lock.json` | ESLint, Oxlint, Prettier | Vitest, React Testing Library | `npm run lint && npm run format:check && npm run typecheck && npm test && npm run build` |
| `backend/` | Python 3.12 | uv, commit `uv.lock` | ruff, cấu hình giống `pipeline/` | pytest | B ghi vào `backend/README.md` khi làm BE-01 |
| `pipeline/` | Python 3.12 (`.python-version`) | uv, commit `uv.lock` | `ruff check`, `ruff format` | pytest | `uv run ruff check . && uv run ruff format --check . && uv run pytest -m "not model"` |
| `evaluation/` | Python ≥ 3.11 | uv, commit `uv.lock` | `ruff check`, `ruff format` | pytest | `uv run ruff check . && uv run ruff format --check . && uv run pytest && uv run python datasets/check_manifest.py` |

Với Python:

- Ruff: `line-length = 100`, rule `E, F, W, I, B, UP, SIM`, `target-version = "py311"`, như `pipeline/pyproject.toml`.
- Hàm và class dùng ở module khác phải có type hint.
- CI cài bằng `uv sync --locked`, nên đổi dependency thì phải commit lockfile.

Thêm thư viện:

- Dùng `uv add <gói>` hoặc `npm install <gói>`, commit cả lockfile.
- Ghim major version, ví dụ `jiwer>=4.0,<5`.
- Ghi lý do và license trong thân commit. Không dùng thư viện có license phi thương mại hoặc không rõ license.

## Nguyên tắc viết code

1. **Module nhỏ, một trách nhiệm.** Router chỉ nhận request và gọi service, logic nằm trong service. Một file có nhiều lý do để thay đổi thì tách ra.
2. **Dịch vụ bên ngoài đi qua adapter interface có bản fake**, ví dụ `LLMProvider`, model ASR, model diarization. Test không gọi mạng.
3. **Cấu hình đọc ở một chỗ:** pydantic-settings ở backend, biến môi trường ở pipeline. Không hard-code các giới hạn đã có trong `GET /api/v1/config` (dung lượng upload, thời lượng tối đa…). Frontend lấy các giới hạn này từ endpoint đó.
4. **Ngưỡng và timeout** đặt thành hằng số hoặc config. Comment ghi rõ đây là giá trị khởi tạo hay đã đo, và task nào sẽ hiệu chỉnh.
5. **Không bịa số liệu.** WER, latency, chi phí… chỉ ghi khi đã đo thật, kèm lệnh và đường dẫn kết quả.
6. **Lỗi có mã ổn định**, phân loại permanent hoặc transient. Thông điệp lỗi không chứa dữ liệu người dùng.
7. **Thời gian:** thời điểm lưu ở UTC. Thời gian trên audio dùng giây (float), làm tròn ms.
8. **Không để lại** code chết, `print` hay `console.log` để debug, hoặc TODO không ghi Task ID.
9. **Comment giải thích vì sao**, không kể lại code làm gì.

## Quy ước riêng của từng module

| Module | Đọc thêm |
|---|---|
| `frontend/` | `frontend/README.md`: TanStack Query cho server state, React state cho state cục bộ, chia code theo feature, lấy giới hạn upload từ `GET /api/v1/config` |
| `pipeline/` | `pipeline/README.md`, `contracts/pipeline/README.md` |
| `evaluation/` | `evaluation/README.md`, `datasets/CONVENTIONS.md`, `normalizer/RULES.md`, `wer/README.md` |
