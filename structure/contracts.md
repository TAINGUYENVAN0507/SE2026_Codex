# Contracts giữa các module

Contract là chỗ duy nhất hai module được phép phụ thuộc vào nhau. Mỗi contract có một producer (người sở hữu, được sửa) và một hoặc nhiều consumer (người dùng, phải đồng ý khi có breaking change).

## Danh sách

| Contract | File | Producer | Consumer | Sinh và kiểm drift | Trạng thái |
|---|---|---|---|---|---|
| I/O của các stage pipeline | `contracts/pipeline/*.schema.json`, `contracts/fixtures/pipeline/*.json` | C, sinh từ `pipeline/meeting_pipeline/schemas.py` | B (worker persist) | `cd pipeline && uv run python -m meeting_pipeline export-contracts`, thêm `--check` để kiểm drift. CI `pipeline.yml` chạy test drift. | ✓ `schema_version` 1.0 |
| Python API của pipeline | `run_job()`, `overall_progress()`, `JobSpec`, `PipelineOutcome`, các exception trong `errors.py` | C | B (worker) | Mục "Gọi pipeline từ worker" trong `pipeline/README.md` | ✓ |
| CLI của stage | `python -m meeting_pipeline run-stage <stage> --workdir <dir>`; exit 0 = OK, 10 = permanent, 20 = transient | C | Runner (C), B khi debug | `pipeline/README.md` | ✓ |
| REST API | `contracts/openapi.json`, `contracts/fixtures/api/*.json` | B, sinh từ FastAPI | A (type sinh tự động, MSW) | `make openapi` và workflow kiểm drift | ○ BE-02 |
| Mã lỗi | `contracts/error_codes.md` | B, gồm cả mã lỗi của pipeline lấy từ `errors.py` | A (đổi sang thông điệp tiếng Việt) | | ○ BE-02 |
| Export JSON | `contracts/export.schema.json` | A | Người dùng; B dùng trong test | | ○ FE-15. Bản demo đang dùng schema `preview-1`, chưa phải contract. |

## Quy ước dữ liệu chung

Áp dụng cho mọi contract ở trên.

| Chủ đề | Quy ước |
|---|---|
| Tên field | `snake_case` cho cả JSON của API lẫn file của pipeline. Frontend dùng type sinh từ OpenAPI, không đổi sang camelCase. |
| Thời gian trên audio | `start_sec`, `end_sec`: số thực, tính bằng giây từ đầu file gốc, làm tròn 3 chữ số (ms). Bất biến `0 <= start_sec < end_sec <= duration_sec`. Segment sắp theo `(start_sec, end_sec)`, chỉ được chồng lấn khi có cờ `overlap`. |
| Thời điểm, ngày | ISO 8601 UTC, ví dụ `2026-10-15T08:30:00Z`. Ngày dạng `YYYY-MM-DD`. Frontend hiển thị theo giờ `Asia/Ho_Chi_Minh`. |
| ID | UUID v4 dạng chuỗi, opaque: không parse. Pipeline chưa có UUID nên evidence của summary trỏ tới `index` của segment (`evidence_segment_indices`). B ánh xạ sang `segment_id` khi persist. |
| Field vắng | Mọi field luôn có mặt. Không biết thì `null`, danh sách rỗng thì `[]`. |
| Speaker | `label` dạng `SPEAKER_00`, pipeline đánh số theo thứ tự xuất hiện. `default_name` là "Speaker N" (N = số thứ tự + 1). `display_name` do người dùng đặt. `speaker_label`/`speaker_id` bằng `null` nghĩa là chưa xác định được speaker. |
| Phiên bản entity | Entity sửa được có `version` (số nguyên). Gửi version cũ thì nhận 409 `VERSION_CONFLICT`, kèm bản hiện tại trong `details.current`. |
| Mã lỗi | `UPPER_SNAKE`, ổn định: không đổi nghĩa, không dùng lại cho lỗi khác. |
| `schema_version` | Dạng `MAJOR.MINOR` trong mỗi file của pipeline và trong export JSON. |

Các giá trị trạng thái:

| Đối tượng | Giá trị |
|---|---|
| Meeting | `queued`, `processing`, `ready`, `partial` (có transcript nhưng summary lỗi), `failed` (không có transcript) |
| Job | `queued`, `running`, `retry_scheduled`, `succeeded`, `failed`, `cancelled` |
| Stage | `preprocess`, `vad`, `asr`, `diarize`, `merge`, `summarize` |
| Transcript | `pending`, `ready`, `failed` |
| Diarization | `ok`, `fallback` |
| Summary | `pending`, `ready`, `failed`, `insufficient_content`, `disabled` |

## Quy tắc thay đổi contract

1. **Không sửa tay file được sinh ra** (`contracts/pipeline/*`, `contracts/openapi.json`). Sửa nguồn (Pydantic, FastAPI), sinh lại rồi commit cả hai.
   PR đổi `contracts/openapi.json` phải sinh lại luôn type của frontend (`cd frontend && npm ci && npm run gen:api`) và commit `frontend/src/api/schema.d.ts` cùng PR. Nếu không, bước kiểm drift của `frontend.yml` trên `main` sẽ đỏ.
2. **Additive** (thêm field nullable hoặc có default, thêm endpoint): tăng minor, ví dụ `1.0` → `1.1`. Consumer cũ vẫn chạy.
3. **Breaking** (đổi tên, xóa field, đổi kiểu, đổi nghĩa, thêm giá trị vào enum): tăng major. Consumer phải đồng ý trước. Producer cập nhật fixture, và phần code của consumer cũng được cập nhật trong cùng PR hoặc trong PR của consumer được merge cùng lúc.
4. **PR chạm `contracts/`:** tick ô "Đổi contract" trong PR template, tag consumer vào PR. Consumer xác nhận bằng comment trong PR, sau đó nhóm trưởng mới merge.
5. **Sau khi freeze API v1** (mốc M1, tuần 4): chỉ được thay đổi additive.
6. **Consumer kiểm `schema_version`** trước khi dùng. Major không hỗ trợ thì báo lỗi rõ ràng (worker báo `PIPELINE_OUTPUT_INVALID`), không đoán.

## Làm việc song song trên mock

| Ai | Làm việc trên | Không phải chờ |
|---|---|---|
| A | Dữ liệu demo trong frontend; sau BE-02 chuyển sang MSW đọc `contracts/fixtures/api/` | Backend chạy thật |
| B | Fake pipeline (`PIPELINE_BACKEND=fake`, `FAKE_SCENARIO`) và `contracts/fixtures/pipeline/` | Model AI thật |
| C | CLI `run-stage` và `run_job()` trên workdir tự tạo | Backend, DB |

Fake pipeline và fixtures được giữ lâu dài cho CI, không xóa khi đã có bản thật.
