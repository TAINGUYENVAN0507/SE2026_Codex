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
- Frontend: đã có scaffold FE-01 ở nhánh `vantuong`, chưa vào `main`.
- Backend: chưa bắt đầu.

Chi tiết từng thư mục ở [`structure/repository.md`](structure/repository.md). Mỗi module có README riêng.
