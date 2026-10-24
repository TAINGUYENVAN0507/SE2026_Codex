# Frontend

React SPA của Vietnamese Meeting Minutes Assistant. Owner: member A.

## Trạng thái

Giao diện graphite/cam được triển khai từ bộ ảnh đã duyệt, gồm:

- `/login`
- `/meetings`
- `/meetings/new`
- `/meetings/sprint-42`: cuộc họp mẫu đầy đủ để thử player và chỉnh sửa.
- `/meetings/:meetingId`: chi tiết cuộc họp từ API.

`/meetings/sprint-42` vẫn là trang mẫu trong React Context. Danh sách,
upload và transcript của các cuộc họp khác dùng API. Khi chạy dev, MSW bật
mặc định và trả fixture từ `contracts/fixtures/api/`; đặt `VITE_API_MOCK=0`
để gọi backend thật. Bản mock không lưu file audio lên server. Tài khoản/mật
khẩu demo vẫn không được gửi hoặc lưu.

Đã có tìm kiếm/lọc meeting và transcript, player mô phỏng hoặc nghe audio trên máy,
sửa transcript và speaker của segment, xem bản gốc, sửa tổng quan, quản lý công việc,
export bản hiện tại ra TXT/MD/JSON, upload preview và recorder có consent.
Waveform hiện là minh họa, không phân tích từ audio. Transcript mẫu không tự khớp
với file người dùng chọn. Export JSON có schema `preview-1`, chưa là API contract.

API client có type sinh từ `contracts/openapi.json`; MSW đọc fixture chung trong
`contracts/fixtures/api/`. Danh sách poll mỗi 5 giây khi còn cuộc họp đang chờ
hoặc xử lý; transcript pending cũng được lấy lại. Upload dùng XHR với tiến độ,
hủy và Idempotency-Key. `useJobQuery` và `JobStatusCard` đã poll endpoint job,
nhưng chưa gắn vào trang demo. Giới hạn 200 MB cần được thay bằng `GET /config`
khi tích hợp backend. Tùy chọn số người nói đang disable vì chưa được xử lý.

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

Yêu cầu Node.js 24 và npm.

```bash
npm install
npm run dev
```

Trên PowerShell chặn script `npm.ps1`, dùng `npm.cmd run dev`.
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
Font Inter Variable được self-host tại `public/fonts/InterVariable.woff2`, kèm giấy phép OFL trong `Inter-LICENSE.txt`.

## Kiểm tra

```bash
npm run lint
npm run format:check
npm run typecheck
npm test
npm run build
```

CI chạy đủ năm lệnh trên cho pull request thay đổi `frontend/`, push lên
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
