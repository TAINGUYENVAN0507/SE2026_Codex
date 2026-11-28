# 2026-11-28 · Member C: giới hạn dẫn chứng ở pipeline, chạy lại khi không còn audio, 247 client 2/4 process, 40 client (Đợt 18, sau hạn nộp)

- **Người làm:** C (`@TAINGUYENVAN0507`), nhánh `tainguyen`.
- **Số commit:** 5.
- **Điều kiện bắt đầu:**
  - C review #83 (A) và #84 (B); CI xanh 12/12 và 19/19.
  - C gộp hai PR với `main` rồi chạy lại trên Linux trước khi merge:
    - Backend trên PostgreSQL 16 nghe IPv4 và IPv6: 575 passed, 0 skipped, 0 xfailed, 1 warning.
    - Frontend: lint, format, typecheck, 364 passed, build, `gen:api` không drift.
    - E2E trên API thật: `missing-audio` 1, `upload` 2, `retention` 1, `evidence-seek` 1, `summary-edit` 1, đều đạt. Không có `backend/appdata` trong worktree sạch, không còn thư mục `se-e2e-storage-*`.
  - Merge `af2dc6a` (#84) rồi `03f16fb` (#83). `main` sau merge giống hệt bản đã chạy (diff 0 dòng).
- **Phạm vi:** sau hạn nộp 11-14. Sửa lỗi trong pipeline (phần của C), test, công cụ đo, bằng chứng. Không đổi code backend và frontend.

| # | Việc | Message | Hash |
|---|---|---|---|
| 1 | [x] Hậu kiểm tóm tắt giữ tối đa 50 evidence mỗi ý chính và quyết định, theo thứ tự transcript; phần bỏ đếm trong warning `SUMMARY_EVIDENCE_DROPPED`. 3 ca test mới, 2 ca đỏ trước sửa (ca biên đúng 50 xanh sẵn) | `fix(pipeline): a key point or decision keeps at most 50 evidence segments, so a new AI summary can still be edited (AI-09, BE-05)` | `036194a` |
| 2 | [x] Test PostgreSQL: chạy lại từ `asr` khi audio hết hạn hoặc mất (2 ca `xfail` strict), tóm tắt AI có 51 dẫn chứng không lưu được (`xfail` strict), tạo lại tóm tắt khi audio hết hạn vẫn chạy (ca bảo vệ). Giao B | `test(backend): a rerun without audio hides the transcript and a stored AI summary over 50 evidence ids cannot be saved on PostgreSQL, marked for B; summary rerun after expiry stays allowed (BE-10, BE-16, BE-05)` | `9edaf3b` |
| 3 | [x] 247 client, 2 và 4 process xen kẽ cùng tổng 80 request cùng lúc, 8 lượt; 40 client có tìm kiếm, 6 lượt | `test(backend): 247 clients on 2 and 4 API processes interleaved with the same connection budget, and 40 clients with search, on main after #83 and #84 (AD-018, VT-018)` | `253501e` |
| 4 | [x] Bản đồ bằng chứng, ROADMAP (kết quả Đợt 17, Đợt 18), thời gian phản hồi PR tới #84; giao việc 11-28 | `docs(evidence): evidence map, PR response times and roadmap after #83 and #84; assign 2026-11-28 (RE-018, AD-018, VT-018)` | `466786f` |
| 5 | [x] Tick, hash | `docs(tasks): record 2026-11-28 member C results (G0)` | commit này |

## Kết quả và điều còn mở

- **Review #83:** không có điểm chặn. P3: player và spec còn nhận `NOT_FOUND`; kiểm storage nằm trong `afterAll`.
- **Review #84:** merge, kèm hai lỗi P2:
  - Giới hạn 50 dẫn chứng chặn cả tóm tắt do AI sinh. **Lỗi của C:** việc giao ngày 11-27 đặt giới hạn mà không kiểm đầu ra của pipeline.
  - Chạy lại không còn audio làm transcript không đọc được (có từ trước #84).
  - P3: `error_message` không khớp mã; mất `description` trong OpenAPI. PR có 6 commit, việc giao là 5.
- **Review chéo:** A chưa review #84 và B chưa review #83. C merge #84 khi hạn 18 giờ của A còn khoảng 8 phút. #83 được review sau 18,7 giờ, quá mốc 18 giờ.
- **247 client:**

  | Cấu hình | p95 upload | Đạt mốc 2,0 s |
  |---|---|---|
  | 2 process, `API_MAX_INFLIGHT=40` | 1,57 đến 1,91 s | 4/4 |
  | 4 process, `API_MAX_INFLIGHT=20` | 1,18 đến 1,43 s | 4/4 |

  - 4 process nhanh hơn ở cả 4 cặp, trung bình 0,46 s.
  - 2 process đạt hôm nay (load trước khi đo 2,5), không đạt hôm qua (load 8,8).
- **40 client:** 6/6 đạt (0,62 đến 0,73 s). Gộp 13 ngày: 98/100.
- **Phản hồi PR:** 21/53 PR có phản hồi của người khác; 15/21 trong 18 giờ, 16/21 trong 20 giờ.
- **Backend (PostgreSQL 16, nhánh `tainguyen` sau 4 commit):**
  - **576 passed, 0 skipped, 3 xfailed, 1 warning.** 3 xfailed là các ca giao B.
  - Chạy với `backend/appdata` tạm cất đi rồi trả lại.
  - Ruff sạch.
- **Pipeline:**
  - `-m "not model"`: 333 passed, 18 deselected.
  - `tests/model`: 5 passed, **2 failed** vì GPU của máy đo (GTX 1650 Ti, 4 GB) hết bộ nhớ ở bước ASR. Thay đổi hôm nay chỉ ở bước tóm tắt.
- **Còn mở:**
  - Hai lượt 40 client trên 1,5 s (11-12, 11-26) chưa rõ nguyên nhân.
  - 247 client ở 2 process phụ thuộc tải của máy; `API_WORKERS: 1` mặc định không đạt.
  - Thư mục WAV cũ của harness trong `backend/appdata` trên máy đo. C chưa xóa vì chưa được đồng ý.
