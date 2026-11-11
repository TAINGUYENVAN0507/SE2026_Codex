# 247 client trên `main` sau #47, #48 (2026-11-11)

Người đo: C. Mục tiêu AD-018: p95 ≤ 2,0 s ở 247 người dùng đồng thời. Bảng dưới xét **p95 của upload** (`POST /meetings`), giống các ngày trước. Dòng `PASS`/`FAIL` trong `summary.md` tính trên mọi request (upload và poll gộp lại), nên không dùng để kết luận.

- **Code:** app là `main` tại `1f9d1ca`. Harness lấy từ commit 1 và 2 của C hôm nay (`393c934`, ghi trong `env.json`). `git diff 1f9d1ca 393c934 -- backend/app` rỗng.
- **Môi trường:** 1 máy 12 CPU, Postgres 16 cục bộ `max_connections=100`, 1 worker, pipeline fake, WAV im lặng 3 s.
- **Máy sinh tải:** 4 process, client chia đều. Mỗi client đăng nhập (ngoài phép đo), chờ barrier, upload 1 lần, rồi poll 5 lần cách nhau 2 s.
- **Cấu hình 4 process:** `API_MAX_INFLIGHT=20`.

Lệnh (trong `backend/`):

```bash
uv run python scripts/load_vt018.py --db postgresql+psycopg://... --clients 247 --threshold 2.0 \
  --api-workers <1|4> --client-procs 4 --out <thư mục>
```

Điểm khác cách đo so với 2026-11-10:
- Client đóng kết nối rảnh sau 1 s, không phải 5 s.
- Mỗi lượt đo có một `PROMETHEUS_MULTIPROC_DIR` riêng, như Compose. Nhờ vậy có số phía server cho 4 process.

Phần A/B bên dưới cho thấy hai thay đổi này không làm số khác đi trong cùng điều kiện.

## Kết luận

- **AD-018 hôm nay không đạt, ở cả 1 lẫn 4 process API.**
  - 1 process: p95 upload 3,16 đến 3,79 s.
  - 4 process: p95 upload 2,30 đến 2,60 s. Hôm nay có 15 lượt chạy app `main` với 4 process (loạt chính 3, A/B harness 9, A/B app 3), cả 15 đều trên 2,0 s (2,30 đến 2,60 s).
  - Ngày 11-10 đạt ở 10/12 lượt, nhưng hôm nay chạy 40d2431 xen kẽ cũng ra 2,31 đến 2,37 s. Phần lớn chênh lệch giữa hai ngày đến từ tình trạng máy, không phải từ code. Vì vậy dòng ◐ của ngày 11-10 không còn đứng được: ghi là ✗.
- **Số phía server cho 4 process có lần đầu, và cho thấy thời gian nằm trong app.**
  - Server đếm 247/247 upload và 1.235/1.235 poll ở mọi lượt.
  - Phía server chỉ 71 đến 82 % upload xong trong ≤ 2,0 s, p95 nằm trong khoảng 2,0 đến 2,5 s (một lượt 2,5 đến 3,0 s). Phía client là 71 đến 80 %, gần bằng.
  - Chờ admission không phải nguyên nhân: 95 đến 97 % request được vào trong ≤ 1,5 s, trung bình khoảng 0,14 s.
  - Thời gian còn lại nằm ở xử lý upload trong lúc 4 process API, worker, Postgres và 4 process sinh tải cùng tranh 12 CPU. Load average lên tới 10 đến 16 trong lúc đo (`run-log.txt`).
- **1 process thì ngược lại: thời gian nằm ngoài app.**
  - Phía server: 2/3 lượt có p95 upload trong khoảng 1,5 đến 2,0 s, và 99,6 đến 100 % upload ≤ 2,0 s. Lượt đầu là 77,7 %.
  - Phía client cùng lượt: chỉ 49 đến 58 % upload ≤ 2,0 s.
  - Phần chênh nằm trước middleware, tức uvicorn một event loop nhận 247 upload, cộng với máy sinh tải. Đây là quan sát từ số đo, chưa tách riêng được từng phần.
- **Lỗi: 0 ở mọi lượt hôm nay**, tổng 21 lượt × 247 = 5.187 upload. Có 115 đến 164 kết nối/lượt rảnh quá 5 s trước khi upload. Ngày 11-10, harness cũ có 6/6.669 upload lỗi `RemoteProtocolError`. Hôm nay A/B dùng harness cũ cũng ra 0 lỗi trong 6 lượt, nên chưa chứng minh được là đã hết lỗi; chỉ biết điều kiện gây race đã bị loại (commit `10d991a`).

