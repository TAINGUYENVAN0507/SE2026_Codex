# Kết quả tải VT-018 (247 client đồng thời)

| Loại | n | p50 (s) | p95 (s) | max (s) |
|---|---|---|---|---|
| tạo cuộc họp (upload) | 247 | 1.8983 | 2.9628 | 2.9967 |
| poll trạng thái job | 1235 | 0.0143 | 0.0898 | 0.1686 |
| tìm kiếm `?q=` | 988 | 0.8401 | 1.302 | 1.7304 |
| **tất cả** | 1482 | 0.0194 | **2.3217** | 2.9967 |

Mục tiêu p95 ≤ 2.0 s: upload **FAIL** (p95 upload 2.9628 s); mọi request gộp upload và poll **FAIL** (exit code theo số này). Lỗi: 0 . Từ lúc thả client tới khi xong: 16.31 s. Process sinh tải: 4.
Trạng thái meeting khi kết thúc: {'queued': 100}.
Máy sinh tải dùng trung bình 0.43 CPU trong pha upload (được dùng 12). Ghim CPU: server không, client không.

CPU phía server trong pha upload (3.04 s), process dùng ≥ 0,05 CPU: api python cấp 2: luồng chính 0.25, cả process 0.98; api python cấp 2: luồng chính 0.27, cả process 0.97.

Tìm kiếm: 4 lượt mỗi client sau upload (wildcard `%`, `_`, `100%` và tiêu đề của client); kết quả sai: **0**. Khi có tìm kiếm, dòng upload phía server gộp cả GET `/api/v1/meetings` (histogram chỉ có nhãn route). Dòng "tất cả" chỉ gộp upload và poll.

Stdout của API: 2969 dòng, trong đó 2722 dòng access của app, 0 dòng access của uvicorn; dòng có query string: **0**.

Thư mục lưu (thư mục trống của lượt, STORAGE_DIR) có 0 thư mục lúc bắt đầu, 0 lúc kết thúc (đã xóa 254 thư mục audio và artifact của 247 meeting lượt này tạo).
Kết nối nằm rảnh từ lúc đăng nhập tới lúc upload: p50 7.554 s, max 15.0839 s; 164/247 quá 5 s (timeout keep-alive mặc định của uvicorn). Lỗi upload chi tiết: `summary.json`, khóa `create_error_detail`.

## Phía server (`/metrics`, hiệu giữa lúc thả barrier và lúc mọi client xong)

| Loại | n | trung bình (s) | p50 trong khoảng (s) | p95 trong khoảng (s) | tỷ lệ ≤ 1,5 s | tỷ lệ ≤ 2,0 s |
|---|---|---|---|---|---|---|
| upload, tổng thời gian ở app | 1235 | 0.9693 | 0.75 – 1.0 | 1.5 – 2.0 | 0.8899 | 0.9976 |
| poll, tổng thời gian ở app | 1235 | 0.0208 | 0.01 – 0.025 | 0.05 – 0.1 | 1.0 | 1.0 |
| chờ admission (mọi request, không tách route) | 2470 | 0.3262 | 0.0 – 0.001 | 1.0 – 1.5 | 1.0 | 1.0 |

Phía client cùng lượt, upload: tỷ lệ ≤ 1,5 s = 0.3239, ≤ 2,0 s = 0.6478.
Từ bucket chỉ biết quantile nằm trong khoảng; tỷ lệ dưới mốc 1,5 và 2,0 là chính xác vì đó là biên bucket.
Thời gian ở app gồm chờ admission. Client trừ server là phần ngoài app: máy sinh tải, loopback, uvicorn trước middleware.
Số request server đếm / client gửi: create 1235/1235, poll 1235/1235 (2 process API).

## Giới hạn của phép đo

- Worker chạy mỗi lúc 1 job, hàng đợi dài dần trong lúc đo; đây là độ trễ của API, không phải thông lượng pipeline.
- Pipeline là fake, audio WAV im lặng 3 giây; chưa phản ánh tải của ASR/diarize thật.
- Client, API, worker và Postgres chung một máy (12 CPU), nên tranh chấp CPU làm số đo xấu hơn môi trường tách riêng.
- Client là thread Python (4 process, 62 thread mỗi process); số phía client gồm cả thời gian chờ GIL của máy sinh tải.
- Một lần chạy, chưa lặp để lấy khoảng tin cậy. Chi tiết máy ở `env.json`, từng request ở `raw.csv`.
