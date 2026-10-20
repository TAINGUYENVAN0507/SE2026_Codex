# structure/

Cấu trúc chung của *Vietnamese Meeting Minutes Assistant*. **Mọi thành viên, kể cả AI coding assistant của từng người, đọc thư mục này và [`rules/`](../rules/README.md) trước khi code.**

## Thứ tự đọc

| # | File | Trả lời câu hỏi |
|---|---|---|
| 1 | [repository.md](repository.md) | Thư mục nào của ai? File mới đặt ở đâu? Cái gì không được commit? |
| 2 | [architecture.md](architecture.md) | Hệ thống gồm những thành phần nào? Dữ liệu đi qua đâu? Module nào được gọi module nào? |
| 3 | [contracts.md](contracts.md) | Các module trao đổi dữ liệu qua file nào? Quy ước dữ liệu chung là gì? Đổi contract thế nào? |
| 4 | [../rules/README.md](../rules/README.md) | Checklist trước khi code. Quy tắc nhánh, commit, PR, code, test, privacy. |

Sau đó đọc README của module mình sắp sửa (`frontend/`, `backend/`, `pipeline/`, `evaluation/`).

## Quan hệ với kế hoạch triển khai

Task ID (`FE-xx`, `BE-xx`, `AI-xx`, `SH-xx`), scope, timeline và acceptance criteria lấy theo kế hoạch triển khai MVP (report 001 của nhóm trưởng).

`structure/` và `rules/` chốt lại các quy ước của kế hoạch theo thực tế trong repo. Khi hai nơi nói khác nhau, theo `structure/` và `rules/`. Những điểm đã đổi so với kế hoạch:

| Chủ đề | Kế hoạch 001 | Quy định hiện hành |
|---|---|---|
| Nhánh | `feat/<TaskID>-<slug>`, sống tối đa 3 ngày | Mỗi người một nhánh cá nhân ([git-workflow.md](../rules/git-workflow.md)) |
| Merge | Squash merge | Merge commit, không squash |
| Review | 1 thành viên khác approve | Nhóm trưởng review và merge mọi PR |
| Tài liệu | `docs/` | `docs/` là tài liệu chung, được commit. Ghi chú cá nhân để ở `reports/`, không commit. |
| Quy ước chung (G0) | `docs/adr/0000-conventions.md` | Thay bằng `structure/` và `rules/` |
| Bố cục frontend | `src/features/*` | Theo code của A: `app/`, `components/`, `pages/`, `features/` ([repository.md](repository.md)) |
| Transcript tham chiếu của cuộc họp nội bộ | `evaluation/datasets/refs/` | Không commit, vì repo public ([privacy-security.md](../rules/privacy-security.md)) |

## Cập nhật

- PR nào đổi cấu trúc (thêm thư mục cấp 1, đổi ranh giới module, đổi contract) thì sửa file tương ứng ở đây trong cùng PR.
- Muốn đổi quy tắc chung: mở PR sửa `structure/` hoặc `rules/`. Nhóm trưởng merge và báo cả nhóm.
