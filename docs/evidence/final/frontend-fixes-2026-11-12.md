# Sửa lỗi phát hiện khi kiểm frontend — 12/11/2026

Nguồn trước sửa: `101f17e5d4cf28fbe3f8303bdee590ff15010820` (main đã đóng băng).
Chỉ sửa lỗi và độ ổn định kiểm thử; không thêm tính năng.

## Bằng chứng trước sửa

- Clone mới: coverage mặc định lần 1 có 292 passed / 4 failed, lần 2 có 294 passed / 2 failed. Các file lỗi: App, Accessibility, BusyUpload và Session.
- Cùng source, một worker: 296/296 passed. Đây là bằng chứng kết quả phụ thuộc lịch chạy; không dùng lượt này để che hai lượt mặc định bị lỗi.
- App và axe vượt timeout 5 giây khi chạy song song. BusyUpload chờ bốn phản hồi nhưng dùng thời hạn tìm nút mặc định 1 giây.
- Đổi assertion logout sang waitFor vẫn không giải quyết cache còn lại. Test trực tiếp `clears residual private queries when the login route is committed` đỏ trước sửa: PRIVATE_CANARY vẫn còn khi màn đăng nhập đã hiện (1 failed, 5 ca khác không được chọn).
- Log trích nguyên thông báo lỗi, không chứa dữ liệu thật: [frontend-test-failures-2026-11-12.log](frontend-test-failures-2026-11-12.log). Log đầy đủ giữ local, hash có trong bản trích.

## Thay đổi

- SessionEvents dọn cache lần cuối sau khi route `/login` commit. Các observer của trang trước không làm cache còn lại trên màn đăng nhập. Không đổi cookie hay contract API.
- Giữ assertion cache rỗng; chờ cập nhật bất đồng bộ. Test hai 401 kiểm cancelQueries đúng một lần để xác nhận một lần bắt đầu kết thúc phiên; cleanup ở login không bị tính nhầm thành lần đăng xuất thứ hai.
- Chỉ tăng timeout hai ca UI/axe nặng lên 15 giây và thời gian tìm nút sau bốn 503 lên 5 giây. Không bỏ assertion, không tăng retry, không skip test hay hạ ngưỡng coverage.

## Sau sửa

- `npm run lint`, `npm run format:check`, `npm run typecheck`, `npm run test:coverage`, `npm run build`: exit 0.
- Toàn bộ cây làm việc, gồm test double-click của việc 3: **298 passed / 49 file**, không skip.
- Coverage lines **86.75%**, branches **81.37%**. Ngưỡng giữ 84.53/79.11.
- Kết quả trên là local, chưa phải CI. Các test trên dùng MSW/jsdom; E2E và ảnh progress được ghi ở báo cáo riêng.
