# Phân tích: 247 client đồng thời so với p95 ≤ 2,0 s (AD-018), lần đo 2026-11-08

> **Cập nhật 2026-11-09:** nguyên nhân 63 s đã tìm ra, xem [`diagnosis.md`](diagnosis.md); số đo sau khi sửa ở [`after/README.md`](after/README.md). Ba giả thuyết bên dưới là của hôm 2026-11-08: giả thuyết 1 không phải nguyên nhân chính (`ffprobe` ~15 ms), giả thuyết 2 gần đúng nhất, giả thuyết 3 chưa loại được.

Kết quả: **không đạt**. Số đo thật, một lần chạy; `summary.md`, `raw.csv`, `env.json` nằm cùng thư mục.

## So với lần đo 239 (trước khi sửa pool)

| | 239 client, pool 5+10 | 247 client, pool 20+30 |
|---|---|---|
| Upload thành công (201) | 1 | 91 |
| Upload bị từ chối | 101 × **500** (`QueuePool limit ... reached`) | 155 × **503** `SERVICE_UNAVAILABLE` kèm `Retry-After` |
| p95 toàn bộ | 91,5 s | 63,3 s |
| Thời gian chạy | 208 s | 98 s |

Hai lần đo khác số client (239 và 247) nên so sánh chỉ mang tính chiều hướng.

## Đã sửa trong lần này

- Pool kết nối cấu hình được (`DB_POOL_SIZE`=20, `DB_MAX_OVERFLOW`=30, `DB_POOL_TIMEOUT_SEC`=10), tổng 50 < `max_connections` 100 của Postgres.
- Hết kết nối trả `503 SERVICE_UNAVAILABLE` (mã có sẵn trong `contracts/error_codes.md`) kèm `Retry-After: 2`, thay vì 500. Test đỏ trước khi sửa: `01-red.log`.
- Khi quá tải không còn lỗi 500 nào trong lần đo này.

## Chưa đạt và chưa biết vì sao

Một upload thành công mất tới ~63 s (p50 62,9 s), trong khi ở 40 client mỗi upload dưới 1 s. Thời gian tăng vọt hơn nhiều so với tỷ lệ số client, và **chưa được lý giải bằng số đo**. Các giả thuyết chưa kiểm:

1. Mỗi upload gọi `ffprobe` và ghi file khi đang giữ kết nối DB, nên pool 50 bị giữ lâu.
2. Chỉ một process uvicorn với bộ thread mặc định (40 thread cho endpoint đồng bộ), nên request xếp hàng chờ thread trước khi chờ kết nối.
3. Client, API, worker và Postgres tranh nhau 12 CPU.

Việc tiếp theo cho B: lấy profile của `POST /meetings` (thời gian giữ kết nối, thời gian `ffprobe`), rồi thử `--workers N` cho uvicorn. Chỉ ghi vào tài liệu "đạt" khi một lần đo cho p95 ≤ 2,0 s.

## Giới hạn

Một lần chạy, một worker pipeline giả, mọi thành phần chung một máy; `ffprobe` cục bộ là bản thật. Không dùng số này để khẳng định hệ thống chịu được hay không chịu được 247 người dùng thật.
