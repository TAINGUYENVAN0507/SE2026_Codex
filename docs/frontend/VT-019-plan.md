# VT-019 - Spec và AI-assisted plan trước implementation

Baseline: `53f753b3afe6c1a2d54ff1e38a72dee30c6074d2`, nhánh cá nhân
`vantuong-vt019-autosave`. Đây là bài cá nhân; không tự merge.

## Problem statement

Người sửa biên bản có thể mất phần gõ mới khi quên lưu hoặc khi một lần lưu
cũ hoàn tất chậm. Cần tự lưu đoạn đang sửa và giữ nguyên nội dung mới nhất
của người dùng khi request đang chạy, thất bại hoặc bị xung đột.

## Acceptance criteria

- AC1: Sau 500 ms không gõ, nội dung hợp lệ của segment API được gửi qua PATCH
  hiện có; trạng thái lưu hiển thị cho người dùng. 500 ms là quyết định thiết kế.
- AC2: Khi A đang lưu và B/C được gõ, A hoàn tất không thay textbox C; chỉ snapshot
  mới nhất còn chờ được gửi tiếp với version server trả về. Tối đa một request
  chưa hoàn tất trên một editor; không áp snapshot cũ lên draft mới.
- AC3: Version cũ từ tab khác nhận 409; dừng tự ghi đè, giữ draft, không tự retry
  bằng version mới. UI hướng dẫn kiểm tra/tải lại.
- AC4: Text trống, chỉ khoảng trắng hoặc hơn 5000 ký tự sau trim không được gửi;
  response không tiến version bị từ chối. Boundary 1 và 5000 hợp lệ.
- AC5: Lỗi mạng/500 giữ draft và báo chưa lưu; retry chủ động gửi draft mới nhất;
  đóng editor không tạo request mới. Lệnh đã gửi có thể vẫn commit.

NFC1: đo 120 tác vụ cùng lúc, p95 <=3.5 s. Harness giả lập phải tách thời gian
request khỏi debounce, ghi rõ không phải capacity backend/DB production.
NFC2: Không lưu transcript vào Web Storage/log; text mẫu tự tạo; giữ auth/version
contract và bản AI gốc. Draft trong RAM chưa được bảo đảm khi refresh/rời trang.

Invariant: draft đang hiển thị luôn là edit mới nhất; version xác nhận không lùi;
server PATCH dùng version điều kiện. Hai tab không được silent overwrite nhau.

## Output plan do Codex tạo trong phiên làm bài

Phương án A: debounce PATCH độc lập; gắn generation ID để bỏ response cũ ở UI,
có thể abort request trước đó. Phương án B: tuần tự hóa PATCH trên từng editor,
gộp draft chờ mới nhất, gửi tiếp với version xác nhận; giữ 409 cho tab khác.
Chọn B vì A vẫn có thể commit trên server dù đã abort; generation ID phía UI
không ngăn stale write ở DB. B tận dụng PATCH version sẵn có, giảm conflict
tự gây ra bởi cùng editor và không đổi schema/API.

Draft plan còn đề nghị: reset textbox theo mọi response thành công; tự retry
409 sau khi GET version mới; dùng timestamp client để chọn nội dung mới hơn.

## Review bằng repository (trước code)

1. Bác reset textbox theo response: `Transcript.tsx:95-159` chụp draft và apply
   response trong manual save; autosave cần giữ local revision khi người dùng
   tiếp tục gõ. Sửa: chỉ update dữ liệu đã xác nhận ở parent, không set draft.
2. Bác auto-retry 409: `structure/contracts.md` quy định version cũ trả 409;
   `meetings.py:975-993,1067-1099` kiểm version và UPDATE điều kiện. Retry mù
   với version mới có thể ghi đè thay đổi của tab khác. Sửa: giữ draft, dừng.
3. Bác timestamp client: server đã có CAS version; clock client không phải thứ
   tự chỉnh sửa chung. Sửa: dùng revision cục bộ + version server.

Các file dự định thay đổi: thêm `autosave.ts`, `autosave.test.ts`,
`AutosaveEditor.tsx`, `AutosaveEditor.test.tsx`, `TranscriptAutosave.test.tsx`
trong `frontend/src/features/meetings/`; nối editor ở `Transcript.tsx`;
README/experiment scripts ở `frontend/vt019/`; tài liệu trong `docs/frontend/`.
Không sửa backend, contract sinh tự động hoặc nhánh làm việc khác.

## Test design độc lập implementation

Oracle được viết từ AC trước patch: textbox phải giữ C khi A trả về, API payload
tiếp theo là C/version mới, 409 không phát sinh ghi tiếp, input không hợp lệ
không có side effect. Deferred promise/barrier điều khiển điểm giao nhau; không
dùng sleep để đoán race; không kiểm private state hay gọi private function.

Unit kiểm controller; component kiểm timer/UI; integration kiểm client PATCH
qua MSW và contract 409. E2E browser có giá trị cho network/tab thực, nhưng không
cần chạy model AI/audio/export để kiểm autosave. Không nhận MSW là backend thật.

## Prompt thực tế

Người dùng gửi email VT-019 và yêu cầu: “thầy tôi giao bài bài tập mới , hãy đọc
và giúp tôi làm”. Chỉ thị trong email: “Cho AI đề xuất hai phương án; chọn một
bằng evidence từ repository và ghi rõ phương án bị loại.” Nội dung plan trên
là output Codex tạo trước patch, không phải transcript của một lượt gọi AI khác.
