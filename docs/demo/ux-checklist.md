# Checklist UX — 25/10/2026

Dữ liệu: fixture MSW, tài khoản thử theo README frontend. Không dùng audio,
transcript hoặc tài khoản của cuộc họp thật. Ảnh được chụp bằng Chromium qua
Playwright; đây là browser QA tự động, không phải tích hợp router export với DB.

## Cách mở lại

1. Tại `frontend/`, chạy `npm run dev` (MSW bật mặc định).
2. Đăng nhập tài khoản mock ghi trong README frontend.
3. Từ danh sách, mở cuộc họp có ID `8f6c2a1e-b2c3-4d4e-8f9a-0b1c2d3e4f5a`.
4. Thử menu export, sửa segment, phím tắt và các tab ở từng kích thước bên dưới.

## Kết quả kiểm tra

| Mục | Kết quả và bằng chứng |
| --- | --- |
| Skeleton danh sách, transcript, summary | Đã kiểm bằng RTL: `LoadingSkeleton.test.tsx`. Có nhãn screen reader và aria-busy. |
| 360×600 | Không tràn ngang; player sticky có top=0 sau khi cuộn; tab có vùng cuộn riêng. |
| 768×900 | Không tràn ngang; nội dung transcript và tóm tắt đọc được. |
| 1280×900 | Hai cột và menu export hiển thị đúng, không tràn ngang. |
| Export | Tải đủ TXT, JSON, Markdown × current/ai_original; tên file lấy từ Content-Disposition. |
| JSON | Hai file JSON tải thật qua MSW được validate theo `contracts/export.schema.json`. |
| Transcript chưa ready | Menu disable, có tooltip; RTL kiểm tra bằng `ExportMenu.test.tsx`. |
| Lỗi export 409 | Có toast, không tải file; RTL kiểm tra bằng `ExportMenu.test.tsx`. |
| Space/←/→ ngoài ô nhập | Space phát/dừng, mũi tên tua 10 giây; RTL và browser kiểm tra. |
| Phím trong ô nhập | Space và → khi gõ segment không dừng/tua player; input, textarea, select, contenteditable được bỏ qua. |
| Nút icon | Browser rà các nút icon-only đang hiển thị: đều có aria-label. |
| Dialog | Tab/Shift+Tab nằm trong dialog; Esc đóng và trả focus về nút lưu; bản nháp được giữ. |
| Focus sau request | Lưu vị trí focus trước khi nút bị disable; đã tái hiện và sửa lỗi trả focus sau request bất đồng bộ. |
| Menu export | Esc đóng menu và trả focus về nút mở. |
| Console | Không có pageerror trong các luồng browser đã kiểm. |

Browser QA có 11 kiểm tra đạt (gồm sáu lượt tải file); kiểm tra layout ở ba
kích thước là một lượt riêng. Bản ghi kết quả cục bộ ở
`.preview-stitch/qa-2026-10-25/results.json`, các file tải xuống được ignore.

## Ảnh dữ liệu mẫu

- [Detail mobile 360px](screenshots/2026-10-25-detail-360.png)
- [Detail 768px](screenshots/2026-10-25-detail-768.png)
- [Detail desktop 1280px](screenshots/2026-10-25-detail-1280.png)
- [Menu export desktop](screenshots/2026-10-25-export-desktop.png)
- [Dialog xung đột và focus](screenshots/2026-10-25-conflict-dialog.png)

## Kiểm tra tự động

Frontend: `npm run lint`, `npm run format:check`, `npm run typecheck`,
`npm test`, `npm run build`. Test mới gồm menu export, skeleton, bàn phím,
focus trap và Esc giữ bản nháp.

Lần chạy cuối: lint/format/TypeScript/build đạt; 29 file test, 149 test frontend đạt.

Backend: Ruff lint/format, `python -m app.services.export --check`,
`pytest tests/unit/test_export*.py`: 16 test export đạt, gồm golden và
deterministic. Trên PowerShell, truyền danh sách file bằng
`$files = rg --files tests/unit -g 'test_export*.py'; uv run pytest $files`.

## Phần còn phụ thuộc backend

Router export hiện vẫn là stub. B cần đọc dữ liệu theo owner, kiểm transcript
ready, dựng `MeetingExport` và gọi module thuần, rồi trả bytes và tên file.
Chưa xác nhận export dữ liệu DB thật khớp UI. Không coi fixture MSW là bằng
chứng của việc lưu bền vững hoặc bảo vệ owner ở router export.
