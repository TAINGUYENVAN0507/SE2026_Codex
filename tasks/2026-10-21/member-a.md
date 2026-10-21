# 2026-10-21 · Member A: frontend

- **Người làm:** A (`@mactuongmvt`), nhánh `vantuong`.
- **Số commit:** 5.
- **Mục tiêu:** contract REST v0 của B đã vào `main` (`contracts/openapi.json`, `contracts/fixtures/api/`). Hôm nay nối frontend vào contract đó (FE-02, FE-07) và làm phần không cần backend của FE-08.

Đọc trước: [`structure/contracts.md`](../../structure/contracts.md) (mục "Làm việc song song trên mock"), `contracts/openapi.json`, `docs/frontend/FE-02.md`, `docs/frontend/FE-07.md`.

Lệnh kiểm tra cho mọi commit, chạy trong `frontend/`:

```bash
npm run lint && npm run format:check && npm run typecheck && npm test && npm run build
```

## Bước 0: cập nhật nhánh (không tính vào số commit)

```bash
git checkout vantuong
git fetch origin
git merge origin/main
```

## 5 commit

### 1. [ ] Sinh type TypeScript từ `contracts/openapi.json` (FE-02)

- **Việc:** thêm `openapi-typescript` (dev dependency), script `npm run gen:api` sinh `src/api/schema.d.ts` từ `../contracts/openapi.json`, commit file đã sinh. Thêm bước kiểm drift vào `frontend.yml`: sinh lại rồi `git diff --exit-code`, và thêm `contracts/openapi.json` vào `paths` của workflow.
- **Xong khi:** `npm run gen:api` chạy lại không đổi gì. Thử đổi tên một field trong bản sao `openapi.json` thì `npm run typecheck` báo lỗi (chỉ thử ở máy, không commit).
- **Message:** `feat(frontend): generate API types from contracts/openapi.json (FE-02)`
- **Hash:**

### 2. [ ] API client có kiểu, lỗi đi qua `ApiError` (FE-02)

- **Việc:** `src/api/client.ts` dùng `openapi-fetch` với các type vừa sinh, `credentials: 'include'`, base URL `/api/v1`. Mọi response lỗi đi qua `ApiError` (đã có ở `src/api/errors.ts`). Các hàm `getMeeting(id)` và `getJob(id)` trả về type sinh từ contract.
- **Xong khi:** có test cho response 200, 404 có error envelope và lỗi mạng. Code không còn dùng `fetch` trực tiếp cho hai endpoint này.
- **Message:** `feat(frontend): typed API client with ApiError mapping (FE-02)`
- **Hash:**

### 3. [ ] MSW trả dữ liệu từ `contracts/fixtures/api/` (FE-02)

- **Việc:** cài `msw`. `src/mocks/handlers.ts` đọc `contracts/fixtures/api/*.json` (`meeting_processing.json`, `job_retry_scheduled.json`), dùng chung cho Vitest và cho chế độ dev bật bằng `VITE_API_MOCK=1`. Biến này chỉ là cờ bật tắt, không chứa secret. Test của client (commit 2) chạy qua MSW.
- **Xong khi:** `npm test` dùng MSW và không gọi mạng thật. B đổi fixture thì test phía frontend thấy ngay.
- **Message:** `feat(frontend): MSW handlers served from contract fixtures (FE-02)`
- **Hash:**

### 4. [ ] Poll trạng thái job mỗi 2 s tới khi job kết thúc (FE-07)

- **Việc:** hook `useJobQuery(jobId)` dùng TanStack Query, `refetchInterval` 2 s khi job ở `queued`, `running` hoặc `retry_scheduled`, dừng khi `succeeded`, `failed`, `cancelled`. `JobStatusCard` lấy dữ liệu từ hook này, thay cho props cứng.
- **Xong khi:** test dùng fake timers và MSW: poll đúng chu kỳ, dừng khi trạng thái kết thúc, lỗi mạng thì hiện thông báo qua `ApiError`.
- **Message:** `feat(frontend): poll job status every 2 s until the job ends (FE-07)`
- **Hash:**

### 5. [ ] `useActiveSegment` tìm segment đang phát bằng binary search (FE-08)

- **Việc:** hook (hoặc hàm thuần kèm hook) nhận `currentTime` và danh sách segment đã sắp theo `start_sec`, trả về segment đang phát bằng binary search. Segment chồng lấn (có cờ `overlap`) thì chọn segment bắt đầu muộn nhất mà vẫn chứa `currentTime`. Ở khoảng lặng giữa hai segment thì trả `null`.
- **Xong khi:** test cho danh sách rỗng, `currentTime` trước segment đầu, sau segment cuối, đúng biên `start_sec` và `end_sec`, chồng lấn, khoảng lặng; 1000 segment vẫn nhanh.
- **Message:** `feat(frontend): find the playing segment with binary search (FE-08)`
- **Hash:**

## Việc chung (không phải commit)

- [ ] SH-01: cùng nhóm ghi một buổi họp pilot 5–10 phút. Mỗi người ký phiếu theo `evaluation/datasets/consent_form.md`. Audio gửi cho C qua kênh riêng của nhóm, **không commit**.

## Cuối ngày

- [ ] Tick các ô ở trên và ghi hash commit. Cập nhật `docs/frontend/FE-02.md`, `FE-07.md`, thêm `FE-08.md`.
- [ ] Push `vantuong`, mở PR vào `main` theo template. **Không tự merge:** nhóm trưởng review và merge.
