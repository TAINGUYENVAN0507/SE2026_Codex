# Checklist UX và demo — 08/11/2026

Ảnh chụp Chromium từ ứng dụng đang chạy: API, worker và PostgreSQL thật;
pipeline fake, WAV tổng hợp 30 giây. Không dùng cuộc họp hay ghi âm của người
thật. Đây là kiểm thử luồng sản phẩm, không phải đánh giá độ chính xác/tốc độ AI.

## Checklist đã kiểm tra local

| Mục | Kết quả và bằng chứng |
| --- | --- |
| Upload có consent | Chỉ tạo meeting sau thao tác xác nhận; xem ảnh upload và `upload.spec.ts`, PRIV-01…09. |
| Theo dõi tiến độ | Sáu bước ở trang riêng; trang nội dung chỉ có dòng gọn. Reload vẫn theo job cũ; `upload.spec.ts`/RT-11. |
| Tóm tắt và audio | Bấm evidence tua đúng `currentTime` của audio thật; `export.spec.ts`. WAV đủ 30 giây để kiểm các mốc của pipeline fake. |
| Kiểm chứng từng ý/công việc | Tất cả timestamp khớp giữa API, UI và từng dòng TXT/MD; nội dung thiếu evidence có nhãn ở cả hai nơi; `export-evidence.spec.ts`. |
| Export | Nút tải TXT, Markdown, JSON gọi router thật; kiểm HTTP 200, tên file và nội dung đúng meeting. |
| Sửa và lịch sử | Sửa segment, speaker, CRUD công việc; reload và đối chiếu audit; `edit.spec.ts`. |
| Xóa cuộc họp | Có hộp xác nhận và hủy; E2E xóa khi job đang chạy rồi meeting/audio/job trả 404; `delete.spec.ts`. Không dùng kết quả UI để kết luận worker cleanup hoàn hảo. |
| Audio hết hạn | Chạy CLI cleanup thật: audio/artifact biến mất, GET audio trả 410, transcript DB/API/UI không đổi; `retention.spec.ts`. |
| Cài đặt tài khoản | Mở từ bánh răng, reload được; nút xóa bật theo contract. E2E xóa user tổng hợp riêng kiểm mất cookie/phiên cũ, đăng nhập lại thất bại và user khác còn hoạt động. |
| Form xác nhận tài khoản | Vitest: gõ lại email, hủy/Escape, focus, chống gửi lặp, lỗi mạng/5xx giữ email/cache, success xóa phiên. HTTP được giả lập riêng trong test component. |
| Desktop/mobile | 14 ảnh ở viewport 1280×900 và 360×800; không tràn ngang trong các màn đã chụp. Trang cài đặt còn được kiểm riêng ở 1280px/360px. |
| Bản ghi ngắn | Header hiện giây khi dưới một phút; không ghi 30 giây thành 0 phút. Chưa có thời lượng thì ghi rõ, không dựng số giả. |
| Lỗi khi chạy | Không có `pageerror` trong luồng chụp ảnh. Lỗi nghiệp vụ được kiểm riêng bằng E2E permanent/retry/partial và Vitest. |

Kết quả local: **238 Vitest**, **19 E2E slow + 3 E2E lỗi/retry/partial** đạt;
lint, format, typecheck và build đạt. Ruff cho fixture Python retention đạt.
Chưa push nên chưa xác nhận CI của đợt 08/11. CI mới chỉ được báo khi đã push và kiểm tra đúng commit.

## Ảnh mới từ ứng dụng

| Màn | Desktop | Điện thoại |
| --- | --- | --- |
| Upload | [1280px](screenshots/2026-11-08-upload-desktop.png) | [360px](screenshots/2026-11-08-upload-mobile.png) |
| Tiến độ riêng | [1280px](screenshots/2026-11-08-progress-desktop.png) | [360px](screenshots/2026-11-08-progress-mobile.png) |
| Tóm tắt có evidence | [1280px](screenshots/2026-11-08-summary-desktop.png) | [360px](screenshots/2026-11-08-summary-mobile.png) |
| Công việc có evidence | [1280px](screenshots/2026-11-08-tasks-desktop.png) | — |
| Menu export | [1280px](screenshots/2026-11-08-export-desktop.png) | — |
| Xác nhận xóa cuộc họp | [1280px](screenshots/2026-11-08-delete-desktop.png) | — |
| Audio hết hạn, còn transcript | [1280px](screenshots/2026-11-08-expired-desktop.png) | — |
| Cài đặt tài khoản | [1280px](screenshots/2026-11-08-settings-desktop.png) | [360px](screenshots/2026-11-08-settings-mobile.png) |
| Xác nhận xóa tài khoản | [1280px](screenshots/2026-11-08-account-confirm-desktop.png) | [360px](screenshots/2026-11-08-account-confirm-mobile.png) |

Bản sao tiện duyệt ở `.preview-stitch/anh-duyet/2026-11-08/` (ngoài Git).
Ảnh ở `docs/demo/screenshots/` là dữ liệu tổng hợp, dùng làm bằng chứng của tài liệu.

