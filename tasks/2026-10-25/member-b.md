# 2026-10-25 · Member B: backend

- **Người làm:** B (`@minhquangha`), nhánh `haquang`.
- **Số commit:** 5.
- **Mục tiêu:**
  - Sửa 2 lỗi tìm ra khi review PR #25.
  - Làm xong phần còn lại của Edit APIs (BE-11): action items, tiêu đề.
  - Lịch sử chỉnh sửa từ DB (BE-12), để panel lịch sử của A (FE-14) chạy với backend thật.

Đọc trước:
- Mục BE-11, BE-12, mục 7.1 (`version`, 409) và AUD-01…12 của kế hoạch.
- `contracts/fixtures/api/action_items.json`, `edits.json`.

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

- PR #25 đã được merge (`ec50e82`). 3 lỗi của ngày hôm qua đã được sửa đúng.
- [ ] **Tiêu đề PR theo format commit.** PR #25 vẫn có tiêu đề "Haquang" (lần thứ 5: #7, #10, #16, #20, #25). Ví dụ cho hôm nay: `fix(backend): atomic version checks, lease ownership, action items and edit history (BE-08, BE-11, BE-12)`. Đổi tiêu đề PR mà không cần đổi tên nhánh: `gh pr edit <số> --title "..."`.

## Phần 0: sửa lỗi tìm ra khi review PR #25

### 1. [ ] Optimistic locking nguyên tử (BE-11)

- **Lỗi:**
  - `meetings.py:904`, `:1128`, `:1313` đọc bản ghi, so `payload.version` với `version`, rồi mới ghi.
  - Hai request đồng thời cùng `version=2`, ví dụ từ 2 tab, đều qua được bước kiểm. Cả hai cùng ghi `version=3`, nên bản sửa đầu bị mất mà không ai nhận được 409. Có 2 edit event cùng `entity_version_after=3`.
- **Việc:**
  - Dùng `UPDATE ... SET ..., version = version + 1 WHERE id = :id AND version = :expected`. Nếu `rowcount == 0` thì trả 409 kèm bản hiện tại.
  - Có thể dùng `version_id_col` của SQLAlchemy. Áp dụng cho segment, speaker, summary, và action item ở commit 3.
- **Xong khi:** test trên Postgres với 2 session: hai lần PATCH cùng `version`, một lần 200, một lần 409; chỉ có 1 edit event.
- **Message:** `fix(backend): atomic optimistic locking with a conditional update (BE-11)`
- **Hash:**

### 2. [ ] Heartbeat dừng job khi đã mất lease (BE-08)

- **Lỗi:** `heartbeat_job()` (`reaper.py`) luôn gia hạn `locked_until`, không kiểm job còn thuộc worker này không. Tình huống lỗi:
  1. DB bị gián đoạn hơn 60 s, lease hết hạn.
  2. Reaper trả job về `queued`, worker khác nhận job.
  3. Worker cũ kết nối lại vẫn chạy tiếp và ghi đè lease của worker mới.
  4. Hai worker cùng chạy một job trên cùng `workdir`.
- **Việc:**
  - Heartbeat dùng `UPDATE jobs SET locked_until = ... WHERE id = :id AND status = 'running' AND locked_by = :worker`.
  - `rowcount == 0` thì raise `LeaseLostError`. Pipeline kill stage đang chạy, vì callback ném lỗi (xem `pipeline/README.md`).
  - Worker không ghi kết quả, không đổi trạng thái job, chỉ log.
- **Xong khi:** test: reaper requeue và worker khác claim giữa chừng, thì worker cũ dừng trong 1 lần heartbeat và không ghi gì vào DB.
- **Message:** `fix(backend): heartbeat stops the job when the lease is lost (BE-08)`
- **Hash:**

## Phần 1: Edit APIs và audit (BE-11, BE-12)

### 3. [ ] Action items: thêm, sửa, xóa mềm (BE-11)

- **Việc:**
  - `POST`, `PATCH`, `DELETE /meetings/{id}/action-items[/{item_id}]` thật, thay cho stub.
  - `description` 1–1000 ký tự. `assignee_speaker_id` phải là speaker của cùng meeting, hoặc dùng `assignee_name` tự do. `due_date` có thể null. `status` là open hoặc done.
  - `DELETE` là xóa mềm (`deleted_at`), item đã xóa không còn trong `GET`.
  - Item do AI tạo (`source=ai`) giữ `ai_original`. Có `version`; mọi thay đổi ghi `edit_events`.
- **Xong khi:** API test happy path, 422, 409, 404 (meeting của người khác) cho từng method; xóa rồi `GET` không còn item.
- **Message:** `feat(backend): action item CRUD with soft delete and versions (BE-11)`
- **Hash:**

### 4. [ ] Sửa tiêu đề meeting; mỗi trường đổi một edit event (BE-11)

- **Việc:**
  - `PATCH /meetings/{id}` sửa `title` (1–200 ký tự) kèm `version`.
  - Sửa luôn chỗ PATCH segment đổi cả text lẫn speaker: hiện tạo 1 event với `field=None`, khiến panel lịch sử của A không lọc được theo trường. Giờ mỗi trường đổi giá trị thì tạo 1 event riêng.
  - Dùng chung một hàm `record_edit()` trong `services/audit/`.
- **Xong khi:** test: đổi cả text và speaker thì có 2 event với `field` là `text` và `speaker_id`; đổi tiêu đề có event; cập nhật không đổi giá trị thì không có event.
- **Message:** `feat(backend): meeting title edits and one edit event per changed field (BE-11)`
- **Hash:**

### 5. [ ] `GET /edits` từ DB, chặn sửa lịch sử (BE-12)

- **Việc:**
  - `GET /meetings/{id}/edits` lọc theo `entity_type`, `entity_id`, `field`, có phân trang (`limit`, `offset`, `total`), mới nhất lên đầu, đúng format của `edits.json`.
  - Migration Alembic thêm trigger Postgres chặn `UPDATE` và `DELETE` trên `edit_events`. Chỉ cho xóa theo meeting khi xóa cả meeting (BE-14 làm sau).
- **Xong khi:** API test lọc và phân trang; test Postgres: `UPDATE edit_events` bị trigger từ chối (AUD-xx).
- **Message:** `feat(backend): edit history from the database with an append-only trigger (BE-12)`
- **Hash:**

## Việc chung (không phải commit)

- [ ] SH-01: ghi âm buổi họp pilot có consent (vẫn chưa có).

## Cuối ngày

- [ ] Tick các ô ở trên và ghi hash. Làm không hết thì ghi rõ commit nào chuyển sang ngày sau.
- [ ] Push `haquang`, mở PR vào `main`, tiêu đề theo format commit. **Không tự merge.** Nếu đổi `contracts/openapi.json` thì commit cả `frontend/src/api/schema.d.ts`.
