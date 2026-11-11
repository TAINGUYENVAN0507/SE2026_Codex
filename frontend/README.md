# Frontend

React SPA của Vietnamese Meeting Minutes Assistant. Owner: member A.

Đợt 06/11: [dẫn chứng FE-18](../docs/frontend/FE-18.md),
[xóa và hạn audio FE-19](../docs/frontend/FE-19.md),
[tiến độ FE-20](../docs/frontend/FE-20.md). Các chức năng thật gọi API;
chế độ MSW phục vụ xem thử và test component, không thay E2E stack thật.

Kiểm thử trình duyệt trên stack thật: xem [FE-17](../docs/frontend/FE-17.md).
Chạy `npm run e2e` sau khi cấu hình database E2E và mật khẩu demo theo tài liệu.
Ảnh mới, checklist và kịch bản demo 5 phút: [UX checklist](../docs/demo/ux-checklist.md).

## Trạng thái

Giao diện graphite/cam được triển khai từ bộ ảnh đã duyệt, gồm:

- `/login`
- `/meetings`
- `/meetings/new`
- `/meetings/sprint-42`: cuộc họp mẫu đầy đủ để thử player và chỉnh sửa.
- `/meetings/:meetingId`: chi tiết cuộc họp từ API.
- `/meetings/:meetingId/processing`: theo dõi sáu bước xử lý, tách khỏi trang đọc transcript.
- `/settings`: thông tin tài khoản và xóa tài khoản. Contract trên main đã có `DELETE /auth/me`; E2E dùng user tổng hợp riêng kiểm xóa thật, cookie/phiên cũ vô hiệu, đăng nhập lại thất bại và user khác không bị ảnh hưởng.

`/meetings/sprint-42` vẫn là trang mẫu trong React Context. Danh sách,
upload và transcript của các cuộc họp khác dùng API. Khi chạy dev, MSW bật
mặc định và trả fixture từ `contracts/fixtures/api/`; đặt `VITE_API_MOCK=0`
để gọi backend thật. Bản mock không lưu file audio lên server. Đăng nhập gọi
API auth; cookie phiên do backend đặt, không lưu token/mật khẩu vào Web Storage.

Đã có tìm kiếm/lọc meeting và transcript, player mô phỏng hoặc nghe audio trên máy,
sửa transcript và speaker của segment, xem bản gốc, sửa tổng quan, quản lý công việc,
menu tải TXT/MD/JSON theo bản hiện tại hoặc bản AI gốc, upload preview và recorder có consent.
Waveform hiện là minh họa, không phân tích từ audio. Transcript mẫu không tự khớp
với file người dùng chọn. Với cuộc họp API, router export đã đọc DB và gọi module
JSON schema 1.1/TXT/Markdown; E2E kiểm download và evidence khớp UI. MSW vẫn chỉ trả file mẫu.

API client có type sinh từ `contracts/openapi.json`; MSW đọc fixture chung trong
`contracts/fixtures/api/`. Danh sách poll mỗi 5 giây khi còn cuộc họp đang chờ
hoặc xử lý; transcript pending cũng được lấy lại. Upload dùng XHR với tiến độ,
hủy và Idempotency-Key. `useJobQuery` và `JobStatusCard` đã gắn vào trang chi tiết
API và trang tiến độ riêng. Trang upload lấy giới hạn và đuôi file từ `GET /config`;
khi chưa tải được cấu hình, khóa chọn file và có nút thử lại. Khóa nguồn, metadata
và ghi âm trong lúc upload; hủy bằng bàn phím có thông báo trạng thái.
Tùy chọn số người nói đang disable vì chưa được xử lý.

## Thử giao diện

Mở `/meetings/sprint-42` để xem màn hình chính. Có thể tua và chạy mô phỏng;
chọn audio trên máy để nghe file thật. Tạo cuộc họp mới gửi file tới API; ở chế
độ MSW, phản hồi được mô phỏng bằng fixture và không tạo transcript từ file đó.

Recorder chỉ xin quyền micro khi bấm bắt đầu sau consent; dừng track khi dừng ghi
hoặc rời trang. Cần localhost/HTTPS và trình duyệt hỗ trợ MediaRecorder. File WebM
thiếu duration sử dụng thời gian đo trong phiên ghi âm làm fallback.
Logic ghi âm nằm trong `src/features/audio/useRecorder.ts`, có test giả lập quyền
micro, hủy và cleanup. Các cuộc họp API dùng endpoint cho chỉnh sửa segment,
tóm tắt và công việc; cuộc họp `sprint-42` vẫn là bản demo cục bộ.

## Chạy local

Yêu cầu Node.js 24 và npm. Đã kiểm tra trên clone sạch với Node v24.13.0, npm 11.6.2.
Chạy các lệnh sau trong thư mục `frontend/`.