## Kịch bản demo 5 phút

Chuẩn bị bản chạy `VITE_API_MOCK=0`, backend/worker và database test riêng,
`PIPELINE_BACKEND=fake`, `FAKE_SCENARIO=slow`; dùng tài khoản demo và WAV tổng
hợp. Không dùng tài khoản/cuộc họp thật để thử xóa. Tên người nói trong dữ liệu
fake chỉ là nhãn minh họa, không phải nhận dạng danh tính từ giọng nói.

| Thời gian | Thao tác và điểm cần nói |
| --- | --- |
| 00:00–00:30 | Giới thiệu mục tiêu: từ bản ghi đến transcript, tóm tắt và công việc có thể kiểm chứng. Nói rõ đang dùng dữ liệu/pipeline fake. |
| 00:30–01:10 | Vào Tạo cuộc họp, chọn WAV, nghe thử tại máy, đặt tên và xác nhận consent; bấm Tạo biên bản. |
| 01:10–01:40 | Mở Xem tiến độ để thấy sáu bước, phần trăm/thời gian; reload rồi trở về nội dung. |
| 01:40–02:40 | Đọc transcript và tóm tắt; bấm một mốc evidence để tua audio. Sửa một đoạn, lưu, reload và mở Lịch sử. |
| 02:40–03:40 | Mở Công việc, thử thêm/sửa một việc. Giải thích nhãn Chưa có bằng chứng với nội dung chưa có dẫn chứng. |
| 03:40–04:20 | Tải TXT/MD/JSON; mở file TXT/MD, chỉ mốc dẫn chứng trùng giao diện. Giới thiệu lựa chọn bản hiện tại/bản AI gốc. |
| 04:20–04:45 | Mở Xóa cuộc họp, đọc phạm vi dữ liệu, thử hủy rồi xác nhận xóa meeting tổng hợp. Mở lại link cũ để thấy không tìm thấy. |
| 04:45–05:00 | Chỉ ảnh audio hết hạn còn transcript; mở Cài đặt, giải thích phạm vi xóa tài khoản và thử hủy. Chỉ thử xóa thật với user tổng hợp riêng, không xóa tài khoản demo chung. |

Nếu máy xử lý chậm, dùng một meeting tổng hợp đã ready để trình bày phần đọc,
chỉnh sửa và export. Phân bố 5 phút là kịch bản trình bày, không phải benchmark.

## Chạy lại kiểm tra

Chuẩn bị PostgreSQL riêng có tên chứa `e2e`, đặt `E2E_DATABASE_URL` và mật khẩu
demo theo [FE-17](../frontend/FE-17.md). Từ `frontend/`:

```powershell
npm run lint
npm run format:check
npm run typecheck
npm test
npm run build
$env:FAKE_SCENARIO='slow'
npx playwright test
```

Chạy tiếp từng `FAKE_SCENARIO=permanent`, `transient_once`, `summary_fail` bằng
`npx playwright test`. Stack tự bật API/worker với pipeline fake và tắt khi xong;
không tái sử dụng API/database phát triển. Fixture retention chỉ chạy trên dữ
liệu E2E, kiểm đường dẫn rồi gọi CLI cleanup chính thức.

## Còn chờ hoặc cần nhóm xác nhận

- Xóa tài khoản: phần frontend và E2E user riêng đã đạt local; chờ CI/review
  của đợt 08/11, không còn chờ API BE-18. Bằng chứng xóa log/DB/file ở mọi
  nơi lưu vẫn thuộc phần backend của B.
- Review PR mới của B: chưa có PR `haquang` mới tại lần kiểm tra cuối buổi.
- Native Windows từng có log `os.killpg` khi hủy job đang chạy. Pipeline thuộc C;
  cần xử lý riêng nếu hỗ trợ worker native Windows. Không giấu lỗi để báo sạch.
- Race worker Linux từng được ghi nhận ngày 06/11 cần B/C xác nhận lại trên main
  mới; xem [FE-19](../frontend/FE-19.md). Test UI/API không thay evidence backend.
- SH-01 ghi âm pilot có consent là việc chung, chưa được thực hiện trong đợt này.

## Bug bash và thay đổi 08/11

Chi tiết tái hiện, mong đợi/thực tế, mức độ và test hồi quy:
[`bug-bash-2026-11-08.md`](bug-bash-2026-11-08.md).

- API hiện không có tự đăng ký; tài khoản do CLI quản trị cung cấp.
- Upload dùng giới hạn/định dạng server, có trạng thái lỗi và thử tải lại config.
  Khi upload đang chạy không đổi nguồn hoặc bật micro; bàn phím vẫn hủy được.
- 48 mã lỗi công bố có thông báo riêng; không lộ raw message backend.
- Docker Web build/khởi động được sau sửa contract path và PID Nginx.
- Các ảnh chỉ xác nhận layout/overflow ở viewport giả lập Chromium; chưa kiểm
  điện thoại vật lý hoặc screen reader thực tế. Detector trên trang sửa trả []
  không đồng nghĩa toàn bộ ứng dụng đã đạt WCAG.
