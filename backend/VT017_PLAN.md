# VT-017: kế hoạch hoàn thiện ngày 10/11/2026

## Phạm vi và baseline
Baseline: 2dea2bfdfea220d0492cedbd56d30340ed41f0b6. Nhánh bài tập độc lập, không merge vào main. Tái thực hiện slice tìm kiếm metadata trên baseline để lưu chứng cứ test-first mới, không giả định các thao tác ngày 06/11 đã được chứng minh.

## Prompt và giả định
Yêu cầu hiện tại: hoàn thiện PDF nộp BT3 VT-017 với code/test và bằng chứng thật. Ràng buộc: patch nhỏ, giữ FastAPI/SQLAlchemy, không thêm dependency sản phẩm. Giả định: tìm tiêu đề không phân biệt hoa thường ASCII; Unicode phụ thuộc DB/collation, chưa cam kết unaccent. Tập dữ liệu không đổi giữa các trang. Các filter tùy chọn là phép giao. meeting_date null dùng ngày created_at UTC trong harness SQLite.

## Đề xuất ban đầu được review
1. Dùng test TC08 cũ đủ bảo vệ tie-breaker: bác bỏ. Audit bỏ id mà TC08 vẫn pass; test mới phải assert thứ tự ID cố định, insert khác thứ tự ID.
2. Dùng schema hiện tại làm oracle tương thích cũ: sửa. Đóng băng JSON Schema response từ OpenAPI baseline; thử lỗi đổi tên page_size và thêm field. Không tự kết luận mọi client cũ tương thích chỉ vì drift pass.
3. Đo TestClient/SQLite rồi suy ra PostgreSQL dưới 3s: bác bỏ. Chỉ kết luận trong mô phỏng; lưu seed, raw latency, barrier, peak in-flight và môi trường.

## Thứ tự thực hiện trước khi patch
- Lưu plan này.
- Viết test API/BVA/legacy contract, dùng fixtures của chính bài VT-017; chạy trên baseline và lưu RED.
- Port lại service và route từ commit cá nhân 30a932665e1c4689cd7b169bbc3371acd782741d, không viết lại framework; sinh OpenAPI từ app.
- Bổ sung harness tải và mutation có thể chạy lại, chạy GREEN và quality gates. Bỏ auth trên nhánh mutation tạm; không đưa lỗi vào nhánh nộp.
- Chạy lặp/đảo thứ tự test và coverage nếu công cụ sẵn có; báo skip/fail thật. PDF tối đa 8 trang chính, appendix riêng.

## File dự kiến
- backend/tests/api/test_meeting_search_pagination.py: giữ 16 test cá nhân gốc và tăng oracle thứ tự.
- backend/tests/api/test_vt017_evidence.py: test mới cho BVA, filter, frozen contract và workflow API.
- backend/tests/fixtures/vt017/legacy-response.schema.json: schema từ baseline.
- backend/app/services/meeting_search.py: service hiện có của cá nhân.
- backend/app/api/v1/meetings.py: query tùy chọn, route gọi service.
- backend/scripts/run_load_test.py: harness với seed/barrier/raw samples.
- backend/scripts/check_vt017_mutations.py: thí nghiệm cô lập.
- backend/VT017_README.md và backend/evidence/vt017/: lệnh, log và dữ liệu tổng hợp.
- contracts/openapi.json: chỉ sinh từ nguồn. Không sửa pipeline/frontend thuộc owner khác; phần kiểm thử consumer cũ dùng schema baseline độc lập.

## Invariant và kiểm chứng
Response giữ items/page/page_size/total và item DTO cũ. Mọi item/count chỉ thuộc owner. Sort primary + id cùng chiều; page>=1, size 1..100. Không bảo đảm snapshot pagination khi có concurrent writes. API workflow dùng database giả lập và auth override; không gắn nhãn browser E2E.
