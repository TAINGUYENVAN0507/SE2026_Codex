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
