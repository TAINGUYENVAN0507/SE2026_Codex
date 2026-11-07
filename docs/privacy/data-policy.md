# Chính sách Lưu trữ và Bảo vệ Dữ liệu (Data Policy)

Tài liệu này quy định chi tiết về các loại dữ liệu, vị trí lưu trữ, thời hạn lưu trữ, quy trình xóa bỏ dữ liệu, cơ chế tích hợp dịch vụ bên thứ ba và chính sách quản lý nhật ký (log) trong hệ thống *Vietnamese Meeting Minutes Assistant*.

---

## 1. Danh mục và phân loại dữ liệu

Hệ thống phân loại dữ liệu thành 4 nhóm chính:

| Nhóm dữ liệu | Thành phần cụ thể | Mục đích sử dụng | Mức độ nhạy cảm |
|---|---|---|---|
| **Dữ liệu âm thanh (Audio)** | Tệp ghi âm cuộc họp gốc (`.wav`, `.mp3`, `.m4a`, `.webm`, `.flac`, `.ogg`, `.aac`) | Làm đầu vào cho quá trình nhận dạng giọng nói (ASR, VAD, Diarization) và phát lại trên giao diện người dùng | Rất cao |
| **Dữ liệu trung gian (Artifacts)** | Các tệp JSON trung gian sinh ra bởi từng stage của pipeline: `preprocess.json`, `vad.json`, `asr.json`, `diarization.json`, `transcript.json`, `summary.json`, `audio.wav` | Phục vụ checkpoint/resume khi retry tiến trình xử lý mà không phải chạy lại từ đầu | Cao |
| **Dữ liệu nghiệp vụ (Business Data)** | Siêu dữ liệu cuộc họp, danh sách người nói (`speakers`), văn bản phân đoạn (`segments`), tóm tắt (`summaries`), nhiệm vụ (`action_items`), lịch sử chỉnh sửa (`edit_events`) | Hiển thị, cho phép người dùng chỉnh sửa và xuất biên bản cuộc họp | Cao |
| **Dữ liệu vận hành (Operational Data)** | Bản ghi chống gọi trùng (`idempotency_keys`), trạng thái tiến trình xử lý (`jobs`), nhật ký hệ thống (log files) | Đảm bảo tính nhất quán của hệ thống, chống replay request, kiểm soát lỗi và giám sát vận hành | Trung bình |

---

## 2. Vị trí lưu trữ dữ liệu

1. **Hệ thống tệp (Filesystem / Volume `appdata`):**
   - Tệp âm thanh gốc: `appdata/audio/{meeting_id}/original.<ext>`
   - Thư mục làm việc của job (Artifacts): `appdata/artifacts/{meeting_id}/{job_id}/`
2. **Cơ sở dữ liệu quan hệ (PostgreSQL 16):**
   - Toàn bộ thông tin tài khoản người dùng (`users`), cuộc họp (`meetings`), tiến trình (`jobs`), kết quả AI gốc (`ai_outputs`), văn bản transcript (`segments`), người nói (`speakers`), tóm tắt (`summaries`), công việc (`action_items`), sự kiện kiểm toán (`edit_events`), và khóa idempotent (`idempotency_keys`).
3. **Bộ nhớ tạm thời phía Client (Frontend):**
   - Chỉ lưu phiên làm việc (access token) trong cookie HttpOnly hoặc bộ nhớ ram của trình duyệt. Không lưu cache âm thanh hoặc transcript lâu dài trên LocalStorage.

---

## 3. Thời hạn lưu trữ (Data Retention Periods)

Thời hạn lưu trữ được cấu hình qua biến môi trường để dễ dàng điều chỉnh mà không phải can thiệp mã nguồn:

| Dữ liệu | Thời hạn lưu trữ mặc định | Biến cấu hình | Hành vi khi hết hạn |
|---|---|---|---|
| **Tệp âm thanh gốc (Audio)** | 14 ngày kể từ khi tạo | `AUDIO_RETENTION_DAYS=14` | Tự động xóa vĩnh viễn tệp trên ổ đĩa. Cột `audio_path` chuyển thành `null`, trường `audio.available` chuyển thành `false`. Yêu cầu nghe lại `GET /audio` trả về mã lỗi HTTP 410 `AUDIO_EXPIRED`. |
| **Tệp trung gian (Artifacts)** | 14 ngày (cùng kỳ với audio) | `AUDIO_RETENTION_DAYS=14` | Tự động xóa toàn bộ thư mục `artifacts/{meeting_id}/` trên ổ đĩa khi dọn dẹp audio. |
| **Dữ liệu vận hành (`idempotency_keys`)** | 28 ngày kể từ khi tạo | `OPERATIONAL_RETENTION_DAYS=28` | Tự động xóa các bản ghi quá 28 ngày khỏi bảng `idempotency_keys`. |
| **Văn bản cuộc họp trong DB** | Không tự động xóa | — | Lưu trữ trong cơ sở dữ liệu cho tới khi người dùng chủ động thực hiện thao tác xóa cuộc họp hoặc xóa tài khoản. |

