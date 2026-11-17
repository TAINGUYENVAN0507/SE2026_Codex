# 2026-11-16 · Member A: log nginx không giữ query string, tìm cuộc họp ngoài trang đầu, transcript không có lời nói (Đợt 10, sau hạn nộp)

- **Người làm:** A (`@mactuongmvt`), nhánh `vantuong`.
- **Số commit:** 5.
- **Điều kiện bắt đầu:** #60 (A) đã vào `main`. C review diff, CI xanh 11/11, merge `544333d`. #61 (B) **chưa merge**: C xác nhận hai điểm A nêu ở review 11-15, B sửa trên chính #61 hôm nay.
- **Phạm vi:** sau hạn nộp 11-14. Chỉ sửa lỗi, thêm test và bằng chứng; không thêm tính năng.
- **Hạn:** mở PR khi push xong, trong ngày 11-16. **PR của A merge sau #61**: việc 2 làm giao diện gửi tiêu đề tìm kiếm lên API qua `?q=`, mà trước khi #61 tắt access log của uvicorn thì query string bị ghi vào log.

## Bước 0
```bash
git checkout vantuong && git fetch origin && git merge origin/main
```

Log ghi **UTF-8**: `... 2>&1 | Out-File -Encoding utf8 <file>` (PowerShell `>` ghi UTF-16; test `backend/tests/unit/test_docs_utf8.py` sẽ đỏ).

## Việc

### 1. [x] Log truy cập của nginx không ghi query string (AD-018, FE-19)
- `infra/docker/nginx.conf` không có `access_log`, nên nginx dùng format `main` trong `/etc/nginx/nginx.conf` của image. Format đó có `"$request"`, gồm cả query string, và `"$http_referer"`, gồm URL trang trước. Log ra stdout, tức vào log Docker của service `web`. API có `GET /meetings?q=<tiêu đề>` (`backend/app/api/v1/meetings.py:138`), và từ việc 2 giao diện sẽ gửi `q`. Đây là cùng lỗi C xác nhận ở uvicorn trong review #61.
- Thêm vào `infra/docker/smoke_web.sh`: gọi `/?q=<canary>` và `/api/v1/meetings?q=<canary>`; smoke này không chạy api, nên 502 vẫn được vì nginx vẫn ghi log. Sau đó `docker logs` của container không được chứa canary.
- Chạy smoke với image build từ `main` trước: phải đỏ. Lưu log đỏ `docs/evidence/final/web-access-log-red-2026-11-16.log`.
- Sửa:
  - Thêm một `log_format` riêng ở đầu `nginx.conf`, ngoài `server {}`. Format này chỉ dùng `$uri`, không dùng `$request`, `$request_uri`, `$args` hay `$http_referer`.
  - Trong `server`, thêm `access_log /var/log/nginx/access.log <tên format>;`.
  - Chạy lại smoke: phải xanh, `nginx -t` đạt.
- Máy không có Docker thì dùng job `build-web` của CI và ghi link run.
- **Message:** `fix(web): nginx access log without query strings (AD-018, FE-19)`

### 2. [x] Tìm cuộc họp chỉ lọc trang đang xem (FE-04)
- **Lỗi:**
  - `frontend/src/pages/MeetingListPage.tsx:35-38` lọc `meetings` của trang hiện tại, mà API trả 10 mục mỗi trang (`meetings.py:134`).
  - Có 11 cuộc họp thì cuộc họp cũ nhất nằm ở trang 2, và tìm theo tiêu đề của nó ra "không tìm thấy". Dòng "Hiển thị X trên Y" cũng lệch.
  - API đã có `q`, nhưng `listMeetings` (`frontend/src/api/client.ts:138`) và `useMeetingsQuery.ts:13` không gửi.
- **Sửa:**
  - Gửi `q` đã trim, có debounce khoảng 300 ms. `queryKey` phải có `q`, và đổi `q` thì về trang 1.
  - Bỏ lọc ở client. Nếu chế độ demo không có API cần giữ lọc, ghi rõ nhánh đó.
  - MSW (`frontend/src/mocks/handlers.ts`) lọc theo `q` như API.
