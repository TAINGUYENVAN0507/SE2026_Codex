# Vietnamese Meeting Minutes Assistant

Web app ghi âm hoặc tải audio cuộc họp tiếng Việt lên, sau đó tạo transcript có timestamp và speaker, tóm tắt cuộc họp và action items. Người dùng chỉnh sửa được kết quả và export ra TXT/JSON/Markdown.

Dự án môn học SE2026, nhóm 3 người.

## Thành viên và phần việc

| Member | Phần việc | Thư mục chính |
|---|---|---|
| A | Frontend, UX, chỉnh sửa, export | `frontend/`, `backend/app/services/export/` |
| B | Backend, API, DB, job orchestration, tích hợp | `backend/`, `contracts/openapi.json`, `tests/`, Docker, CI |
| C | AI/Speech pipeline và evaluation | `pipeline/`, `contracts/pipeline/`, `evaluation/` |

## Trạng thái

Đang ở giai đoạn khởi động. Mỗi phần có README riêng trong thư mục của mình.

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
