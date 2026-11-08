# VT-018 · Mutation `>` thành `>=`

Công cụ: `scripts/mutation_check.py`. Script sửa file, chạy test, rồi luôn khôi phục nguyên trạng; từ chối chạy khi file có thay đổi chưa commit. Thực hiện ngày 2026-11-07, không mutant nào còn lại trong working tree (`git status` sạch).

| # | Vị trí | Mutant | Test chạy | Trước | Sau |
|---|---|---|---|---|---|
| 1 | `backend/app/db/models/job.py`, `Job.can_retry` | `max_attempts > attempt` → `>=` | `tests/unit/test_vt018_can_retry.py` | KILLED | KILLED |
| 2 | `pipeline/meeting_pipeline/stages/preprocess.py`, `duration > max_sec` | `>` → `>=` | toàn bộ `pipeline/tests/unit` | **SURVIVED** (297 passed) | KILLED sau khi thêm `test_preprocess_duration_bounds.py` |

## Mutant 1: lượt cuối còn retry

`can_retry` dùng ở API (`retryable`), worker (lên lịch retry) và reaper (queued hay failed). Mutant làm job ở lượt 3/3 vẫn còn retry. Test bắt được ở biên:

```
FAILED tests/unit/test_vt018_can_retry.py::test_can_retry_boundary[3-3-False]
RESULT: KILLED
```

## Mutant 2: sống sót, rồi được bắt

Bộ test pipeline có 297 test đều xanh khi `duration > max_sec` đổi thành `>=`: không test nào thử đúng bằng giới hạn, nên audio dài đúng 3600 s sẽ bị từ chối sai. Bổ sung biên (2.0 và 10.0 được nhận; 1.999 và 10.001 bị từ chối):

```
FAILED tests/unit/test_preprocess_duration_bounds.py::test_duration_equal_to_limit_is_accepted[10.0]
RESULT: KILLED
```

## Giới hạn

- Hai mutant thủ công, không phải phép đo mutation score.
- Mutant 2 sinh ở biên số thực: chỉ chứng minh test phân biệt được hai phía của đúng giá trị biên đã chọn.
- `time.monotonic() > deadline` ở `runner.py` không thử vì mutant gần như tương đương (so sánh số thực lệch nhau cỡ nano giây).
