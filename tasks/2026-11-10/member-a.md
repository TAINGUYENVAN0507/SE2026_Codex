# 2026-11-10 · Member A: giao diện chịu được quá tải, thời gian job, E2E qua container web (Đợt 5)

- **Người làm:** A (`@vantuong`), nhánh `vantuong`.
- **Số commit:** 10, **cộng việc review**.
- **Điều kiện bắt đầu:** #44 và #45 đã vào `main` (2026-11-10).
- **Hạn:** mở PR trước tối 11-11. Ngày 11-12 đóng băng code (chỉ sửa lỗi), xem [`tasks/ROADMAP.md`](../ROADMAP.md), mục Lịch tới hạn nộp.
- **Mục tiêu:** từ #43, API trả `503 SERVICE_UNAVAILABLE` kèm `Retry-After: 2` khi quá tải (`backend/app/core/admission.py`). Giao diện chưa biết xử lý trường hợp này. Thêm vào đó: giao diện hiện thời gian thật của job (VT-018), và E2E chạy qua đúng đường người dùng đi (nginx → API).

Kiểm tra trong `frontend/`: `npm run lint && npm test && npm run build`. E2E: `npm run e2e` như các đợt trước.

## Review (không bắt buộc, không tính commit)
Từ 2026-11-10, nhóm trưởng quyết định PR không cần chờ review của thành viên khác. Nhóm trưởng tự review diff, chờ CI xanh rồi merge. Nhận xét của bạn vẫn có ích nhưng không chặn merge.

## Bước 0
```bash
git checkout vantuong && git fetch origin && git merge origin/main
```

## 10 commit

### 1. [ ] Upload gặp 503: thông báo và tự thử lại với cùng `Idempotency-Key` (AD-018, VT-018)
- Khi `POST /meetings` trả 503 `SERVICE_UNAVAILABLE`, hiện thông báo tiếng Việt "máy chủ đang bận", đợi theo `Retry-After` (mặc định 2 s nếu thiếu), thử lại tối đa 3 lần với **cùng** `Idempotency-Key`. Hết lượt thì cho người dùng bấm thử lại, vẫn giữ key đó.
- Test MSW **đỏ trước**: 503 hai lần rồi 201 thì phải có đúng 1 meeting và 3 request cùng key; 503 bốn lần thì hiện nút thử lại.
- **Message:** `fix(frontend): upload waits and retries with the same key when the API is busy (AD-018)`

### 2. [ ] Poll tiến độ lùi lại khi 503 hoặc lỗi mạng (VT-018, FE-20)
- Poll `GET /jobs/{id}` hiện chạy mỗi 2 s. Khi gặp 503 hoặc lỗi mạng thì giãn khoảng poll theo `Retry-After` hoặc tăng dần (tối đa 10 s), không chồng request. Có kết quả 200 thì về lại 2 s. Thanh tiến độ không tụt về 0 khi lỗi.
- Test dùng fake timer: đếm số request trong 30 s khi API lỗi liên tục.
- **Message:** `fix(frontend): progress polling backs off on busy or failed responses (VT-018)`

### 3. [ ] Gặp 503 khi đang sửa thì không mất nội dung đã gõ (AD-018, FE-16)
- Các thao tác ghi khác: sửa đoạn transcript, đổi tên speaker, sửa tóm tắt, chạy lại job, xóa. Khi API trả 503, giữ nguyên nội dung người dùng đã gõ, hiện "máy chủ đang bận" và nút thử lại. Không tự gửi lại thao tác xóa.
- (`src/api/errorCoverage.test.ts` đã kiểm mọi mã lỗi có thông báo; việc này kiểm **hành vi** của từng màn hình khi gặp 503.)
- Test MSW **đỏ trước** cho ít nhất sửa đoạn transcript và đổi tên speaker.
- **Message:** `fix(frontend): edits survive a busy API and can be retried (AD-018)`

### 4. [ ] Hiện thời gian chờ trong hàng đợi, giờ bắt đầu và giờ xong (VT-018, FE-20)
- `JobStatusCard` đã hiện "Đã chạy …" (`ElapsedTime`). Worker chạy mỗi lúc 1 job nên khi đông, job chờ lâu ở `queued`. Thêm "Đã chờ …" (từ `created_at` tới `started_at` hoặc tới hiện tại), cùng giờ bắt đầu và giờ xong theo giờ máy người dùng.
- Test cho 3 trạng thái: đang chờ, đang chạy, đã xong. Thiếu trường thì không hiện `NaN` hay `Invalid Date`.
- **Message:** `feat(frontend): show queue wait, start and finish time of a job (VT-018)`

### 5. [ ] E2E qua container web trên Compose trong CI (BE-16, FE-19)
- B đã có job `compose-smoke` (API). Thêm job (hoặc bước) chạy **một** spec Playwright vào `http://localhost:8080` qua nginx: đăng nhập → upload → chờ xong → export. Tạo user tổng hợp như `backend/scripts/smoke_compose.py`.
- **Xong khi:** CI chạy spec đó trên container web thật. Thử trên nhánh tạm: sửa sai `proxy_pass` trong `infra/nginx` làm job đỏ, dán link run đỏ vào thân commit, rồi trả lại.
- **Message:** `test(e2e): one Playwright flow through the web container on Compose (BE-16)`

### 6. [ ] Chỉ dùng bàn phím đi hết luồng chính (FE-16)
- Playwright: dùng Tab/Enter/Space để đăng nhập, upload, mở cuộc họp, export, không dùng chuột. Focus luôn nhìn thấy được. Gặp chỗ không đi được thì sửa.
- **Message:** `test(frontend): keyboard-only main flow (FE-16)`

### 7. [ ] Coverage frontend có ngưỡng, ghi số thật (FE-16)
- Bật coverage (line và branch) trong Vitest, đặt ngưỡng bằng mức hiện tại trừ 2 điểm để không tụt. Ghi số đo được vào `frontend/README.md`. Không viết thêm test chỉ để kéo số.
- **Message:** `test(frontend): coverage thresholds at the measured level (FE-16)`

### 8. [ ] Clone sạch: README frontend chạy đúng từng bước (G0)
- Clone repo vào thư mục mới, làm theo `frontend/README.md` và phần frontend trong `README.md`: `npm ci`, dev, build, test, E2E. Bước nào sai hoặc thiếu thì sửa tài liệu. Ghi phiên bản Node đã dùng.
- **Message:** `docs(frontend): README steps verified on a clean clone (G0)`

### 9. [ ] Ảnh demo và kịch bản demo theo giao diện mới (FE-16)
- Cập nhật `docs/demo/` cho thông báo bận, poll lùi lại, thời gian job. Chỉ dùng dữ liệu tổng hợp.
- **Message:** `docs(demo): screenshots and script for busy state and job times (FE-16)`

### 10. [ ] Tick, hash (G0)
- Ghi hash từng commit vào file này. Việc chưa xong thì ghi "chuyển sang 11-11" và lý do, không tick.
- **Message:** `docs(tasks): record 2026-11-10 member A results (G0)`
