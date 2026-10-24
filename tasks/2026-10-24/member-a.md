# 2026-10-24 · Member A: frontend

- **Người làm:** A (`@mactuongmvt`), nhánh `vantuong`.
- **Số commit:** 5.
- **Mục tiêu:** chạy frontend với backend thật. Backend đã có login, logout, me (cookie JWT `HttpOnly`) và các API đọc (PR #20), nhưng frontend vẫn đăng nhập giả bằng `sessionStorage` (`DEMO_AUTH_KEY`). Sau đó làm panel lịch sử chỉnh sửa (FE-14) và error boundary (FE-16).

Đọc trước:
- `backend/README.md`, mục chạy API và worker.
- `contracts/openapi.json`, các path `/api/v1/auth/*` và `/api/v1/meetings/{meeting_id}/edits`.
- `contracts/fixtures/api/user_me.json`, `edits.json`.
- [`rules/privacy-security.md`](../../rules/privacy-security.md).
- Mục FE-03, FE-14, FE-16 của kế hoạch.

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

PR #19 đã được merge (`2ab123b`).

## 5 commit

### 1. [x] Chạy frontend với backend thật qua proxy của Vite (FE-02)

- **Việc:**
  - `vite.config.ts`: proxy `/api` tới `VITE_API_PROXY_TARGET` (mặc định `http://localhost:8000`). Frontend và API dùng chung origin, nên cookie `SameSite=Lax` gửi được.
  - `VITE_API_MOCK=0` thì tắt MSW và dùng proxy.
  - MSW thêm handler cho `POST /auth/login`, `GET /auth/me`, `POST /auth/logout` (fixture `user_me.json`, sai mật khẩu thì 401 `INVALID_CREDENTIALS`).
  - `frontend/README.md`: thêm cách chạy với backend thật.
- **Xong khi:** test cấu hình proxy; test handler auth của MSW. Chạy thử bằng tay: `VITE_API_MOCK=0 npm run dev` cùng backend (`uv run uvicorn ...`), mở `/meetings` thấy dữ liệu từ DB.
- **Message:** `feat(frontend): dev proxy to the real API and auth mock handlers (FE-02)`
- **Hash:** `f10f057`

### 2. [x] Đăng nhập bằng API thật (FE-03)

- **Việc:**
  - `LoginPage` gọi `POST /auth/login`. Thành công thì chuyển tới `safeNext(next)`.
  - 401 thì hiện "Email hoặc mật khẩu không chính xác." và giữ email đã nhập. Lỗi mạng hiện thông báo riêng.
  - Bỏ `DEMO_AUTH_KEY`.
  - Không lưu token hay mật khẩu vào `localStorage`/`sessionStorage`: cookie do server đặt và JS không đọc được.
- **Xong khi:** RTL test: đăng nhập thành công rồi chuyển trang, sai mật khẩu, lỗi mạng, nút submit bị disable khi đang gửi.
- **Message:** `feat(frontend): log in against the API with an HttpOnly cookie (FE-03)`
- **Hash:** `a383faf`

### 3. [x] `useMe`, chặn route và đăng xuất (FE-03)

- **Việc:**
  - `useMe()` gọi `GET /auth/me` bằng TanStack Query.
  - `RequireAuth` dùng `useMe`: đang tải thì hiện skeleton; gặp 401 thì chuyển tới `/login?next=`.
  - API nào trả 401 thì xóa cache `me` và chuyển về login.
  - Nút đăng xuất gọi `POST /auth/logout` rồi `queryClient.clear()`, để transcript của phiên trước không còn trong cache.
- **Xong khi:** RTL test: chưa đăng nhập thì redirect kèm `next`; đã đăng nhập thì vào được; logout thì cache rỗng và về `/login`; một API trả 401 giữa chừng thì về login.
- **Message:** `feat(frontend): session guard with useMe, 401 handling and logout (FE-03)`
- **Hash:** `ffe337a`

### 4. [x] Panel lịch sử chỉnh sửa (FE-14)

- **Việc:**
  - Tab "Lịch sử" trên trang detail gọi `GET /meetings/{id}/edits` (MSW, fixture `edits.json`).
  - Mỗi dòng gồm thời gian, người sửa, đối tượng (`entity_type`), trường, giá trị trước và sau.
  - Lọc theo loại đối tượng (segment, speaker, summary, action item). Có phân trang.
  - Có các trạng thái rỗng, đang tải, lỗi.
- **Xong khi:** RTL test: hiển thị đúng fixture, lọc theo loại, trạng thái rỗng và lỗi.
- **Message:** `feat(frontend): edit history panel with type filter (FE-14)`
- **Hash:** `e187c4c`

### 5. [x] Error boundary, banner offline, trang 404 (FE-16)

- **Việc:**
  - Error boundary ở mức route, có nút "Tải lại".
  - Banner khi mất mạng (`navigator.onLine`, sự kiện `online`/`offline`).
  - Toast khi request lỗi mạng.
  - `NotFoundPage` cho route lạ và cho `MEETING_NOT_FOUND`.
  - Thông điệp lỗi không hiện stack trace hay nội dung transcript.
- **Xong khi:** RTL test: component ném lỗi thì hiện fallback; banner offline bật và tắt; route lạ hiện 404.
- **Message:** `feat(frontend): error boundary, offline banner and not-found page (FE-16)`
- **Hash:** `76c9542`

## Việc chung (không phải commit)

- [ ] SH-01: ghi âm buổi họp pilot có consent (vẫn chưa có).

## Cuối ngày

- [x] Tick các ô ở trên và ghi hash. Cập nhật `docs/frontend/` (FE-03, FE-14, FE-16).
- [x] Push `vantuong`, mở [PR #24](https://github.com/TAINGUYENVAN0507/SE2026_Codex/pull/24) vào `main`. **Không tự merge.**

Kiểm tra local: lint, format, TypeScript, 136 test và build đạt. Browser QA tự
động với MSW tắt, FastAPI thật và PostgreSQL 16 riêng đạt 11 kiểm tra; đã thấy
một cuộc họp seed trong `/meetings`, cookie HttpOnly, reload và logout. Ảnh và
kết quả ở `.preview-stitch/qa-2026-10-24/` (không commit). Lịch sử backend vẫn
trả fixture; lọc/phân trang được kiểm tra qua MSW. Đã dừng Vite/API và container
DB QA sau khi kiểm tra. PR #24 đang chờ review, chưa merge.