```bash
npm ci
npm run dev
```

Nếu PowerShell chặn `npm.ps1`/`npx.ps1`, dùng `npm.cmd`/`npx.cmd` thay
`npm`/`npx` trong các lệnh dưới đây.
Để dùng backend thật, chạy PostgreSQL và API theo `backend/README.md`, rồi chạy:

```powershell
$env:VITE_API_MOCK = '0'
npm run dev
```

Proxy `/api` mặc định trỏ tới `http://localhost:8000`; đổi bằng
`VITE_API_PROXY_TARGET` nếu API chạy cổng khác. Mở frontend qua `localhost` để
request API và cookie cùng origin. Không đặt token, mật khẩu hoặc secret vào biến `VITE_*`.
MSW dùng tài khoản giả `user@example.com` / `demo-password`; phiên mock chỉ tồn tại
trong bộ nhớ service worker. Backend thật dùng tài khoản do quản trị viên tạo.

Với PostgreSQL từ `docker-compose.yml` hiện tại, môi trường backend cần
`DATABASE_URL=postgresql+psycopg://postgres:postgrespassword@localhost:5432/meeting_assistant`
(thông tin dev trong Compose). Chạy `uv run alembic upgrade head` trước lần đầu.
Tạo tài khoản bằng `uv run python -m app.scripts.create_user --email <email> --name <tên>`;
CLI hỏi mật khẩu, không đưa mật khẩu vào tham số dòng lệnh.
Nếu seed dữ liệu mẫu, cung cấp `SEED_DEMO_PASSWORD` trong môi trường backend,
chạy `uv run python -m app.scripts.seed`, rồi bỏ biến đó. Tài khoản seed là
`demo@meeting.local`. Nếu máy có biến `DEBUG=release`, đặt `DEBUG=false` trong
terminal chạy backend vì cấu hình này yêu cầu boolean.

Đăng xuất xóa query cache và dữ liệu xem thử trong bộ nhớ. Tab Lịch sử hỗ trợ
lọc và phân trang, lấy edit event từ backend thật; E2E kiểm đúng các event vừa sửa.
Trang có thông báo mất mạng và lỗi giao diện an toàn.
Font Inter Variable được self-host tại `public/fonts/InterVariable.woff2`, kèm giấy phép OFL trong `Inter-LICENSE.txt`.

## Kiểm tra

```bash
npm run lint
npm run format:check
npm run typecheck
npm test
npm run test:coverage
npm run build
```

CI chạy lint, format, typecheck, test có coverage và build ở trên cho pull request thay đổi `frontend/`, push lên
`main`/`vantuong` có thay đổi frontend/workflow, hoặc khi chạy thủ công.
Node.js được thống nhất ở bản 24 qua `.nvmrc` và workflow.

FE-01 có smoke test cho các route, redirect và bộ provider trong
`src/app/scaffold.test.tsx`. Checklist và trạng thái nghiệm thu:
[docs/frontend/FE-01.md](../docs/frontend/FE-01.md).
CI trên GitHub chỉ được xác nhận sau khi được phép push và workflow chạy thành công.

## Quy ước

- Chia code theo feature khi bắt đầu FE-02; component dùng chung nằm trong `src/components/`.
- Server state dùng TanStack Query. State cục bộ dùng React state.
- Không import trực tiếp schema trong `contracts/pipeline/`; đó là contract giữa pipeline và backend.
- Khi kết nối backend, frontend phải đọc giới hạn upload từ `GET /api/v1/config`.

## Hardening và axe — 09/11/2026

401 từ API (ngoài lỗi đăng nhập) dọn cache và về login có thông báo hết phiên,
giữ URL đích qua `next`. Thông báo dùng router state, không lưu credential.
Ma trận rỗng/tải/lỗi: `docs/demo/ux-checklist.md`, có test các trang và panel.

`axe-core` 4.x (MPL-2.0) là dev dependency. `npm test` chạy kiểm cấu trúc trên
bốn trang qua jsdom; chỉ kiểm Chromium mới bao gồm tương phản màu/layout.
`FAKE_SCENARIO=slow npx playwright test` gồm bốn ca axe desktop/mobile cùng E2E
hiện có. PowerShell đặt `$env:FAKE_SCENARIO='slow'` trước khi chạy lệnh.
Không tắt color-contrast trong browser. JSON/ảnh được ghi ở `test-results/`
(ngoài Git); bản tổng hợp đã soát ở `docs/demo/accessibility-2026-11-09.json`.
Kết quả tự động không thay kiểm screen reader hoặc chứng nhận toàn bộ WCAG.

## Coverage — 10/11/2026

