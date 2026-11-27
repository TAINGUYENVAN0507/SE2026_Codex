# 2026-11-27 · Member B: danh sách dẫn chứng không giới hạn làm PostgreSQL lỗi, mã lỗi audio mất file và hết hạn, 7 warning còn lại (Đợt 17, sau hạn nộp)

- **Người làm:** B (`@minhquangha`), nhánh `haquang`.
- **Số commit:** 5, **đúng 5**.
- **Điều kiện bắt đầu:** #80 (A) và #81 (B) đã vào `main` (`4259a4f`, `6c84724`). C gộp hai PR với `main` rồi chạy trên PostgreSQL 16 nghe IPv4 và IPv6:
  - **568 passed, 0 skipped, 0 xfailed, 7 warning** (trước là 28).
  - E2E `summary-edit.spec.ts` và `evidence-seek.spec.ts` trên API thật: mỗi spec 1 passed.
- **Review #81 (C):** 4 việc đúng, đúng 5 commit. Ba ghi chú P3; hai ghi chú thành việc 2 và việc 3 hôm nay. A không review #81, và B không review #80.
- **Phạm vi:** sau hạn nộp 11-14. Chỉ sửa lỗi, thêm test và bằng chứng; không thêm tính năng.
- **Hạn:** mở PR trong ngày 11-27. Không phụ thuộc PR của A.

## Bước 0
```bash
git checkout haquang && git fetch origin && git merge origin/main
```

Log ghi **UTF-8**: `uv run pytest ... 2>&1 | Out-File -Encoding utf8 <file>`.

## Việc

### 1. [x] `PUT /summary` với 70.000 id dẫn chứng trả 500 trên PostgreSQL (BE-05, FE-18)
- **Lỗi (C tìm ngày 11-27):** `SummaryPointUpdate.evidence_segment_ids` không giới hạn số phần tử hay độ dài mỗi id. `validate_evidence_segments` (`app/services/action_items.py`) đưa cả danh sách vào một `IN (...)`. PostgreSQL và psycopg chỉ nhận tối đa 65.535 tham số trong một câu lệnh.
  - 70.000 id: **500** `INTERNAL_SERVER_ERROR`.
  - 30.000 id: 4xx (cả test, tính cả bước chuẩn bị, mất 2,7 s; C chưa đo riêng request).
  - Id dài 10.000 ký tự: 422 đúng.
  - Id lặp: được nhận và lưu nguyên cả bản lặp.
- **Test:** `backend/tests/integration/test_field_limits_postgres.py`:
  - `test_put_summary_with_70000_evidence_ids_answers_4xx` đánh `xfail(strict=True)`.
  - `test_put_summary_with_a_repeated_evidence_id` ghi lại hành vi hiện tại.
- **Sửa (chỉ áp cho đầu vào `SummaryPointUpdate`, không áp cho `SummaryPointOut`):**
  - Tối đa **50 id mỗi ý**, mỗi id tối đa 36 ký tự. Quá thì trả 422.
  - Id lặp trong cùng một ý chỉ lưu một lần, giữ thứ tự. Sửa `test_put_summary_with_a_repeated_evidence_id` theo hành vi mới.
  - Với 50 ý chính + 50 quyết định × 50 id = 5.000 id, `validate_evidence_segments` phải chạy dưới 65.535 tham số. Thêm một ca biên đúng 50 id mỗi ý và chạy thành công.
  - **Bỏ dấu xfail.**
- **Message:** `fix(backend): each summary point takes at most 50 distinct evidence ids so PostgreSQL never sees more than its parameter limit (BE-05, FE-18)`
- **Commit:** `1b1b186`

### 2. [x] Worker báo `AUDIO_INVALID` cả khi audio đã bị xóa vì hết hạn lưu (BE-10, BE-16; P3 của C trên #81)
- **Lỗi:** `app/worker/runner.py` (dòng 263 đến 266) báo `AUDIO_INVALID` mỗi khi `resolve_audio_file` trả `None` và job không bắt đầu từ `summarize`.
  - Khi `retention_until` đã qua, lý do thật là hết hạn. `GET /audio` khi đó trả `AUDIO_EXPIRED`.
- **Test đỏ trước:** cuộc họp có `retention_until` đã qua, audio đã xóa, enqueue job từ `asr`: job `failed` với `error_code = AUDIO_EXPIRED`. Audio mất mà hạn lưu chưa tới thì vẫn là `AUDIO_INVALID` hoặc mã của việc 3.
- **Message:** `fix(backend): the worker reports AUDIO_EXPIRED when retention already removed the audio (BE-10, BE-16)`
- **Commit:** `a37e3fd`

