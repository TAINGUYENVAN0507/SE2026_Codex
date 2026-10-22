# 2026-10-22 · Member A: frontend

- **Người làm:** A (`@mactuongmvt`), nhánh `vantuong`.
- **Số commit:** 5.
- **Mục tiêu:** contract v0 đã đủ endpoint (PR #10). Hôm nay đưa các màn hình chính lên API qua MSW: danh sách meeting (FE-04), upload (FE-05), transcript (FE-09), player (FE-08), đổi tên speaker (FE-11).

Đọc trước: `contracts/openapi.json`, `contracts/fixtures/api/` (B vừa thêm `meeting_list.json`, `meeting_created.json`, `transcript_ready.json`, `transcript_pending.json`, `error_version_conflict.json`), `contracts/error_codes.md`.

Lệnh kiểm tra cho mọi commit, chạy trong `frontend/`:

```bash
npm run lint && npm run format:check && npm run typecheck && npm test && npm run build
```

## Bước 0 (không tính vào số commit)

```bash
git checkout vantuong
git fetch origin
git merge origin/main
```

`main` đã có `src/api/schema.d.ts` sinh lại theo contract mới (PR #12). Giữ bản của `main`, không sửa tay.

## 5 commit

### 1. [ ] Danh sách meeting từ `GET /meetings` (FE-04)

- **Việc:** `useMeetingsQuery({page, status})` gọi API client; `MeetingListPage` hiển thị đủ 4 trạng thái loading, empty, error (qua `ApiError`), data. Refetch mỗi 5 s khi còn meeting `queued` hoặc `processing`, dừng khi không còn. MSW handler dùng `meeting_list.json`.
- **Xong khi:** RTL test cho 4 trạng thái, và test polling dừng đúng lúc bằng fake timers.
- **Message:** `feat(frontend): meeting list from GET /meetings with four states (FE-04)`
- **Hash:**

### 2. [ ] Upload bằng XHR có progress và hủy (FE-05)

- **Việc:** `uploadMeeting(file, form, key, onProgress)` gửi multipart tới `POST /api/v1/meetings` bằng XHR, kèm header `Idempotency-Key` (hook đã có), `consent_confirmed=true`. Có progress và nút hủy (`xhr.abort()`). Lỗi 400, 409, 413, 415, 422 đi qua `ApiError` với thông điệp tiếng Việt. Nhận 201 thì chuyển tới `/meetings/:id`.
- **Xong khi:** test bằng XHR giả: progress tăng dần; hủy thì không chuyển trang; retry dùng lại cùng key; từng mã lỗi hiện đúng thông điệp.
- **Message:** `feat(frontend): upload meetings with progress, cancel and error mapping (FE-05)`
- **Hash:**

### 3. [ ] Hiển thị transcript từ API (FE-09)

- **Việc:** `useTranscriptQuery(meetingId)`. Trạng thái `pending` hiện skeleton. Trạng thái `ready` nhóm các segment liền nhau của cùng speaker, có màu theo speaker và thời gian `hh:mm:ss`. `speaker_id: null` hiện "Chưa xác định" màu xám. Cờ `low_confidence`, `overlap` hiện badge. MSW dùng `transcript_ready.json`, `transcript_pending.json`.
- **Xong khi:** RTL test theo fixture: 2 speaker cộng 1 segment chưa xác định, trạng thái pending, format thời gian.
- **Message:** `feat(frontend): render transcript from the API with unknown speakers and flags (FE-09)`
- **Hash:**

### 4. [ ] Player: click thời gian để tua, highlight đoạn đang phát (FE-08)

- **Việc:** trên trang chi tiết, click timestamp thì đặt `audio.currentTime`. Đoạn đang phát (dùng `useActiveSegment` đã có) được highlight và tự cuộn tới; có công tắc bật tắt tự cuộn. Tốc độ phát 0.75–2×.
- **Xong khi:** RTL test: click đặt đúng `currentTime`, highlight đổi theo `timeupdate`, tắt tự cuộn thì không gọi `scrollIntoView`.
- **Message:** `feat(frontend): seek on timestamp click and highlight the playing segment (FE-08)`
- **Hash:**

### 5. [ ] Đổi tên speaker (FE-11)

- **Việc:** đổi tên inline (1–50 ký tự), gọi `PATCH /meetings/{id}/speakers/{speaker_id}` kèm `version`. Thành công thì tên mới hiện ở mọi segment. 422 `SPEAKER_NAME_DUPLICATE` thì báo lỗi tại ô nhập. 409 `VERSION_CONFLICT` thì hiện dialog đề nghị tải lại, không mất chữ đang gõ.
- **Xong khi:** RTL test: đổi tên lan ra toàn transcript, tên trùng, tên rỗng, 409.
- **Message:** `feat(frontend): rename speakers inline with version conflict handling (FE-11)`
- **Hash:**

## Việc chung (không phải commit)

- [ ] SH-01: ghi âm buổi họp pilot có consent (chưa làm hôm qua). Audio gửi cho C qua kênh riêng, không commit.

## Cuối ngày

- [ ] Tick các ô ở trên và ghi hash. Cập nhật `docs/frontend/` cho FE-04, FE-05, FE-08, FE-09, FE-11.
- [ ] Push `vantuong`, mở PR vào `main`. **Không tự merge.**