Đo bằng Vitest 5.0.5 và `@vitest/coverage-v8` 5.0.5 (MIT), Node v24.13.0.
Lệnh: `npm run test:coverage`. CI frontend chạy lệnh này để chặn giảm coverage.

| Chỉ số   | Đo được | Ngưỡng tổng |
| -------- | ------- | ----------- |
| Lines    | 86.53%  | 84.53%      |
| Branches | 81.11%  | 79.11%      |

Ngưỡng lấy mức đã đo trừ 2 **điểm phần trăm**, không tự nâng/hạ và không
viết thêm test chỉ để tăng số. Include toàn bộ source TS/TSX, kể cả file
chưa được import trong test; loại file test, test helpers, mock và type API
sinh tự động. Không loại component khó test để nâng coverage.
Bản tổng hợp: [coverage-2026-11-10.json](../docs/frontend/coverage-2026-11-10.json).
HTML/JSON đầy đủ ở `coverage/` ngoài Git và ngoài Docker build context.
Cấu hình theo [tài liệu coverage của Vitest](https://vitest.dev/config/coverage).

## E2E từ clone sạch — 10/11/2026

Dev mặc định dùng MSW nên chỉ cần Node/npm; E2E sau đây cần thêm Python 3.12,
uv, Docker với PostgreSQL 16 và ffprobe. Nếu chưa có trong PATH, đặt `UV` và
`FFPROBE_BIN` tới executable tương ứng. Chromium được cài riêng bằng lệnh bên dưới.

Từ `frontend/`, PowerShell:

```powershell
npm ci
npx playwright install chromium
# Tên container/cổng sau phải chưa được dùng; chỉ tạo database E2E tổng hợp.
docker run --rm -d --name meeting-frontend-e2e-db -e POSTGRES_DB=meeting_e2e -e POSTGRES_PASSWORD=postgrespassword -p 127.0.0.1:55450:5432 postgres:16
docker exec meeting-frontend-e2e-db pg_isready -U postgres -d meeting_e2e
# Chờ pg_isready báo accepting connections rồi chạy tiếp.
$env:E2E_DATABASE_URL='postgresql+psycopg://postgres:postgrespassword@127.0.0.1:55450/meeting_e2e'
$env:SEED_DEMO_PASSWORD=[guid]::NewGuid().ToString()
$env:DEBUG='false'
$env:FAKE_SCENARIO='slow'
npm run e2e
# Chạy từng kịch bản, không chạy đồng thời vì dùng chung cổng 14173/18000.
$env:FAKE_SCENARIO='permanent'
npm run e2e
$env:FAKE_SCENARIO='transient_once'
npm run e2e
$env:FAKE_SCENARIO='summary_fail'
npm run e2e
# Dừng đúng container do các lệnh trên tạo, không dùng database thật.
docker stop meeting-frontend-e2e-db
Remove-Item Env:SEED_DEMO_PASSWORD
```

Stack tự sync backend, migrate, seed tài khoản tổng hợp, build frontend, bật
API/worker/preview rồi dừng các tiến trình của nó. Lệnh `docker stop` cuối cùng
xóa container/database E2E do dùng `--rm`. Cần giữ cổng 14173/18000 trống.
Chi tiết phạm vi và kết quả: [clean-clone-2026-11-10.md](../docs/frontend/clean-clone-2026-11-10.md).
E2E qua nginx dùng stack riêng và `npm run e2e:compose`; xem [FE-19](../docs/frontend/FE-19.md).

## Query đọc dữ liệu khi API bận — 11/11/2026

Query chung chỉ retry ApiError HTTP 503 hoặc NETWORK_ERROR, tối đa hai lần
sau request đầu; chờ Retry-After (thiếu thì 2 giây). 4xx/500 không tự gửi lại.
Mutation giữ retry false. Poll job có lịch riêng, không cộng retry của provider.
Danh sách/chi tiết hết lượt có thông báo và nút Thử lại. Thông báo poll với dữ
liệu cũ dùng status/polite; lỗi chặn thao tác dùng alert và không tự chuyển focus.

[Chi tiết hành vi và test](../docs/frontend/query-busy-2026-11-11.md),
[browser axe với response tổng hợp](../docs/frontend/accessibility-busy-2026-11-11.json).
Đợt này có 296 Vitest/48 file đạt; coverage lines 86.65%, branches 81.34%, giữ
floors 84.53/79.11 từ baseline ngày 10/11; xem [số đo](../docs/frontend/coverage-2026-11-11.json).
Nhóm test được giao chạy 20 lượt và E2E mặc định slow chạy 3 lượt; kết quả từng
lượt, commit nguồn và giới hạn ở [báo cáo flaky](../docs/evidence/vt-018/flaky-frontend-2026-11-11.md).
Kết quả local chưa thay CI của PR ngày 11/11; chưa push/mở PR trong bước triển khai này.
