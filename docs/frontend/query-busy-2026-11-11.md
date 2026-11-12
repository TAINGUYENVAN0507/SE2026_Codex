# Query đọc dữ liệu khi API bận — 11/11/2026

## Retry chung (AD-018, FE-16)

`AppProviders` chỉ thử lại query khi lỗi là `ApiError` có HTTP 503 hoặc code
`NETWORK_ERROR`. Tối đa hai lần retry sau request đầu. Mỗi lần chờ theo
`retryAfterMs` được parse từ header `Retry-After`; thiếu header thì chờ 2 giây.
401/403/404/422, lỗi 500 và exception không phải ApiError không tự thử lại.
Mutation vẫn không retry tự động. `useJobQuery` giữ `retry: false` và lịch
poll riêng; không cộng hai cơ chế retry.

`QueryRetry.test.tsx` lấy QueryClient từ AppProviders thật, dùng MSW và clock
giả: kiểm request thứ hai ở đúng 3 giây khi Retry-After=3, 4xx/500 chỉ một
request, 503/network có tối đa ba request và fallback 2 giây. Không gọi API thật.
Chạy trước sửa: **9 test đỏ** trên cấu hình cũ; sau sửa kiểm lại cùng test.
Kết quả gate toàn bộ module được ghi trong thân commit và báo cáo tổng kết.

Không thay UI library, dependency, OpenAPI hoặc pipeline. Các lần tự retry là
request đọc dữ liệu, không tự gửi lại thao tác ghi/xóa.

## Danh sách và chi tiết (AD-018, FE-16)

Danh sách đã có thông báo an toàn và nút refetch trước đợt này: không sửa lại
component đó, chỉ bổ sung test. Trang chi tiết thêm nút Thử lại, refetch cả
meeting và transcript, giữ đường về danh sách; 404 vẫn dùng trang không tìm thấy.

`BusyReads.test.tsx` dùng provider thật + MSW: 503 liên tục phải có đúng ba
request, hết skeleton và thấy thông báo/nút. Sau khi API phục hồi, bấm nút
hiện dữ liệu. Kiểm riêng danh sách, GET meeting và GET transcript. Trước sửa:
danh sách đạt, hai ca chi tiết đỏ vì thiếu nút; sau sửa kiểm lại cùng test.

## Thông báo và focus (FE-16)

- Upload đang chờ: vùng status có sẵn, giữ nguyên node và tên Trạng thái tải lên.
- Poll vẫn có progress cũ: status (polite) có tên Trạng thái kết nối tiến độ,
  không ngắt người dùng. Khi chưa có job hoặc lỗi không retry, giữ alert.
- Lưu transcript/tên speaker/tóm tắt, retry summary, xóa và lỗi trang đọc:
  thao tác bị chặn dùng alert. Không gọi focus vào thông báo mới xuất hiện.
- Trang lỗi chi tiết giữ main landmark; alert chỉ bao thông báo bên trong,
  các nút phục hồi ở ngoài alert. Giữ khoảng cách và palette đã duyệt.

Test mở rộng ngay các ca MSW hiện có, không tạo bản sao để tăng số lượng:
getByRole status/alert, giữ focus của điều khiển đang dùng, draft và đường retry.
Bốn regression đỏ trước sửa: hai poll cần status có tên, hai lỗi chi tiết mất
main landmark do role alert đặt trực tiếp trên main. Các alert upload/sửa đã
đúng nên chỉ tăng kiểm tra hành vi/focus, không viết lại component đó.

ARIA và focus tự động không chứng nhận screen reader/điện thoại thật; lượt
browser riêng kiểm bố cục desktop/mobile và semantics trên DOM thật.

Browser axe phát hiện đoạn thông báo lỗi ở danh sách chỉ tương phản 3.82:1 (12px, màu #7b8390 trên trắng) tại cả 1280px/360px. Chỉ chỉnh đoạn thông báo lỗi dùng màu muted hiện tại và 16px; không đổi palette, tên web hoặc cỡ chữ toàn ứng dụng.

Sau sửa, browser kiểm 6 view (list/detail/poll × 1280×900 và 360×900): 0 violation axe, không tràn ngang, trang lỗi phục hồi sau nút Thử lại; poll giữ 65% và focus. Xem [JSON bằng chứng](accessibility-busy-2026-11-11.json). Ảnh tổng hợp mới ở `.preview-stitch/anh-duyet/2026-11-11/` ngoài Git; không dùng response giả lập để tuyên bố backend chịu tải.
