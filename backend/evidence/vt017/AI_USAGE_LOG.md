# AI Usage Log - vòng kiểm chứng 10/11/2026

Công cụ: Codex trong phiên chat hiện tại; Python/pytest/Ruff/coverage, SQLAlchemy/FastAPI TestClient; Git; Typst để dàn PDF. Không khai báo lại tên model của phiên cũ không thể xác minh.

| Prompt/yêu cầu chính | Output được dùng | Review/sửa/bác bỏ | Evidence |
|---|---|---|---|
| Đọc đề và hai bài giảng, kiểm tra code/branch/PR | Audit theo VT-017 | Không dùng bài VT-018 của thành viên khác; đọc quy tắc repo | Báo cáo audit 10/11 và baseline |
| Để hoàn thành toàn bộ yêu cầu, cần làm gì | Kế hoạch test-first mới | Bác bỏ TC08 cũ và suy luận tải production; dùng schema baseline làm oracle | VT017_PLAN.md, commit plan |
| Làm 1 PDF để có thể nộp theo yêu cầu | 16 test gốc được củng cố, 28 lượt API bổ sung, 6 unit metric | Bổ sung thứ tự ID cụ thể; code sản phẩm tái dùng patch cá nhân 30a9326; không đổi framework/dependency sản phẩm | RED 16 fail/28 pass, GREEN50pass |
| Kiểm chứng mutation/coverage/flaky/load | Runner mutation và harness barrier/raw | Mutation auth và tie-breaker phải fail. Cờ pool từng chưa nối vào engine: review source phát hiện, sửa và lưu cả kết quả lỗi | mutations, flaky logs, load/README.md |
| Hoàn thiện nội dung và bố cục PDF | Spec, test table, traceability, reflection, phụ lục | Chỉ ghi số đo thật; tách mô phỏng/production; reflection có AI hỗ trợ soạn, người nộp cần đọc và xác nhận | PDF và log chạy |

Các prompt trên tóm lược yêu cầu trong phiên chat, không giả là bản ghi nguyên văn của phiên 06/11. Không tuyên bố nhóm trưởng hoặc owner A đã approve. Nhánh chưa merge.

Kiểm tra trước phát hành phát hiện một số ghi chú bị mất dấu do encoding của PowerShell pipe; đã sửa nội dung UTF-8 bằng patch trực tiếp, không thay đổi kết quả test hoặc dữ liệu đo.
