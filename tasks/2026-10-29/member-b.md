# 2026-10-29 · Member B: backend

- **Người làm:** B (`@minhquangha`), nhánh `haquang`.
- **Số commit:** 5.
- **Mục tiêu:** thay nốt các endpoint còn là stub, để mọi màn hình của A chạy với dữ liệu thật:
  - tóm tắt (`GET /summary`), export, tạo lại hoặc chạy lại job (BE-13, BE-10);
  - xóa meeting (BE-14).

Đọc trước:
- Mục BE-05, BE-10, BE-13, BE-14 và mục 10.4 (RT-06, RT-10, RT-14, RT-15, PRIV-12, PRIV-13) của kế hoạch.
- `contracts/error_codes.md` (`JOB_ALREADY_ACTIVE`, `JOB_ALREADY_SUCCEEDED`, `HAS_USER_EDITS`, `TRANSCRIPT_NOT_READY`, `FORMAT_NOT_SUPPORTED`).
- `backend/app/services/export/` của A (PR #29).
- `pipeline/README.md`, mục "Gọi pipeline từ worker": `transcript_override_path`, `from_stage`, `is_cancelled`.

Lệnh kiểm tra cho mọi commit, chạy trong `backend/` (cần Postgres: `docker compose up -d db` ở gốc repo):

```bash
uv run ruff check . && uv run ruff format --check . && uv run pytest
```

## Bước 0 (không tính vào số commit)

```bash
git checkout haquang
git fetch origin
git merge origin/main
```

- PR #28 đang chờ nhóm trưởng review. Làm tiếp trên `haquang`.
- Commit 2 dùng `services/export/` của A: merge `origin/main` sau khi #29 vào `main`, hoặc làm commit 3, 4, 5 trước.
- Tiêu đề PR #28 đã đúng format. Giữ như vậy.

## Phần 1: thay stub còn lại

Theo kiểm tra trên nhánh `haquang` lúc phân công, các chỗ sau vẫn trả fixture hoặc nội dung giả:
- `GET /summary` (`get_meeting_summary`);
- export (`export_meeting` trả `# Biên bản cuộc họp {id}`);
- `POST /meetings/{id}/jobs` (`retry_meeting_job`);
- nhánh fallback `if db is not None and current_user is not None` trong `get_meeting`, `get_meeting_transcript`, `get_job`.

### 1. [ ] `GET /summary` từ DB, bỏ nhánh stub (BE-05, BE-07)

- **Việc:**
  - Đọc summary theo meeting của owner. Trả trạng thái `pending`, `ready`, `failed`, `insufficient_content`, `disabled` đúng như pipeline ghi, kèm evidence là id segment, `version`, `is_edited`.
  - Xóa các hàm `load_*_fixture()` và nhánh fallback không còn dùng trong `meetings.py`, `jobs.py`.
- **Xong khi:** API test cho từng trạng thái, 404 với meeting của người khác (PRIV-12), không còn fixture nào được đọc trong `app/api/`.
- **Message:** `feat(backend): summary from the database and removal of stub fallbacks (BE-05)`
- **Hash:**

### 2. [ ] Export dựng từ DB (FE-15, BE-05)

- **Việc:**
  - Dựng `MeetingExport` từ DB, cả 2 biến thể:
    - `current`: bản đã sửa;
    - `ai_original`: `ai_text`, `ai_speaker_id` và summary trong `ai_outputs`.
  - Gọi `services/export/` của A, trả file kèm `Content-Disposition` dùng tên slug của A.
  - Chưa có transcript thì 409 `TRANSCRIPT_NOT_READY`; định dạng lạ thì 422 `FORMAT_NOT_SUPPORTED`.
- **Xong khi:** API test 3 định dạng × 2 biến thể; RT-13: gọi 3 lần cùng tham số thì ra cùng byte và không ghi gì vào DB; PRIV-12.
- **Message:** `feat(backend): export built from the database for both variants (BE-05, FE-15)`
- **Hash:**

## Phần 2: chạy lại job và xóa meeting

### 3. [ ] `POST /meetings/{id}/jobs` thật (BE-13)

- **Việc:**
  - Nhận `from_stage` (mặc định chạy lại cả pipeline) và `Idempotency-Key`.
  - Đang có job `queued` hoặc `running` thì 409 `JOB_ALREADY_ACTIVE` kèm job.
  - Job gần nhất đã thành công mà gửi lại cùng yêu cầu thì 409 `JOB_ALREADY_SUCCEEDED`.
  - Chạy lại từ `asr` hoặc `diarize` khi người dùng đã sửa transcript thì 409 `HAS_USER_EDITS`, vì sẽ mất bản sửa.
  - Partial unique index của DB đảm bảo chỉ 1 job active.
- **Xong khi:** RT-06 (5 request đồng thời: đúng 1 job, 4 lần 409 kèm job id); RT-10 (gửi lại sau khi xong: 409, dùng lại key cũ thì nhận response cũ).
- **Message:** `feat(backend): create jobs with from_stage, idempotency and conflict codes (BE-13)`
- **Hash:**

### 4. [ ] Tạo lại tóm tắt từ transcript đã sửa (BE-10, RT-14)

- **Việc:**
  - `from_stage=summarize`: worker xuất transcript hiện tại trong DB (text và speaker đã sửa, tên hiển thị của speaker) thành file JSON đúng `contracts/pipeline/transcript.schema.json`, rồi truyền qua `transcript_override_path`.
  - Pipeline chỉ chạy summarize, không chạy lại ASR.
  - Summary mới vào `ai_outputs`. Nếu người dùng chưa sửa summary thì thay summary hiện tại; đã sửa thì giữ bản của người dùng và trả trạng thái để UI hỏi.
- **Xong khi:** RT-14 với `FAKE_SCENARIO=summary_fail` rồi retry: meeting từ `partial` thành `ready`, ASR không chạy lại (kiểm `stage_status`); test override chứa text đã sửa.
- **Message:** `feat(backend): regenerate the summary from the edited transcript (BE-10)`
- **Hash:**

### 5. [ ] Xóa meeting: hủy job, xóa file và row (BE-14)

- **Việc:**
  - `DELETE /meetings/{id}`, thêm vào contract và sinh lại `schema.d.ts`.
  - Job đang chạy chuyển `cancelled`. Worker truyền `is_cancelled` (đọc trạng thái job trong DB, tối đa mỗi giây) vào `run_job`; pipeline kill stage trong khoảng 1 s.
  - Xóa audio, artifacts, các row liên quan (kể cả `edit_events` theo meeting, trigger cần cho phép trường hợp này).
  - Log chỉ ghi meeting id, không ghi tiêu đề hay nội dung.
- **Xong khi:**
  - RT-15: xóa khi job đang chạy với `FAKE_SCENARIO=slow`, thì job `cancelled`, không còn file hay row mồ côi.
  - PRIV-13: `GET /audio` sau khi xóa trả 404.
- **Message:** `feat(backend): delete a meeting with its job, files and rows (BE-14)`
- **Hash:**

## Việc chung (không phải commit)

- [ ] SH-01: ghi âm buổi họp pilot có consent (vẫn chưa có).

## Cuối ngày

- [ ] Tick các ô ở trên và ghi hash. Làm không hết thì ghi rõ commit nào chuyển sang ngày sau.
- [ ] Push `haquang`, mở PR vào `main` (hoặc push thêm vào #28 nếu chưa merge), tiêu đề theo format commit. **Không tự merge.** Nếu đổi `contracts/openapi.json` thì commit cả `frontend/src/api/schema.d.ts`.
