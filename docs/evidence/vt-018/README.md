# VT-018 · Bằng chứng và cách chạy lại

Chạy từ gốc repo. Ngày kiểm: 2026-11-07, nhánh `tainguyen-vt018-tests` (xếp trên `tainguyen-vt018`, PR #35).

## Chạy test của bài

```bash
cd backend
uv run pytest tests/unit/test_vt018_rerun_progress.py tests/unit/test_vt018_pairwise.py \
  tests/unit/test_vt018_can_retry.py tests/unit/test_engine_reuse.py \
  tests/unit/test_migration_0006_segments_unique.py tests/unit/test_migration_0007_job_times.py
```

Hai file migration cần Postgres (skip khi không có). Dựng Postgres không cần Docker: `initdb` + `pg_ctl` trong `/usr/lib/postgresql/16/bin`, rồi đặt `DATABASE_URL`.

| Tệp | Nội dung |
|---|---|
| `01-red.log` | 5 test đỏ trước khi vá, mỗi test fail đúng assert (không phải lỗi fixture) |
| `02-green-rerun.log`, `03-green-progress.log` | Sau vá |
| `pairwise.md` | 20 ca thay cho 120 tổ hợp; sinh bằng `python -m tests.unit.test_vt018_pairwise` |
| `mutation.md` | Mutation `>` → `>=`: 1 mutant bị bắt ngay, 1 mutant sống sót rồi bị bắt sau khi thêm test |
| `load-40-before/`, `load-40/` | Đo 40 client đồng thời trước và sau khi sửa engine DB |

## Coverage (line + branch)

```bash
cd backend && uv run pytest tests/unit/test_vt018_*.py tests/unit/test_engine_reuse.py \
  tests/unit/test_persist_transcript.py tests/unit/test_worker_*.py \
  --cov=app --cov-branch --cov-report=term-missing
```

Dùng `--cov=app`. Dạng `--cov=app.worker --cov=app.api.v1.jobs` làm coverage import module sớm và khiến fixture đăng nhập fail (22 failed, 34 errors) dù chạy không coverage thì 67 pass.

Kết quả của bộ test trên, cho các module liên quan tới bài:

| Module | Line | Branch | Chưa phủ |
|---|---|---|---|
| `db/models/job.py` | 100 % | – | – |
| `worker/reaper.py` | 100 % | 100 % | – |
| `worker/queue.py` | 96 % | 100 % | `validate_transition` nhánh lỗi (87-95) |
| `worker/persister.py` | 85 % | 11 nhánh một phần | đường lỗi schema, summary `disabled` |
| `worker/runner.py` | 80 % | 21 nhánh một phần | hủy job, SIGTERM, hết lease (451-465) |
| `api/v1/jobs.py` | 85 % | 2 nhánh một phần | dòng 42, 49 |

Tổng `app/` của bộ này là 57 % (2603 dòng): bộ test chỉ nhắm vào luồng retry, nên con số tổng không nói gì về phần còn lại. Coverage không chứng minh test đủ mạnh; mutation ở `mutation.md` mới là phép thử đó, và nó tìm ra 1 lỗ hổng mà coverage không thấy.

## Kiểm tra flaky

Hai nguy cơ, chạy ngày 2026-11-07:

| Nguy cơ | Vì sao | Cách kiểm | Kết quả |
|---|---|---|---|
| Thời gian | `test_vt018_job_out_has_real_timestamps` so `started_at` với giờ hệ thống; SQLite trả datetime không có múi giờ | Chạy 39 test VT-018 với `TZ=UTC`, `Asia/Ho_Chi_Minh`, `America/Los_Angeles`, `Pacific/Kiritimati`; lặp riêng 2 test về thời gian và retry 8 lần | 39/39 pass ở cả 4 múi giờ; 8/8 lần lặp pass |
| Thứ tự | Các test dùng chung fixture `env` qua import (`test_vt018_can_retry.py`) | Chạy 39 test theo thứ tự ngược | 39/39 pass |

Test về retry không dùng `sleep` chờ giờ thật: lượt chạy lại truyền `now=` cách 1 giờ. Chưa kiểm: chạy song song (`pytest-xdist`), và thời gian khi máy quá tải.

## Tải 40 client

`backend/scripts/load_vt018.py`, kết quả ở `load-40/summary.md`: p95 0,67 s, 0 lỗi, mục tiêu 1,5 s. Trước khi sửa `get_db` dùng chung engine: 10 lỗi 500 `too many clients already`. Phép đo là một lần chạy, một worker, pipeline fake, mọi thành phần chung một máy; xem phần giới hạn trong từng `summary.md`. Sau thay đổi giới hạn request đang xử lý (2026-11-09) chạy lại: p95 0,65 s, 0 lỗi (`load-40-after/`).

## Tải 239 và 247 client (RE-018, AD-018)

Chẩn đoán và sửa: [`../load-247/diagnosis.md`](../load-247/diagnosis.md). Số đo sau sửa: [`../load-247/after/README.md`](../load-247/after/README.md). Tóm tắt trung thực: hết lỗi và hết độ trễ 61 s, nhưng cấu hình mặc định (1 process) vẫn có p95 3,1 đến 3,4 s ở 247 client, trên mốc 2,0 s; 4 process cho p95 1,8 đến 1,9 s khi tính cả poll nhưng p95 chỉ-upload vẫn 2,2 đến 2,4 s.
