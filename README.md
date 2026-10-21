# Vietnamese Meeting Minutes Assistant

Web app ghi âm hoặc tải audio cuộc họp tiếng Việt lên, sau đó tạo transcript có timestamp và speaker, tóm tắt cuộc họp và action items. Người dùng chỉnh sửa được kết quả và export ra TXT/JSON/Markdown.

Dự án môn học SE2026, nhóm 3 người.

## Đọc trước khi code

Mọi thành viên, kể cả AI coding assistant của từng người, đọc theo thứ tự:

1. [`structure/`](structure/README.md): cấu trúc repo, kiến trúc, ranh giới module, contracts.
2. [`rules/`](rules/README.md): checklist trước khi code, nhánh và PR, quy ước code, test, privacy.
3. [`tasks/`](tasks/README.md): việc trong ngày của mình, `tasks/<YYYY-MM-DD>/member-<a|b|c>.md`.
4. README của module sắp sửa.

## Thành viên và phần việc

| Member | Phần việc | Thư mục chính | GitHub | Nhánh |
|---|---|---|---|---|
| A | Frontend, UX, chỉnh sửa, export | `frontend/`, `backend/app/services/export/` | `@mactuongmvt` | `vantuong` |
| B | Backend, API, DB, job orchestration, tích hợp | `backend/`, `contracts/openapi.json`, `tests/`, Docker, CI | `@minhquangha` | chưa tạo |
| C, nhóm trưởng | AI/Speech pipeline và evaluation; review và merge mọi PR | `pipeline/`, `contracts/pipeline/`, `evaluation/` | `@TAINGUYENVAN0507` | `tainguyen` |

## Trạng thái

- Đã có trong `main`: pipeline (khung chạy, contracts, stage `preprocess` và `merge` thật, các stage khác có bản fake) và bộ đánh giá (datasets, normalizer, chấm WER).
- Frontend: đã có scaffold FE-01 ở nhánh `vantuong`, đang chờ review và merge PR #5.
- Backend: chưa bắt đầu.

Chi tiết từng thư mục ở [`structure/repository.md`](structure/repository.md). Mỗi module có README riêng.

## Frontend (FE-01)

Đã có nền Vite + React + TypeScript strict, router, TanStack Query provider và
workflow kiểm tra frontend. Giao diện hiện dùng dữ liệu demo trong phiên, chưa
kết nối đăng nhập, Backend hay AI thật.

Yêu cầu Node.js 24 và npm. Từ thư mục gốc:

```bash
cd frontend
npm ci
npm run dev
```

Mở địa chỉ Vite in trong terminal (mặc định `http://localhost:5173`).
Hướng dẫn chi tiết: [frontend/README.md](frontend/README.md).
Checklist và bằng chứng FE-01: [docs/frontend/FE-01.md](docs/frontend/FE-01.md).

Kiểm tra trước khi bàn giao (chạy trong `frontend/`):

```bash
npm run lint
npm run format:check
npm run typecheck
npm test
npm run build
```

Workflow `.github/workflows/frontend.yml` chạy khi có thay đổi frontend trong PR,
push vào `main`/`vantuong`, hoặc chạy thủ công. Cấu hình workflow không đồng nghĩa
CI đã xanh: cần xem kết quả GitHub Actions sau khi được phép push.
