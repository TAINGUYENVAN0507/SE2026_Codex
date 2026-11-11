# 247 client trên `main` sau #44, #45 (2026-11-10)

Người đo: C. Mục tiêu AD-018: p95 ≤ 2,0 s ở 247 người dùng đồng thời. Code dưới test: `main` tại `fc7d80f` cộng các commit 1–5 của C trong PR #46. Phần app chỉ khác `fc7d80f` ở `app/core/admission.py` và `app/core/metrics.py` (histogram thời gian chờ). Commit trong `env.json` đổi giữa các lượt (`495b1a8`, `9f7cf78`, `7695f24`) vì C commit tài liệu trong lúc đo; `git diff 495b1a8 7695f24 -- backend` rỗng.

Môi trường: 1 máy 12 CPU, Postgres 16 cục bộ `max_connections=100`, 1 worker, pipeline fake, WAV im lặng 3 s. Client, API, worker và Postgres chạy chung máy. Mỗi client đăng nhập (ngoài phép đo), chờ barrier, upload 1 lần, poll 5 lần cách 2 s. Lệnh (trong `backend/`):

```bash
uv run python scripts/load_vt018.py --db postgresql+psycopg://... --clients 247 --threshold 2.0 \
  --api-workers <1|4> --client-procs <1|4> --out <thư mục>
# 4 process: API_MAX_INFLIGHT=20 (4 × 20 = 80 < 100); 4 × 40 bị kiểm tra ngân sách kết nối từ chối khởi động
```

> Đo lại ngày 2026-11-11 sau #47, #48, có số phía server cho 4 process: [`../after-2026-11-11/README.md`](../after-2026-11-11/README.md). Kết quả 4 process của ngày này không lặp lại được hôm sau.

## Kết luận

