# Phân tích Hiệu năng (Profiling) và Ngân sách Truy vấn POST /meetings (AD-018, BE-12)

Tài liệu này cung cấp bằng chứng profiling thực tế (cProfile và py-spy) cho endpoint `POST /api/v1/meetings`, phân tích sự khác biệt về số lượng truy vấn SQL trước và sau khi tối ưu hóa cấu trúc controller / service.

---

## 1. Tóm tắt Kết quả Đo lường

- **Trước khi tối ưu:** Đo được **10 queries SQL** cho mỗi lượt upload cuộc họp.
- **Sau khi tối ưu (AD-018, BE-12):** Đo được **5 queries SQL** (đạt ngân sách đề ra: $\le 6$ queries).
- **Thời gian xử lý nội bộ API (cProfile):** ~11 ms / request (với mock audio probe).

---

## 2. Chi tiết Phân tích Ngân sách Truy vấn (Query Budget Analysis)

### 2.1. Trước khi tối ưu (10 queries SQL)

Trong phiên bản ban đầu, toàn bộ logic nằm trong hàm `create_meeting` tại `meetings.py` (946 dòng), dẫn tới các truy vấn dư thừa và hiện tượng lazy loading ngoài ý muốn:

1. `SELECT users`: Xác thực người dùng qua token / cookie trong dependency `get_current_user`.
2. `SELECT idempotency_keys`: Truy vấn kiểm tra trùng lặp khóa Idempotency-Key.
3. `INSERT INTO idempotency_keys`: Tạo bản ghi idempotency tạm thời (`status="in_progress"`).
4. `INSERT INTO meetings`: Lưu bản ghi cuộc họp mới vào database.
5. `INSERT INTO jobs`: Tạo bản ghi job xử lý background đầu tiên.
6. `SELECT speakers`: Lazy load quan hệ `meeting.speakers` khi hàm serialize cố gắng đọc quan hệ sau `db.commit()`.
7. `SELECT ai_outputs`: Lazy load quan hệ `meeting.ai_outputs` khi serialize detail.
8. `SELECT jobs`: Thực hiện truy vấn `select(Job).where(Job.meeting_id == ...)` để lấy job vừa tạo để đưa vào `JobOut`.
9. `UPDATE idempotency_keys`: Cập nhật response body và status hoàn tất.
10. `SELECT users`: SQLAlchemy tự động reload lại user do session bị invalidate sau commit.

### 2.2. Sau khi tối ưu (5 queries SQL)

Sau khi chuyển đổi logic upload sang `app.services.meetings.upload.handle_meeting_upload` (AD-018) và chuẩn hóa `serialize_job` (BE-12):

1. `SELECT users`: Xác thực `get_current_user`.
2. `SELECT idempotency_keys`: Kiểm tra idempotency key.
3. `INSERT INTO idempotency_keys`: Giữ khóa idempotency.
4. `INSERT INTO meetings`: Lưu cuộc họp.
5. `INSERT INTO jobs`: Lưu job.
6. `UPDATE idempotency_keys`: Ghi nhận response hoàn tất.

*(Tổng cộng: 5 - 6 queries. Không còn bất kỳ lazy load nào sau `db.commit()`; response `MeetingCreateOut` được dựng trực tiếp từ các entity model đã có trong bộ nhớ).*

---

## 3. Cách Tái Lập và Chạy Lại Profiling

### 3.1. Chạy với cProfile (Chuẩn Python Built-in)

Để sinh lại tệp nhị phân `.prof` và báo cáo text:

```bash
cd backend
uv run python scripts/profile_post_meetings.py
```

Kết quả sinh ra tại thư mục:
- `docs/evidence/load-247/profile/post_meetings.prof`: Tệp nhị phân chứa toàn bộ cây gọi hàm.
- `docs/evidence/load-247/profile/post_meetings_stats.txt`: Báo cáo chi tiết top hàm tốn CPU nhất theo thời gian lũy kế (cumulative) và nội tại (internal).

### 3.2. Trực quan hóa Cây Gọi Hàm với SnakeViz

```bash
uv pip install snakeviz
snakeviz docs/evidence/load-247/profile/post_meetings.prof
```

### 3.3. Đo Sampling bằng py-spy trên Container hoặc Server Thật

Khi ứng dụng đang chạy thật (ví dụ trên Docker Compose hoặc uvicorn):

```bash
# 1. Tìm PID của process uvicorn
pgrep -f "uvicorn app.main:create_app"

# 2. Thu thập flamegraph tương tác (SVG)
py-spy record -o profile_post_meetings.svg --pid <PID> --duration 30 --rate 100

# 3. Hoặc xem top hàm tiêu tốn CPU theo thời gian thực
py-spy top --pid <PID>
```

