# 40 client có tìm kiếm, thư mục lưu trống, trên `main` sau #80 và #81, máy đo đang bận (VT-018, 2026-11-27)

Người đo: C. Mục tiêu VT-018: p95 upload ≤ 1,5 s ở 40 người dùng đồng thời.

- **Code:** `main` `4259a4f` (sau #80, #81). `env.json` ghi `f8ec95c`, tức `main` cộng hai commit test và bằng chứng của C; `backend/app` như `4259a4f`.
- **Cấu hình:** như [`../load-40-2026-11-26/README.md`](../load-40-2026-11-26/README.md): `--search 4`, `--storage temp`, 1 process API, pipeline fake, Postgres 16 cục bộ, một máy 12 CPU.
- **6 lượt liên tiếp** ([`run.sh`](run.sh), [`run-log.txt`](run-log.txt)), nghỉ 15 s, từ 10:08 đến 10:12, ngay sau 10 lượt 247 client.
  - Load average 1 phút lúc bắt đầu lượt: 3,5 đến 5,7.
  - Máy đang được dùng cùng lúc (trình duyệt, VS Code), như ghi ở [`../../load-247/resolve-2026-11-27/README.md`](../../load-247/resolve-2026-11-27/README.md).

## Kết quả

| Lượt | p95 upload (s) | p50 upload (s) | p95 tìm kiếm (s) | Upload trung bình phía server (s) | CPU process API (luồng chính / cả process) |
|---|---|---|---|---|---|
| r1 | 0,53 | 0,51 | 0,29 | 0,25 | 0,31 / 1,12 |
| r2 | 0,82 | 0,80 | 0,54 | 0,38 | 0,26 / 1,06 |
| r3 | 0,69 | 0,66 | 0,34 | 0,30 | 0,31 / 1,20 |
| r4 | 0,79 | 0,77 | 0,35 | 0,31 | 0,23 / 0,91 |
| r5 | 0,46 | 0,44 | 0,45 | 0,27 | 0,34 / 1,19 |
| r6 | 0,48 | 0,47 | 0,32 | 0,24 | 0,30 / 1,14 |

p95 lấy từ `summary.json` (khóa `create`). **6/6 lượt đạt.** 0 lỗi trong 240 upload, 960 lượt tìm kiếm, 0 kết quả sai, 0 dòng có query string.

- p95 upload (0,46 đến 0,82 s) cao hơn và rải rộng hơn ngày 11-26 (r2 đến r6: 0,47 đến 0,53 s), khớp với việc máy đang bận.
- Không lượt nào rơi vào mức chậm 1,4 đến 1,6 s như ngày 11-12 và 11-26.

## Kết luận cho VT-018

Gộp 12 ngày trên `main` (11-11: 6/6, 11-12: 5/6, 11-13: 12/12, 11-15: 16/16, 11-16: 12/12, 11-17: 6/6, 11-19: 6/6, 11-23: 6/6, 11-24: 6/6, 11-25: 6/6, 11-26: 5/6, 11-27: 6/6), chưa tính 4 lượt thêm ngày 11-26: **92/94 lượt đạt** p95 upload ≤ 1,5 s. Hai lượt không đạt (11-12, 11-26) vẫn chưa rõ nguyên nhân.

## Giới hạn

Một máy dùng chung, pipeline fake, client là thread Python, 6 lượt trong 4 phút.
