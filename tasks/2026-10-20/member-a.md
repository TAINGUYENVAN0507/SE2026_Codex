# 2026-10-20 · Member A: frontend

- **Người làm:** A (`@mactuongmvt`), nhánh `vantuong`.
- **Mục tiêu:** đưa FE-01 vào `main` (PR #5), rồi làm phần frontend của FE-02, FE-03, FE-05, FE-07 mà không cần backend chạy thật.

Đọc trước: [`structure/contracts.md`](../../structure/contracts.md) (error envelope, trạng thái job/stage, các field của `GET /config`) và [`rules/`](../../rules/README.md).

Lệnh kiểm tra cho mọi commit, chạy trong `frontend/`:

```bash
npm run lint && npm run format:check && npm run typecheck && npm test && npm run build
```

## Bước 0: gỡ conflict của PR #5 (không tính vào 5 commit)

PR #5 đang báo conflict với `main` ở `.gitignore`.

```bash
git checkout vantuong
git fetch origin
git merge origin/main
# Conflict ở .gitignore: chọn bản của main (dòng "reports/").
# docs/frontend/FE-01.md vẫn được commit bình thường, vì main không còn ignore docs/.
git add .gitignore
git commit
git push origin vantuong
```

- [ ] PR #5 hết conflict, CI `frontend` xanh. Nhóm trưởng review và merge.

Tiến độ Bước 0: đã đồng bộ main tại `28fcdf7`, gỡ conflict `.gitignore` và README;
lint, format, typecheck, 19 test và build frontend đều đạt local. Chờ CI mới và
nhóm trưởng review/merge, nên chưa tick hoàn thành toàn bộ Bước 0.

## 5 commit

### 1. [x] Giới hạn upload lấy từ config, không hard-code 200 MB (FE-05)

- **Việc:** `validateAudio(file, config)` nhận `UploadConfig { max_upload_mb, allowed_extensions }`, có giá trị mặc định khớp với `GET /api/v1/config`. Bỏ hằng số `MAX_AUDIO_BYTES`. Thông báo lỗi lấy con số từ config.
- **File:** `src/features/audio/validation.ts`, `NewMeetingPage.tsx`, test cạnh file.
- **Xong khi:** đổi config thì giới hạn và thông báo đổi theo. Test: file rỗng, vượt dung lượng, sai đuôi, đuôi viết hoa, file hợp lệ.
- **Message:** `feat(frontend): take upload limits from config instead of hard-coded 200 MB (FE-05)`
- **Hash:** `ed6b842`

### 2. [x] Kiểu `ApiError` đọc từ error envelope (FE-02)

- **Việc:** `src/api/errors.ts`. Parse `{"error": {"code", "message", "details", "request_id"}}` thành `ApiError`. Response không phải JSON, hoặc lỗi mạng, thì thành mã `NETWORK_ERROR`/`UNKNOWN_ERROR`. Map sang tiếng Việt các mã đã có trong kế hoạch: `FILE_TOO_LARGE`, `UNSUPPORTED_MEDIA_TYPE`, `AUDIO_INVALID`, `AUDIO_TOO_SHORT`, `AUDIO_TOO_LONG`, `CONSENT_REQUIRED`, `VERSION_CONFLICT`, `UNAUTHENTICATED`. Mã lạ thì dùng `message` từ server.
- **Xong khi:** có test cho envelope đúng, envelope thiếu field, body HTML, lỗi mạng, mã lạ.
- **Message:** `feat(frontend): ApiError parsed from the backend error envelope (FE-02)`
- **Hash:** `8b95c9b`

### 3. [x] `Idempotency-Key` gắn với file đã chọn (FE-05)

- **Việc:** hook `useIdempotencyKey(file)` sinh UUID bằng `crypto.randomUUID()`. Cùng một `File` thì giữ nguyên key (kể cả khi retry upload), đổi file thì sinh key mới.
- **Xong khi:** test bằng `renderHook`: rerender với cùng file thì key không đổi, đổi file thì key mới, `file = null` thì key là `null`.
- **Message:** `feat(frontend): keep one Idempotency-Key per selected file across retries (FE-05)`
- **Hash:** `f15a136`

### 4. [x] Redirect `/login?next=` an toàn (FE-03)

- **Việc:** route cần đăng nhập thì chuyển sang `/login?next=<đường dẫn hiện tại>`. Sau khi đăng nhập, quay về `next`. `safeNext()` chỉ nhận đường dẫn tương đối bắt đầu bằng `/` (chặn `//evil.com`, `https://…`, `javascript:`), sai thì về `/meetings`. Chưa có backend thì giữ cơ chế đăng nhập demo hiện tại.
- **Xong khi:** test cho `safeNext()` với các input trên. RTL test luồng: vào route được bảo vệ, bị chuyển sang login, đăng nhập xong quay về đúng trang.
- **Message:** `feat(frontend): safe ?next= redirect around the login page (FE-03)`
- **Hash:** `a561b60`

### 5. [x] Stepper trạng thái job cho 6 stage (FE-07)

- **Việc:** component `JobStatusCard` hiển thị 6 stage `preprocess → vad → asr → diarize → merge → summarize`, trạng thái job (`queued`, `running`, `retry_scheduled`, `succeeded`, `failed`, `cancelled`), `attempt/max_attempts` và thông báo lỗi lấy qua `ApiError` (commit 2). Dữ liệu lấy từ fixture đặt trong test, theo ví dụ Job ở mục 7.3 của kế hoạch. Chưa gọi API thật.
- **Xong khi:** RTL test cho từng trạng thái job, gồm `retry_scheduled` có hiển thị lượt thử, và `failed` có thông báo lỗi tiếng Việt.
- **Message:** `feat(frontend): job status stepper for the six pipeline stages (FE-07)`
- **Hash:** `e6877f3`

## Cuối ngày

- [ ] Push `vantuong`. Các commit tự vào PR #5 nếu PR chưa được merge; nếu đã merge thì mở PR mới vào `main`.
- [x] Cập nhật `docs/frontend/` cho FE-02, FE-03, FE-05, FE-07 (phần đã làm, phần còn lại).
- [x] Tick các ô ở trên và ghi hash commit.

Tiến độ ngày 20/10: đã hoàn thành 5 commit tính năng riêng; lint, format,
typecheck, 50 test và build frontend đều đạt local. Các thay đổi chưa được push;
PR #5 chỉ nhận chúng sau khi chủ nhánh cho phép push.
