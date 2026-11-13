# Bằng chứng Xóa Dữ liệu Cá nhân và Ranh giới Lưu trữ (AD-018)

Tài liệu này ghi nhận bằng chứng kiểm chứng việc xóa dữ liệu cá nhân trên toàn bộ các thành phần hệ thống (cơ sở dữ liệu PostgreSQL, hệ thống tệp lưu trữ, dữ liệu vận hành và nhật ký log) theo yêu cầu của **AD-018** (Đợt 7, 2026-11-12).

---

## 1. Bản đồ Nơi lưu trữ và Kiểm thử Xóa Dữ liệu (Deletion Verification Matrix)

Bảng dưới đây thống kê mọi vị trí lưu trữ dữ liệu trong hệ thống, chính sách bảo vệ/xóa, và test case tương ứng khẳng định dữ liệu bị xóa sạch:

| Nơi lưu trữ | Loại dữ liệu | Khi xóa cuộc họp (`DELETE /meetings/{id}`) | Khi xóa tài khoản (`DELETE /auth/me`) | Khi quá hạn retention (14d/28d) | Test kiểm chứng |
|---|---|---|---|---|---|
| **PostgreSQL: `meetings`** | Bản ghi thông tin cuộc họp (title, metadata) | Bị xóa hoàn toàn khỏi DB | Bị xóa hoàn toàn khỏi DB (cascade) | Giữ nguyên (chỉ set `audio_path=None`) | `tests/api/test_delete_meeting.py`<br>`tests/api/test_delete_user.py`<br>`tests/privacy/test_privacy_canary.py` |
| **PostgreSQL: `jobs`** | Tiến trình xử lý (status, timing, metrics) | Hủy job active (`cancelled`), xóa bản ghi khỏi DB | Hủy job active, xóa bản ghi khỏi DB | Giữ nguyên | `tests/api/test_delete_meeting.py`<br>`tests/api/test_delete_user.py` |
| **PostgreSQL: `speakers`, `segments`** | Phân đoạn người nói và văn bản transcript | Bị xóa hoàn toàn khỏi DB (cascade) | Bị xóa hoàn toàn khỏi DB (cascade) | **Giữ nguyên vẹn** (PRIV-14: transcript giữ tới khi người dùng chủ động xóa) | `tests/api/test_delete_meeting.py`<br>`tests/api/test_delete_user.py`<br>`tests/api/test_retention.py` |
| **PostgreSQL: `summaries`, `action_items`** | Tóm tắt cuộc họp và danh sách công việc | Bị xóa hoàn toàn khỏi DB (cascade) | Bị xóa hoàn toàn khỏi DB (cascade) | **Giữ nguyên vẹn** (PRIV-14) | `tests/api/test_delete_meeting.py`<br>`tests/api/test_delete_user.py`<br>`tests/api/test_retention.py` |
| **PostgreSQL: `edit_events`** | Lịch sử chỉnh sửa transcript/summary | Bị xóa (trigger DB cho phép xóa khi meeting cha bị xóa) | Bị xóa hoàn toàn khỏi DB (cascade) | Giữ nguyên | `tests/api/test_delete_meeting.py`<br>`tests/api/test_delete_user.py` |
| **PostgreSQL: `ai_outputs`** | Dữ liệu đầu ra thô của các stage pipeline | Bị xóa hoàn toàn khỏi DB (cascade) | Bị xóa hoàn toàn khỏi DB (cascade) | Giữ nguyên | `tests/api/test_delete_meeting.py`<br>`tests/api/test_delete_user.py` |
| **PostgreSQL: `idempotency_keys`** | Khóa giao dịch idempotency của client | Bị xóa các dòng liên quan tới `meeting_id` (tránh rò rỉ response cache) | Bị xóa toàn bộ các dòng thuộc về user | Quá hạn 28 ngày (`OPERATIONAL_RETENTION_DAYS`) bị xóa sạch | `tests/api/test_delete_meeting.py`<br>`tests/api/test_delete_user.py`<br>`tests/privacy/test_privacy_canary.py`<br>`tests/api/test_retention.py` |
| **Tệp âm thanh trên đĩa (`audio/{id}/*`)** | Tệp âm thanh gốc cuộc họp | Bị xóa hoàn toàn khỏi ổ đĩa (`LocalStorage.delete_meeting_files`) | Bị xóa toàn bộ tệp audio của mọi meeting thuộc user | Quá hạn 14 ngày (`AUDIO_RETENTION_DAYS`) bị xóa sạch | `tests/api/test_delete_meeting.py`<br>`tests/api/test_delete_user.py`<br>`tests/privacy/test_privacy_canary.py`<br>`tests/api/test_retention.py` |
| **Tệp Artifacts trên đĩa (`artifacts/{id}/*`)** | Bản kết quả trung gian / transcript JSON của job | Bị xóa hoàn toàn khỏi ổ đĩa | Bị xóa toàn bộ artifacts thuộc user | Quá hạn 14 ngày bị xóa sạch cùng audio | `tests/api/test_delete_meeting.py`<br>`tests/api/test_delete_user.py`<br>`tests/privacy/test_privacy_canary.py`<br>`tests/api/test_retention.py` |
| **Log hệ thống (Console / Container JSON log)** | Nhật ký ghi nhận sự kiện hệ thống | **Ngăn chặn từ đầu:** Log chỉ ghi các ID kỹ thuật (`job_id`, `meeting_id`, `request_id`, `stage`, `error_code`, `status`), tuyệt đối không ghi tiêu đề, tên file, nội dung transcript hay dữ liệu cá nhân (được kiểm chứng qua chuỗi Canary bí mật). Log container xoay vòng theo kích thước (10MB x 3 file). | Như bên | Như bên | `tests/privacy/test_privacy_canary.py` (`test_canary_logs_never_contain_sensitive_content`) |

