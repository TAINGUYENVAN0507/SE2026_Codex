# Ma trận mutation cho test AI sinh, bản thô (2026-11-12)

- **Lệnh** (từ gốc repo, working tree sạch):
  ```bash
  python3 scripts/mutation_matrix.py docs/evidence/vt-018/ai-tests/mutants.json \
    --cwd backend --tests tests/unit/test_vt018_ai_raw.py --out docs/evidence/vt-018/ai-tests/03-matrix-raw.json
  ```
- **Mutant:** 24, ở `mutants.json`, đặt theo quy tắc ghi trong file đó trước khi chạy. M24 là mutation `>` thành `>=` của đề.
- **Script:** sửa file, chạy pytest, đọc junit XML, luôn khôi phục file gốc. Test đã fail khi chưa có mutant thì không được tính là giết mutant. Sau khi chạy, `git status` chỉ còn các file kết quả mới.
- **Kết quả thô:** `03-matrix-raw.json` (test nào giết mutant nào) và `03-matrix-raw.log`.

## Kết quả: 18/24 mutant bị giết

| Mutant | Thay đổi | Bị giết bởi |
|---|---|---|
| M01 | backoff lệch một mốc | 3 test |
| M02 | jitter vượt +20 % | 1 |
| **M03** | bỏ jitter | **sống** |
| M04 | cho phép queued → succeeded | 1 |
| M05 | cho phép failed → running | 1 |
| M06 | tắt kiểm tra chuyển trạng thái | 7 |
| M07 | về queued vẫn giữ lịch cũ | 1 |
| M08 | không ghi `finished_at` | 3 |
| **M09** | job queued có `next_run_at` không bao giờ được claim | **sống** |
| M10 | retry đúng giờ chưa được claim (`<=` thành `<`) | 1 |
| M11 | claim job mới nhất trước | 1 |
| **M12** | bỏ điều kiện `status == candidate.status` chống race khi claim | **sống** |
| M13 | lease dài hơn 1 s | 4 |
| M14 | claim lại ghi đè `started_at` | 1 |
| M15 | hoàn thành không đặt progress 1,0 | 1 |
| M16 | `fail_job` không ghi `error_code` | 2 |
| **M17** | `schedule_retry` không tăng `attempt` | **sống** |
| **M18** | `schedule_retry` không đặt `next_run_at` | **sống** |
| **M19** | reaper thu hồi job đúng lúc hết lease (`<` thành `<=`) | **sống** |
| M20 | reaper không tăng `attempt` | 1 |
| M21 | reaper không bao giờ đánh failed | 1 |
| M22 | sai mã lỗi `LEASE_TIMEOUT` | 1 |
| M23 | SIGTERM tăng `attempt` | 1 |
| M24 | `can_retry`: `>` thành `>=` | 2 (`test_can_retry[3-3-False]`, `test_reaper_fails_expired_job_on_last_attempt`) |

Plan AI (`01-plan-raw.md`) kỳ vọng bộ test "bắt được phần lớn mutant đổi toán tử so sánh". Thực tế, trong 5 mutant đổi phép so sánh (M10, M12, M19, M24, và M09 bỏ một vế so sánh), có 3 mutant sống: M09, M12, M19.

## Test theo số mutant giết được

45 test (tính cả từng bộ tham số). 21 test giết 0 mutant. Giết 0 mutant chưa chắc là test yếu: test có thể giữ một hành vi mà tập mutant này không đụng tới. Bảng dưới chỉ liệt kê những test mà **ngoài số 0 còn có bằng chứng thứ hai**.

| Test | Giết | Bằng chứng thứ hai |
|---|---|---|
| `test_schedule_retry_increments_attempt_and_sets_next_run` | 0 (fail sẵn) | Fail trên code đúng (`02-raw-run.log`): SQLite trả `next_run_at` không có múi giờ, test so với datetime có múi giờ. Vì đây là test duy nhất kiểm `schedule_retry`, M17 và M18 sống. |
| `test_backoff_returns_float` | 0 | Chỉ kiểm kiểu trả về. |
| `test_can_retry_is_bool` | 0 | Chỉ kiểm kiểu trả về. |
| `test_reaper_returns_list` | 0 | Chỉ kiểm kiểu trả về, trên DB rỗng. |
| `test_succeeded_is_terminal` | 0 | Kiểm một hằng số trong code, không kiểm hành vi. `test_invalid_transitions_raise[succeeded-*]` đã kiểm hành vi đó. |
| `test_same_job_cannot_be_claimed_twice` | 0 | Tên nói về chống claim trùng, nhưng hai lần claim chạy tuần tự: lần hai không thấy job vì job đã `running`. Bỏ điều kiện chống race (M12) test vẫn xanh. |
| `test_requeued_job_is_not_duplicated` | 1 (M13, gián tiếp) | `db.query(Job).count() == 1` không thể sai vì reaper không tạo job mới. Phần claim lại trùng với `test_claim_picks_queued_job`. |
| `test_backoff_with_jitter_stays_within_twenty_percent` | 2 | Chỉ kiểm cận; bỏ hẳn jitter (M03) vẫn xanh vì giá trị gốc nằm trong cận. |
| `test_reaper_ignores_job_with_valid_lease` | 0 | Chỉ thử ở giây 30, xa biên 60 s, nên M19 sống. |

Những test không có trong bảng (ví dụ `test_can_retry[1-3-True]`, `test_unknown_status_raises`) giết 0 mutant trong tập này nhưng kiểm hành vi thật, nên không xếp vào ứng viên.

Quyết định xóa hay sửa và kết quả chạy lại nằm ở `04-review.md`.
