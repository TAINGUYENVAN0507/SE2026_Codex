# Lỗi tìm thấy khi chụp tiến độ — 12/11/2026

## Partial nhưng tóm tắt còn pending

Kịch bản API + worker + fake summary_fail ghi nhận job failed và meeting partial,
nhưng GET summary trả pending khi chưa có row Summary. API hiện chỉ đổi giá trị
này sang failed nếu meeting failed (`backend/app/api/v1/summary.py`, nhánh summary None).
Frontend trước đó bỏ thông tin partial khi chuyển sang view model, nên chỉ hiện skeleton
và không có nút tạo lại. Đây là lỗi thực tế của lượt chụp đầu, không phải ảnh mô phỏng.

Sửa trong frontend: giữ cờ summaryFailed từ trạng thái partial; nếu summary vẫn pending,
hiện trạng thái lỗi và nút retry sẵn có. POST retry thành công invalidate meeting/list,
để đọc latest_job_id mới thay vì giữ job failed cũ. Không đổi backend hay OpenAPI.
Test `PartialSummaryRetry.test.tsx` đỏ trước sửa vì không tìm thấy nút, rồi đạt sau sửa.

Backend còn cần thống nhất GET summary cho meeting partial; ghi rõ cho B theo dõi,
không coi là đã sửa API. Frontend chỉ xử lý trường hợp đã biết từ trạng thái partial.

## Queued bị ghi là đang chạy

Ảnh cho thấy job queued, chưa bật worker, nhưng bước sắp tới ghi Đang chạy.
Đổi nhãn bước current của job queued sang Chờ bắt đầu. Hai test trong
`JobStatusCard.test.tsx` (queued toàn bộ và queued từ summarize) đều đỏ trước sửa.
Không đổi CSS, bố cục hay cách tính tiến độ.

Log đỏ: [frontend-progress-failures-2026-11-12.log](frontend-progress-failures-2026-11-12.log).

## Kiểm sau sửa

- Lint, format, TypeScript strict, build: exit 0.
- Toàn bộ cây làm việc, gồm test double-click: **301 passed / 50 file**, không skip.
- Coverage lines **86.78%**, branches **81.63%**; giữ floors 84.53/79.11.
- E2E API/worker/Postgres thật + fake pipeline: chụp đủ queued, running giữa chừng,
  succeeded có hai mốc thời gian, retry summary job failed. Sáu segment giữ nguyên ID,
  số hàng trên transcript khớp; xem [ảnh và cách chạy](../vt-018/ui/README.md).
- Retry chỉ từ summarize bắt đầu ở 5/6 (~83%), giữ năm bước trước. Không ép về 0;
  lượt mới có ID mới, attempt 1, started_at/finished_at null khi queued.

Các lần sửa harness (kỳ vọng nhầm HTTP 201 thay vì 202, và 0% thay vì 5/6) được ghi
trong manifest ảnh, không ghi thành lỗi sản phẩm hay giấu thành lượt chạy xanh đầu tiên.
Đây là kiểm local, chưa xác nhận CI của PR mới.
