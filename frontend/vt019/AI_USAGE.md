# AI Usage Log - VT-019

Công cụ sinh nội dung/code/test: Codex. Không gọi một AI khác để kiểm chứng.
Công cụ thực thi: Git local, Node 24, npm, Vitest, MSW, Playwright/Chromium,
ESLint, Oxlint, TypeScript, Prettier và Vite. PDF do Python/ReportLab tạo,
PyMuPDF/pypdf dùng để kiểm tra. Không đưa dữ liệu họp thật hoặc secret vào prompt.

## Prompt chính thực nhận

Người dùng: “thầy tôi giao bài bài tập mới , hãy đọc và giúp tôi làm”, kèm email
VT-019. Phần chỉ thị trong email: “Cho AI đề xuất hai phương án; chọn một bằng
evidence từ repository và ghi rõ phương án bị loại.” “Dùng coding agent tạo
implementation plan trước khi code.” “Risk trọng tâm: AI sinh test bám vào
implementation hiện tại thay vì requirement.”

Steering về sau của người dùng: “nếu làm gì thì chỉ làm ở máy local thôi nhé”.
Đây là lý do chưa có link branch/PR công bố. Không push, tạo PR hay merge.

## Output Codex đã dùng và nguồn có thể đối chiếu

Output plan được tạo trước patch trong `docs/frontend/VT-019-plan.md`, phần
“Output plan do Codex tạo trong phiên làm bài”:

> Phương án A: debounce PATCH độc lập; gắn generation ID để bỏ response cũ ở UI,
> có thể abort request trước đó. Phương án B: tuần tự hóa PATCH trên từng editor,
> gộp draft chờ mới nhất, gửi tiếp với version xác nhận; giữ 409 cho tab khác.

Chọn B sau khi đọc `frontend/src/api/client.ts:163-174` và
`backend/app/api/v1/meetings.py:975-993,1067-1099`: API đã có version/CAS.
Abort không hoàn tác được request đã commit; generation ID phía UI không bảo vệ DB.

Các file được agent tạo thực tế: `autosave.ts`, `AutosaveEditor.tsx`, bốn file
test cạnh feature và hai E2E trong `vt019/autosave.spec.ts`. Điểm nối nằm ở
`Transcript.tsx`. Output code nguyên văn nằm trong commit implementation
`cc332f01f65be6d194fd7adbd4ccab2879b0ee32`, không tái dựng transcript khác.

## Quyết định sửa/bác bỏ

| Đề xuất trong plan                | Review và quyết định                                                           | Evidence                                                                    |
| --------------------------------- | ------------------------------------------------------------------------------ | --------------------------------------------------------------------------- |
| Apply mọi response vào textbox    | Bác bỏ; textbox giữ local draft, chỉ version và dữ liệu xác nhận được cập nhật | TC02/13/16 ép A chậm trong khi C đã được gõ                                 |
| Tự GET version mới rồi retry 409  | Bác bỏ; giữ draft, dừng autosave, hiển thị conflict                            | Contract version cũ 409; TC03/14/17 không cho silent overwrite              |
| Timestamp client xác định bản mới | Bác bỏ; dùng thứ tự edit cục bộ và server version                              | Server UPDATE có điều kiện theo version; clock client không có thứ tự chung |
| Debounce song song + abort (A)    | Loại; chọn serialize/coalesce (B)                                              | API CAS sẵn có; TC02 kiểm tối đa một request trên editor                    |

## Hai điểm AI trông hợp lý nhưng chưa đáng tin

1. Test chỉ đếm PATCH sau debounce có thể pass dù response cũ làm mất C. Cần
   deferred response và assertion textbox/payload mới nhất (TC02/13/16).
2. Test dùng cùng logic hàng đợi để tự tính expected result sẽ lặp lại bug của
   implementation. Expected ở đây cố định từ AC: C phải còn, version phải tăng,
   request sai không có side effect. Mutation TC04 kiểm chứng oracle này.

Không tạo timestamp hoặc log giả. Các log đính kèm là stdout/stderr từ lệnh
thực thi, gồm cả lần fail có chủ đích; không coi lời giải thích của AI là evidence.
