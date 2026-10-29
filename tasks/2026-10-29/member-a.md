# 2026-10-29 · Member A: frontend, E2E

- **Người làm:** A (`@mactuongmvt`), nhánh `vantuong`.
- **Số commit:** 5.
- **Mục tiêu:** bộ E2E bằng Playwright chạy trên stack thật (FE-17):
  - Postgres, API, worker với fake pipeline, frontend bản build;
  - các luồng chính, bộ PRIV của recorder, và luồng lỗi rồi retry.

  Phần tóm tắt và export trong E2E làm ở ngày sau, khi B xong `GET /summary` và export thật (hôm nay, phần 1 của B).

## Cập nhật local ngày 29/10

- Đã triển khai và kiểm tra local mục **1, 2, 4, 5**; hash ghi dưới từng mục.
- **152 unit test và 15 E2E đạt**, không skip; lint, format, typecheck và build đạt.
  Chi tiết: [FE-17](../../docs/frontend/FE-17.md).
- Các ô nghiệm thu vẫn để `[ ]` vì điều kiện “xanh trên CI” chưa được xác nhận:
  cần theo dõi kết quả trên PR #29; không tự merge.
- Mục **3** chờ PR #28 của B được merge vào main; kiểm tra lại ngày 29/10,
  PR vẫn `open`, `merged=false`. Chưa viết test giả hoặc bỏ qua bước này để báo đủ 5 commit.
- SH-01 là việc chung của nhóm, chưa thực hiện trong đợt này.

### Phân biệt các phần đang chờ backend

- **Mục 3 hôm nay:** chờ PR #28 được merge để kiểm thử toàn luồng sửa segment,
  đổi tên speaker, thêm/sửa/xóa action item, reload và lịch sử trên backend thật.
- **Phần chờ từ trước:** giao diện và module export FE-15 đã có; B cần nối
  `GET /summary`, export và tạo lại tóm tắt với DB/worker thật. E2E tóm tắt/export
  làm tiếp sau khi các API tương ứng sẵn sàng, không làm lại giao diện từ đầu.
- Hai phụ thuộc này khác nhau. PR #28 được merge chưa đồng nghĩa các API
  tóm tắt/export/tạo lại tóm tắt đã hoàn tất; kiểm tra từng phần trước khi làm tiếp.
- **PR:** #29 (`vantuong` → `main`) vẫn mở, chưa merge tại lần kiểm tra ngày 29/10.
  Người dùng đã cho phép push cập nhật ngày 29/10. Các commit mới trên `vantuong` sẽ tự vào #29; cập nhật mô tả
  để nêu phần FE-17 và việc còn chờ. Không mở PR trùng cùng nhánh đích/nguồn.

Đọc trước:
- Mục FE-17 và mục 10.4 (RT-11, PRIV-01…09) của kế hoạch.
- `backend/README.md`, mục 5: chạy API và worker.
- `pipeline/README.md`, mục "Fake pipeline": `FAKE_SCENARIO`.
- [`rules/testing.md`](../../rules/testing.md).

Lệnh kiểm tra cho mọi commit, chạy trong `frontend/` (trên máy cần Postgres: `docker compose up -d db` ở gốc repo):

```bash
npm run lint && npm run format:check && npm run typecheck && npm test && npm run build
npx playwright test
```

## Bước 0 (không tính vào số commit)

```bash
git checkout vantuong
git fetch origin
git merge origin/main
```

