# Phân tích: 239 client đồng thời (RE-018), lần đo 2026-11-08

Kết quả: **không đạt**. Đây là số đo thật, không chỉnh để đẹp. Chi tiết trong `summary.md`, `raw.csv`, `env.json`.

| Quan sát | Giá trị |
|---|---|
| Upload thành công | 1 trong 102 phản hồi ghi nhận (101 là HTTP 500) |
| Client không ghi nhận phản hồi | 137 (quá 120 s hoặc harness kết thúc trước; chưa phân biệt) |
| Thời gian chạy | 208 s |
| Nguyên nhân 500 | `sqlalchemy.exc.TimeoutError: QueuePool limit of size 5 overflow 10 reached, connection timed out, timeout 30.00` (390 dòng trong log của API) |

## Giải thích

`get_engine()` dùng pool mặc định của SQLAlchemy: 5 kết nối + 10 tràn = 15, chờ tối đa 30 s. Mỗi request giữ một kết nối trong suốt thời gian upload (ghi file, kiểm tra audio). Khi 239 request cùng tới, phần lớn đứng chờ kết nối quá 30 s và API trả 500.

Hai điểm cần sửa, đều thuộc B (backend):
1. Pool phải cấu hình được và đủ lớn so với `max_connections` của Postgres (mặc định 100).
2. Hết kết nối phải trả `503` kèm `Retry-After`, không phải `500`.

## Lỗi của harness đã gặp và sửa

Lần chạy đầu treo hơn 10 phút: một lượt đăng nhập bị timeout 30 s (argon2 tốn CPU khi 239 lượt cùng lúc) làm luồng đó chết trước `barrier.wait()`, 238 luồng còn lại chờ mãi. Đã sửa: giới hạn 8 lượt đăng nhập đồng thời (ngoài phép đo), bắt mọi lỗi HTTP trước barrier và `abort()` barrier.

Khóa `postgres` trong `env.json` thực ra là phiên bản `psycopg`; đã đổi tên khóa ở harness và ở hai file `env.json` đã sinh (nội dung giá trị không đổi).

## Giới hạn

Một lần chạy, một worker uvicorn, pipeline giả, mọi thành phần chung một máy 12 CPU. Số đo này không nói hệ thống "chịu được" hay "không chịu được" 239 người dùng thật: nó chỉ cho thấy cấu hình pool mặc định không đủ cho 239 upload cùng lúc.

## Cập nhật 2026-11-09: sau khi sửa pool và giới hạn request đang xử lý

Chạy lại 239 client với cấu hình mặc định (1 process, `API_MAX_INFLIGHT=40`), `after/`: **239/239 upload thành công, 0 lỗi** (trước đó 1 thành công và 101 lỗi 500). Latency: upload p50 2,56 s, p95 4,36 s; p95 tất cả 3,73 s. Thời gian chạy khoảng 35 s thay vì 208 s. RE-018 không nêu mục tiêu độ trễ cho 239 người dùng; con số 2,0 s ở trên chỉ là mốc tham chiếu của AD-018, và cấu hình này vượt mốc đó. Một lần chạy, cùng giới hạn đo như trên; nguyên nhân và cách sửa ở `../load-247/diagnosis.md`.

## Cập nhật 2026-11-10: trên `main` sau #44, #45

`after-2026-11-10/`: 4 lượt, 239/239 upload, 0 lỗi; p95 upload 2,09 đến 2,37 s; phía server 92 đến 100 % upload xong trong 2,0 s. RE-018 không nêu mục tiêu độ trễ.
