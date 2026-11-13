# 40 client: chẩn đoán hai mức thời gian (VT-018, 2026-11-13)

Ngày 11-12, 6 lượt 40 client trên `main` đóng băng chia hai mức: 4 lượt quanh 0,5 s, 2 lượt quanh 1,4 đến 1,6 s (1 lượt p95 upload 1,56 s, không đạt). Nghi vấn chưa kiểm khi đó: 40 lần gọi `ffprobe` song song, fsync của Postgres, ghi file audio ([`../load-40-2026-11-12/README.md`](../load-40-2026-11-12/README.md)). Hôm nay kiểm nghi vấn đầu. Người đo: C.

- **Code:** app là `main` `a75853d` (`env.json`). #54 merge giữa lúc đo không đổi `backend/app` (`git diff a75853d f255e01 -- backend/app` rỗng).
- **Cấu hình:** như 11-12: 1 process API, 1 process sinh tải, 1 worker, pipeline fake, WAV im lặng 3 s. Postgres 16 cục bộ, cluster mới khởi tạo hôm nay, `max_connections=100`. Một máy 12 CPU, chạy chung VS Code.
- **Hai biến thể, chạy xen kẽ** (`real-1`, `stub-1`, `real-2`, ...), nghỉ 15 s giữa các lượt, 09:11 đến 09:19 ([`run.sh`](run.sh), [`run-log.txt`](run-log.txt)):
  - `real`: ffprobe thật (`/home/<user>/anaconda3/bin/ffprobe`, một lần gọi đơn lẻ mất khoảng 0,01 s).
  - `stub`: `FFPROBE_BIN=ffprobe-stub.sh`, chỉ `cat` JSON mà ffprobe thật in ra cho đúng file WAV của harness ([`ffprobe-stub.sh`](ffprobe-stub.sh), [`ffprobe-stub.json`](ffprobe-stub.json)). Đã kiểm app dùng stub: với một file text, `probe_audio` báo `AUDIO_INVALID` khi dùng ffprobe thật và trả `duration_sec=3.0` khi dùng stub.

## Kết quả (upload, phía client, giây)

| Cặp | `real` p50 | `real` p95 | `stub` p50 | `stub` p95 | `real` − `stub` (p95) |
|---|---|---|---|---|---|
| 1 | 0,40 | 0,42 | 0,40 | 0,42 | 0,00 |
| 2 | 0,64 | 0,66 | 0,38 | 0,40 | +0,26 |
| 3 | 0,47 | 0,48 | 0,35 | 0,36 | +0,12 |
| 4 | 0,50 | 0,52 | 0,45 | 0,47 | +0,06 |
| 5 | 0,85 | 0,87 | 0,64 | 0,66 | +0,22 |
| 6 | 0,53 | 0,55 | 0,77 | 0,79 | −0,24 |

p50 và p95 tính từ `raw.csv` (quantile theo hạng gần nhất). Chi tiết từng lượt, gồm số phía server: `<lượt>/summary.md`.

- **12/12 lượt đạt** p95 ≤ 1,5 s, 0 lỗi trong 480 upload. Không lượt nào rơi vào mức 1,4 đến 1,6 s của ngày 11-12.
- **ffprobe không giải thích được mức chậm.** Lượt `real` chậm hơn `stub` ở 4/6 cặp, trung bình 0,07 s, và nhanh hơn ở 1 cặp. Mức chậm của 11-12 là thêm khoảng 0,9 s cho cả 40 upload; chênh lệch hôm nay nhỏ hơn thế nhiều và đổi dấu.
- **Không tái hiện được mức chậm, nên chưa biết nguyên nhân.** Hai nghi vấn còn lại (fsync Postgres, ghi file audio) chưa kiểm. Hôm nay cluster Postgres mới khởi tạo và máy nhẹ hơn (load average lúc bắt đầu lượt 1,1 đến 6,8, so với 2,0 đến 6,4 ngày 11-12), nên không loại được việc trạng thái máy gây ra mức chậm.

## Kết luận cho VT-018

Gộp 3 ngày trên `main` (11-11: 6/6, 11-12: 5/6, 11-13: 12/12): **23/24 lượt đạt** p95 ≤ 1,5 s. Lượt không đạt là 1,56 s. Ghi là "đạt ở phần lớn lượt, có 1 lượt không đạt chưa rõ nguyên nhân", không ghi là đạt ổn định.

## Giới hạn

Như các ngày trước: một máy, pipeline fake, client là thread Python. 12 lượt trong 8 phút cùng một trạng thái máy.
