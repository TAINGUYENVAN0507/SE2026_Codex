# 40 client có tìm kiếm, thư mục lưu trống, trên `main` sau #83 và #84 (VT-018, 2026-11-28)

Người đo: C. Mục tiêu VT-018: p95 upload ≤ 1,5 s ở 40 người dùng đồng thời.

- **Code:** `main` `03f16fb` (sau #83, #84). `env.json` ghi `9edaf3b`, tức `main` cộng hai commit của C; `backend/app` như `03f16fb`.
- **Cấu hình:** như [`../load-40-2026-11-27/README.md`](../load-40-2026-11-27/README.md): `--search 4`, `--storage temp`, 1 process API, pipeline fake, Postgres 16 cục bộ, một máy 12 CPU.
- **6 lượt liên tiếp** ([`run.sh`](run.sh), [`run-log.txt`](run-log.txt)), nghỉ 15 s, từ 16:25 đến 16:29, ngay sau 8 lượt 247 client ([`../../load-247/procs-2026-11-28/README.md`](../../load-247/procs-2026-11-28/README.md)).
  - Load average 1 phút lúc bắt đầu lượt: 3,4 đến 4,8.

## Kết quả

| Lượt | p95 upload (s) | p50 upload (s) | p95 tìm kiếm (s) | Upload trung bình phía server (s) | CPU process API (luồng chính / cả process) |
|---|---|---|---|---|---|
| r1 | 0,64 | 0,62 | 0,37 | 0,33 | 0,30 / 1,20 |
| r2 | 0,68 | 0,66 | 0,44 | 0,34 | 0,30 / 1,21 |
| r3 | 0,73 | 0,69 | 0,40 | 0,34 | 0,32 / 1,21 |
| r4 | 0,71 | 0,69 | 0,37 | 0,33 | 0,30 / 1,18 |
| r5 | 0,62 | 0,59 | 0,41 | 0,32 | 0,33 / 1,21 |
| r6 | 0,62 | 0,60 | 0,40 | 0,32 | 0,31 / 1,22 |

p95 lấy từ `summary.json` (khóa `create`). **6/6 lượt đạt.** 0 lỗi trong 240 upload, 960 lượt tìm kiếm, 0 kết quả sai, 0 dòng có query string.

- Không lượt nào rơi vào mức chậm 1,4 đến 1,6 s như ngày 11-12 và 11-26.

## Kết luận cho VT-018

Gộp 13 ngày trên `main` (11-11: 6/6, 11-12: 5/6, 11-13: 12/12, 11-15: 16/16, 11-16: 12/12, 11-17: 6/6, 11-19: 6/6, 11-23: 6/6, 11-24: 6/6, 11-25: 6/6, 11-26: 5/6, 11-27: 6/6, 11-28: 6/6), chưa tính 4 lượt thêm ngày 11-26: **98/100 lượt đạt** p95 upload ≤ 1,5 s. Hai lượt không đạt (11-12, 11-26) vẫn chưa rõ nguyên nhân.

## Giới hạn

Một máy dùng chung, pipeline fake, client là thread Python, 6 lượt trong 4 phút.
