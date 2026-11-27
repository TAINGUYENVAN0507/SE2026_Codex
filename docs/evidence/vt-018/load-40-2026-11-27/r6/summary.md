# Kết quả tải VT-018 (40 client đồng thời)

| Loại | n | p50 (s) | p95 (s) | max (s) |
|---|---|---|---|---|
| tạo cuộc họp (upload) | 40 | 0.4702 | 0.483 | 0.4876 |
| poll trạng thái job | 200 | 0.0316 | 0.3125 | 0.3434 |
| tìm kiếm `?q=` | 160 | 0.1976 | 0.3151 | 0.3321 |
| **tất cả** | 240 | 0.038 | **0.4747** | 0.4876 |

Mục tiêu p95 ≤ 1.5 s: upload **PASS** (p95 upload 0.483 s); mọi request gộp upload và poll **PASS** (exit code theo số này). Lỗi: 0 . Từ lúc thả client tới khi xong: 11.85 s. Process sinh tải: 1.
Trạng thái meeting khi kết thúc: {'queued': 36, 'ready': 4}.
Máy sinh tải dùng trung bình 0.24 CPU trong pha upload (được dùng 12). Ghim CPU: server không, client không.

CPU phía server trong pha upload (0.5 s), process dùng ≥ 0,05 CPU: api uvicorn cấp 1: luồng chính 0.3, cả process 1.14.

Tìm kiếm: 4 lượt mỗi client sau upload (wildcard `%`, `_`, `100%` và tiêu đề của client); kết quả sai: **0**. Khi có tìm kiếm, dòng upload phía server gộp cả GET `/api/v1/meetings` (histogram chỉ có nhãn route). Dòng "tất cả" chỉ gộp upload và poll.

Stdout của API: 485 dòng, trong đó 445 dòng access của app, 0 dòng access của uvicorn; dòng có query string: **0**.

Thư mục lưu (thư mục trống của lượt, STORAGE_DIR) có 0 thư mục lúc bắt đầu, 0 lúc kết thúc (đã xóa 45 thư mục audio và artifact của 40 meeting lượt này tạo).
Kết nối nằm rảnh từ lúc đăng nhập tới lúc upload: p50 1.0759 s, max 2.2212 s; 0/40 quá 5 s (timeout keep-alive mặc định của uvicorn). Lỗi upload chi tiết: `summary.json`, khóa `create_error_detail`.

## Phía server (`/metrics`, hiệu giữa lúc thả barrier và lúc mọi client xong)

| Loại | n | trung bình (s) | p50 trong khoảng (s) | p95 trong khoảng (s) | tỷ lệ ≤ 1,5 s | tỷ lệ ≤ 2,0 s |
|---|---|---|---|---|---|---|
| upload, tổng thời gian ở app | 200 | 0.2362 | 0.1 – 0.25 | 0.25 – 0.5 | 1.0 | 1.0 |
| poll, tổng thời gian ở app | 200 | 0.0635 | 0.025 – 0.05 | 0.25 – 0.5 | 1.0 | 1.0 |
| chờ admission (mọi request, không tách route) | 400 | 0.0084 | 0.0 – 0.001 | 0.025 – 0.05 | 1.0 | 1.0 |

Phía client cùng lượt, upload: tỷ lệ ≤ 1,5 s = 1.0, ≤ 2,0 s = 1.0.
Từ bucket chỉ biết quantile nằm trong khoảng; tỷ lệ dưới mốc 1,5 và 2,0 là chính xác vì đó là biên bucket.
Thời gian ở app gồm chờ admission. Client trừ server là phần ngoài app: máy sinh tải, loopback, uvicorn trước middleware.
Số request server đếm / client gửi: create 200/200, poll 200/200 (1 process API).

## Giới hạn của phép đo

- Worker chạy mỗi lúc 1 job, hàng đợi dài dần trong lúc đo; đây là độ trễ của API, không phải thông lượng pipeline.
- Pipeline là fake, audio WAV im lặng 3 giây; chưa phản ánh tải của ASR/diarize thật.
- Client, API, worker và Postgres chung một máy (12 CPU), nên tranh chấp CPU làm số đo xấu hơn môi trường tách riêng.
- Client là thread Python (1 process, 40 thread mỗi process); số phía client gồm cả thời gian chờ GIL của máy sinh tải.
- Một lần chạy, chưa lặp để lấy khoảng tin cậy. Chi tiết máy ở `env.json`, từng request ở `raw.csv`.