- **1 process API (cấu hình mặc định): không đạt.** p95 upload 2,25 đến 3,75 s, cả 14 lượt hôm nay đều trên 2,0 s (6 lượt ở loạt đầu, 6 lượt sau, và 2 lượt ở `../client-procs/`).
- **4 process API, `API_MAX_INFLIGHT=20`: đạt ở 10/12 lượt, nhưng sát mốc khi máy bận.** p95 upload 1,08 đến 1,68 s ở loạt đầu; 1,92 đến 2,18 s ở các loạt sau, khi VS Code trên cùng máy dùng khoảng 3,7 CPU (`top` lúc 12:58). Không ghi là đạt chắc chắn.
- **Thay đổi của B (#45, 10 → 6 query mỗi upload) có giúp, nhưng ít.** Chạy xen kẽ trước và sau #45 trong cùng điều kiện, 4 process API: p95 upload 2,10 đến 2,25 s trước, 1,92 đến 2,18 s sau. Cặp nào cũng giảm, trung bình 0,15 s. Không dùng số hôm qua để so, vì máy dao động giữa các thời điểm nhiều hơn mức chênh này.
- **Lỗi: 6 `RemoteProtocolError` trong 27 lượt của thư mục này (6/6.669 upload), do harness chứ không do app.** Ba lỗi có chi tiết đều xảy ra trên kết nối đã rảnh 4,938 s, 4,997 s và 4,998 s, tức đúng lúc hết `timeout_keep_alive` 5 s mặc định của uvicorn. Khoảng 178/247 kết nối rảnh quá 5 s vì phải chờ mọi client đăng nhập xong. Server đóng kết nối rảnh đúng lúc client gửi upload. Gửi riêng lẻ trên 1 kết nối, nghỉ 4,90 đến 5,10 s, thì không gặp lỗi nào trong 42 lần (`keepalive/repro-output.md`). Có vẻ cần máy đang bận thì mới xảy ra. Đường thật đi qua nginx (`infra/docker/nginx.conf`) không dùng lại kết nối tới uvicorn, vì không có `upstream … keepalive`.

## Loạt đầu, 12:37 đến 12:43

Server: tỷ lệ và khoảng p95 lấy từ `/metrics`, chỉ có khi chạy 1 process API.

| Lượt | Process API × `API_MAX_INFLIGHT` | Process sinh tải | Upload n | p50 upload (s) | p95 upload (s) | Upload ≤ 2,0 s, client | p95 tất cả (s) | Upload ≤ 2,0 s, server | p95 upload ở server (s) | Lỗi | Commit |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `api-workers-1/client-procs-1/run1` | 1 × 40 | 1 | 247 | 1,37 | **2,31** | 72,5 % | 1,86 | 100,0 % | 1,5–2,0 | 0 | `495b1a8` |
| `api-workers-1/client-procs-1/run2` | 1 × 40 | 1 | 247 | 1,57 | **2,39** | 70,5 % | 1,99 | 100,0 % | 1,5–2,0 | 0 | `7695f24` |
| `api-workers-1/client-procs-1/run3` | 1 × 40 | 1 | 246 | 1,46 | **2,25** | 73,2 % | 1,87 | 91,5 % | 2,0–2,5 | 1 {'create:RemoteProtocolError': 1} | `7695f24` |
| `api-workers-1/client-procs-4/run1` | 1 × 40 | 4 | 247 | 1,84 | **2,74** | 63,6 % | 2,24 | 100,0 % | 1,5–2,0 | 0 | `495b1a8` |
| `api-workers-1/client-procs-4/run2` | 1 × 40 | 4 | 247 | 1,51 | **2,9** | 65,6 % | 2,18 | 76,5 % | 2,5–3,0 | 0 | `7695f24` |
| `api-workers-1/client-procs-4/run3` | 1 × 40 | 4 | 247 | 1,39 | **2,32** | 76,5 % | 1,88 | 100,0 % | 1,5–2,0 | 0 | `7695f24` |
| `api-workers-4/client-procs-1/run1` | 4 × 20 | 1 | 247 | 0,8 | **1,31** | 100,0 % | 0,91 | không đo |  | 0 | `495b1a8` |
| `api-workers-4/client-procs-1/run2` | 4 × 20 | 1 | 246 | 0,86 | **1,34** | 100,0 % | 0,96 | không đo |  | 1 {'create:RemoteProtocolError': 1} | `7695f24` |
| `api-workers-4/client-procs-1/run3` | 4 × 20 | 1 | 246 | 0,78 | **1,2** | 100,0 % | 0,94 | không đo |  | 1 {'create:RemoteProtocolError': 1} | `7695f24` |
| `api-workers-4/client-procs-4/run1` | 4 × 20 | 4 | 247 | 1,01 | **1,41** | 100,0 % | 1,27 | không đo |  | 0 | `9f7cf78` |
| `api-workers-4/client-procs-4/run2` | 4 × 20 | 4 | 247 | 1,36 | **1,68** | 100,0 % | 1,53 | không đo |  | 0 | `7695f24` |
| `api-workers-4/client-procs-4/run3` | 4 × 20 | 4 | 247 | 0,73 | **1,08** | 100,0 % | 0,96 | không đo |  | 0 | `7695f24` |

## Các loạt sau, 12:52 đến 12:58 (máy bận hơn)

`keepalive/` là 3 lượt 1 process có ghi thời gian rảnh của kết nối trước upload (`summary.json`, khóa `idle_before_upload` và `create_error_detail`).

| Lượt | Process API × `API_MAX_INFLIGHT` | Process sinh tải | Upload n | p50 upload (s) | p95 upload (s) | Upload ≤ 2,0 s, client | p95 tất cả (s) | Upload ≤ 2,0 s, server | p95 upload ở server (s) | Lỗi | Commit |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `recheck/api-workers-1/run1` | 1 × 40 | 1 | 247 | 2,2 | **3,75** | 39,3 % | 2,93 | 48,2 % | 2,5–3,0 | 0 | `7695f24` |
| `recheck/api-workers-1/run2` | 1 × 40 | 1 | 247 | 2,04 | **3,16** | 49,8 % | 2,68 | 66,0 % | 2,0–2,5 | 0 | `7695f24` |
| `recheck/api-workers-1/run3` | 1 × 40 | 1 | 247 | 2,1 | **3,68** | 46,6 % | 2,77 | 53,0 % | 2,5–3,0 | 0 | `7695f24` |
| `recheck/api-workers-4/run1` | 4 × 20 | 1 | 247 | 1,52 | **2,04** | 91,9 % | 1,71 | không đo |  | 0 | `7695f24` |
| `recheck/api-workers-4/run2` | 4 × 20 | 1 | 247 | 1,38 | **1,94** | 98,8 % | 1,58 | không đo |  | 0 | `7695f24` |
| `recheck/api-workers-4/run3` | 4 × 20 | 1 | 247 | 1,37 | **1,99** | 96,0 % | 1,59 | không đo |  | 0 | `7695f24` |
| `keepalive/idle-run1` | 1 × 40 | 1 | 246 | 2,16 | **3,54** | 44,7 % | 2,8 | 49,6 % | 2,5–3,0 | 1 {'create:RemoteProtocolError': 1} | `7695f24` |
| `keepalive/idle-run2` | 1 × 40 | 1 | 246 | 2,03 | **3,3** | 49,6 % | 2,71 | 58,9 % | 2,5–3,0 | 1 {'create:RemoteProtocolError': 1} | `7695f24` |
| `keepalive/idle-run3` | 1 × 40 | 1 | 247 | 2,2 | **3,35** | 47,0 % | 2,8 | 49,4 % | 2,5–3,0 | 0 | `7695f24` |

## Trước và sau #45, chạy xen kẽ, 12:59 đến 13:03

Cùng harness (bản hiện tại, chép sang worktree `b654a99`), 4 process API, `API_MAX_INFLIGHT=20` qua biến môi trường. Code `b654a99` chưa có `API_WORKERS` trong `Settings` nên `env.json` không ghi được cấu hình.

| Lượt | Process API × `API_MAX_INFLIGHT` | Process sinh tải | Upload n | p50 upload (s) | p95 upload (s) | Upload ≤ 2,0 s, client | p95 tất cả (s) | Upload ≤ 2,0 s, server | p95 upload ở server (s) | Lỗi | Commit |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `ab-45/after-7695f24/run1` | 4 × 20 | 1 | 247 | 1,52 | **2,18** | 89,1 % | 1,66 | không đo |  | 0 | `7695f24` |
| `ab-45/after-7695f24/run2` | 4 × 20 | 1 | 247 | 1,25 | **1,92** | 99,2 % | 1,56 | không đo |  | 0 | `7695f24` |
| `ab-45/after-7695f24/run3` | 4 × 20 | 1 | 246 | 1,29 | **1,92** | 99,6 % | 1,64 | không đo |  | 1 {'create:RemoteProtocolError': 1} | `7695f24` |
| `ab-45/before-b654a99/run1` | 4 × 20 (biến môi trường) | 1 | 247 | 1,5 | **2,25** | 85,4 % | 1,78 | không đo |  | 0 | `b654a99` |
| `ab-45/before-b654a99/run2` | 4 × 20 (biến môi trường) | 1 | 247 | 1,43 | **2,14** | 89,5 % | 1,7 | không đo |  | 0 | `b654a99` |
| `ab-45/before-b654a99/run3` | 4 × 20 (biến môi trường) | 1 | 247 | 1,53 | **2,1** | 85,4 % | 1,81 | không đo |  | 0 | `b654a99` |

## Giới hạn

- Một máy, chung CPU với máy sinh tải và trình soạn thảo. Kết quả thay đổi theo thời điểm (1 process: 2,25 s ở loạt đầu, 3,75 s ở loạt sau).
- Tải là barrier: cả 247 client upload cùng một lúc. Đây là trường hợp xấu nhất cho upload, không phải mô hình người dùng thật.
- Số phía server chỉ có khi chạy 1 process: với nhiều process, `/metrics` chỉ là của một process (B làm ở Đợt 5).
- Pipeline fake. Không nói gì về thông lượng ASR thật.
