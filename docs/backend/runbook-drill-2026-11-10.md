# Báo cáo Diễn tập Runbook: Hai Sự cố Vận hành và Thời gian Truy Nguyên nhân (RE-018, BE-19)

- **Ngày thực hiện diễn tập:** 2026-11-10
- **Người thực hiện:** Member B (`@minhquangha`)
- **Môi trường:** Docker Compose (`docker-compose.yml`), Python 3.12, PostgreSQL 16
- **Mục tiêu:** Kiểm chứng tính hiệu quả của tài liệu Runbook (`docs/backend/BE-19.md`), khả năng phát hiện sự cố qua Prometheus `/metrics` và Structured JSON logs, đo lường thời gian thực tế để phát hiện và tìm ra nguyên nhân gốc rễ (Root Cause Analysis - RCA).

---

## 1. Sự cố A: Worker bị tiêu diệt đột ngột giữa lúc Job đang xử lý (`docker compose kill worker`)

### 1.1. Kịch bản và Tiền điều kiện
- Cuộc họp mẫu được tạo thành công qua `POST /api/v1/meetings` với tệp âm thanh 3 giây, sinh ra `job_id`: `7ded0493-cc0b-472d-bcec-2777198637b4` (Meeting ID: `0db9a18a-b613-4d96-bccb-c066149b3ad5`).
- Worker đã nhận job và chuyển sang trạng thái `running` tại stage `preprocess`.
- Cấu hình pipeline: `PIPELINE_BACKEND=fake`, `FAKE_SCENARIO=slow`, `FAKE_STAGE_SLEEP_SEC=15`.

### 1.2. Nhật ký Thời gian Diễn tập (Measured Timings)

| Mốc sự kiện | Thời điểm thực tế (UTC) | Thời gian trôi qua ($\Delta t$) |
|---|---|---|
| **Khởi tạo Job (`job_created`)** | `2026-11-10T09:13:08.467767+00:00` | — |
| **Worker claim job (`status=running`)** | `2026-11-10T09:13:09.497416+00:00` | +1.03s |
| **Tạo lỗi: Giết worker đột ngột (`t_inject`)** | `2026-11-10T09:13:09.506269+00:00` | +0.00s |
| **Phát hiện sự cố (`t_detect`)** | `2026-11-10T09:13:10.040914+00:00` | **+0.53s** |
| **Biết nguyên nhân gốc rễ (`t_cause`)** | `2026-11-10T09:13:10.208536+00:00` | **+0.70s** |
| **Worker tái khởi động (`t_restart`)** | `2026-11-10T09:13:12.630132+00:00` | +3.12s |
| **Reaper thu hồi lease và retry (`t_reap`)** | `2026-11-10T09:14:12.795391+00:00` | +63.28s |
| **Job hoàn thành thành công (`job_succeeded`)**| `2026-11-10T09:17:01.774080+00:00` | +232.26s |

### 1.3. Các Lệnh Đã Thực Thi Theo Runbook

1. **Gây sự cố:**
   ```bash
   docker compose kill worker
   ```
2. **Kiểm tra trạng thái container và số đo `/metrics` (Phát hiện sự cố trong 0.53s):**
   ```bash
   docker compose ps worker
   # Kết quả: container meeting_assistant_worker biến mất khỏi danh sách running hoặc trạng thái Exited (137)

   curl -s http://localhost:8000/metrics | grep jobs_total
   # Kết quả: jobs_total{status="running"} 1.0 (nhưng worker container không còn chạy)
   ```
3. **Tra cứu nhật ký JSON để xác định nguyên nhân (Xác định nguyên nhân trong 0.70s):**
   ```bash
   docker compose logs --no-log-prefix worker | grep "7ded0493-cc0b-472d-bcec-2777198637b4"
   ```
4. **Khắc phục:**
   ```bash
   docker compose start worker
   ```

### 1.4. Trích xuất Nhật ký JSON Khớp `job_id`

```json
{"timestamp": "2026-11-10T09:13:09.367939+00:00", "level": "INFO", "logger": "backend.worker", "message": "Worker worker-1 đã claim job 7ded0493-cc0b-472d-bcec-2777198637b4", "request_id": null, "event": "job_claimed", "job_id": "7ded0493-cc0b-472d-bcec-2777198637b4", "meeting_id": "0db9a18a-b613-4d96-bccb-c066149b3ad5", "worker_id": "worker-1", "stage": "preprocess", "attempt": 1, "status": "running"}
{"timestamp": "2026-11-10T09:13:09.384254+00:00", "level": "INFO", "logger": "meeting_pipeline.runner", "message": "stage_started", "request_id": null, "event": "stage_started", "job_id": "7ded0493-cc0b-472d-bcec-2777198637b4", "meeting_id": "0db9a18a-b613-4d96-bccb-c066149b3ad5", "stage": "preprocess", "attempt": 1, "status": "running"}
```
*(Tại mốc này worker bị kill, container dừng với exit code 137 mà không có event kết thúc)*.

