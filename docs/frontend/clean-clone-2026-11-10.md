# Clone sạch frontend — 10/11/2026

## Nguồn và môi trường

- Clone mới từ repository local ở commit `8beb86e148a15371bb978b2b6ba54b61985b59cb`; code chưa push nên không
  gọi đây là kiểm tra clone từ GitHub của commit mới.
- Windows, Git mặc định của máy, Node v24.13.0, npm 11.6.2, Python 3.12 qua uv,
  PostgreSQL 16 riêng. Dùng Chromium và ffprobe; không gọi model AI thật.
- Lần clone đầu phát hiện Git đổi frontend sang CRLF, làm 147 file fail format.
  Sửa `frontend/.gitattributes` để text dùng LF, giữ font/ảnh dạng binary;
  clone mới lần hai chạy đạt, không định dạng lại hàng loạt source.
- SHA256 Inter WOFF2 giữa source và clone khớp: `693b77d4f32ee9b8bfc995589b5fad5e99adf2832738661f5402f9978429a8e3`.

## Các bước đã kiểm

| Bước | Kết quả |
| --- | --- |
| `npm ci --no-audit --no-fund` | Cài dependency từ lockfile trên clone mới |
| `npm run lint` | Đạt ESLint và Oxlint |
| `npm run format:check` | Đạt sau khi cố định LF |
| `npm run typecheck` | Đạt |
| `npm run test:coverage` | 284 test / 46 file đạt; lines 86.53%, branches 81.11%; ngưỡng 84.53/79.11 đạt |
| `npm run build` | Đạt |
| Dev mặc định | Mở qua Vite cổng riêng 15173, MSW đăng ký, login giả lập và danh sách hoạt động; dừng đúng server do kiểm thử tạo |
| `FAKE_SCENARIO=slow npm run e2e` | 24 test đạt, không skip |
| `FAKE_SCENARIO=permanent npm run e2e` | 1 test đạt |
| `FAKE_SCENARIO=transient_once npm run e2e` | 1 test đạt |
| `FAKE_SCENARIO=summary_fail npm run e2e` | 1 test đạt |

Tổng 27 E2E trên clone sạch, backend/API/worker thật và database riêng tên có
`e2e`, pipeline fake. Flow bàn phím nằm trong 24 ca slow; không đếm lại thành
test mới khi chạy riêng qua nginx. Stack tự sync/migrate/seed/build trước mỗi
scenario. Bộ chạy tự dừng API/worker/preview. Database E2E được dọn riêng sau QA.

## Tài liệu đã sửa

`frontend/README.md` dùng `npm ci`, ghi Node đã kiểm, tài khoản MSW, cách bật
API thật và block PowerShell tạo/chạy/dọn database E2E. README chung chỉ sửa
lệnh frontend, mô tả chế độ mặc định và địa chỉ healthcheck cho đúng cấu hình;
không đưa tiến độ cá nhân vào README chung.

Log/trace/report đầy đủ ở thư mục QA ngoài Git. JSON coverage tổng hợp nằm
trong `coverage-2026-11-10.json`; ảnh tổng hợp ở `docs/demo/screenshots/`.
Log worker native Windows vẫn có cảnh báo `os.killpg` khi hủy job đang chạy,
đã được ghi nhận từ các đợt trước và thuộc pipeline. Các assertion UI/API
vẫn đạt; không dùng kết quả đó để khẳng định cleanup subprocess đã đúng trên
native Windows. Stack Compose Linux được kiểm riêng ở task 5.

Kết quả local không thay CI GitHub. Bổ sung sau khi được phép chạy nhánh thử:
task 5 có [CI đỏ](https://github.com/TAINGUYENVAN0507/SE2026_Codex/actions/runs/42786190434) với proxy sai và [CI xanh](https://github.com/TAINGUYENVAN0507/SE2026_Codex/actions/runs/42786612344) sau khôi phục;
chi tiết tại FE-19. CI PR bàn giao được kiểm riêng trên head cuối. Không dùng fake pipeline để kết luận
WER, chất lượng tóm tắt hoặc khả năng chịu tải thực tế.
