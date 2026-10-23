# 2026-10-23 · Member A: frontend

- **Người làm:** A (`@mactuongmvt`), nhánh `vantuong`.
- **Số commit:** 5.
- **Mục tiêu:** phần chỉnh sửa của MVP (nối API qua MSW): sửa segment (FE-10), tóm tắt (FE-12), action items (FE-13). Tách phần ghi âm thành hook có test để chuẩn bị bộ test PRIV (FE-06).

Đọc trước: mục 7.1 (version, 409 `VERSION_CONFLICT`), 7.3 (ví dụ JSON summary, action item) của kế hoạch; `contracts/fixtures/api/` (`summary_ready.json`, `summary_disabled.json`, `action_items.json`, `error_version_conflict.json`); [`rules/privacy-security.md`](../../rules/privacy-security.md) mục "Ghi âm trên trình duyệt".

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

## 5 commit

### 1. [ ] Sửa text của segment (FE-10)

- **Việc:** sửa ngay tại chỗ: Enter (hoặc click) để mở ô sửa, Ctrl+Enter để lưu, Esc để hủy. Gọi `PATCH /meetings/{id}/segments/{segment_id}` kèm `version`. Cập nhật lạc quan (optimistic update), lỗi thì hoàn tác. 409 thì hiện dialog đề nghị tải lại và **giữ nguyên chữ đang gõ**. Chỉ cho sửa khi transcript `ready`. Kiểm tra 1–5000 ký tự.
- **Xong khi:** RTL test: thành công (reload vẫn còn qua MSW), 409, hoàn tác khi gặp 500, text rỗng, text quá dài.
- **Message:** `feat(frontend): inline segment text editing with version conflicts (FE-10)`
- **Hash:**

### 2. [ ] Đổi speaker của segment, xem bản AI gốc (FE-10)

- **Việc:** dropdown đổi `speaker_id` của segment, có lựa chọn "Chưa xác định". Segment có `is_edited` thì hiện badge "Đã sửa". Công tắc "Bản AI gốc" hiện `ai_text`, `ai_speaker_id` ở chế độ chỉ đọc.
- **Xong khi:** RTL test đổi speaker, đặt về chưa xác định, bật tắt bản AI gốc.
- **Message:** `feat(frontend): change segment speakers and show the AI original (FE-10)`
- **Hash:**

### 3. [ ] Tóm tắt từ API, có chỉnh sửa (FE-12)

- **Việc:** thay dữ liệu demo trong `NotesPanel` bằng `GET /meetings/{id}/summary`. Sửa overview, key points, decisions (thêm, xóa, sửa), lưu bằng `PUT` kèm `version`. Hiện đủ các trạng thái `pending`, `failed` (có nút "Tạo lại tóm tắt"), `insufficient_content`, `disabled`. Click evidence thì tua tới segment tương ứng. Badge AI/Đã sửa.
- **Xong khi:** RTL test từng trạng thái (`summary_ready.json`, `summary_disabled.json`), payload của PUT đúng, 409.
- **Message:** `feat(frontend): summary from the API with editing and all states (FE-12)`
- **Hash:**

### 4. [ ] Action items: thêm, sửa, xóa (FE-13)

- **Việc:** `GET/POST/PATCH/DELETE /meetings/{id}/action-items`. Mô tả bắt buộc (1–1000 ký tự). Assignee chọn từ speaker hoặc nhập tự do. Hạn dùng date picker, có thể để trống, và hiện kèm `due_date_text` gốc. Trạng thái open/done. Badge AI/User và "Cần kiểm tra" (`needs_review`). Xóa có hỏi xác nhận. Không có hạn thì hiện "Chưa có hạn", không có người nhận thì hiện "Chưa giao".
- **Xong khi:** RTL test thêm, sửa, xóa, các field null, 409 (fixture `action_items.json`).
- **Message:** `feat(frontend): action item CRUD with nullable assignee and due date (FE-13)`
- **Hash:**

### 5. [ ] Hook `useRecorder` có state machine (FE-06)

- **Việc:** tách logic ghi âm khỏi `NewMeetingPage.tsx` thành `useRecorder`, với các trạng thái `idle → requesting → recording → stopped → uploading → done`, cộng `denied` và `error`. Chỉ gọi `getUserMedia` trong handler click và sau khi đã tick consent. Dừng hoặc hủy thì gọi `track.stop()` cho mọi track; unmount thì cleanup. Chọn `mimeType` bằng `isTypeSupported` (webm/opus, rồi ogg/opus, rồi mp4).
- **Xong khi:** Vitest với `MediaRecorder` và `getUserMedia` giả: các chuyển trạng thái; chưa consent thì gọi `getUserMedia` 0 lần (PRIV-02); dừng thì mọi track có `readyState === "ended"` (PRIV-04); hủy thì không upload (PRIV-05); unmount thì dừng track (PRIV-09).
- **Message:** `feat(frontend): useRecorder state machine with privacy guarantees (FE-06)`
- **Hash:**

## Việc chung (không phải commit)

- [ ] SH-01: ghi âm buổi họp pilot có consent (vẫn chưa có).

## Cuối ngày

- [ ] Tick các ô ở trên và ghi hash. Cập nhật `docs/frontend/` (FE-06, FE-10, FE-12, FE-13).
- [ ] Push `vantuong`, mở PR vào `main`. **Không tự merge.**
