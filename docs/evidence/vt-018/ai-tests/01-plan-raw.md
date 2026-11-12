# Plan của AI, bản thô (2026-11-12)

Nguyên văn câu trả lời của AI cho prompt ở `00-prompt.md`, viết trước khi có test. Không sửa sau đó; đánh giá của nhóm nằm ở các file sau.

---

**Phạm vi.** Bốn đơn vị thuần hoặc gần thuần, test được trên SQLite in-memory không cần worker chạy thật:

1. `compute_backoff_delay(attempt, with_jitter)`: mốc 30 / 120 / 480 s, jitter ±20 %.
2. Máy trạng thái trong `queue.py`: `validate_transition`, `transition_job_status`, và các hàm dùng nó (`enqueue_job`, `claim_job`, `complete_job`, `fail_job`, `schedule_retry`).
3. `reap_expired_jobs` và `release_job_on_sigterm` trong `reaper.py`.
4. `Job.can_retry`.

**Test sẽ viết.**

- Backoff: mỗi lượt 1, 2, 3 cho đúng mốc khi tắt jitter; lượt lớn hơn 3 giữ mốc 480 s; lượt 0 hoặc âm dùng mốc đầu; khi bật jitter, giá trị nằm trong `[0,8·base, 1,2·base]` qua nhiều lần gọi.
- Máy trạng thái: mọi cặp hợp lệ trong `VALID_TRANSITIONS` không ném lỗi; một số cặp không hợp lệ (succeeded → bất kỳ, queued → succeeded) ném `InvalidJobStateTransitionError`; trạng thái lạ ném lỗi; về `queued` thì xóa `next_run_at` và khóa; về trạng thái kết thúc thì đặt `finished_at`.
- `enqueue_job`: job mới ở `queued`, `attempt = 1`, `progress = 0`, `stage` mặc định `preprocess`.
- `claim_job`: lấy job `queued`; không lấy job `retry_scheduled` chưa tới giờ; lấy job `retry_scheduled` đã tới giờ; lấy theo thứ tự `created_at`; đặt `started_at` lần đầu và **không ghi đè** ở lần claim sau (thời gian bắt đầu là thật, VT-018).
- `schedule_retry`: tăng `attempt` đúng 1, đặt `next_run_at`, nhả khóa.
- `can_retry`: đúng khi `attempt < max_attempts`, sai ở biên `attempt == max_attempts` (biên này là chỗ mutation `>` thành `>=` của bài).
- Reaper: job hết lease còn lượt thì về `queued` và tăng `attempt`; hết lượt thì `failed` với `LEASE_TIMEOUT`; job còn lease thì không đụng tới; SIGTERM trả job về `queued` mà **không** tăng `attempt`.
- Bản ghi trùng: claim hai lần liên tiếp cùng một job chỉ thành công một lần (job đã `running` không bị claim lại).

**Kỳ vọng.** Bộ test này sẽ bắt được mutation `>` thành `>=` ở `can_retry` và phần lớn mutant đổi toán tử so sánh trong bốn đơn vị trên. Coverage dòng của `retry.py`, `queue.py`, `reaper.py` sẽ gần 100 %.

**Giới hạn đã biết.** SQLite không có `FOR UPDATE SKIP LOCKED`, nên test claim song song thật giữa hai worker cần Postgres; ở đây chỉ test claim tuần tự. Test không kiểm việc ghi segment khi chạy lại (phần đó nằm ở persister, ngoài phạm vi prompt).
