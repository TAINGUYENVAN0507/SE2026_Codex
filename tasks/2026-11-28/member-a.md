# 2026-11-28 · Member A: thao tác tài khoản và xuất biên bản khi máy chủ bận, player chỉ nhận mã audio, kiểm storage E2E (Đợt 18, sau hạn nộp)

- **Người làm:** A (`@mactuongmvt`), nhánh `vantuong`.
- **Số commit:** 5.
- **Điều kiện bắt đầu:** #83 (A) và #84 (B) đã vào `main` (`03f16fb`, `af2dc6a`). C gộp hai PR với `main` rồi chạy trên Linux trước khi merge:
  - Backend trên PostgreSQL 16: 575 passed, 0 skipped, 0 xfailed, 1 warning.
  - Frontend: lint, format, typecheck, 364 passed, build.
  - E2E `missing-audio`, `upload`, `retention`, `evidence-seek`, `summary-edit`: cả 5 spec đạt. Không có `backend/appdata` trong worktree sạch, không còn thư mục `se-e2e-storage-*`.
- **Review #83 (C):** 4 việc đúng, đúng 5 commit. Phản hồi review #77 đã có trên GitHub. Ghi chú thành việc 3 và việc 4 hôm nay.
- **Review chéo:** A chưa review #84 và B chưa review #83 khi C merge.
- **Phạm vi:** sau hạn nộp 11-14. Chỉ sửa lỗi, thêm test và bằng chứng; không thêm tính năng.
- **Hạn:** mở PR trong ngày 11-28. Không phụ thuộc PR của B.

## Bước 0
```bash
git checkout vantuong && git fetch origin && git merge origin/main
```

Log ghi **UTF-8**.

## Việc

### 1. [ ] Đăng xuất và xóa tài khoản khi 503 bảo người dùng kiểm tra kết nối (FE-03, FE-19, AD-018)
- **Lỗi (C đọc code ngày 11-28):** mọi route trừ health và `/metrics` đi qua admission, nên đăng xuất và xóa tài khoản cũng nhận 503 `SERVICE_UNAVAILABLE` khi quá tải.
  - `components/Topbar.tsx` (`signOut`): mọi lỗi thành "Chưa thể đăng xuất. Hãy kiểm tra kết nối và thử lại."
  - `features/auth/DeleteAccountSection.tsx`: 503 thành "Chưa thể xóa tài khoản. Hãy kiểm tra kết nối và thử lại."
- **Test đỏ trước (MSW trả 503 kèm `Retry-After`):**
  - Hai chỗ báo máy chủ đang bận, nên thử lại sau ít giây (hoặc đúng số giây của `Retry-After`).
  - Vẫn còn đăng nhập, không chuyển trang; bấm lại gửi request mới.
  - Các nhánh cũ (mất mạng, 401, 404/405/501 của xóa tài khoản) giữ nguyên câu.
- Dùng `isServiceBusy`. Câu và cách tính số giây dùng chung với `LoginPage.tsx`, không chép lại lần thứ ba.
- **Message:** `fix(frontend): sign-out and account deletion say the server is busy on 503 (FE-03, FE-19, AD-018)`
- **Commit:** _chưa_

### 2. [ ] Xuất biên bản khi 503 chỉ báo "Không thể xuất" (FE-15, AD-018)
- **Lỗi:** `features/export/ExportMenu.tsx` chỉ có câu riêng cho 409; 503 thành "Không thể xuất biên bản. Hãy thử lại."
- **Test đỏ trước:** MSW trả 503 thì menu báo máy chủ đang bận; bấm lại cùng định dạng thì gửi request mới và tải được file. 409 giữ câu cũ.
- **Message:** `fix(frontend): export says the server is busy on 503 and can be retried (FE-15, AD-018)`
- **Commit:** _chưa_

### 3. [ ] Player còn coi `NOT_FOUND` là mất file audio (FE-19, FE-17; P3 của C trên #83)
- Từ #84, `GET /audio` trả `AUDIO_NOT_FOUND` khi mất file. `NOT_FOUND` chỉ còn nghĩa là không có cuộc họp (hoặc của người khác).
- **Sửa:** `RemoteAudioPlayer.tsx` chỉ nhận `AUDIO_NOT_FOUND`; bỏ ghi chú "API hiện trả NOT_FOUND". `NOT_FOUND` giữ lỗi phát chung.
- **Test:** `RemoteAudioPlayer.test.tsx` đổi ca `NOT_FOUND`; `missing-audio.spec.ts` chỉ chấp nhận `AUDIO_NOT_FOUND`. Chạy spec đó 1 lượt trên API thật, không đặt `E2E_MANUAL_WORKER`.
- **Message:** `fix(frontend): the player treats only AUDIO_NOT_FOUND as a missing file (FE-19, FE-17)`
- **Commit:** _chưa_

### 4. [ ] Kiểm storage của `upload.spec.ts` nằm trong `afterAll` (FE-17; P3 của C trên #83)
- `afterAll` đòi thư mục `audio` và `artifacts` có dữ liệu. Nếu test upload hỏng trước khi có file nào được lưu, hook này hỏng theo và che lỗi thật.
- **Sửa:** đưa phần kiểm vào cuối test upload đầu tiên (hoặc một test riêng), vẫn ghi `upload-storage-result.json`.
- **Chứng minh:** làm test upload hỏng sớm (tạm thời, không commit), log chỉ còn một lỗi. Lượt đúng vẫn 2 passed.
- **Message:** `test(frontend): the upload e2e checks its isolated storage inside the test instead of afterAll (FE-17)`
- **Commit:** _chưa_

### 5. [ ] Tick, hash (G0)
- Ghi hash từng commit; hash của chính commit này ghi "commit này".
- Chạy `npm run lint`, `npm test`, `npm run build`. Ghi số test và số skipped.
- **Message:** `docs(tasks): record 2026-11-28 member A results (G0)`
- **Commit:** _chưa_

## Việc chung (không tính commit)

- Review PR ngày 11-28 của B **trong 18 giờ** kể từ lúc B mở, comment trên GitHub.
