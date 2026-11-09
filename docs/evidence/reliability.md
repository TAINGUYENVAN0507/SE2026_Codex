# Bằng chứng kiểm thử các kịch bản độ tin cậy (Reliability Evidence - BE-15)

- **Người thực hiện:** Hà Minh Quang (`@minhquangha`), Member B.
- **Nhánh thực hiện:** `haquang`.
- **Ngày kiểm:** 2026-11-08.
- **Mã công việc:** BE-15, phục vụ RE-018 và VT-018.

---

## 1. Mục tiêu và phạm vi kiểm thử

Kiểm chứng 3 kịch bản độ tin cậy cốt lõi của hệ thống xử lý tác vụ nền và giao tiếp API:

1. **Worker chết giữa chừng (Worker Crash & Reaper Reclamation):**
   - Khi worker đang xử lý job (`RUNNING`) nhưng bị crash đột ngột, OOM-kill hoặc mất kết nối khiến `locked_until` quá hạn (lease timeout).
   - Cơ chế Reaper (`reap_expired_jobs`) định kỳ quét, phát hiện lease quá hạn và thu hồi an toàn: giải phóng lock (`locked_by=None`, `locked_until=None`), tăng số lượt thử (`attempt`), chuyển về trạng thái `queued` để worker khác tiếp tục xử lý thành công.
2. **Cạn kiệt số lần thử retry (Retry Exhaustion Transitions to Failed):**
   - Khi job đã đạt đến ngưỡng tối đa (`attempt >= max_attempts`, cụ thể `3/3`), thuộc tính `job.can_retry` chuyển sang `False`.
   - Nếu worker gặp lỗi tạm thời (`TransientPipelineError`, ví dụ OOM, mạng) hoặc reaper thu hồi job hết hạn lease, hệ thống dứt khoát chuyển trạng thái job sang `failed` với mã lỗi tương ứng (`OUT_OF_MEMORY`, `LEASE_TIMEOUT`), không còn lên lịch `retry_scheduled` vô hạn.
3. **Tải lên trùng khóa (Idempotent Upload Replay):**
   - Khi người dùng hoặc mạng chập chờn gửi lại cùng một yêu cầu `POST /api/v1/meetings` với cùng header `Idempotency-Key`.
   - Hệ thống phát hiện khóa đã được hoàn tất: trả về phản hồi đồng nhất (HTTP 201 Created), bổ sung header `Idempotent-Replayed: true`, và tuyệt đối không tạo thêm bản ghi cuộc họp hay job trùng lặp trong cơ sở dữ liệu.

---

## 2. Lệnh thực thi và kết quả đo thật

Bộ kiểm thử được xây dựng tại [`backend/tests/reliability/test_reliability_scenarios.py`](../../backend/tests/reliability/test_reliability_scenarios.py).

### Lệnh chạy

```bash
cd backend
uv run pytest tests/reliability/test_reliability_scenarios.py -v
```

### Kết quả đầu ra terminal thật (Recorded Output)

```text
============================= test session starts =============================
platform win32 -- Python 3.12.13, pytest-9.1.1, pluggy-1.7.0 -- D:\kicuoi\SE2026_Codex\backend\.venv\Scripts\python.exe
cachedir: .pytest_cache
rootdir: D:\kicuoi\SE2026_Codex\backend
configfile: pyproject.toml
plugins: anyio-4.15.1, cov-7.1.0
collecting ... collected 3 items

tests/reliability/test_reliability_scenarios.py::test_reliability_worker_crash_and_reaper_reclaims_job PASSED [ 33%]
tests/reliability/test_reliability_scenarios.py::test_reliability_retry_exhaustion_transitions_to_failed PASSED [ 66%]
tests/reliability/test_reliability_scenarios.py::test_reliability_upload_duplicate_idempotency_key_replays_safely PASSED [100%]

============================== warnings summary ===============================
.venv\Lib\site-packages\fastapi\testclient.py:1
  D:\kicuoi\SE2026_Codex\backend\.venv\Lib\site-packages\fastapi\testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
======================== 3 passed, 1 warning in 3.67s =========================
```

---

## 3. Phân tích chi tiết từng kịch bản

### Kịch bản 1: Worker chết giữa chừng, Reaper lấy lại

- **Thiết lập:**
  - Khởi tạo cuộc họp và job đang ở trạng thái `RUNNING`, được giữ bởi `worker-crashed-1`.
  - Khóa lease `locked_until` được gán quá hạn 10 giây so với mốc thời gian kiểm thử `now`.
  - Số lần thử `attempt = 1`, `max_attempts = 3`.
- **Hành vi quan sát:**
  - `reap_expired_jobs` trả về đúng 1 job quá hạn cần thu hồi.
  - Job được chuyển về `QUEUED`, xóa `locked_by` và `locked_until`.
  - Thuộc tính `attempt` tự động tăng lên `2`.
  - Worker kế tiếp (`worker-healthy-2`) gọi `run_worker_once`, claim job thành công và đưa job đến trạng thái `SUCCEEDED` với tiến độ `1.0`.

### Kịch bản 2: Cạn kiệt lượt retry

- **Phần A (Worker):**
  - Job tại `attempt = 3, max_attempts = 3`, `job.can_retry` trả về `False`.
  - Giả lập pipeline ném `TransientPipelineError(code=ErrorCode.OUT_OF_MEMORY)`.
  - Worker bắt lỗi, nhận biết `job.can_retry == False` nên không đưa vào `retry_scheduled` mà chuyển dứt khoát sang `failed` với `error_code="OUT_OF_MEMORY"`. Cuộc họp chuyển sang trạng thái `failed`.
- **Phần B (Reaper):**
  - Job tại `attempt = 3, max_attempts = 3` quá hạn lease.
  - Reaper nhận biết `can_retry == False`, lập tức chuyển job sang `failed` với mã lỗi kỹ thuật `LEASE_TIMEOUT`.

### Kịch bản 3: Tải lên trùng khóa Idempotency

- **Thiết lập:**
  - Gửi yêu cầu tải lên tệp âm thanh qua `POST /api/v1/meetings` với header `Idempotency-Key: IDEM-RELIABILITY-TEST-...`.
  - Nhận HTTP 201 Created với `meeting_id_1` và `job_id_1`.
  - Gửi lại chính xác payload và header đó lần 2.
- **Hành vi quan sát:**
  - Phản hồi trả về vẫn là HTTP 201 Created với cùng dữ liệu cuộc họp `meeting_id_1` và job `job_id_1`.
  - Header `Idempotent-Replayed: true` được thiết lập trên HTTP Response.
  - Đếm tổng số bản ghi trong bảng `meetings` và `jobs` của cơ sở dữ liệu: chính xác bằng 1, chứng minh không có bản ghi mồ côi hay dữ liệu dư thừa.