- **Test:** 11 meeting, tìm tiêu đề meeting thứ 11 → hiện đúng 1 mục, request có `q=`.
- **Mutant tạm (không commit):** bỏ `q` khỏi request thì test phải đỏ. Ghi kết quả vào message commit.
- **Kiểm:** `npm run test -- MeetingListPage`, `npm run lint`, `npm run typecheck`.
- **Message:** `fix(frontend): meeting search asks the API instead of filtering the current page (FE-04)`

### 3. [x] E2E trên API thật: tìm thấy cuộc họp ở trang 2 (FE-04)
- Upload 11 cuộc họp qua API (không cần worker), rồi tìm tiêu đề của cuộc họp tạo đầu tiên.
  - UI hiện đúng 1 mục.
  - Response `GET /api/v1/meetings?q=...` có `total == 1`.
  - Không có `pageerror`.
- Chạy với Postgres thật, retries=0, một lượt trên nhánh đã có việc 2. Lưu log `docs/evidence/final/frontend-search-2026-11-16.log`. Đỏ thì giữ log đỏ.
- **Message:** `test(frontend): e2e finds a meeting beyond the first page on the real API (FE-04)`

### 4. [x] Meeting đã xử lý nhưng không có lời nói (FE-20, BE-05)
- **Lỗi:**
  - `frontend/src/features/meetings/Transcript.tsx:553-565`: khi có 0 segment và không pending, trang hiện "Chưa có transcript" kèm "Transcript sẽ xuất hiện khi cuộc họp được xử lý." Với meeting đã xử lý xong mà không có lời nói, câu này sai.
  - Trước #61, API trả `pending` cho trường hợp này nên trang poll mãi. Sau #61, API trả `ready` với `segments: []`.
- **Sửa:**
  - Transcript `ready` và 0 segment: hiện câu báo không nhận ra lời nói trong bản ghi.
  - Chưa xử lý: giữ câu cũ.
  - `Transcript` cần biết transcript đã `ready`; `MeetingDetailPage.tsx:96` đã có giá trị này.
- **Test:**
  - `ready` + `[]` → hiện câu mới, không có skeleton.
  - Fake timer, như `RemoteSummaryPolling.test.tsx`: `ready` + `[]` → sau 15 s vẫn chỉ 1 GET transcript (`useTranscriptQuery.ts:9`); `pending` → có GET lần 2 ở giây thứ 5.
- **Kiểm:** `npm run test -- Transcript`, `npm run lint`, `npm run typecheck`.
- **Message:** `fix(frontend): a processed meeting without speech says so instead of waiting (FE-20, BE-05)`

### 5. [x] Tick, hash (G0)
- Ghi hash từng commit; hash của chính commit này ghi "commit này".
- Chạy đủ gate frontend (lint, format:check, typecheck, test có coverage, build), ghi số test và coverage.
- **Message:** `docs(tasks): record 2026-11-16 member A results (G0)`

## Việc chung (không tính commit)

