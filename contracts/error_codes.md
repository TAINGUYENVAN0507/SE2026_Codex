# Danh mục mã lỗi hệ thống (Error Code Catalogue)

Tài liệu này là nguồn sự thật chung (Single Source of Truth) quy định danh mục mã lỗi chuẩn hóa cho cả REST API (Backend) và Pipeline xử lý âm thanh AI.

Mọi mã lỗi tuân thủ quy ước:
- Định dạng chuỗi `UPPER_SNAKE_CASE`.
- Mã lỗi có tính ổn định lâu dài (không đổi nghĩa, không tái sử dụng cho mục đích khác).
- Phản hồi lỗi HTTP luôn được bọc trong error envelope chuẩn: `{"error": {"code": "...", "message": "...", "details": ..., "request_id": "..."}}`.

---

## 1. Bảng mã lỗi REST API (Backend)

| Mã lỗi | HTTP Status | Ý nghĩa | Gợi ý thông điệp tiếng Việt (Frontend) |
|---|---|---|---|
| `BAD_REQUEST` | 400 | Yêu cầu không hợp lệ hoặc sai cấu trúc cú pháp | Yêu cầu không hợp lệ. |
| `IDEMPOTENCY_KEY_REQUIRED` | 400 | Thiếu header `Idempotency-Key` bắt buộc khi tạo cuộc họp hoặc job | Header Idempotency-Key là bắt buộc khi thực hiện thao tác này. |
| `UNAUTHENTICATED` | 401 | Người dùng chưa đăng nhập hoặc session đã hết hạn | Phiên đăng nhập đã hết hạn hoặc bạn chưa đăng nhập. |
| `INVALID_CREDENTIALS` | 401 | Email hoặc mật khẩu đăng nhập không chính xác | Email hoặc mật khẩu không chính xác. |
| `FORBIDDEN` | 403 | Không có quyền truy cập hoặc thực hiện thao tác trên tài nguyên này | Bạn không có quyền thực hiện hành động này. |
| `NOT_FOUND` | 404 | Tài nguyên được yêu cầu không tồn tại | Không tìm thấy tài nguyên được yêu cầu. |
| `MEETING_NOT_FOUND` | 404 | Không tìm thấy cuộc họp với mã định danh cung cấp | Không tìm thấy cuộc họp được yêu cầu. |
| `METHOD_NOT_ALLOWED` | 405 | Phương thức HTTP không được hỗ trợ cho endpoint này | Phương thức yêu cầu không được hỗ trợ. |
| `CONFLICT` | 409 | Xung đột trạng thái tài nguyên | Xung đột dữ liệu hoặc trạng thái tài nguyên. |
| `VERSION_CONFLICT` | 409 | Xung đột phiên bản do dữ liệu đã bị cập nhật ở nơi khác (Optimistic Locking) | Dữ liệu đã được cập nhật ở nơi khác. Vui lòng tải lại trang. |
| `JOB_ALREADY_ACTIVE` | 409 | Cuộc họp đang có một tiến trình xử lý đang chạy hoặc đang chờ retry | Cuộc họp hiện đang có một tiến trình xử lý đang chạy. |
| `JOB_ALREADY_SUCCEEDED` | 409 | Tiến trình đã hoàn thành thành công, không thể chạy lại toàn bộ | Cuộc họp đã được xử lý thành công. |
| `HAS_USER_EDITS` | 409 | Không thể chạy lại nhận dạng ASR/Diarize khi người dùng đã chỉnh sửa thủ công | Cuộc họp đã có chỉnh sửa thủ công, không thể chạy lại từ đầu. |
| `TRANSCRIPT_NOT_READY` | 409 | Transcript chưa hoàn tất xử lý để chỉnh sửa hoặc xuất biên bản | Transcript chưa sẵn sàng để thực hiện thao tác này. |
| `REQUEST_IN_PROGRESS` | 409 | Yêu cầu với cùng Idempotency-Key đang được xử lý trong transaction khác | Yêu cầu đang được xử lý, vui lòng chờ trong giây lát. |
| `AUDIO_EXPIRED` | 410 | Tệp âm thanh đã bị xóa theo chính sách lưu trữ (retention policy) | Tệp âm thanh đã hết hạn lưu trữ và đã được dọn dẹp. |
| `FILE_TOO_LARGE` | 413 | Dung lượng tệp tải lên vượt quá giới hạn tối đa cho phép | Dung lượng tệp âm thanh vượt quá giới hạn cho phép. |
| `UNSUPPORTED_MEDIA_TYPE` | 415 | Định dạng Content-Type hoặc MIME type không được hỗ trợ | Định dạng tệp không được hỗ trợ. |
| `RANGE_NOT_SATISFIABLE` | 416 | Khoảng byte yêu cầu trong header Range không hợp lệ hoặc vượt quá kích thước tệp | Khoảng dữ liệu yêu cầu không hợp lệ. |
| `UNPROCESSABLE_ENTITY` | 422 | Dữ liệu yêu cầu hợp lệ về cú pháp nhưng không thể xử lý | Dữ liệu yêu cầu không thể xử lý. |
| `VALIDATION_ERROR` | 422 | Dữ liệu đầu vào không vượt qua kiểm tra ràng buộc schema | Dữ liệu nhập vào không hợp lệ. |
| `CONSENT_REQUIRED` | 422 | Chưa xác nhận sự đồng ý ghi âm/xử lý âm thanh của người tham gia | Cần xác nhận đồng ý xử lý dữ liệu trước khi tải lên. |
| `FORMAT_NOT_SUPPORTED` | 422 | Định dạng file xuất biên bản (export format) không được hỗ trợ | Định dạng xuất biên bản không được hỗ trợ. |
| `TEXT_EMPTY` | 422 | Nội dung đoạn thoại chỉnh sửa bị để trống | Nội dung đoạn thoại không được để trống. |
| `TEXT_TOO_LONG` | 422 | Nội dung đoạn văn bản vượt quá độ dài ký tự tối đa quy định | Nội dung vượt quá độ dài tối đa cho phép. |
| `SPEAKER_NOT_IN_MEETING` | 422 | Người nói được gán không nằm trong danh sách người nói của cuộc họp | Người nói không thuộc cuộc họp này. |
| `SPEAKER_NAME_DUPLICATE` | 422 | Tên hiển thị người nói bị trùng lặp với người nói khác trong cuộc họp | Tên người nói bị trùng với người nói khác trong cuộc họp. |
| `INTERNAL_SERVER_ERROR` | 500 | Lỗi nội bộ không lường trước phía server | Đã xảy ra lỗi nội bộ hệ thống. Vui lòng thử lại sau. |
| `HTTP_ERROR` | 500 | Lỗi HTTP không xác định | Đã xảy ra lỗi khi xử lý yêu cầu. |
| `SERVICE_UNAVAILABLE` | 503 | Dịch vụ backend hoặc cơ sở dữ liệu tạm thời không sẵn sàng | Hệ thống tạm thời không sẵn sàng. Vui lòng thử lại sau. |

