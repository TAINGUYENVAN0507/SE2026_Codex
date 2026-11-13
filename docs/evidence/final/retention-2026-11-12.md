# Bằng chứng Kiểm chứng Ranh giới Lưu trữ (Retention Boundaries) trên PostgreSQL (RE-018, AD-018)

- **Ngày thực hiện:** 2026-11-12 (Đợt 7, đóng băng code)
- **Thành viên thực hiện:** Member B (`@minhquangha`), nhánh `haquang`
- **Mục tiêu:** Đo lường và kiểm chứng thực tế chính sách lưu trữ 14 ngày cho file audio/artifacts (`AUDIO_RETENTION_DAYS=14`) và 28 ngày cho dữ liệu vận hành (`OPERATIONAL_RETENTION_DAYS=28`) trên cơ sở dữ liệu PostgreSQL 16 thật với dữ liệu tổng hợp tại các mốc biên 13, 14, 15 ngày (cho cuộc họp) và 27, 28, 29 ngày (cho idempotency keys).

---

## 1. Kịch bản Kiểm chứng và Dữ liệu Tổng hợp

- **Mốc thời gian quy chiếu (NOW):** `2026-11-12T12:00:00+00:00`
- **Môi trường:** PostgreSQL 16 (`meeting_assistant_db`), local storage engine
- **Dữ liệu tổng hợp khởi tạo:**
  1. **Cuộc họp tuổi 13 ngày:** `retention_until = NOW + 1 ngày` (chưa đến hạn lưu trữ).
  2. **Cuộc họp tuổi 14 ngày:** `retention_until = NOW` (tại đúng thời điểm biên lưu trữ).
  3. **Cuộc họp tuổi 15 ngày:** `retention_until = NOW - 1 ngày` (đã quá hạn lưu trữ 1 ngày).
  - Mỗi cuộc họp đều có: tệp âm thanh gốc `.wav`, tệp artifact `transcript.json`, phân đoạn người nói (`speakers`, `segments`) và bản tóm tắt (`summaries`) trong DB.
  4. **IdempotencyKey tuổi 27 ngày:** `created_at = NOW - 27 ngày` (chưa quá hạn 28 ngày).
  5. **IdempotencyKey tuổi 28 ngày:** `created_at = NOW - 28 ngày` (tại đúng thời điểm biên 28 ngày).
  6. **IdempotencyKey tuổi 29 ngày:** `created_at = NOW - 29 ngày` (đã quá hạn 28 ngày).

---

## 2. Lệnh Thực thi Kiểm chứng

Sử dụng script kiểm chứng độc lập kết nối trực tiếp PostgreSQL 16:

```bash
cd backend
uv run python scripts/verify_retention_postgres.py
```

Log thực thi từ script:
```text
Connecting to Postgres at: postgresql://postgres:postgrespassword@localhost:5432/meeting_assistant
Test reference time (NOW): 2026-11-12T12:00:00+00:00
Đã khởi tạo thành công dữ liệu tổng hợp trên PostgreSQL:
  - Meeting 13d (retention_until = NOW + 1d)
  - Meeting 14d (retention_until = NOW)
  - Meeting 15d (retention_until = NOW - 1d)
  - IdempotencyKey 27d (created_at = NOW - 27d)
  - IdempotencyKey 28d (created_at = NOW - 28d)
  - IdempotencyKey 29d (created_at = NOW - 29d)

--- BẮT ĐẦU CHẠY RETENTION CLEANUP ---
Cleanup Result: audio_expired_meetings=1, operational_keys_cleaned=1

--- KẾT QUẢ KIỂM CHỨNG CHI TIẾT ---
Meeting 13 ngày (chưa hết hạn 14 ngày):
  - audio_path trong DB: audio/90d4546d-69df-4b43-a620-c4e65623960b/original.wav (KỲ VỌNG: còn nguyên)
  - File audio trên đĩa: True (KỲ VỌNG: True)
  - Artifacts trên đĩa: True (KỲ VỌNG: True)
  - Transcript trong DB: True (KỲ VỌNG: True)
Meeting 14 ngày (tại mốc biên retention_until == NOW):
  - audio_path trong DB: audio/291005da-431a-42e1-a368-749c1940607d/original.wav (KỲ VỌNG: còn nguyên - theo quy tắc đúng mốc chưa xóa)
  - File audio trên đĩa: True (KỲ VỌNG: True)
  - Artifacts trên đĩa: True (KỲ VỌNG: True)
  - Transcript trong DB: True (KỲ VỌNG: True)
Meeting 15 ngày (quá hạn 14 ngày):
  - audio_path trong DB: None (KỲ VỌNG: None)
  - File audio trên đĩa: False (KỲ VỌNG: False - ĐÃ XÓA)
  - Artifacts trên đĩa: False (KỲ VỌNG: False - ĐÃ XÓA)
  - Transcript trong DB: True (KỲ VỌNG: True - VẪN GIỮ NGUYÊN)
  - Summary trong DB: True (KỲ VỌNG: True - VẪN GIỮ NGUYÊN)
Dữ liệu vận hành (IdempotencyKey):
  - Key 27 ngày (chưa hết hạn 28 ngày): Tồn tại = True (KỲ VỌNG: True)
  - Key 28 ngày (tại mốc biên 28 ngày): Tồn tại = True (KỲ VỌNG: True)
  - Key 29 ngày (quá hạn 28 ngày): Tồn tại = False (KỲ VỌNG: False - ĐÃ XÓA)

✓ TOÀN BỘ CÁC BIÊN RETENTION ĐÃ ĐƯỢC XÁC THỰC HOÀN TOÀN CHÍNH XÁC VỚI TÀI LIỆU VÀ POSTGRESQL!
```

