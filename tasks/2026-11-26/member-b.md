# 2026-11-26 · Member B: chữ của từng ý trong tóm tắt, `available` khi file audio đã mất, một hàm tìm file audio dùng chung, mã 422 bị deprecated (Đợt 16, sau hạn nộp)

- **Người làm:** B (`@minhquangha`), nhánh `haquang`.
- **Số commit:** 5, **đúng 5**.
- **Điều kiện bắt đầu:** #77 (A) và #78 (B) đã vào `main` (`db8072b`, `3dd5ae0`). C gộp hai PR với `main` rồi chạy trên PostgreSQL 16:
  - 551 passed, 1 skipped, 0 xfailed.
  - Mở thêm `::1` rồi chạy lại `tests/unit/test_db_fixture.py` + `tests/integration`: 43 passed, 0 skipped.
- **Review #78 (C):** 5 việc đúng, đúng 5 commit. Hai ghi chú P3 thành việc 2 và việc 3 hôm nay. A chưa review #78.
- **Phạm vi:** sau hạn nộp 11-14. Chỉ sửa lỗi, thêm test và bằng chứng; không thêm tính năng.
- **Hạn:** mở PR trong ngày 11-26. Không phụ thuộc PR của A.

## Bước 0
```bash
git checkout haquang && git fetch origin && git merge origin/main
```

Log ghi **UTF-8**: `uv run pytest ... 2>&1 | Out-File -Encoding utf8 <file>`.

## Việc

### 1. [x] `PUT /summary` lưu ý chính và quyết định dài tùy ý hoặc rỗng (BE-05, FE-12)
- **Lỗi (C tìm ngày 11-26):** `SummaryPointOut.text` không có giới hạn, và API không giới hạn dung lượng body JSON.
- Trên PostgreSQL, `PUT /summary` trả **200** và lưu nguyên giá trị với:
  - ý chính hoặc quyết định dài 1001 ký tự;
  - ý chính rỗng;
  - quyết định chỉ có khoảng trắng;
  - tổng quan chỉ có khoảng trắng.
- **Test:** `backend/tests/integration/test_field_limits_postgres.py`, `test_put_summary_point_text_outside_1_to_1000_answers_422`. Có 5 ca, đều đánh `xfail(strict=True)`.
- **Sửa:**
  - Chữ của mỗi ý: **1 đến 1000 ký tự** sau khi bỏ khoảng trắng hai đầu. Tổng quan không được chỉ có khoảng trắng. Sai thì trả 422.
  - Frontend dùng cùng số 1000 (A, việc 1).
  - **Chỉ áp cho dữ liệu gửi lên.** `SummaryContentOut` dùng cho cả `SummaryUpdate` và `SummaryOut`. Nếu đặt `max_length` thẳng vào đó, tóm tắt đã lưu (hoặc do AI sinh) dài hơn sẽ làm `GET /summary` trả 500. Test `test_get_summary_still_answers_200_for_stored_points_longer_than_the_input_limit` bắt đúng lỗi đó và phải vẫn xanh.
  - **Mã lỗi:** `validation_exception_handler` (`app/core/errors.py`, dòng 125) gán `TEXT_EMPTY`/`TEXT_TOO_LONG` cho mọi lỗi có `"text"` trong `loc`, kèm câu "Nội dung đoạn thoại…". Với ý của tóm tắt, câu đó sai. Hoặc dùng câu đúng cho tóm tắt, hoặc dùng mã riêng và thêm mã vào `contracts/error_codes.md`.
  - **Bỏ dấu xfail** của 5 ca.
- **Message:** `fix(backend): summary key points and decisions must hold 1 to 1000 characters on save (BE-05, FE-12)`
- **Commit:** `c4f4cc8`

### 2. [x] `audio.available` vẫn là true khi file audio đã mất (BE-05, FE-19; P3 của C trên #78)
- **Lỗi:** `serialize_meeting_summary` đặt `available = meeting.audio_path is not None`. Khi `audio_path` còn mà file đã mất (không do retention), API trả `available: true, size_bytes: null`, còn `GET /meetings/{id}/audio` trả 404.
- **Test đỏ trước:**
  - Upload vào storage tạm rồi xóa file `audio/<id>/original.*`.
  - `GET /meetings/{id}` và `GET /meetings` trả `available: false, size_bytes: null`.
  - Còn file thì vẫn trả `true` kèm số byte đúng.
- **Sửa:** `available` lấy từ kết quả tìm file, không chỉ từ cột DB. Bỏ nhánh `hasattr(..., "get_audio_size")` không còn dùng trong `_resolve_audio_size`. Ngân sách truy vấn của `GET /meetings` không đổi.
- **Message:** `fix(backend): meeting audio is reported unavailable when its file is gone (BE-05, FE-19)`
- **Commit:** `71643ee`

### 3. [x] Ba chỗ tìm file audio theo ba cách (BE-05, BE-16)
- **Lỗi:** `GET /audio` (`app/api/v1/audio.py`, dòng 117), worker (`app/worker/runner.py`, dòng 267) và `LocalStorage.get_audio_size` đều tự tìm file, mỗi chỗ một kiểu.
  - Chỉ `get_audio_size` kiểm đường dẫn dự phòng `base_dir / audio_path` có nằm trong `base_dir`.
  - Hai chỗ kia ghép thẳng `base_dir / audio_path`.