---

## 2. Kiểm thử Chuỗi Canary Bí mật (Privacy Canary)

Nhằm đảm bảo không có bất kỳ dữ liệu nhạy cảm nào lọt vào nhật ký hệ thống hay còn sót lại sau khi xóa, bộ test canary sử dụng các chuỗi nhận diện độc nhất:
- `CANARY_TITLE = "CANARY_TITLE_TOP_SECRET_CODENAME_X99"`
- `CANARY_IDEMPOTENCY = "IDEM_CANARY_TRANSACTION_KEY_A88"`
- `CANARY_TRANSCRIPT_EDIT = "CANARY_TRANSCRIPT_CONFIDENTIAL_CONVERSATION_B77"`
- `CANARY_SUMMARY_EDIT = "CANARY_SUMMARY_HIGHLY_SENSITIVE_DECISION_C66"`
- `CANARY_SPEAKER_NAME = "CANARY_SPEAKER_AGENT_UNDERCOVER_D55"`

Kiểm thử `tests/privacy/test_privacy_canary.py` thực hiện:
1. Đưa các chuỗi canary qua toàn bộ luồng hoạt động: upload, xử lý pipeline, chỉnh sửa transcript, speaker, tóm tắt.
2. Kiểm tra log của API và Worker: khẳng định 100% không chứa bất kỳ chuỗi canary nào.
3. Thực thi xóa cuộc họp / xóa tài khoản:
   - Quét qua toàn bộ các bảng trong `Base.metadata` của cơ sở dữ liệu: 0 bản ghi chứa canary.
   - Quét qua toàn bộ cây thư mục lưu trữ (`appdata/`): 0 tệp chứa canary.
   - Quét qua bảng `idempotency_keys`: 0 bản ghi chứa canary.

Log thực thi kiểm thử trên môi trường PostgreSQL 16 được ghi lại chi tiết tại [`deletion-2026-11-12.log`](./deletion-2026-11-12.log).

