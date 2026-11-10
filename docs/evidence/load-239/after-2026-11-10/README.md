# 239 client trên `main` sau #44, #45 (RE-018, 2026-11-10)

RE-018 yêu cầu chịu được 239 người dùng đồng thời và không nêu mục tiêu độ trễ; mốc 2,0 s trong bảng chỉ để tham chiếu với AD-018. Cùng điều kiện với `../../load-247/after-2026-11-10/README.md`: 1 process API (`API_MAX_INFLIGHT=40`), 1 worker, pipeline fake, một máy 12 CPU.

```bash
cd backend && uv run python scripts/load_vt018.py --db postgresql+psycopg://... --clients 239 --threshold 2.0 [--client-procs 4] --out <thư mục>
```

| Lượt | Process API × `API_MAX_INFLIGHT` | Process sinh tải | Upload n | p50 upload (s) | p95 upload (s) | Upload ≤ 2,0 s, client | p95 tất cả (s) | Upload ≤ 2,0 s, server | p95 upload ở server (s) | Lỗi | Commit |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `client-procs-1/run1` | 1 × 40 | 1 | 239 | 1,44 | **2,37** | 69,5 % | 2,04 | 92,0 % | 2,0–2,5 | 0 | `eefe800` |
| `client-procs-1/run2` | 1 × 40 | 1 | 239 | 1,4 | **2,27** | 77,8 % | 1,95 | 100,0 % | 1,5–2,0 | 0 | `eefe800` |
| `client-procs-1/run3` | 1 × 40 | 1 | 239 | 1,31 | **2,09** | 84,9 % | 1,79 | 100,0 % | 1,5–2,0 | 0 | `eefe800` |
| `client-procs-4/run1` | 1 × 40 | 4 | 239 | 1,29 | **2,13** | 84,9 % | 1,75 | 100,0 % | 1,5–2,0 | 0 | `eefe800` |

- **239/239 upload thành công, 0 lỗi** ở cả 4 lượt (ngày 2026-11-08, trước khi sửa: 1 thành công, 101 lỗi 500).
- p95 upload 2,09 đến 2,37 s (2026-11-09: 4,36 s, một lượt). Phía server, 92 đến 100 % upload xong trong 2,0 s.
- Không có `RemoteProtocolError` ở 4 lượt này. Lỗi đó (`../../load-247/after-2026-11-10/README.md`) là của harness và hiếm, nên 4 lượt không đủ để kết luận nó không xảy ra ở 239.