- **Sửa:** một method của storage, ví dụ `resolve_audio_file(meeting_id, audio_path) -> Path | None`, có kiểm nằm trong `base_dir`. Cả ba chỗ dùng chung.
- **Test:**
  - Đặt `audio_path = "../outside.wav"` và tạo file thật ở ngoài `base_dir`.
  - `GET /audio` trả 404, `size_bytes` là `null`, worker không đọc file đó.
  - Đường dẫn bình thường vẫn chạy như cũ.
- **Message:** `fix(backend): audio playback, the worker and audio size find the file the same way and never outside STORAGE_DIR (BE-05, BE-16)`
- **Commit:** `6390a79`

### 4. [x] Tên mã HTTP 422 và 413 bị deprecated (BE-05)
- **Hiện trạng:** C chạy cả suite trên PostgreSQL ngày 11-26: **28 warning**.
  - 20 là `StarletteDeprecationWarning: 'HTTP_422_UNPROCESSABLE_ENTITY' is deprecated`. Trong `app` và `tests` còn 19 chỗ dùng hằng này.
  - 1 là `'HTTP_413_REQUEST_ENTITY_TOO_LARGE' is deprecated`. Còn 1 chỗ dùng hằng này.
  - 6 là `cookies=` truyền theo từng request của TestClient.
  - 1 là cách dùng `httpx` với `starlette.testclient`.
- **Sửa:**
  - Đổi sang `HTTP_422_UNPROCESSABLE_CONTENT` và `HTTP_413_CONTENT_TOO_LARGE` (giá trị vẫn là 422 và 413).
  - Thêm `filterwarnings` trong `[tool.pytest.ini_options]` (`backend/pyproject.toml`) để hai warning này thành lỗi, tránh dùng lại.
  - Ghi số warning trước và sau. Hai loại warning của TestClient không bắt buộc sửa hôm nay.
- **Message:** `refactor(backend): use HTTP_422_UNPROCESSABLE_CONTENT and HTTP_413_CONTENT_TOO_LARGE and fail tests on the deprecated names (BE-05)`
- **Commit:** `1170d36`

### 5. [x] Tick, hash (G0)
- Ghi hash từng commit; hash của chính commit này ghi "commit này".
- Chạy cả backend **trên Postgres** nghe cả IPv4 và IPv6. Ghi số passed, **skipped 0, xfailed 0**, và số warning.
- Ruff check và format sạch.
- **Message:** `docs(tasks): record 2026-11-26 member B results (G0)`
- **Commit:** `commit này`

## Việc chung (không tính commit)

- Review PR ngày 11-26 của A **trong 18 giờ** kể từ lúc A mở, comment trên GitHub. Ghi đúng tên hằng và tên hàm như trong code.
- Trả lời từng điểm review (nếu có), ghi commit sửa.

## Tiến độ triển khai local

- Nhánh `haquang`, bắt đầu từ `9e501cb`; đã `git fetch origin` và xác nhận khớp
  `origin/main`, không cần merge thêm.
- Đã hoàn thành triển khai/kiểm chứng local việc 1–5 và tạo đúng 5 commit trên
  `haquang`. Người dùng đã duyệt kế hoạch commit; tick/hash ở trên ghi kết quả local.
  Chưa push, chưa có CI/merge PR của B.
- Người dùng đã cho phép sinh lại `contracts/openapi.json` và
  `frontend/src/api/schema.d.ts`; không sửa mã frontend hoặc pipeline.
- Test tái hiện: 5 ca tóm tắt chạy `--runxfail` đều đỏ trước sửa; mất file ngoài
  retention, player và worker dùng đường dẫn ngoài storage cũng đỏ trước sửa.
- Test tập trung sau sửa: 42 passed; Ruff check/format đạt (175 file), OpenAPI
  không drift, frontend typecheck đạt sau `npm ci --ignore-scripts`.
- Toàn suite sau sửa trên Linux/PostgreSQL 16.15 (nghe IPv4 và IPv6):
  **568 passed, 0 failed, 0 skipped, 0 xfailed, 7 warnings** (148.22 giây).
  Baseline `9e501cb`: 554 passed, 5 xfailed, 0 skipped, 28 warnings.
  Warning **28 → 7**: hết 20 warning tên hằng 422 và 1 warning tên hằng 413;
  còn 6 warning cookie theo request và 1 warning TestClient/httpx.
- Lượt suite đầu sau sửa phát hiện 3 fixture privacy/reliability thiếu audio hoặc
  `audio_path`. Đã bổ sung dữ liệu giả để test đi vào pipeline như mục đích ban đầu,
  giữ nguyên assertion; nhóm này đạt 7 passed trước khi chạy lại toàn suite.
- Log UTF-8:
  [baseline](../../docs/backend/backend-before-2026-11-26.log),
  [sau sửa](../../docs/backend/backend-after-2026-11-26.log),
  [test tập trung](../../docs/backend/backend-focused-2026-11-26.log).
- Kế hoạch đủ 5 commit, file và tiêu chí kiểm tra:
  [BE-05-2026-11-26](../../docs/backend/BE-05-2026-11-26.md).
- Đã đọc diff PR [#80](https://github.com/TAINGUYENVAN0507/SE2026_Codex/pull/80)
  của A tại `d6a25bd`, đối chiếu `SUMMARY_POINT_TEXT_MAX_LENGTH`,
  hàm `save()` trong `RemoteSummary` và `checkAvailability()` trong
  `RemoteAudioPlayer` với backend.
  Chưa gửi review/comment lên GitHub, chưa push hoặc mở PR của B.
