# 247 client: máy sinh tải có làm số đo xấu đi không

Ngày 2026-11-10, commit `3283559` (sau #44, #45), 1 process API (`API_MAX_INFLIGHT=40`), 1 worker, pipeline fake, Postgres 16 cục bộ `max_connections=100`, 12 CPU. Mỗi cấu hình **một lượt**.

```bash
cd backend
uv run python scripts/load_vt018.py --db postgresql+psycopg://... --clients 247 --threshold 2.0 --client-procs 1 --out ../docs/evidence/load-247/client-procs/k1
uv run python scripts/load_vt018.py --db postgresql+psycopg://... --clients 247 --threshold 2.0 --client-procs 4 --out ../docs/evidence/load-247/client-procs/k4
```

Trước đây cả 247 client là thread trong **một** process Python. Số phía client vì vậy gồm cả thời gian thread chờ GIL của chính máy sinh tải. `--client-procs 4` chia client ra 4 process (62 thread mỗi process), mọi process đăng nhập xong mới cùng được thả.

| Process sinh tải | p50 upload, client (s) | p95 upload, client (s) | Upload ≤ 2,0 s, client | Upload ≤ 2,0 s, server | Thời gian upload trung bình ở server (s) | Lỗi |
|---|---|---|---|---|---|---|
| 1 (`k1/`) | 2,10 | 3,52 | 44,1 % | 50,2 % | 1,92 | 0 |
| 4 (`k4/`) | 1,90 | 3,06 | 55,5 % | 78,1 % | 1,48 | 0 |

Số phía server lấy từ `/metrics` (`summary.json`, khóa `server`). Tỷ lệ ≤ 2,0 s là chính xác vì 2,0 là biên bucket. p95 thì chỉ biết nằm trong khoảng: phía server, 1 process sinh tải: 2,5–3,0 s; 4 process sinh tải: 2,0–2,5 s.

## Đọc kết quả

- Máy sinh tải có góp phần: với 4 process sinh tải, p95 phía client giảm 0,46 s. Thời gian ở server cũng giảm (1,92 → 1,48 s), vì client và API tranh CPU trên cùng máy.
- Nhưng **cả phía server cũng không đạt** p95 ≤ 2,0 s ở 1 process API: chỉ 50–78 % upload xong trong 2,0 s. Đổi cách sinh tải không biến cấu hình này thành đạt.
- Một lượt mỗi cấu hình, chung một máy; chênh lệch giữa hai lượt có thể một phần là nhiễu. Số lặp 3 lần ở `../after-2026-11-10/`.
- Chờ admission (`api_admission_wait_seconds`) không có nhãn route nên gộp cả upload lẫn poll (1482 request). Số này chỉ dùng để thấy có chờ hay không.