## Loạt chính, 09:17 đến 09:20, xen kẽ 1 và 4 process

| Lượt | Process API | p50 upload (s) | p95 upload (s) | upload ≤ 2,0 s client / server | p95 upload server trong khoảng (s) | lỗi |
|---|---|---|---|---|---|---|
| `api-workers-1/run1` | 1 | 2,18 | 3,79 | 49,0 % / 77,7 % | 2,0 – 2,5 | 0 |
| `api-workers-4/run1` | 4 | 1,72 | 2,35 | 73,7 % / 75,3 % | 2,0 – 2,5 | 0 |
| `api-workers-1/run2` | 1 | 1,87 | 3,17 | 56,3 % / 100 % | 1,5 – 2,0 | 0 |
| `api-workers-4/run2` | 4 | 1,68 | 2,39 | 71,3 % / 73,7 % | 2,0 – 2,5 | 0 |
| `api-workers-1/run3` | 1 | 1,86 | 3,16 | 58,3 % / 99,6 % | 1,5 – 2,0 | 0 |
| `api-workers-4/run3` | 4 | 1,71 | 2,30 | 76,5 % / 79,0 % | 2,0 – 2,5 | 0 |

Từ bucket chỉ biết p95 phía server nằm trong khoảng nào. Tỷ lệ ≤ 2,0 s thì chính xác, vì 2,0 là biên bucket (#46).

## A/B harness, 09:21 đến 09:28 (`ab-harness/`)

Cùng app `main`, 4 process API, xen kẽ ba biến thể, nghỉ 15 s giữa các lượt:
- `old`: harness tại `40d2431` (giữ kết nối 5 s, không có multiproc). Lấy bằng `git show 40d2431:backend/scripts/load_vt018.py`, chạy từ `backend/scripts/`, không commit bản sao.
- `old-multiproc`: harness cũ, thêm `PROMETHEUS_MULTIPROC_DIR`.
- `new`: harness hôm nay.

| Biến thể | p95 upload, 3 lượt (s) | lỗi |
|---|---|---|
| `old` | 2,47 · 2,31 · 2,30 | 0 |
| `old-multiproc` | 2,43 · 2,30 · 2,53 | 0 |
| `new` | 2,57 · 2,53 · 2,32 | 0 |

Khoảng của ba biến thể chồng lên nhau, nên thay đổi cách đo không phải lý do số hôm nay xấu hơn hôm qua. Ghi máy càng lúc càng bận: load average 6 lúc đầu, 14 lúc cuối.

## A/B app, 09:29 đến 09:34 (`ab-app/`)

Cùng harness hôm nay, 4 process API, xen kẽ hai bản app:
- `before-40d2431`: `main` trước #47 và #48, chạy từ một git worktree.
- `main-1f9d1ca`: `main` hiện tại.

| Cặp | trước #48 p95 upload (s) | `main` p95 upload (s) | chênh |
|---|---|---|---|
| 1 | 2,36 | 2,60 | +0,24 |
| 2 | 2,31 | 2,42 | +0,11 |
| 3 | 2,37 | 2,37 | −0,00 |

`main` chậm hơn trung bình 0,12 s qua 3 cặp, nhưng một cặp không khác. Chưa đủ để nói #48 làm chậm upload. Nếu có, nghi vấn đầu tiên là metric ghi qua file mmap (`PROMETHEUS_MULTIPROC_DIR`), vì Compose bật cấu hình này từ #48.

Bằng chứng phụ cho BE-19: ở `before-40d2431`, `server_count_vs_client` chỉ đếm được 54 đến 84/247 upload. Lý do là `/metrics` trước #48 chỉ là của process nhận request scrape. Ở `main`, số này là 247/247.

## Kiểm tra harness

- `01-red-keepalive.log`: test giữ điều kiện keep-alive, đỏ với client giữ kết nối 5,0 s (commit `10d991a`).
- `02-check-4proc-40clients/`: lượt thử 40 client, 4 process. Server/client 40/40 upload, 200/200 poll (commit `393c934`).

## Giới hạn

Một máy, chạy chung VS Code; client, API, worker và Postgres tranh chung CPU. Pipeline fake. Số dao động giữa các thời điểm trong ngày lớn hơn các mức chênh đang so, nên chỉ so những lượt chạy xen kẽ.
