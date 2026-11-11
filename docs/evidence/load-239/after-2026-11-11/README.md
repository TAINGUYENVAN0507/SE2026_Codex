# 239 client trên `main` sau #47, #48 (RE-018, 2026-11-11)

RE-018 yêu cầu chịu được 239 người dùng đồng thời và không nêu mục tiêu độ trễ. Mốc 2,0 s chỉ để đối chiếu với AD-018. Cấu hình: 1 process API (`API_MAX_INFLIGHT=40`, mặc định), 4 process sinh tải, 1 worker, pipeline fake, một máy 12 CPU. App là `main` `1f9d1ca`, harness ở commit 1 và 2 của C hôm nay; `env.json` ghi `527938c`, `git diff 1f9d1ca 527938c -- backend/app` rỗng. Chạy xen kẽ với các lượt 40 client (`run-log.txt`), nghỉ 20 s giữa các lượt.

```bash
cd backend && uv run python scripts/load_vt018.py --db postgresql+psycopg://... --clients 239 --threshold 2.0 --client-procs 4 --out <thư mục>
```

| Lượt | Upload n | p50 upload (s) | p95 upload (s) | Upload ≤ 2,0 s server | Server đếm / client gửi | Lỗi |
|---|---|---|---|---|---|---|
| `run1` | 239 | 1,75 | 3,25 | 86,6 % | 239/239 | 0 |
| `run2` | 239 | 1,65 | 3,03 | 65,3 % | 239/239 | 0 |
| `run3` | 239 | 1,86 | 3,15 | 59,8 % | 239/239 | 0 |

- **Đạt RE-018 (chịu được): 239/239 upload thành công, 0 lỗi ở cả 3 lượt.**
- Độ trễ cao hơn ngày 11-10: p95 upload 3,03 đến 3,25 s, so với 2,09 đến 2,37 s. Không so trực tiếp hai ngày. A/B xen kẽ ở 247 client hôm nay (`../../load-247/after-2026-11-11/README.md`) cho thấy cả bản trước #48 cũng chậm hơn hôm qua. Cùng lúc đó máy bận hơn (load average lúc bắt đầu lượt 2,2 đến 3,2, cộng VS Code và trình duyệt).
- Khi kết thúc, 100 meeting đầu trong danh sách đều ở `queued`. Worker chạy mỗi lúc 1 job, nên đây là hàng đợi pipeline chứ không phải lỗi.
