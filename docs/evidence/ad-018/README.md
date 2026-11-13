# Bằng chứng xóa dữ liệu cá nhân (AD-018)

B lập ngày 2026-11-12 (#54). C sửa ngày 2026-11-13 sau khi review: bản đầu ghi log là "trên PostgreSQL 16" và ghi mọi nơi lưu đều có test, nhưng hai điều đó không đúng.

## Test chạy trên DB nào

| Test | DB | Ghi chú |
|---|---|---|
| `backend/tests/api/test_delete_meeting.py` | SQLite in-memory, cứng trong fixture | Trigger `edit_events` được **viết lại bằng SQL của SQLite** trong fixture, không lấy từ migration |
| `backend/tests/api/test_delete_user.py` | SQLite in-memory | Không có dòng `jobs`, `ai_outputs`, `edit_events` |
| `backend/tests/privacy/test_privacy_canary.py` | SQLite in-memory | Chạy worker với fake pipeline nên có `jobs`, `ai_outputs`; sửa transcript qua API nên có `edit_events`. Chỉ quét chuỗi canary, không đếm dòng |
| `backend/tests/integration/test_erasure_postgres.py` (C, 11-13) | **Postgres đã migrate bằng Alembic** | Mọi bảng con của meeting đều có 1 dòng; đếm dòng trước và sau; trigger và FK cascade là của migration |

`DATABASE_URL` không đổi được DB của ba test đầu. Log [`deletion-2026-11-12.log`](deletion-2026-11-12.log) của B (15 passed, Windows) vì vậy là log chạy trên SQLite dù máy có Postgres. Bản gốc là UTF-16 nên GitHub hiện là file nhị phân; C đổi sang UTF-8, nội dung giữ nguyên. Log của test Postgres: [`erasure-postgres-2026-11-13.log`](erasure-postgres-2026-11-13.log).

## Nơi lưu → test kiểm nó bị xóa

"SQLite" và "Postgres" là DB của test có assert. "Chưa có test" là không tìm thấy assert nào.

| Nơi lưu | Xóa cuộc họp | Xóa tài khoản | Hết hạn lưu trữ |
|---|---|---|---|
| `meetings` | SQLite: `test_delete_meeting_success`; Postgres: `test_delete_meeting_on_migrated_postgres` | SQLite: `test_delete_me_canary_erased_from_all_stores_and_other_user_intact`; Postgres: `test_delete_account_on_migrated_postgres` | Không xóa, chỉ `audio_path = NULL`: `test_retention_boundary_condition` (SQLite), `scripts/verify_retention_postgres.py` (Postgres, chạy tay) |
| `jobs` | SQLite: `test_delete_meeting_success`, `test_rt15_delete_meeting_cancels_running_job`; Postgres | Chỉ Postgres | Không áp dụng |
| `speakers`, `segments` | SQLite: `test_delete_meeting_success`, canary; Postgres | SQLite: canary; Postgres | Không xóa (PRIV-14): `test_priv14_expired_audio_returns_410_transcript_kept` |
| `summaries`, `action_items` | SQLite: `test_delete_meeting_success`, canary; Postgres | SQLite: canary; Postgres | Không xóa (PRIV-14) |
| `ai_outputs` | **Chỉ Postgres** (test SQLite không có dòng nào hoặc không đếm dòng) | **Chỉ Postgres** | Không áp dụng |
| `edit_events` | SQLite (trigger viết lại): `test_delete_meeting_success`; Postgres (trigger của migration) | **Chỉ Postgres** (luồng xóa tài khoản trên SQLite không tạo `edit_events`) | Không áp dụng |
| `idempotency_keys` | SQLite: `test_erasure_removes_canary_from_all_stores_and_logs`, `test_erasure_replay_idempotency_key_creates_new_meeting`; Postgres | SQLite: canary; Postgres | 28 ngày: `test_retention_cleans_expired_idempotency_keys` |
| `users` | Không áp dụng | SQLite: `test_delete_me_canary_erased_from_all_stores_and_other_user_intact`; Postgres | Không áp dụng |
| File audio `audio/<meeting_id>/` | SQLite: `test_delete_meeting_success`, canary; Postgres | SQLite: canary; Postgres | 14 ngày: `test_retention_boundary_condition` |
| Artifact `artifacts/<meeting_id>/` | Như audio | Như audio | 14 ngày: `test_retention_boundary_condition` |
| Log Python của process API (`caplog`) | Canary không có trong log: `test_erasure_removes_canary_from_all_stores_and_logs`, Postgres | `test_delete_me_canary_erased_from_all_stores_and_other_user_intact`, Postgres | Không áp dụng |
| Log của worker và pipeline | `test_privacy_canary_worker_internal_failure_does_not_log_error_data`; `pipeline/tests/unit/test_privacy_canary.py` | Như bên trái | Không áp dụng |
| Log đã ghi ra file hoặc của Docker (`json-file`, `max-size: 10m`) | **Chưa có test.** Thiết kế là không ghi dữ liệu cá nhân vào log, nên không có gì cần xóa; điều này chỉ được kiểm qua `caplog` ở trên, chưa kiểm trên log thật của container | Như bên trái | Docker xoay vòng theo kích thước, không theo 28 ngày. **Chưa có test** |
| Log access của uvicorn | **Chưa có test.** Ghi đường dẫn có `meeting_id` (UUID, không phải dữ liệu cá nhân) | Như bên trái | Như trên |

## Đo test Postgres có bắt được lỗi

C làm hỏng tạm `backend/app/services/erasure/service.py`, chạy hai test Postgres, rồi trả lại (không commit):

| Mutant | Kết quả | Ý nghĩa |
|---|---|---|
| Bỏ lệnh xóa `idempotency_keys` của meeting | **Đỏ** ở `test_delete_meeting_on_migrated_postgres` (canary còn trong `idempotency_keys.response_body`); `test_delete_account_on_migrated_postgres` vẫn xanh vì `erase_user` xóa mọi key của người dùng ở bước sau | Test bắt được |
| Bỏ lệnh `delete(EditEvent)` sau `db.delete(meeting)` | Xanh | Tương đương: trên Postgres FK `ON DELETE CASCADE` đã xóa `edit_events`, và trigger cho phép vì meeting cha đã mất. Lệnh xóa tường minh là thừa trên Postgres, không phải lỗi |

## Privacy canary

`backend/tests/privacy/test_privacy_canary.py` đưa 5 chuỗi canary (tiêu đề, idempotency key, sửa transcript, sửa tóm tắt, tên người nói) qua upload, worker fake, sửa transcript, sửa tóm tắt, đổi tên người nói; rồi xóa cuộc họp hoặc tài khoản, quét mọi bảng trong `Base.metadata` và cây storage. Test chạy trên SQLite.

## Giới hạn

- Dữ liệu tổng hợp. Không có backup DB, nên "xóa khỏi mọi nơi lưu" không tính backup.
- Test Postgres chạy ở CI (CI có Postgres 16) và ở máy C (Postgres 16 cục bộ).
