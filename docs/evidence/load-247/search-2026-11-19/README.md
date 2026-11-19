# 247 client có tìm kiếm `?q=` trên `main` sau #66 và #67: 1, 2 và 4 process API (AD-018, BE-05, 2026-11-19)

Người đo: C. Mục tiêu AD-018: p95 upload ≤ 2,0 s ở 247 người dùng đồng thời.

Từ #64 ô tìm gửi `q` lên API. #67 escape `%`, `_` và `\`. Ngày 11-17 harness chưa gọi `?q=`, nên chưa có số đo nào cho phần tìm kiếm dưới tải. Hôm nay harness có `--search` (`dde0a52`): sau upload, mỗi client gửi 4 lượt `GET /api/v1/meetings?q=`. Bốn từ khóa xoay vòng là `%`, `_`, `100%` và tiêu đề của chính client (`Tải i`). Ba wildcard phải ra 0 kết quả, tiêu đề phải ra ít nhất 1; sai thì tính lỗi `search_wrong`.

- **Code:** `main` `006fd8c`; `env.json` ghi `dde0a52` (thêm commit harness của C, `backend/app` như `006fd8c`).
- **Cấu hình:** như [`../api-log-2026-11-17/README.md`](../api-log-2026-11-17/README.md), thêm `--search 4`: 1 máy 12 CPU, Postgres 16 cục bộ mới khởi tạo, pipeline fake, WAV im lặng 3 s, 4 process sinh tải, không ghim CPU. 4 process API dùng `API_MAX_INFLIGHT=20`.
- **Thứ tự:** hình vuông Latin, 3 vòng ([`run.sh`](run.sh), [`run-log.txt`](run-log.txt)), 12:46 đến 12:53. Load average lúc bắt đầu lượt từ 1,4 (lượt đầu) lên tới 19,2, cao hơn 11-17 (2,8 đến 11,1).
- **Kết luận dùng p95 upload** (`create` trong `summary.json`).

## Kết quả

| Process API | Vòng | p95 upload (s) | p95 tìm kiếm (s) | CPU từng process API (luồng chính / cả process) |
|---|---|---|---|---|
| 1 | 1 | 3,02 | 1,83 | 0,38 / 1,16 |
| 1 | 2 | 2,28 | 1,70 | 0,35 / 1,15 |
| 1 | 3 | 2,55 | 1,51 | 0,37 / 1,18 |
| 2 | 1 | 2,52 | 0,98 | 0,34 / 1,11; 0,30 / 1,11 |
| 2 | 2 | 1,70 | 0,99 | 0,35 / 1,11; 0,30 / 1,10 |
| 2 | 3 | 1,48 | 1,01 | 0,34 / 1,09; 0,32 / 1,08 |
| 4 | 1 | 1,10 | 0,75 | 0,35 / 0,94; 0,32 / 0,95; 0,29 / 0,95; 0,31 / 0,94 |
| 4 | 2 | 1,15 | 0,73 | 0,34 / 0,93; 0,35 / 0,93; 0,32 / 0,94; 0,28 / 0,93 |
| 4 | 3 | 1,15 | 0,70 | 0,33 / 0,97; 0,31 / 0,98; 0,32 / 0,95; 0,33 / 0,95 |

Mỗi lượt có 247 upload, 1.235 poll và 988 tìm kiếm. Cả 9 lượt: **0 lỗi, 0 kết quả tìm sai**.

- **1 process: 3/3 trên mốc** (2,28 đến 3,02 s). Ngày 11-17, chưa có tìm kiếm: 2,12 đến 2,29 s.
- **2 process: 2/3 đạt** (1,48 và 1,70 s). Lượt vòng 1 ra 2,52 s, lúc bắt đầu load 4,6 và lúc kết thúc 16,6. Ngày 11-17, chưa có tìm kiếm: 3/3 đạt, 1,38 đến 1,41 s.
- **4 process: 3/3 đạt** (1,10 đến 1,15 s). Ngày 11-17: 1,01 đến 1,11 s.
- 988 lượt tìm kiếm mỗi lượt đo làm upload chậm hơn ở 1 và 2 process, vì tìm kiếm chen vào lúc các client khác còn đang upload. Ở 4 process gần như không đổi. Load máy hôm nay cao hơn 11-17, nên chưa tách được bao nhiêu phần chậm do tìm kiếm và bao nhiêu do máy.
- **Mỗi lượt tìm có kết quả tốn khoảng 12 truy vấn:** `GET /meetings` chạy 1 truy vấn đếm, 1 truy vấn trang và 1 truy vấn `Job` cho **mỗi** cuộc họp trong trang (`serialize_meeting_summary`, `backend/app/api/v1/meetings.py:70`, N+1). Ba wildcard ra 0 kết quả nên chỉ tốn 2 truy vấn. Chưa có test ngân sách truy vấn cho danh sách (`test_poll_query_budget.py` chỉ phủ job và chi tiết cuộc họp).

## Tìm kiếm dưới tải và log của API

- **Kết quả tìm:** 3 × 988 = 2.964 lượt tìm trên `main`, 0 lượt sai. `%`, `_` và `100%` đều ra 0, tiêu đề đều ra ít nhất 1.
- **Đối chứng trước #67** ([`before-67/`](before-67/)): harness này chạy trên `dddbdef` (trước #67), 5 client, `--search 4`. Có 10/20 lượt tìm sai (`search_wrong:%` 5, `search_wrong:_` 5). `100%` không sai, vì không tiêu đề nào chứa `100`. Lượt này cho thấy harness bắt được lỗi cũ. `env.json` của lượt đối chứng ghi `out: before-67` vì nó chạy trong một worktree tạm, rồi được chép vào đây.
- **Log:** mỗi lượt 2.969 dòng stdout của API, **0 dòng access của uvicorn, 0 dòng có query string**. Lần này có 988 request mang `?q=` mỗi lượt, nên đây là kiểm đúng trường hợp đã thiếu ngày 11-17: từ khóa tìm kiếm không lọt vào stdout của API dưới tải.

## Giới hạn

- Như 11-17: một máy, pipeline fake, Postgres chung máy, 3 lượt mỗi cấu hình trong khoảng 7 phút.
- Histogram phía server chỉ có nhãn route, nên ở `summary.md` dòng upload phía server gộp cả GET tìm kiếm (cùng route `/api/v1/meetings`). Kết luận chỉ dùng số phía client.
- Bảng chỉ có 247 cuộc họp và tiêu đề ngắn. Thời gian tìm kiếm với nhiều cuộc họp hơn (ILIKE `%q%` không dùng được chỉ mục) chưa đo.
- Compose vẫn đặt `API_WORKERS: 1` (`docker-compose.yml:36`). Cấu hình này không đạt mốc, kể cả khi không có tìm kiếm.