---

## 3. Bảng Tổng hợp Kết quả Kiểm chứng Biên Retention

| Đối tượng | Tuổi dữ liệu | retention_until / created_at | Trạng thái sau cleanup | Tệp trên đĩa | Bản ghi DB | Kết luận |
|---|---|---|---|---|---|---|
| **Meeting 13 ngày** | 13 ngày | `NOW + 1d` | Còn nguyên vẹn | Tệp audio và artifacts còn nguyên | `audio_path` còn nguyên, transcript/summary còn | **Đạt** (chưa đến hạn) |
| **Meeting 14 ngày** | 14 ngày | `NOW` | Còn nguyên vẹn | Tệp audio và artifacts còn nguyên | `audio_path` còn nguyên, transcript/summary còn | **Đạt** (quy tắc biên: đúng mốc chưa xóa) |
| **Meeting 15 ngày** | 15 ngày | `NOW - 1d` | **Audio & Artifact bị xóa** | **ĐÃ XÓA SẠCH** khỏi ổ đĩa | `audio_path` chuyển thành `None`, **transcript & summary vẫn giữ nguyên vẹn** | **Đạt** (chuẩn PRIV-14) |
| **IdempotencyKey 27d** | 27 ngày | `NOW - 27d` | Còn nguyên vẹn | N/A | Khóa còn nguyên trong DB | **Đạt** (chưa đến hạn 28 ngày) |
| **IdempotencyKey 28d** | 28 ngày | `NOW - 28d` | Còn nguyên vẹn | N/A | Khóa còn nguyên trong DB | **Đạt** (quy tắc biên: `created_at < cutoff`) |
| **IdempotencyKey 29d** | 29 ngày | `NOW - 29d` | **ĐÃ BỊ XÓA** | N/A | **Bị xóa hoàn toàn** khỏi DB | **Đạt** (quá hạn 28 ngày) |

---

## 4. Kết luận

1. **Chính sách 14 ngày (`AUDIO_RETENTION_DAYS`):** Hoạt động hoàn toàn chính xác. Khi quá hạn 14 ngày, chỉ có dữ liệu âm thanh gốc và artifacts tạm thời bị xóa; văn bản transcript và tóm tắt cuộc họp được bảo toàn nguyên vẹn trong DB cho người dùng tra cứu.
2. **Chính sách 28 ngày (`OPERATIONAL_RETENTION_DAYS`):** Dọn dẹp triệt để các khóa idempotency cũ hơn 28 ngày, giải phóng dung lượng DB và bảo vệ dữ liệu vận hành.
3. **Quy tắc biên:** Điều kiện lọc `< current_time` đảm bảo dữ liệu không bị xóa non trước hạn hoặc đúng hạn. Không phát hiện bất kỳ lỗi lệch biên nào so với tài liệu.