- PR #29 (FE-15, FE-16) đang chờ nhóm trưởng review. Làm tiếp trên `vantuong`; khi #29 được merge thì merge `origin/main` lại.
- Commit 3 dùng action items thật của B (PR #28). Nếu #28 chưa vào `main` lúc làm tới commit 3, làm commit 4 và 5 trước.

## 5 commit

### 1. [ ] Playwright và workflow `e2e.yml` chạy trên stack thật (FE-17)

- **Việc:**
  - Thêm `@playwright/test` (chỉ Chromium) và `frontend/e2e/`.
  - Workflow `.github/workflows/e2e.yml`:
    - service Postgres;
    - backend: `uv sync --locked`, migrate, seed user demo bằng `SEED_DEMO_PASSWORD` (đặt trong workflow, giá trị chỉ dùng cho CI);
    - API: `uvicorn app.main:app`; worker: `PIPELINE_BACKEND=fake python -m app.worker.runner`;
    - frontend: `npm run build` rồi `vite preview`, proxy `/api` tới API;
    - đợi `/api/v1/health` rồi mới chạy test;
    - lỗi thì upload trace và screenshot của Playwright làm artifact.
  - Script `frontend/e2e/start-stack.sh` dùng chung cho máy dev và CI.
- **Xong khi:** test đăng nhập bằng user demo rồi thấy trang danh sách meeting, chạy xanh trên CI.
- **Message:** `test(frontend): Playwright on the real stack with an e2e workflow (FE-17)`
- **Hash:** `fe8f9c6` — login E2E thật đã đạt local; workflow đã viết, chờ CI.

### 2. [ ] Upload tới `ready` với fake pipeline (FE-17, RT-11)

- **Việc:**
  - Sinh file WAV ngắn trong test (không commit audio).
  - Upload có tick consent, theo dõi stepper 6 stage tới `ready`, rồi thấy transcript và player.
  - RT-11: reload trang khi job đang chạy (worker chạy với `FAKE_SCENARIO=slow`): UI tiếp tục hiện tiến trình lấy từ server, và vẫn chỉ có 1 job.
- **Xong khi:** 2 test xanh trên CI; không dùng `waitForTimeout` cố định, chỉ chờ theo trạng thái trên UI.
- **Message:** `test(frontend): upload to ready and reload during processing (FE-17)`
- **Hash:** `cd979b4` — 2 E2E đạt local; kiểm thêm bằng psql: meeting RT-11 có 1 job.

### 3. [ ] Sửa segment, đổi tên speaker, action item, lịch sử (FE-17)

- **Việc:** trên meeting đã `ready`:
  - sửa text một segment;
  - đổi tên speaker;
  - thêm, sửa, xóa action item;
  - reload trang: mọi thay đổi vẫn còn;
  - tab Lịch sử có đúng các event vừa tạo.
- **Xong khi:** test xanh trên CI với backend thật (cần PR #28 của B đã vào `main`).
- **Message:** `test(frontend): edits persist across reloads and show in history (FE-17)`
- **Hash:** chưa có — chờ PR #28 theo Bước 0. Không thay thế bằng mock hoặc skip.

### 4. [ ] Bộ PRIV của recorder trong trình duyệt thật (FE-17, PRIV-01…09)

- **Việc:**
  - Chromium chạy với `--use-fake-device-for-media-stream` và `--use-fake-ui-for-media-stream`.
  - Dùng `addInitScript` bọc `getUserMedia` để đếm số lần gọi và giữ track.
  - Kiểm:
    - PRIV-01, 02: chưa tick consent thì 0 lần gọi;
    - PRIV-03: bấm bắt đầu thì đúng 1 lần;
    - PRIV-04: dừng thì mọi track `ended`;
    - PRIV-05: hủy thì không có request `POST /meetings`;
    - PRIV-06: chỉ upload khi bấm "Tải lên";
    - PRIV-09: rời trang thì track dừng.
- **Xong khi:** mỗi PRIV là một test riêng, tên test ghi mã PRIV; xanh trên CI.
- **Message:** `test(frontend): recorder privacy checks PRIV-01 to PRIV-09 in Chromium (FE-17)`
- **Hash:** `731b84a` — 9 PRIV đạt trên Chromium thật; bổ sung chờ worker kết thúc upload trong `a0bb599`.

### 5. [ ] Luồng lỗi và retry (FE-17)

- **Việc:** chạy worker với `FAKE_SCENARIO` khác nhau:
  - `permanent`: meeting `failed`, UI hiện thông điệp tiếng Việt theo `error.code`, không lộ message kỹ thuật;
  - `transient_once`: UI hiện "Đang thử lại" kèm đếm ngược tới `next_run_at`, rồi tới `ready`;
  - `summary_fail`: meeting `partial`, transcript vẫn đọc và sửa được.
- **Xong khi:** 3 test xanh trên CI. Cập nhật `docs/frontend/FE-17.md`: cách chạy E2E ở máy, các test đã có, phần chờ B (tóm tắt, export, "Tạo lại tóm tắt").
- **Message:** `test(frontend): failure, transient retry and partial result flows (FE-17)`
- **Hash:** `a0bb599` — 3 E2E lỗi/retry/partial đạt local; đã cập nhật hướng dẫn và giới hạn trong FE-17.md.

## Việc chung (không phải commit)

- [ ] SH-01: ghi âm buổi họp pilot có consent (vẫn chưa có).

## Cuối ngày

- [ ] Tick các ô ở trên và ghi hash.
- [ ] Push `vantuong`, mở PR vào `main` (hoặc push thêm vào #29 nếu chưa merge). **Không tự merge.**
