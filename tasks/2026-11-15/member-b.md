# 2026-11-15 · Member B: hai trạng thái sai cùng kiểu #56, log không giữ dữ liệu cá nhân (Đợt 9, sau hạn nộp)

- **Người làm:** B (`@minhquangha`), nhánh `haquang`.
- **Số commit:** 5.
- **Điều kiện bắt đầu:** #56 (B) đã vào `main` (C review diff, CI xanh 15/15, merge `1e71c89`).
- **Phạm vi:** sau hạn nộp 11-14. Chỉ sửa lỗi, thêm test và bằng chứng; không thêm tính năng.
- **Hạn:** mở PR khi push xong, trong ngày 11-15.

## Bước 0
```bash
git checkout haquang && git fetch origin && git merge origin/main
```

**Log trên Windows:** PowerShell `>` ghi UTF-16, nên `docs/evidence/final/summary-partial-red-2026-11-13.log` của #56 hiện là file nhị phân trên GitHub (lần thứ hai, sau `deletion-2026-11-12.log`). Dùng `uv run pytest ... 2>&1 | Out-File -Encoding utf8 <file>`. Từ hôm nay có test chặn file bằng chứng không phải UTF-8 (C, việc 1).

## Việc

### 1. [x] `GET /meetings/{id}` báo `summary_status: "ready"` cho meeting `partial` (BE-05)
- `backend/app/api/v1/meetings.py:87`: `if meeting.status in ("ready", "partial")` gán `summary_status = "ready"`. Meeting `partial` là transcript xong nhưng tóm tắt lỗi, nên đúng phải là `failed`. Sau #56, `GET summary` trả `failed` còn `GET meeting` vẫn trả `ready`: hai endpoint mâu thuẫn.
- Test đỏ trước trong `backend/tests/api/`: meeting `partial` → `summary_status == "failed"`, `transcript_status == "ready"`. Log đỏ UTF-8: `docs/evidence/final/meeting-partial-red-2026-11-15.log`. Rồi sửa. Kiểm `openapi.json` không drift.
- **Message:** `fix(backend): meeting detail reports failed summary for partial meetings (BE-05)`
- **Commit:** `8ae2631`

### 2. [x] Transcript của meeting `ready` không có segment trả `pending` mãi (BE-05)
- `backend/app/api/v1/transcript.py:73`: khi meeting `ready`/`partial` nhưng 0 segment (ví dụ audio im lặng), `if segments:` không chạy, hàm rơi xuống dòng 116 và trả `pending`. Frontend sẽ poll transcript mãi.
- Test đỏ trước: meeting `ready`, 0 segment → `status == "ready"`, `segments == []`. Log đỏ UTF-8: `docs/evidence/final/transcript-empty-red-2026-11-15.log`. Rồi sửa. Nếu thấy hành vi hiện tại là cố ý (có ghi ở `contracts/` hoặc `structure/`), ghi lý do và đổi việc này thành test khóa hành vi đó.
- **Message:** `fix(backend): transcript of a ready meeting with no segments is ready, not pending (BE-05)`
- **Commit:** `d9ef3c3`

### 3. [x] Log access không giữ dữ liệu cá nhân (AD-018, BE-19)
- `docs/evidence/ad-018/README.md` dòng "Log access của uvicorn": **chưa có test**. `app.access` (`backend/app/core/middleware.py:39`) ghi method, path, status, duration, request_id.
- Test: upload với canary ở tiêu đề, tên file và `Idempotency-Key`, gọi thêm `GET /meetings?q=<canary>` nếu có tham số tìm kiếm; bắt log của `app.access` và `uvicorn.access` bằng `caplog`; assert không record nào chứa canary. Ghi rõ uvicorn có bật access log không (cờ `--no-access-log`, `infra/`, `docker-compose.yml`).
- Sửa dòng tương ứng trong `docs/evidence/ad-018/README.md`: tên test và DB.
- **Message:** `test(backend): access logs carry no personal data (AD-018, BE-19)`
- **Commit:** `3ee0ea3`

### 4. [x] Log container: không có canary, có giới hạn ở mọi service (AD-018, BE-16)
- `docs/evidence/ad-018/README.md` dòng "Log đã ghi ra file hoặc của Docker": **chưa có test**, chỉ kiểm qua `caplog`.
- `backend/scripts/smoke_compose.py`: upload với tiêu đề canary, đợi job xong, rồi `docker compose logs api worker` không chứa canary. Chạy ở job `compose-smoke` của CI (máy không có Docker thì dựa vào CI, ghi link run).
- Test đọc `docker-compose.yml`: mọi service có `logging` `json-file` với `max-size` và `max-file` (hiện chỉ `api` và `worker` có, dòng 48 và 81). Sửa compose cho đủ.
- Bảng AD-018 ghi rõ: log Docker xoay vòng theo dung lượng (`10m` × `3`), **không** theo 28 ngày.
- **Message:** `test(infra): container logs hold no title canary and are bounded (AD-018, BE-16)`
- **Commit:** `6e91438`

### 5. [x] Tick, hash (G0)
- Ghi hash từng commit; hash của chính commit này ghi "commit này".
- **Message:** `docs(tasks): record 2026-11-15 member B results (G0)`
- **Commit:** commit này

## Việc chung (không tính commit)

- Comment review lên PR ngày 11-15 của A trong 18 giờ kể từ lúc A mở PR (đọc diff, chạy test liên quan, ghi kết quả). Nhóm trưởng vẫn merge khi CI xanh, không chờ review. Lý do: `docs/evidence/pr-response-times.md` hiện ghi 18/23 PR merge khi chưa có phản hồi của người khác (RE-018 20 giờ, AD-018 18 giờ đang ◐).
