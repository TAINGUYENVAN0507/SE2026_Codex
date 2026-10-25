# 2026-10-25 · Member A: frontend, export

- **Người làm:** A (`@mactuongmvt`), nhánh `vantuong`.
- **Số commit:** 5.
- **Mục tiêu:**
  - Export end-to-end (FE-15). Theo kế hoạch, A viết cả module Python `backend/app/services/export/` (B review) và menu export trên UI.
  - Phần còn lại của FE-16: skeleton, responsive từ 360px, a11y cơ bản.

Đọc trước:
- Mục FE-15, FE-16 của kế hoạch.
- `contracts/openapi.json`, path `/api/v1/meetings/{meeting_id}/export` (`format`: txt, json, md; `variant`: current, ai_original).
- `backend/README.md`, mục chạy test.
- [`rules/coding.md`](../../rules/coding.md), phần Python: ruff, line 100, test bằng pytest.

Lệnh kiểm tra:

```bash
cd backend && uv run ruff check . && uv run ruff format --check . && uv run pytest tests/unit/test_export*.py
cd frontend && npm run lint && npm run format:check && npm run typecheck && npm test && npm run build
```

## Bước 0 (không tính vào số commit)

```bash
git checkout vantuong
git fetch origin
git merge origin/main
```

PR #24 đã được merge (`fe6e8e0`).

## 5 commit

### 1. [x] DTO `MeetingExport` và export JSON (FE-15)

- **Việc:**
  - `backend/app/services/export/`: dataclass hoặc model Pydantic `MeetingExport`, gồm meeting (title, ngày, thời lượng), speakers, segments (text, speaker, thời gian), summary, action items.
  - `variant=ai_original` dùng `ai_text`, `ai_speaker_id` và bản AI của summary; `current` dùng bản đã sửa.
  - `to_json()` có `schema_version: "1.0"`, key theo thứ tự cố định, `ensure_ascii=False`.
  - Sinh `contracts/export.schema.json` từ model (giống cách `contracts/pipeline/` được sinh), có lệnh `--check` để kiểm drift.
  - Module này là pure function: không đọc DB, không đọc file.
- **Xong khi:** test golden file; export 2 lần cho ra byte giống hệt; output hợp lệ theo `export.schema.json`.
- **Message:** `feat(backend): MeetingExport DTO and deterministic JSON export (FE-15)`
- **Hash:** `0caf964`

### 2. [x] Export TXT và Markdown, tên file không dấu (FE-15)

- **Việc:**
  - `to_txt()`: mỗi segment một dòng `[hh:mm:ss] Tên: text`.
  - `to_markdown()`: tiêu đề, tóm tắt, quyết định, bảng action items (người nhận "Chưa giao", hạn "Chưa có hạn" khi null), transcript.
  - `filename(meeting, fmt)`: slug không dấu (`đ` thành `d`), chỉ gồm `[a-z0-9-]`, kèm ngày họp.
- **Xong khi:** golden file cho TXT và MD, gồm các trường hợp: hạn null, speaker chưa xác định, tiêu đề toàn ký tự đặc biệt, variant `ai_original`. Output deterministic.
- **Message:** `feat(backend): TXT and Markdown export with ASCII slug filenames (FE-15)`
- **Hash:** `0c2305f`

### 3. [x] Menu export trên trang detail (FE-15)

- **Việc:**
  - Menu chọn định dạng (TXT, JSON, Markdown) và biến thể (bản hiện tại, bản AI gốc).
  - Tải bằng `GET /meetings/{id}/export?format=&variant=` (MSW trả file mẫu, kèm `Content-Disposition`).
  - Disable khi transcript chưa `ready`, có tooltip giải thích. Lỗi thì hiện toast.
- **Xong khi:** RTL test: menu disable khi chưa ready; chọn định dạng thì gọi đúng URL; lỗi 409 thì hiện thông báo.
- **Message:** `feat(frontend): export menu with format and variant (FE-15)`
- **Hash:** `49e37d0`

### 4. [x] Skeleton và responsive từ 360px (FE-16)

- **Việc:**
  - Skeleton cho danh sách meeting, transcript, tóm tắt thay cho chữ "Đang tải".
  - Layout trang detail ở 360px: player vẫn sticky, các tab cuộn ngang, không có thanh cuộn ngang của cả trang.
- **Xong khi:** RTL test skeleton hiện khi đang tải; kiểm tra bằng tay ở 360, 768, 1280px (ghi vào checklist ở commit 5).
- **Message:** `feat(frontend): loading skeletons and a 360px responsive layout (FE-16)`
- **Hash:** `3919b0c`

### 5. [x] Phím tắt không bắt khi đang gõ, a11y cơ bản, checklist UX (FE-16)

- **Việc:**
  - Phím tắt của player (Space, ←, →) bị bỏ qua khi focus đang ở `input`, `textarea` hoặc `contenteditable`.
  - Mọi nút icon có `aria-label`; dialog giữ focus bên trong và Esc để đóng.
  - Viết `docs/demo/ux-checklist.md`: các mục đã kiểm, kèm screenshot desktop và mobile. Screenshot dùng dữ liệu mẫu của MSW, không dùng dữ liệu họp thật.
- **Xong khi:** RTL test: gõ Space trong ô sửa segment không làm player dừng; Esc đóng dialog và trả focus.
- **Message:** `feat(frontend): typing-safe shortcuts, basic a11y and a UX checklist (FE-16)`
- **Hash:** `40d2dfa`

## Việc chung (không phải commit)

- [ ] SH-01: ghi âm buổi họp pilot có consent (vẫn chưa có).

## Cuối ngày

- [x] Tick các ô ở trên và ghi hash. Cập nhật `docs/frontend/` (FE-15, FE-16).
- [ ] Push `vantuong`, mở PR vào `main`. **Không tự merge.**

Kiểm tra local: backend Ruff lint/format, schema drift và 16 test export đạt;
frontend lint/format/TypeScript, 149 test và build đạt. Browser QA dùng MSW tải
đủ sáu file, kiểm tra phím tắt/focus và ba layout 360/768/1280px. Hai JSON tải
xuống hợp lệ theo schema. Checklist kèm ảnh ở `docs/demo/ux-checklist.md`.

Module export chỉ nhận DTO, không query DB hoặc thay router của B. Endpoint
export hiện vẫn là stub: B cần review và nối dữ liệu DB vào DTO trước khi
nghiệm thu export end-to-end với dữ liệu thật. Chưa push hoặc mở PR trong lượt này.
