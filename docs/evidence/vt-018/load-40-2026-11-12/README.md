# 40 client trên `main` đã đóng băng (VT-018, 2026-11-12)

VT-018: 40 người dùng đồng thời, p95 ≤ 1,5 s. Người đo: C.

- **Code:** app là `main` tại `d9c2d50` (sau #50, #51; đóng băng code). Lượt đo chạy từ nhánh `tainguyen-vt018-ai-tests`, nên `env.json` ghi `3617a0b`. `git diff d9c2d50 3617a0b -- backend/app` rỗng: nhánh chỉ thêm test và công cụ đo.
- **Cấu hình mặc định:** 1 process API, 1 process sinh tải, 1 worker, pipeline fake, WAV im lặng 3 s. Postgres 16 cục bộ, `max_connections=100`, khởi tạo mới hôm nay. Một máy 12 CPU, chạy chung VS Code.
- **Cách đo:** 6 lượt liên tiếp, nghỉ 15 s giữa các lượt, 12:23 đến 12:27. Load average ghi ở `run-log.txt`, từ 2,0 đến 6,4. Lượt 4 đến 6 chạy thêm sau khi thấy lượt 2 không đạt.

```bash
cd backend && uv run python scripts/load_vt018.py --db postgresql+psycopg://... --clients 40 --threshold 1.5 --out <thư mục>
```

| Lượt | p50 upload (s) | p95 upload (s) | Upload trung bình phía server (s) | Upload ≤ 1,5 s client / server | Server đếm / client gửi | Lỗi | Kết quả |
|---|---|---|---|---|---|---|---|
| `run1` | 0,56 | 0,57 | 0,54 | 100 % / 100 % | 40/40 | 0 | đạt |
| `run2` | 1,53 | **1,56** | 1,43 | 22,5 % / 80 % | 40/40 | 0 | **không đạt** |
| `run3` | 0,57 | 0,59 | 0,54 | 100 % / 100 % | 40/40 | 0 | đạt |
| `run4` | 0,48 | 0,49 | 0,45 | 100 % / 100 % | 40/40 | 0 | đạt |
| `run5` | 0,49 | 0,51 | 0,47 | 100 % / 100 % | 40/40 | 0 | đạt |
| `run6` | 1,39 | 1,43 | 1,32 | 100 % / 100 % | 40/40 | 0 | đạt, sát mốc |

## Kết luận

- **5/6 lượt đạt, 1/6 không đạt** (p95 upload 1,56 s). Trước đây ghi "đạt ở mọi lượt" (11-10: 3/3, 11-11: 6/6 trên `main`); hôm nay không còn đúng nữa. Cộng với lượt 1,80 s của bản trước #48 ngày 11-11, có thể nói: mốc 1,5 s đạt ở phần lớn lượt đo, nhưng **không ổn định** trên máy dùng chung.
- **Kết quả có hai mức rõ rệt, không rải đều:** 4 lượt quanh 0,5 s, 2 lượt quanh 1,4 đến 1,6 s.
  - Trong một lượt chậm, cả 40 upload xong gần cùng lúc: lượt 2 có p50 1,53 s và p95 1,56 s.
  - Như vậy cả 40 upload cùng bị một chỗ chung giữ thêm khoảng 0,9 s. Nếu chúng xếp hàng chờ nhau thì thời gian sẽ trải đều từ thấp tới cao.
- **Thời gian chậm nằm trong app, không phải ở hàng chờ hay ở máy sinh tải.**
  - Upload trung bình phía server là 1,43 s ở lượt 2, so với 0,54 s ở lượt 1.
  - Chờ admission là 0 ở mọi lượt, vì 40 thấp hơn `API_MAX_INFLIGHT`.
- **Chưa biết nguyên nhân.** Các nghi vấn chưa kiểm:
  - fsync của Postgres hoặc đĩa khi 40 commit cùng lúc;
  - 40 lần gọi `ffprobe` song song (máy này có ffprobe ở `/home/tai/anaconda3/bin`);
  - ghi file audio lên đĩa.

  Ngày 11-12 đóng băng code, nên chỉ ghi lại, không sửa.
- **Lỗi:** 0 trong 240 upload. Server đếm đủ 40/40 upload ở mọi lượt.

## Giới hạn

Một máy, pipeline fake, client là thread Python. Sáu lượt chạy trong 4 phút, cùng một trạng thái máy, nên không nói được tỷ lệ lượt chậm vào lúc khác trong ngày.