Sau khi worker được start lại, cơ chế Reaper (`app.worker.reaper`) tự động phát hiện hết hạn lease 60 giây và thu hồi:
```json
{"timestamp": "2026-11-10T09:14:12.795391+00:00", "level": "WARNING", "logger": "backend.worker.reaper", "message": "Job 7ded0493-cc0b-472d-bcec-2777198637b4 hết hạn lease (locked_until=2026-11-10 09:14:09.376341+00:00), đưa về queued và tăng attempt 1 -> 2", "request_id": null}
{"timestamp": "2026-11-10T09:14:12.804041+00:00", "level": "INFO", "logger": "backend.worker", "message": "Reaper đã thu hồi 1 job hết hạn", "request_id": null}
{"timestamp": "2026-11-10T09:14:12.812323+00:00", "level": "INFO", "logger": "backend.worker", "message": "Worker worker-1 đã claim job 7ded0493-cc0b-472d-bcec-2777198637b4", "request_id": null, "event": "job_claimed", "job_id": "7ded0493-cc0b-472d-bcec-2777198637b4", "meeting_id": "0db9a18a-b613-4d96-bccb-c066149b3ad5", "worker_id": "worker-1", "stage": "preprocess", "attempt": 2, "status": "running"}
```

---

## 2. Sự cố B: Cơ sở Dữ liệu Dừng Hoạt động trong 30 giây (`docker compose stop db`)

### 2.1. Kịch bản và Tiền điều kiện
- Cụm hệ thống đang hoạt động bình thường, API và Worker duy trì kết nối tới Postgres qua pool kết nối.
- Tiến hành dừng dịch vụ `db` trong thời gian liên tục 30 giây để mô phỏng gián đoạn mạng hoặc DB restart/failover.

### 2.2. Nhật ký Thời gian Diễn tập (Measured Timings)

| Mốc sự kiện | Thời điểm thực tế (UTC) | Thời gian trôi qua ($\Delta t$) |
|---|---|---|
| **Tạo lỗi: Dừng cơ sở dữ liệu (`t_inject`)** | `2026-11-10T09:15:12.168583+00:00` | +0.00s |
| **Phát hiện sự cố qua `/ready` (`t_detect`)** | `2026-11-10T09:15:16.734055+00:00` | **+4.57s** |
| **Biết nguyên nhân gốc rễ (`t_cause`)** | `2026-11-10T09:15:17.048014+00:00` | **+4.88s** |
| **Khởi động lại DB (`t_start_db`)** | `2026-11-10T09:15:42.169057+00:00` | +30.00s |
| **Hệ thống phục hồi hoàn toàn (`t_recovered`)**| `2026-11-10T09:15:43.704665+00:00` | **+1.54s** (sau khi start DB) |

### 2.3. Các Lệnh Đã Thực Thi Theo Runbook

1. **Gây sự cố:**
   ```bash
   docker compose stop db
   ```
2. **Kiểm tra endpoint sẵn sàng và log (Phát hiện trong 4.57s):**
   ```bash
   curl -i http://localhost:8000/ready
   # Kết quả: HTTP/1.1 503 Service Unavailable
   # Payload: {"status":"unhealthy","database":"disconnected"}
   ```
3. **Tra cứu nguyên nhân gốc rễ (Xác định trong 4.88s):**
   ```bash
   docker compose ps db
   # Kết quả: Container meeting_assistant_db trạng thái Exited (0)

   docker compose logs --tail=30 api
   # Kết quả: sqlalchemy.exc.OperationalError / psycopg.OperationalError: failed to connect
   ```
4. **Khắc phục sau 30s:**
   ```bash
   docker compose start db
   ```
5. **Kiểm tra xác nhận phục hồi:**
   ```bash
   curl -i http://localhost:8000/ready
   # Kết quả: HTTP/1.1 200 OK
   # Payload: {"status":"ready"}
   ```

### 2.4. Trích xuất Nhật ký JSON và Triệu chứng Ghi nhận

**1. Log từ Container API:**
```json
{"timestamp": "2026-11-10T09:15:16.732104+00:00", "level": "WARNING", "logger": "backend.api.ready", "message": "Healthcheck ready thất bại: Database không phản hồi kết nối.", "status": "unhealthy", "database": "disconnected"}
```

**2. Log từ Container Worker:**
```json
{"timestamp": "2026-11-10T09:15:18.947910+00:00", "level": "ERROR", "logger": "backend.worker", "message": "Lỗi khi chạy reaper trong worker: (psycopg.OperationalError) failed to resolve host 'db': [Errno -2] Name or service not known\n(Background on this error at: https://sqlalche.me/e/21/e3q8)", "request_id": null}
{"timestamp": "2026-11-10T09:15:22.951135+00:00", "level": "ERROR", "logger": "backend.worker", "message": "Lỗi không mong muốn trong worker loop: (psycopg.OperationalError) failed to resolve host 'db': [Errno -5] No address associated with hostname\n(Background on this error at: https://sqlalche.me/e/21/e3q8)", "request_id": null}
```