> [!NOTE]
> Mốc thời gian hết hạn audio được tính toán ngay khi tạo cuộc họp: `retention_until = created_at + timedelta(days=AUDIO_RETENTION_DAYS)`. Tiến trình dọn dẹp chạy định kỳ sẽ chỉ xóa khi thời điểm hiện tại đã vượt qua mốc `retention_until`.

---

## 4. Cơ chế xóa dữ liệu (Data Erasure Mechanism)

### 4.1. Dọn dẹp tự động định kỳ (Retention Cleanup)
- Dịch vụ nền thực hiện quét định kỳ mỗi giờ (`DEFAULT_CLEANUP_INTERVAL_SEC = 3600.0`) trong worker loop hoặc chạy thủ công bằng lệnh CLI:
  ```bash
  python -m app.scripts.cleanup [--dry-run]
  ```
- **Nguyên tắc an toàn:**
  - Bỏ qua các cuộc họp đang có tiến trình xử lý active (`queued`, `running`, `retry_scheduled`) để tránh làm gián đoạn job đang thực thi.
  - Cờ `--dry-run` cho phép kiểm tra số lượng tài nguyên sẽ bị ảnh hưởng mà không thực hiện bất kỳ thao tác xóa tệp hay cập nhật DB nào.

### 4.2. Người dùng chủ động xóa cuộc họp (Erasure Service)
Khi người dùng gọi `DELETE /api/v1/meetings/{id}`:
1. Xác thực quyền sở hữu: Cuộc họp không thuộc về người dùng đang đăng nhập sẽ trả về HTTP 404 `MEETING_NOT_FOUND` (tuân thủ nguyên tắc PRIV-12 nhằm chống rò rỉ sự tồn tại của tài nguyên).
2. Chuyển trạng thái các tiến trình đang active liên quan sang `cancelled`.
3. Xóa hoàn toàn thư mục âm thanh `audio/{meeting_id}/` và toàn bộ thư mục `artifacts/{meeting_id}/` khỏi ổ đĩa.
4. Xóa toàn bộ các dòng liên quan trong bảng `idempotency_keys` của người dùng có chứa `meeting_id` trong `endpoint` hoặc `response_body` (tránh rò rỉ tiêu đề và đảm bảo replay cùng key sẽ tạo tài nguyên mới).
5. Xóa cuộc họp và kích hoạt cascade xóa các bản ghi liên quan trong DB (`segments`, `speakers`, `summaries`, `action_items`, `ai_outputs`, `edit_events`).
6. Dọn dẹp thư mục cha rỗng khi worker hoàn tất việc dừng job bị hủy.

---

## 5. Gửi dữ liệu ra bên thứ ba (External Services)

- **Nguyên tắc cốt lõi:** Hệ thống **tuyệt đối không gửi tệp âm thanh (audio)** ra bất kỳ dịch vụ bên thứ ba nào. Quá trình xử lý âm thanh (VAD, ASR, Diarization) hoàn toàn diễn ra on-premise (trong container nội bộ).
- **Dịch vụ LLM tóm tắt (Claude API):**
  - Chỉ gửi văn bản transcript dạng plain text sau khi đã gộp và gắn nhãn người nói.
  - Chỉ gửi khi người dùng đã xác nhận consent và hệ thống có cấu hình API key hợp lệ (`LLM_PROVIDER != disabled`).
  - Khi không có API key hoặc ở chế độ ngoại tuyến, tóm tắt ở trạng thái `disabled` và không có bất kỳ kết nối mạng nào ra ngoài (PRIV-16).
  - Tích hợp thông qua một adapter interface duy nhất có bản fake phục vụ môi trường kiểm thử cô lập.

---

## 6. Chính sách Nhật ký (Logging Policy)

Hệ thống tuân thủ nghiêm ngặt các quy tắc an toàn nhật ký (PRIV-10, PRIV-11):
- **Những trường được phép ghi log:** `event`, `job_id`, `meeting_id`, `request_id`, `worker_id`, `stage`, `attempt`, `error_code`, `duration_sec`, `status`, `http_status`.
- **Nghiêm cấm ghi log:**
  - Tuyệt đối không ghi nội dung âm thanh, transcript lời thoại, bản tóm tắt hoặc mô tả nhiệm vụ.
  - Tuyệt đối không ghi tiêu đề cuộc họp hoặc tên tệp âm thanh tải lên của người dùng.
  - Tuyệt đối không ghi thông tin nhạy cảm: token JWT, API key, mật khẩu, header `Authorization`, cookie.
  - Tuyệt đối không ghi đường dẫn tuyệt đối của hệ điều hành vào thông báo lỗi trả về cho client.
- Khi xảy ra lỗi hoặc exception ngoài dự kiến: hệ thống chỉ ghi lại loại lỗi (`error_type`) và vị trí mã nguồn, không in message chi tiết có thể chứa dữ liệu người dùng.