### 3. [x] `GET /audio` trả `NOT_FOUND` cho file mất, trùng mã với cuộc họp không tồn tại (BE-05, FE-19; P3 của C trên #81)
- **Lỗi:** `app/api/v1/audio.py` trả `404 NOT_FOUND` cả khi không có cuộc họp lẫn khi file audio đã mất, nên frontend không phân biệt được (#80 phải nhận cả hai mã).
- **Sửa:**
  - File mất (hoặc cuộc họp không có audio) thì trả 404 với mã riêng `AUDIO_NOT_FOUND`.
  - Thêm mã vào `contracts/error_codes.md`, `contracts/openapi.json` (nếu liệt kê) và `frontend/src/api/errors.ts` (câu tiếng Việt).
  - Cuộc họp không tồn tại hoặc của người khác vẫn trả như cũ.
- **Test:** ba trường hợp trên trả đúng mã. Test hợp đồng (`tests/contract`) vẫn xanh.
- **Message:** `fix(backend): a missing audio file answers 404 AUDIO_NOT_FOUND, distinct from a missing meeting (BE-05, FE-19)`
- **Commit:** `656513d`

### 4. [x] 7 warning còn lại khi chạy backend (BE-05)
- Sau #81 còn 7 warning:
  - 6 `DeprecationWarning: Setting per-request cookies=<...> is being deprecated` (TestClient);
  - 1 `StarletteDeprecationWarning: Using httpx with starlette.testclient is deprecated`.
- **Sửa:** đặt cookie trên client (`client.cookies.set(...)`, hoặc tạo `TestClient(app, cookies=...)`), không truyền theo từng request. Thêm `filterwarnings` để hai warning này thành lỗi.
- Nếu warning `httpx` không sửa được trong phạm vi test, ghi rõ lý do và giữ nó là warning duy nhất.
- Ghi số warning trước và sau (mục tiêu 0).
- **Message:** `test(backend): set TestClient cookies on the client and fail on the deprecated per-request form (BE-05)`
- **Commit:** `cd6da17`

### 5. [x] Tick, hash (G0)
- Ghi hash từng commit; hash của chính commit này ghi "commit này".
- Chạy cả backend **trên Postgres** nghe cả IPv4 và IPv6. Ghi số passed, **skipped 0, xfailed 0**, và số warning.
- Ruff check và format sạch.
- **Message:** `docs(tasks): record 2026-11-27 member B results (G0)`
- **Kết quả thực tế:** `ruff check .` sạch; `ruff format --check .` sạch (175 file). Backend trên PostgreSQL 16 qua `localhost:5432`: **572 passed, 3 skipped, 0 xfailed, 1 warning** trong 174,25 giây với `JWT_SECRET` thử nghiệm đủ dài. Ba test bị skip vì hai ca chỉ chạy trên Linux (`sched_setaffinity`, `/proc`) và một ca cần quyền tạo symlink trên Windows. Không ghi 0 skipped vì môi trường này không đáp ứng điều kiện.
- **Warning:** trước sửa, C ghi 7 warning (6 cookie theo request, 1 Starlette). Sau sửa không còn warning cookie. Warning còn lại do `fastapi.testclient` hiện dùng `starlette.testclient` với `httpx`; phiên bản Starlette này yêu cầu `httpx2` để bỏ warning, vượt phạm vi sửa test. Khi chạy với `JWT_SECRET` cục bộ 31 byte, PyJWT phát thêm 210 warning về khóa ngắn; lần đo trên dùng khóa thử nghiệm dài hơn 32 byte.
- **PostgreSQL:** container `db` đã khởi động và test tích hợp 4/4 ca evidence ID pass. Môi trường Windows chỉ dùng kết nối `localhost` trên IPv4; chưa xác minh listener IPv6.
- **Review PR A:** tại lúc kiểm tra, GitHub chưa có PR mở ngày 11-27 của A để review.
- **Commit:** commit này

## Việc chung (không tính commit)

- Review PR ngày 11-27 của A **trong 18 giờ** kể từ lúc A mở, comment trên GitHub. #80 hôm qua không có review của B.
- Trả lời từng điểm review (nếu có) trên PR, ghi commit sửa.
