# docs/

Tài liệu chung của nhóm, **được commit**. Cấu trúc dự án và quy tắc làm việc nằm ở [`structure/`](../structure/README.md) và [`rules/`](../rules/README.md), không lặp lại ở đây.

| Thư mục | Nội dung | Tên file | Người viết |
|---|---|---|---|
| `adr/` | Quyết định kiến trúc: bối cảnh, các phương án, quyết định, hệ quả | `NNNN-<slug>.md`, ví dụ `0001-asr.md` | Người đề xuất. Nhóm trưởng duyệt khi merge. |
| `frontend/`, `backend/`, `pipeline/`, `evaluation/` | Tài liệu nghiệm thu từng task: phạm vi, đối chiếu acceptance criteria, cách chạy, kết quả kiểm tra | `<TaskID>.md`, ví dụ `frontend/FE-01.md` | Owner của module |
| `evidence/` | Bằng chứng kiểm thử cho GitHub evidence checklist | `wer.md`, `noisy.md`, `audit.md`, `reliability.md`, `privacy.md` | Owner của bộ test |
| `privacy/` | Chính sách dữ liệu: consent, retention, dữ liệu gửi ra ngoài, quy trình xóa | `data-policy.md` | B, cả nhóm review |
| `milestones/` | Biên bản các mốc tích hợp | `M0.md` … `M4.md` | Cả nhóm |
| `demo/` | Kịch bản demo, ảnh chụp, link video | — | Cả nhóm |

Quy tắc:

- Chỉ tạo thư mục khi có file đầu tiên.
- Số liệu trong `evidence/` và `adr/` phải đến từ lần chạy thật. Ghi kèm lệnh, đường dẫn kết quả và ngày chạy.
- Không để ghi chú cá nhân hay report theo từng prompt ở đây. Ghi chú cá nhân để trong `reports/`, thư mục này đã nằm trong `.gitignore`.