---

## 2. Bảng mã lỗi Pipeline AI

Các mã lỗi dưới đây trích xuất từ enum `ErrorCode` trong `contracts/pipeline/error.schema.json`.

| Mã lỗi | HTTP Status tương ứng | Ý nghĩa | Gợi ý thông điệp tiếng Việt (Frontend) |
|---|---|---|---|
| `AUDIO_INVALID` | 422 | Tệp âm thanh hỏng, không thể giải mã hoặc không đúng định dạng mono 16 kHz | Tệp âm thanh bị lỗi hoặc định dạng không được hỗ trợ. |
| `AUDIO_TOO_SHORT` | 422 | Thời lượng âm thanh quá ngắn (< 1 giây) | Thời lượng tệp âm thanh quá ngắn, vui lòng chọn tệp dài hơn. |
| `AUDIO_TOO_LONG` | 422 | Thời lượng âm thanh vượt quá giới hạn tối đa cho phép của hệ thống | Thời lượng tệp âm thanh vượt quá giới hạn tối đa. |
| `NO_SPEECH_DETECTED` | 422 | Module VAD không phát hiện thấy tiếng nói nào trong file âm thanh | Không phát hiện thấy tiếng nói trong tệp âm thanh. |
| `MODEL_UNAVAILABLE` | 503 | Mô hình AI (Whisper, Silero, Pyannote) không sẵn sàng hoặc không tải được | Hệ thống AI tạm thời không sẵn sàng. Vui lòng thử lại sau. |
| `OUT_OF_MEMORY` | 503 | Hết bộ nhớ GPU (CUDA OOM) hoặc RAM trong quá trình inference | Hệ thống đang quá tải bộ nhớ. Đang lên lịch thử lại. |
| `DIARIZATION_FAILED` | 500 | Lỗi trong quá trình phân tách người nói (diarization) | Không thể phân tách người nói, chuyển sang chế độ dự phòng. |
| `LLM_UNAVAILABLE` | 503 | Dịch vụ LLM tóm tắt tạm thời không phản hồi (429 rate limit hoặc 5xx) | Dịch vụ tóm tắt tạm thời không phản hồi. Hệ thống sẽ tự thử lại. |
| `LLM_REQUEST_INVALID` | 400 | Yêu cầu gửi tới LLM không hợp lệ (vượt token context hoặc prompt sai) | Yêu cầu tóm tắt không hợp lệ. |
| `LLM_OUTPUT_INVALID` | 500 | Kết quả phản hồi từ LLM không thể parse hoặc không đúng cấu trúc JSON | Kết quả tóm tắt không đúng định dạng. |
| `STAGE_TIMEOUT` | 504 | Quá thời gian quy định khi thực thi một stage trong pipeline | Tiến trình xử lý bị quá hạn thời gian. |
| `STAGE_CRASHED` | 500 | Tiến trình subprocess của stage bị dừng đột ngột (crash/exit bất thường) | Tiến trình xử lý gặp sự cố ngoài dự kiến. |
| `STAGE_NOT_IMPLEMENTED` | 501 | Stage được yêu cầu chưa có hiện thực hóa khả dụng | Tính năng xử lý này đang được hoàn thiện. |
| `MISSING_INPUT` | 400 | Thiếu tệp artifact đầu vào cần thiết để chạy stage tiếp theo | Thiếu dữ liệu đầu vào cho bước xử lý tiếp theo. |
| `PIPELINE_OUTPUT_INVALID` | 500 | Dữ liệu đầu ra của pipeline vi phạm JSON schema hoặc sai `schema_version` | Dữ liệu kết quả xử lý của pipeline không hợp lệ. |
| `PIPELINE_CANCELLED` | 499 | Pipeline bị hủy chủ động do người dùng xóa cuộc họp khi đang xử lý | Tiến trình xử lý cuộc họp đã bị hủy. |
| `INTERNAL_ERROR` | 500 | Lỗi nội bộ không xác định trong runner hoặc stage pipeline | Đã xảy ra lỗi nội bộ trong hệ thống pipeline. |
