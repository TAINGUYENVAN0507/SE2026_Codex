# 2026-11-08 · Member B: tách controller, privacy, độ tin cậy (Đợt 3)

- **Người làm:** B (`@minhquangha`), nhánh `haquang`.
- **Số commit:** 5, **cộng việc review**.
- **Điều kiện bắt đầu:** PR #38 và #39 đã vào `main`.
- **Mục tiêu:** `meetings.py` nhỏ hơn (hiện 1940 dòng, 14 route); test privacy và reliability; `make`.

Kế hoạch: [`tasks/ROADMAP.md`](../ROADMAP.md), Đợt 3. Kiểm tra trong `backend/`: `uv run ruff check . && uv run ruff format --check . && uv run pytest`. Trên máy có `ffprobe` thật, 5 test upload lỗi `AUDIO_INVALID` từ trước (không phải do thay đổi của bạn; CI xanh).

## Việc đầu tiên (không tính commit): review PR của C
C mở PR `tainguyen` hôm nay (ADR 0002, test canary log của pipeline, đồng bộ README, đo tải 239 và 247). Ghi nhận xét thật vào PR; kiểm riêng: con số tải có khớp `docs/evidence/` và có ghi giới hạn phép đo không.

## Bước 0
```bash
git checkout haquang && git fetch origin && git merge origin/main
```

## 5 commit

### 1. [ ] Tách route segment và key point khỏi `meetings.py` (BE-12)
- Chuyển nguyên route sang module riêng, **không đổi hành vi**. Test drift OpenAPI không đổi; ghi số dòng trước/sau.
- **Message:** `refactor(backend): move segment and key point routes out of meetings.py (BE-12)`

### 2. [ ] Tách route export và job khỏi `meetings.py`; bỏ `serialize_job` lặp (BE-12)
- Dùng một `serialize_job` duy nhất (hiện lặp giữa `meetings.py` và `jobs.py`).
- **Message:** `refactor(backend): move export and job routes, share serialize_job (BE-12)`

### 3. [ ] `tests/privacy`: canary không lọt vào log và DB sau khi xóa (BE-18, BE-19)
- Tiêu đề/transcript canary đi qua upload → xử lý → xóa; kiểm log API, log worker, `idempotency_keys`, artifact. C làm tầng pipeline; bạn làm API và worker.
- **Message:** `test(backend): privacy canary across API and worker logs and tables (BE-18, BE-19)`

### 4. [ ] `tests/reliability` và `docs/evidence/` (BE-15)
- Kịch bản: worker chết giữa chừng, reaper lấy lại; retry hết lượt → `failed`; tải lên trùng khóa. Ghi lệnh chạy và kết quả vào `docs/evidence/reliability.md`, không bịa số.
- **Message:** `test(backend): reliability scenarios with recorded evidence (BE-15)`

### 5. [ ] `Makefile`: `make test`, `make lint`, `make up`, `make down` (BE-16)
- Mỗi target gọi đúng lệnh đã ghi trong README; README trỏ tới `make`.
- **Message:** `chore(infra): Makefile for test, lint and compose (BE-16)`

## Cuối ngày
- [ ] Tick và ghi hash. Push `haquang`, mở PR vào `main`. **Không tự merge.**
