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

### 1. [x] Stack E2E ghi audio vào `backend/appdata` thật (FE-17, BE-16)
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
- **Commit:** `15cdd33`

### 2. [x] E2E trên API thật: file audio mất thì player báo không tìm thấy file (FE-19, FE-17)
- Từ #80 và #81, file audio mất mà hạn lưu chưa tới thì API trả `available: false`, và player báo "Không tìm thấy file audio". Hiện mới có test MSW.
- **Kịch bản (dùng `E2E_STORAGE_DIR` của việc 1):**
  - Upload và chờ `ready`.
  - Xóa `audio/<id>/original.*` trong thư mục lưu.
  - Tải lại trang chi tiết: thấy "Không tìm thấy file audio" và transcript vẫn đọc được.
  - `GET /meetings/{id}/audio` trả 404.
- Chạy 3 lượt, `--retries=0`, không đặt `E2E_MANUAL_WORKER`. Log UTF-8 ở `docs/evidence/final/frontend-missing-audio-e2e-2026-11-27.log`. Dọn dữ liệu trong `finally`.
- **Message:** `test(frontend): e2e on the real API shows a missing audio file as missing, not expired (FE-19, FE-17)`
- **Commit:** `b1b044d`

### 3. [x] `useIdempotencyKey` có trường không dùng (P3 của C trên #77)
- `useIdempotencyKey.ts` tạo object `{ identity, key }` nhưng chỉ trả `key`.
- **Sửa:** `useMemo(() => (file ? crypto.randomUUID() : null), [file, requestIdentity])`, có ghi chú vì sao `requestIdentity` nằm trong dependency.
- **Test** (`useIdempotencyKey.test.ts` phải vẫn xanh, thêm ca nếu thiếu):
  - Thử lại cùng payload thì giữ khóa.
  - Đổi tiêu đề, ngày hoặc nguồn thì tạo khóa mới.
  - Chọn file khác thì tạo khóa mới.
- **Message:** `refactor(frontend): useIdempotencyKey memoises the key alone on file and request identity (FE-05)`
- **Commit:** `e8bfb40`

### 4. [x] Máy chủ bận (503) khi đăng nhập thì form báo lỗi chung và xóa mật khẩu (FE-03, AD-018)
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
- **Commit:** `27ce518`

### 5. [x] Tick, hash (G0)
- Ghi hash từng commit; hash của chính commit này ghi "commit này".
- Chạy `npm run lint`, `npm test`, `npm run build`. Ghi số test và số skipped.
- **Message:** `docs(tasks): record 2026-11-27 member A results (G0)`
- **Commit:** `commit này`

## Việc chung (không tính commit)

- [x] Đăng phản hồi review #77 lên GitHub: https://github.com/TAINGUYENVAN0507/SE2026_Codex/pull/77#issuecomment-7219357584 (đã kiểm comment tồn tại, tác giả mactuongmvt).
- Review PR ngày 11-27 của B **trong 18 giờ** kể từ lúc B mở, comment trên GitHub. #81 hôm qua chưa có review của A.


## Kết quả local — 27/11/2026

Đã cập nhật vantuong theo main 6d3e2c4 trước khi code; đúng 5 việc/5 commit theo thứ tự. Tick là kết quả local; chưa push/mở PR/CI GitHub hoặc merge đợt này.

1. Storage: stack tạo thư mục tạm riêng, chia sẻ E2E_STORAGE_DIR/STORAGE_DIR cho worker/spec/helper; kiểm path/token/PID và thêm reporter sau teardown cho Windows. Baseline upload có 2 test đạt nhưng kiểm cách ly đỏ do ghi canary kế thừa 2 audio/2 artifacts; dữ liệu phát triển không bị ghi. Sau sửa 6 test storage đạt; lượt cuối upload.spec.ts + retention.spec.ts **3 passed/0 skipped**, retries=0. Appdata phát triển **144 audio/155 artifacts** trước/sau không đổi; storage tạm đã xóa. Giữ log lỗi hook/Windows cleanup/guard retention và ca collection lỗi vẫn dọn được sau sửa reporter. Không sửa backend.
2. Audio mất file: **3/3 lượt** Chromium/API thật/PostgreSQL 16 mới đạt, 0 failed/0 skipped/retries=0/pageerror=0. Xóa đúng original.* trong storage riêng khi meeting còn hạn; GET audio 404 NOT_FOUND, available=false, reload UI báo không tìm thấy file và transcript giữ nguyên. finally dọn meeting/user, reporter dọn storage; container QA đã xóa. Worker fake bật, không đặt E2E_MANUAL_WORKER, không intercept API; không dùng để đánh giá AI.
3. Hook: useMemo trả thẳng key, bỏ object không dùng. Dependency requestIdentity chủ ý được ghi chú và miễn đúng một dòng exhaustive-deps, không tắt rule cả file. Sáu test hợp đồng trước refactor đạt; sau refactor nhóm hook/login/upload 28 passed/4 file, 0 skipped. Kiểm đổi title/date/source/File và retry payload cũ.
4. Login: trước sửa **3 failed/5 passed**. 503 hiện máy chủ bận kèm thời gian chờ từ Retry-After hoặc ít giây, giữ email/password và cho gửi request mới. Chỉ INVALID_CREDENTIALS xóa password khi lỗi; thành công vẫn xóa trước chuyển trang. Không ghi Web Storage, không tự gửi lại. Nhóm 28 test đạt, giữ hồi quy 401/network/500.
5. Gate cuối: lint sạch, format/TypeScript/build đạt, sinh schema API không drift. npm test -- --coverage: **363 passed/59 file, 0 failed, 0 skipped**; lines **88.35%**, branches **83.49%**, giữ floors 84.53%/79.11%. Server QA cổng 14173/18000, container theo nhãn riêng và các thư mục se-e2e-storage đã dọn.

Docs: FE-03, FE-05, FE-17, FE-19, README frontend; bằng chứng UTF-8 dưới docs/evidence/final với hậu tố 2026-11-27: frontend-e2e-storage (JSON và log red/green/transition), frontend-missing-audio-e2e và result r1/r2/r3, frontend-idempotency-refactor, frontend-login-busy-{red,green}, frontend-gates.

### Việc chung

- Phản hồi #77 đã đăng thật trên GitHub, không chỉ lưu trong repo; link ở trên. Nội dung ghi rõ thời điểm bản nháp 26/11 và phần hook được giao/sửa 27/11.
- Kiểm trực tiếp GitHub lúc **20:51 ngày 27/11** (giờ Việt Nam): không có PR mở. Review PR mới của B vẫn chờ, hạn 18 giờ từ khi B mở. #81 hôm qua đã merge mà chưa có review của A; không đánh dấu hoàn tất review này.
