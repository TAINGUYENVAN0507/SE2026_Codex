# Xóa và sửa test yếu do AI sinh (2026-11-12)

- **Bản thô:** `backend/tests/ai_raw/vt018_ai_raw.py`. File được `git mv` từ `tests/unit/test_vt018_ai_raw.py`, nội dung không đổi (`git log --follow -p` cho thấy 0 dòng sửa). Bản thô có một test fail trên code đúng. Vì tên file không bắt đầu bằng `test_`, `pytest` mặc định và CI không chạy nó. Muốn chạy thì chỉ đích danh: `uv run pytest tests/ai_raw/vt018_ai_raw.py` ra 44 passed, 1 failed.
- **Bản đã review:** `backend/tests/unit/test_vt018_ai_reviewed.py`. Mỗi chỗ đổi có chú thích `REVIEW:` kèm lý do.
- **Người quyết định xóa và sửa:** Claude Code (cùng phiên đã sinh test), theo yêu cầu của C ngày 2026-11-12. Căn cứ là bảng ứng viên ở `03-mutation-matrix.md`.

## Đã làm

| Test bản thô | Quyết định | Lý do | Bằng chứng sau khi đổi |
|---|---|---|---|
| `test_schedule_retry_increments_attempt_and_sets_next_run` | **Sửa** | Fail trên code đúng: so datetime có múi giờ với giá trị SQLite trả về không có múi giờ. Đây là test duy nhất kiểm `schedule_retry`. | Giết M17, M18 |
| `test_same_job_cannot_be_claimed_twice` | **Sửa** | Hai lần claim chạy tuần tự nên không kiểm được race như tên test nói. Bản sửa cho worker khác claim job vào giữa lúc đọc và lúc ghi, qua kết nối thứ hai tới cùng file SQLite. | Giết M12 |
| `test_backoff_with_jitter_stays_within_twenty_percent` | **Sửa** | Chỉ kiểm cận, nên bỏ hẳn jitter vẫn xanh. Thêm điều kiện: 200 lần gọi phải ra hơn một giá trị. | Giết M03 |
| `test_reaper_ignores_job_with_valid_lease` | **Sửa** | Chỉ thử ở giây 30. Thêm đúng biên 60 s. | Giết M19 |
| `test_backoff_returns_float` | **Xóa** | Chỉ kiểm kiểu, giết 0/24 | – |
| `test_can_retry_is_bool` | **Xóa** | Chỉ kiểm kiểu; bộ tham số `test_can_retry` đã so bằng `is` | – |
| `test_reaper_returns_list` | **Xóa** | Chỉ kiểm kiểu, trên DB rỗng | – |
| `test_succeeded_is_terminal` | **Xóa** | Kiểm hằng số, trùng `test_invalid_transitions_raise[succeeded-*]` | – |
| `test_requeued_job_is_not_duplicated` | **Xóa** | `count() == 1` không thể sai; phần còn lại trùng `test_claim_picks_queued_job` | – |
| (không có) | **Thêm** `test_claim_respects_next_run_at_of_queued_job` | M09 sống vì không test nào có job queued kèm `next_run_at` | Giết M09 |

Tổng: sửa 4 test, xóa 5 test, thêm 1 test.

## Trước và sau

| | Bản thô | Bản đã review |
|---|---|---|
| Số test (tính cả bộ tham số) | 45 | 42 |
| Fail trên code đúng | 1 | 0 |
| Mutant bị giết | **18/24** | **24/24** |
| Mutant sống | M03, M09, M12, M17, M18, M19 | không có |
| Mutation của đề (M24, `>` thành `>=`) | bị giết | bị giết |

Lệnh: như ở `03-mutation-matrix.md`, nhưng thay `--tests` bằng `tests/unit/test_vt018_ai_reviewed.py`. Kết quả ở `04-matrix-reviewed.json` và `04-matrix-reviewed.log`.

Kiểm flaky cho bản đã review, nhất là test race dùng file SQLite: chạy cả file 20 lần liên tiếp, 20/20 lần pass (42 passed mỗi lần).

## Giới hạn

- **24/24 không phải phép thử độc lập.** Người sửa test đã thấy danh sách mutant sống, nên sửa đúng vào chỗ đó. Kết quả cho biết các lỗ hổng đã tìm ra nay đã được đóng, không cho biết bộ test mạnh với các lỗi khác. Muốn đo độc lập thì cần một tập mutant mới, đặt sau khi đã sửa xong.
- Tập mutant chỉ gồm 24 mutant viết tay theo một quy tắc, không phải mutation score do công cụ sinh ra.
- Test race chạy trên SQLite. Nó kiểm điều kiện `status == candidate.status` trong lệnh `UPDATE`; nó không kiểm `FOR UPDATE SKIP LOCKED`, vì SQLite bỏ qua mệnh đề này.
- `heartbeat_job` không nằm trong plan nên không có test hay mutant nào trong bộ này. File đã có sẵn test riêng, `tests/unit/test_worker_reaper.py`.
