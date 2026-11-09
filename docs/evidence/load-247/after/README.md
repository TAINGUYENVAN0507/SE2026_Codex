# 247 client sau khi giới hạn request đang xử lý (AD-018), 2026-11-09

Commit đo: `a224812` (hash trong `env.json` là `a0906f0` vì `git rev-parse` chạy khi các thay đổi của commit này chưa được commit). Mỗi cấu hình đo ba lần, mỗi lần dựng lại DB trống. Lệnh:

```bash
cd backend
uv run python scripts/load_vt018.py --db postgresql+psycopg://... --clients 247 --threshold 2.0 --out <thư mục>
API_MAX_INFLIGHT=20 uv run python scripts/load_vt018.py ... --api-workers 4 --out <thư mục>
```

| Cấu hình | Lần | Upload thành công | Lỗi | p50 upload | p95 upload | p95 tất cả | Kết luận harness |
|---|---|---|---|---|---|---|---|
| 1 process, `API_MAX_INFLIGHT=40` (mặc định) | 1 | 247/247 | 0 | 2,23 s | 4,19 s | 3,09 s | FAIL |
| | 2 | 247/247 | 0 | 2,42 s | 4,14 s | 3,10 s | FAIL |
| | 3 | 247/247 | 0 | 2,51 s | 4,21 s | 3,44 s | FAIL |
| 4 process, `API_MAX_INFLIGHT=20` mỗi process | 1 | 247/247 | 0 | 1,60 s | 2,23 s | 1,79 s | PASS |
| | 2 | 247/247 | 0 | 1,66 s | 2,43 s | 1,84 s | PASS |
| | 3 | 247/247 | 0 | 1,58 s | 2,22 s | 1,92 s | PASS |

Trước khi sửa (`../summary.md`): 91 upload thành công, 155 lỗi 503, p95 63,3 s.

## Đọc kết quả cho đúng

- **"p95 tất cả" gồm cả poll.** Mỗi client gửi 1 upload rồi 5 poll, nên poll chiếm 5/6 số request và kéo p95 xuống. Chỉ tính **upload**, p95 là 2,2 đến 2,4 s với 4 process, vẫn trên 2,0 s. Đề AD-018 nói "p95 ≤ 2.0 s" mà không định nghĩa request nào; cách tính ở đây là lựa chọn của harness, và cách tính chỉ-upload nghiêm hơn nên không nên coi 4 lần PASS là đạt theo mọi cách hiểu.
- **Tải là một cú bắn đồng thời** (barrier), không phải lưu lượng ổn định. Pipeline là fake, audio 3 giây; client, API, worker và Postgres chung một máy 12 CPU.
- Cấu hình mặc định (1 process) **không đạt** dù hết lỗi. Chạy 4 process là cấu hình khác, phải đặt `API_MAX_INFLIGHT` theo `max_connections` của Postgres (4 × 20 = 80 < 100).
- Mỗi cấu hình ba lần chạy, chưa đủ để tính khoảng tin cậy.
