# Chẩn đoán: vì sao một upload mất ~61 s ở 247 client (AD-018), 2026-11-09

`analysis.md` (lần đo 2026-11-08) để lại câu hỏi chưa trả lời: p95 63,3 s trong khi ở 40 client mỗi upload dưới 1 s. Tài liệu này ghi cách tìm ra nguyên nhân và bằng chứng. Mọi số là một lần chạy trên một máy (12 CPU), pipeline giả; xem phần giới hạn.

## Kết luận

Hai thứ chặn nhau, và chỉ có `DB_POOL_TIMEOUT_SEC` (10 s) phá được vòng chờ:

1. `get_db` (dependency) mở session và giữ **một kết nối DB suốt request**.
2. Endpoint và dependency đồng bộ chạy trong threadpool của AnyIO, **40 thread** mặc định.
3. 247 request cùng đến: các thread đầu tiên chạy `get_current_user`, lấy được kết nối rồi **chờ một thread** cho phần còn lại của request; các thread khác chờ kết nối từ pool. Request giữ kết nối thì không có thread, thread thì đang chờ kết nối.
4. Mỗi 10 s pool timeout cắt một nhóm (503), giải phóng kết nối cho nhóm sau. Upload thành công vì vậy phải chờ nhiều bước 10 s.

Giả thuyết 1 và 3 trong `analysis.md` (ffprobe giữ kết nối, tranh CPU) không phải nguyên nhân chính: `ffprobe` một file mất khoảng 15 ms (10 lần liên tiếp: 0,15 s).

## Bằng chứng

Probe `probe/probe_app.py` bọc `anyio.to_thread.run_sync` để ghi thời gian **chờ có thread** của từng lần gọi (không sửa mã ứng dụng). Chạy `load_vt018.py --clients 247 --app probe_app:app`, log nén ở `probe/exp-a-threadpool-waits.log.gz`:

| Quan sát | Giá trị |
|---|---|
| Lần gọi threadpool | 4508 |
| Chờ thread > 1 s | 408 |
| Chờ thread p95 / p99 / max | 19,97 s / 30,1 s / 39,9 s |
| Các lần chờ > 1 s làm tròn theo bội của 10 s | 1 × 10 s: 111; 2 × 10 s: 197; 3 × 10 s: 63; 4 × 10 s: 37 |
| Upload thành công trong lần chạy này | 97 / 247, p50 61,5 s; 150 lỗi |

Các lần chờ dồn vào bội của 10 s, đúng bằng `DB_POOL_TIMEOUT_SEC`. Chờ do xếp hàng thông thường sẽ trải đều.

## Thử giả thuyết

`probe/probe_limit.py` chỉ cho tối đa N request vào ứng dụng cùng lúc (N nhỏ hơn 40 thread và nhỏ hơn 50 kết nối), phần còn lại chờ ngoài, chưa giữ kết nối:

| Cấu hình | Upload thành công | Lỗi | p50 upload | p95 tất cả |
|---|---|---|---|---|
| Hiện trạng (`probe/exp-a-summary.md`) | 97 | 150 | 61,5 s | 61,7 s |
| Giới hạn 40, 1 process (`probe/exp-b-limit40-summary.md`) | 246 | 0* | 2,57 s | 3,40 s |
| Giới hạn 20 mỗi process, 4 process (`probe/exp-c-limit20-workers4-summary.md`) | 247 | 0 | 1,79 s | 2,02 s |

\* Lần này harness không đếm một client (246 thay vì 247 create, không có lỗi ghi nhận): ngoại lệ HTTP ở bước create làm luồng chết im lặng. Đã sửa trong harness (commit này): lỗi giờ vào `errors` và `error_kinds`.

Giả thuyết đúng ở mức: bỏ vòng chờ thì 61 s thành vài giây và hết lỗi. Việc sửa thật trong mã nằm ở commit sau (`app/core/admission.py`).

## Thay đổi harness trong commit này

- `--app` và `--api-workers` để thử biến thể.
- Lỗi create không còn làm luồng chết im lặng.
- `summary.json` có `error_kinds`.

## Giới hạn

- Một lần chạy mỗi biến thể; chưa lặp để có khoảng tin cậy (lặp ba lần ở phép đo sau sửa).
- Probe chỉ đo thời gian chờ thread, không đo trực tiếp thời gian chờ kết nối; kết luận về kết nối suy ra từ việc các lần chờ dồn vào bội của `DB_POOL_TIMEOUT_SEC` và từ việc giới hạn số request làm hết lỗi.
- Client, API, worker và Postgres chung một máy.
