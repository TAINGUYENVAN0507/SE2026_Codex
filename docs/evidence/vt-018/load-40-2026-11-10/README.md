# 40 client trên `main` sau #44, #45 (VT-018, 2026-11-10)

Mục tiêu VT-018: p95 ≤ 1,5 s ở 40 người dùng đồng thời. Cùng điều kiện với `../../load-247/after-2026-11-10/README.md`: một máy 12 CPU, 1 process API (`API_MAX_INFLIGHT=40`), 1 worker, pipeline fake. 3 lượt, mỗi lượt dựng lại DB trống.

```bash
cd backend && uv run python scripts/load_vt018.py --db postgresql+psycopg://... --clients 40 --threshold 1.5 --out <thư mục>
```

| Lượt | Process API × `API_MAX_INFLIGHT` | Process sinh tải | Upload n | p50 upload (s) | p95 upload (s) | Upload ≤ 2,0 s, client | p95 tất cả (s) | Upload ≤ 2,0 s, server | p95 upload ở server (s) | Lỗi | Commit |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `run1` | 1 × 40 | 1 | 40 | 0,34 | **0,36** | 100,0 % | 0,34 | 100,0 % | 0,25–0,5 | 0 | `eefe800` |
| `run2` | 1 × 40 | 1 | 40 | 0,39 | **0,41** | 100,0 % | 0,39 | 100,0 % | 0,25–0,5 | 0 | `eefe800` |
| `run3` | 1 × 40 | 1 | 40 | 0,34 | **0,36** | 100,0 % | 0,35 | 100,0 % | 0,25–0,5 | 0 | `eefe800` |

**Đạt ở cả 3 lượt**: p95 upload 0,36 đến 0,41 s, 0 lỗi. Phía server, 100 % upload xong trong 1,5 s (biên bucket). Lần trước: 0,65 s (`../load-40-after/`, 2026-11-09, một lượt). Không tách được phần giảm do #45 và phần do trạng thái máy.

Giới hạn như mọi lần đo khác: chung một máy, tải dạng barrier, pipeline fake.
