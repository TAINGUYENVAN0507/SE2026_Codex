# 40 client trên `main` sau #47, #48 (VT-018, 2026-11-11)

VT-018: 40 người dùng đồng thời, p95 ≤ 1,5 s. Cấu hình mặc định: 1 process API, 1 process sinh tải, 1 worker, pipeline fake, một máy 12 CPU. Harness ở commit 1 và 2 của C hôm nay.

```bash
cd backend && uv run python scripts/load_vt018.py --db postgresql+psycopg://... --clients 40 --threshold 1.5 --out <thư mục>
```

## `main` (`1f9d1ca`), xen kẽ với 239 client

| Lượt | p50 upload (s) | p95 upload (s) | p95 tất cả (s) | Server đếm / client gửi | Lỗi |
|---|---|---|---|---|---|
| `run1` | 0,63 | 0,66 | 0,64 | 40/40 | 0 |
| `run2` | 0,54 | 0,56 | 0,55 | 40/40 | 0 |
| `run3` | 0,54 | 0,56 | 0,55 | 40/40 | 0 |

## A/B app, xen kẽ, nghỉ 15 s giữa các lượt (`ab-app/`)

`before-40d2431` là `main` trước #47 và #48, chạy từ một git worktree với cùng harness.

| Cặp | trước #48 p95 upload (s) | `main` p95 upload (s) |
|---|---|---|
| 1 | 1,42 | 0,77 |
| 2 | **1,80** | 0,82 |
| 3 | 0,73 | 0,84 |

## Kết luận

- **`main` đạt VT-018 ở cả 6 lượt hôm nay:** p95 upload 0,56 đến 0,84 s, 0 lỗi.
- **Không thấy #48 làm chậm ở 40 client.** Biên an toàn hôm nay nhỏ hơn ngày 11-10 (0,36 đến 0,41 s).
- **Máy dao động mạnh.** Hai lượt của bản trước #48 chậm đều cả đợt: p50 1,40 và 1,77 s, gần bằng max. Có một lượt vượt 1,5 s. Trong lúc đó load average là 8 (`ab-app/run-log.txt`). Một lần đo 40 client trên máy này có thể vượt mốc vì máy bận mà không phải vì code. Vì vậy bảng ghi mọi lượt, không chọn lượt đẹp.
