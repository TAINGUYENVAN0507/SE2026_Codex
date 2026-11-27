# 2026-11-27 · Member A: E2E không ghi vào `backend/appdata`, E2E audio mất file, dọn `useIdempotencyKey`, đăng nhập khi máy chủ bận (Đợt 17, sau hạn nộp)

- **Người làm:** A (`@mactuongmvt`), nhánh `vantuong`.
- **Số commit:** 5.
- **Điều kiện bắt đầu:** #80 (A) và #81 (B) đã vào `main` (`4259a4f`, `6c84724`). C gộp hai PR với `main` rồi chạy lại trước khi merge:
  - Backend trên PostgreSQL 16: 568 passed, 0 skipped, 0 xfailed.
  - Frontend: lint, 352 passed, build.
  - E2E `evidence-seek.spec.ts` và `summary-edit.spec.ts` trên API thật: mỗi spec 1 passed.
- **Review:**
  - B không review #80 (PR mở hơn 20 giờ).
  - Việc 2 hôm qua của C ghi mã `AUDIO_NOT_FOUND`, nhưng API thật trả `NOT_FOUND`. A bắt cả hai mã, đúng hơn việc giao.
  - `docs/frontend/reviews/PR-77-response-2026-11-26.md` ghi "Chưa đăng trên GitHub". **Đăng nội dung đó thành comment trên #77** (không tính commit). File trong repo không được tính là phản hồi review.
- **Phạm vi:** sau hạn nộp 11-14. Chỉ sửa lỗi, thêm test và bằng chứng; không thêm tính năng.
- **Hạn:** mở PR trong ngày 11-27. Không phụ thuộc PR của B.

## Bước 0
```bash
git checkout vantuong && git fetch origin && git merge origin/main
```

Log ghi **UTF-8**.

## Việc

### 1. [ ] Stack E2E ghi audio vào `backend/appdata` thật (FE-17, BE-16)
- **Lỗi (C tìm ngày 11-27):** `frontend/e2e/stack.mjs` không đặt `STORAGE_DIR`, nên API của E2E dùng thư mục mặc định `backend/appdata`, chung với máy phát triển.
  - Spec có dọn trong `finally`. Nhưng một lượt hỏng giữa chừng, hoặc một lượt bị dừng, sẽ để file lại trong `backend/appdata`.
  - Harness tải (`backend/scripts/load_vt018.py --storage temp`) đã dùng thư mục tạm từ 11-23.
- **Sửa:**
  - `stack.mjs` tạo một thư mục tạm riêng cho mỗi lần chạy, truyền vào API và worker bằng `STORAGE_DIR`, và xóa thư mục đó khi stack dừng.
  - Xuất đường dẫn đó cho spec, ví dụ qua `E2E_STORAGE_DIR`; việc 2 cần biến này.
- **Test:**
  - Đếm thư mục trong `backend/appdata/audio` và `backend/appdata/artifacts` trước và sau một lượt `upload.spec.ts`: không đổi.
  - Ghi số đếm vào log.
- **Message:** `fix(frontend): the e2e stack keeps uploads in its own temporary STORAGE_DIR instead of backend/appdata (FE-17, BE-16)`
- **Commit:** _chưa_

### 2. [ ] E2E trên API thật: file audio mất thì player báo không tìm thấy file (FE-19, FE-17)
- Từ #80 và #81, file audio mất mà hạn lưu chưa tới thì API trả `available: false`, và player báo "Không tìm thấy file audio". Hiện mới có test MSW.
- **Kịch bản (dùng `E2E_STORAGE_DIR` của việc 1):**
  - Upload và chờ `ready`.
  - Xóa `audio/<id>/original.*` trong thư mục lưu.
  - Tải lại trang chi tiết: thấy "Không tìm thấy file audio" và transcript vẫn đọc được.
  - `GET /meetings/{id}/audio` trả 404.
- Chạy 3 lượt, `--retries=0`, không đặt `E2E_MANUAL_WORKER`. Log UTF-8 ở `docs/evidence/final/frontend-missing-audio-e2e-2026-11-27.log`. Dọn dữ liệu trong `finally`.
- **Message:** `test(frontend): e2e on the real API shows a missing audio file as missing, not expired (FE-19, FE-17)`
- **Commit:** _chưa_

### 3. [ ] `useIdempotencyKey` có trường không dùng (P3 của C trên #77)
- `useIdempotencyKey.ts` tạo object `{ identity, key }` nhưng chỉ trả `key`.
- **Sửa:** `useMemo(() => (file ? crypto.randomUUID() : null), [file, requestIdentity])`, có ghi chú vì sao `requestIdentity` nằm trong dependency.
- **Test** (`useIdempotencyKey.test.ts` phải vẫn xanh, thêm ca nếu thiếu):
  - Thử lại cùng payload thì giữ khóa.
  - Đổi tiêu đề, ngày hoặc nguồn thì tạo khóa mới.
  - Chọn file khác thì tạo khóa mới.
- **Message:** `refactor(frontend): useIdempotencyKey memoises the key alone on file and request identity (FE-05)`
- **Commit:** _chưa_

### 4. [ ] Máy chủ bận (503) khi đăng nhập thì form báo lỗi chung và xóa mật khẩu (FE-03, AD-018)
- **Lỗi:** `/api/v1/auth/login` đi qua admission (`backend/app/core/admission.py`). Khi quá tải, API trả 503 `SERVICE_UNAVAILABLE` kèm `Retry-After: 2`.
  - `LoginPage.tsx` (dòng 37 đến 45) chỉ có câu riêng cho `INVALID_CREDENTIALS` và `NETWORK_ERROR`, còn lại báo "Không thể đăng nhập. Hãy thử lại.".
  - Form xóa mật khẩu với **mọi** lỗi.
  - Các màn khác đã dùng `isServiceBusy` (`errors.ts`).
- **Test đỏ trước (MSW trả 503 kèm `Retry-After`):**
  - Form báo máy chủ đang bận và nên thử lại sau ít giây.
  - Email và mật khẩu còn nguyên.
  - Bấm đăng nhập lại thì gửi request mới.
  - Với 401 `INVALID_CREDENTIALS`, vẫn xóa mật khẩu như cũ.
- **Message:** `fix(frontend): login says the server is busy on 503 and keeps the password, clearing it only on wrong credentials (FE-03, AD-018)`
- **Commit:** _chưa_

### 5. [ ] Tick, hash (G0)
- Ghi hash từng commit; hash của chính commit này ghi "commit này".
- Chạy `npm run lint`, `npm test`, `npm run build`. Ghi số test và số skipped.
- **Message:** `docs(tasks): record 2026-11-27 member A results (G0)`
- **Commit:** _chưa_

## Việc chung (không tính commit)

- Đăng phản hồi review #77 lên GitHub (xem trên).
- Review PR ngày 11-27 của B **trong 18 giờ** kể từ lúc B mở, comment trên GitHub. #81 hôm qua chưa có review của A.