**3. Khôi phục tự động sau khi DB trực tuyến:**
Ngay khi container DB được start lại (`09:15:42.169057`), API phục hồi sau 1.54s (`09:15:43.704665`). Worker tự động kết nối lại cơ sở dữ liệu mà không cần khởi động lại. Reaper quét và phục hồi job đang xử lý dở ở attempt 3:
```json
{"timestamp": "2026-11-10T09:16:15.081639+00:00", "level": "WARNING", "logger": "backend.worker.reaper", "message": "Job 7ded0493-cc0b-472d-bcec-2777198637b4 hết hạn lease (locked_until=2026-11-10 09:16:10.945886+00:00), đưa về queued và tăng attempt 2 -> 3", "request_id": null}
{"timestamp": "2026-11-10T09:16:15.091295+00:00", "level": "INFO", "logger": "backend.worker", "message": "Worker worker-1 đã claim job 7ded0493-cc0b-472d-bcec-2777198637b4", "request_id": null, "event": "job_claimed", "job_id": "7ded0493-cc0b-472d-bcec-2777198637b4", "meeting_id": "0db9a18a-b613-4d96-bccb-c066149b3ad5", "worker_id": "worker-1", "stage": "diarize", "attempt": 3, "status": "running"}
{"timestamp": "2026-11-10T09:16:15.100279+00:00", "level": "INFO", "logger": "meeting_pipeline.runner", "message": "stage_skipped", "request_id": null, "event": "stage_skipped", "job_id": "7ded0493-cc0b-472d-bcec-2777198637b4", "meeting_id": "0db9a18a-b613-4d96-bccb-c066149b3ad5", "stage": "preprocess", "attempt": 3, "duration_sec": 0.0, "status": "skipped"}
{"timestamp": "2026-11-10T09:16:15.103652+00:00", "level": "INFO", "logger": "meeting_pipeline.runner", "message": "stage_skipped", "request_id": null, "event": "stage_skipped", "job_id": "7ded0493-cc0b-472d-bcec-2777198637b4", "meeting_id": "0db9a18a-b613-4d96-bccb-c066149b3ad5", "stage": "vad", "attempt": 3, "duration_sec": 0.0, "status": "skipped"}
{"timestamp": "2026-11-10T09:16:15.107842+00:00", "level": "INFO", "logger": "meeting_pipeline.runner", "message": "stage_skipped", "request_id": null, "event": "stage_skipped", "job_id": "7ded0493-cc0b-472d-bcec-2777198637b4", "meeting_id": "0db9a18a-b613-4d96-bccb-c066149b3ad5", "stage": "asr", "attempt": 3, "duration_sec": 0.0, "status": "skipped"}
{"timestamp": "2026-11-10T09:16:15.112088+00:00", "level": "INFO", "logger": "meeting_pipeline.runner", "message": "stage_started", "request_id": null, "event": "stage_started", "job_id": "7ded0493-cc0b-472d-bcec-2777198637b4", "meeting_id": "0db9a18a-b613-4d96-bccb-c066149b3ad5", "stage": "diarize", "attempt": 3, "status": "running"}
{"timestamp": "2026-11-10T09:17:01.774080+00:00", "level": "INFO", "logger": "backend.worker", "message": "Job 7ded0493-cc0b-472d-bcec-2777198637b4 đã hoàn thành thành công", "request_id": null, "event": "job_succeeded", "job_id": "7ded0493-cc0b-472d-bcec-2777198637b4", "meeting_id": "0db9a18a-b613-4d96-bccb-c066149b3ad5", "worker_id": "worker-1", "stage": "summarize", "attempt": 3, "status": "succeeded"}
```

---

## 3. Tổng kết Đánh giá và Cải tiến Runbook

1. **Hiệu quả phát hiện sự cố:**
   - Thời gian phát hiện (Mean Time to Detect - MTTD) cực kỳ nhanh: **0.53s** cho worker crash (nhờ `/metrics` đối chiếu container status) và **4.57s** cho DB downtime (nhờ endpoint `/ready`).
   - Thời gian xác định nguyên nhân (Mean Time to Identify - MTTI): **0.70s** cho worker crash và **4.88s** cho DB outage.
2. **Khả năng tự phục hồi (Self-Healing):**
   - Cơ chế Reaper giải phóng và thu hồi job hết hạn lease sau 60s mà không cần sự can thiệp thủ công vào cơ sở dữ liệu.
   - Nhờ lưu trữ artifact trung gian (checkpoint caching), khi chạy lại attempt 3, các stage `preprocess`, `vad`, `asr` được bỏ qua ngay lập tức (`stage_skipped`), tiết kiệm tài nguyên tính toán.
3. **Cải tiến tài liệu đã bổ sung:**
   - Đã bổ sung mục `6.1` và `6.2` vào `docs/backend/BE-19.md` hướng dẫn chi tiết các bước xử lý đặc thù cho sự cố worker crash (exit code 137, reaper recovery) và sự cố ngắt kết nối cơ sở dữ liệu.