- **Kiểm lại #61:** sau khi B push head mới, comment review trong 18 giờ. Ở review 11-15, A đã hẹn "A sẽ kiểm lại head mới". Cần kiểm lại cả P1 (uvicorn thật) và P2 (smoke khi không đọc được log). Nếu không còn vấn đề thì ghi rõ là đóng hai điểm đó.
- **Không cần commit file review** (như `docs/frontend/reviews/PR-61-2026-11-15.md` ở #60). Comment trên GitHub đã là bằng chứng phản hồi; số commit ngày này là đúng 5.

## Kết quả thực hiện của A — 16/11/2026

| Việc | Commit | Kết quả |
|---|---|---|
| 1 — Log nginx (AD-018, FE-19) | `7bc05c03b9296684291d795fb7ed2b825a745aff` | Baseline đỏ; format access log chỉ giữ URI. Phát hiện error log 502 cũng giữ query/referer nên lọc query qua FIFO, vẫn giữ chẩn đoán. Docker smoke và nginx -t xanh. |
| 2 — Tìm kiếm API (FE-04) | `44d47c3974107190c4cad41e179a785c19e85711` | Trim q, debounce 300 ms, queryKey có q, đổi q về trang 1; bỏ lọc trang hiện tại, MSW lọc trước phân trang. 6 test đạt. Mutant bỏ q làm 2 test đỏ; đã khôi phục. |
| 3 — E2E API/Postgres (FE-04) | `3fca11e61a56e69a88f2092eddfbb13a6586737e` | Upload 11 bản ghi tổng hợp; cuộc cũ nhất ở trang 2, tìm qua UI ra 1 mục, response total=1, không pageerror. 1 passed, retries=0, 47.1 s Playwright; không chạy worker/model. |
| 4 — Transcript ready/rỗng (FE-20, BE-05) | `21abf36f76d346ddaccd4f1313261a2d09d0ccd5` | Trang hiện không nhận ra lời nói; chưa xử lý giữ thông báo chờ. Ready/rỗng sau 15 s vẫn 1 GET; pending có GET lần 2 ở giây 5. Cập nhật 2 kỳ vọng PageStates cũ; 19 test liên quan đạt. |
| 5 — Gate và phân công (G0) | commit này | Lint, format:check, typecheck, coverage và production build đạt. 311 test / 53 file. |

Kiểm UTF-8 tài liệu: **2 passed** (`frontend-docs-utf8-2026-11-16.log`).

Coverage V8: statements **84.51%**, branches **82.11%**, functions **80.87%**, lines **86.91%**.
Lần chạy toàn bộ đầu có 2 test PageStates đỏ do kỳ vọng cũ; đã giữ log,
sửa test chờ tìm kiếm bất đồng bộ và kiểm thông báo ready/rỗng mới, rồi chạy
lại toàn bộ đạt. Không bỏ test hoặc đổi số liệu.

Bằng chứng UTF-8 trong `docs/evidence/final/`:
- `web-access-log-red-2026-11-16.log`, `web-access-error-red-2026-11-16.log`,
  `web-access-log-green-2026-11-16.log` và JSON cùng nhóm: Docker thật, kể cả lỗi upstream 502.
- `frontend-search-red-2026-11-16.log`, `frontend-search-mutant-2026-11-16.log`,
  `frontend-search-unit-2026-11-16.log`: tái hiện, mutant và khôi phục.
- `frontend-search-2026-11-16.log` và JSON: E2E API/PostgreSQL thật, dữ liệu tổng hợp.
- `frontend-transcript-empty-red-2026-11-16.log` và bản green: ready/rỗng và polling.
- `frontend-full-suite-initial-red-2026-11-16.log`, các log `frontend-final-*-corrected-2026-11-16.log`,
  `frontend-pagestates-transcript-corrected-2026-11-16.log`, `frontend-gates-2026-11-16.json`:
  gate tổng hợp, lệnh, exit code, thời điểm và hash mã nguồn được kiểm.

### Còn chờ / điều kiện merge

- Review lại #61 **chưa hoàn tất**: lúc kiểm cuối, PR còn mở và head vẫn
  `32f188fee4a4b58d1af6e31933fa8cd4ab3a2984`, chưa có head mới sau review 11-15.
  Khi B push bản sửa, kiểm P1 Uvicorn thật và P2 lỗi đọc Docker log, comment
  trong 18 giờ. Không tạo thêm commit file review hôm nay.
- PR của A phải merge **sau #61** để tiêu đề tìm kiếm gửi trong q không vào
  access log Uvicorn cũ. Frontend unit test không chứng minh backend cũ đã sửa.
- Chưa push hoặc mở PR trong bước triển khai này; CI GitHub chưa chạy cho 5 commit hôm nay.
