# 2026-11-08 · Member A: bug bash giao diện (Đợt 3)

- **Người làm:** A (`@vantuong`), nhánh `vantuong`.
- **Số commit:** 5, **cộng việc review**.
- **Điều kiện bắt đầu:** PR #38 và #39 đã vào `main`.
- **Mục tiêu:** tìm và sửa lỗi giao diện bằng cách dùng thật; mỗi lỗi sửa có test hồi quy.

Kế hoạch: [`tasks/ROADMAP.md`](../ROADMAP.md), Đợt 3. Kiểm tra trong `frontend/`: `npm run lint && npm test && npm run build`.

## Kết quả local ngày 08/11

- Đã cập nhật main `be9f08d` trước khi code; PR #38/#39 đã merge.
- Năm tick bên dưới xác nhận đã triển khai/kiểm tra **local**, không phải DoD
  đã merge. Chưa push, chưa mở PR mới và chưa xác nhận CI của đợt này.
- Frontend: **238 test / 35 file**, lint, format, typecheck, production build đạt.
- E2E stack thật: **19 slow + 1 permanent + 1 transient_once + 1 summary_fail**
  đạt, không skip. PostgreSQL/API/worker thật, pipeline fake, chỉ dữ liệu tổng hợp.
- Docker build bản cuối đạt; nginx -t, HTTP /settings 200, /metrics 404 đạt.
- 14 ảnh mới tại `docs/demo/screenshots/2026-11-08-*`; bản sao khớp SHA256 ở
  `.preview-stitch/anh-duyet/2026-11-08/` (ngoài Git).
- Báo cáo: `docs/demo/bug-bash-2026-11-08.md`; cập nhật FE-16, FE-19, FE-20,
  README frontend. Không sửa README chung, API hoặc pipeline của người khác.

## Việc đầu tiên (không tính commit): review PR của B
B mở PR `haquang` hôm nay. Bạn review (18 giờ từ lúc mở). Ghi nhận xét thật vào PR: có route nào bị đổi hành vi, có test nào yếu.

**Trạng thái:** chưa thực hiện vì chưa có PR mới từ `haquang`. Kiểm GitHub
lúc khoảng 16:43 ngày 08/11 chỉ có PR #40 từ `tainguyen` đang mở. PR #39 của
B đã merge là đợt trước, không thay cho review đợt này. Không đăng nhận xét
khi chưa có PR hoặc tự nhận đã review.

## Bước 0
```bash
git checkout vantuong && git fetch origin && git merge origin/main
```

## 5 commit

### 1. [x] Bug bash luồng chính, ghi danh sách lỗi (FE-16)
- Chạy stack thật (Compose của B hoặc dev server), đi hết: đăng ký → upload → xem tiến độ → xem tóm tắt → export → xóa cuộc họp. Ghi mỗi lỗi vào `docs/demo/bug-bash-2026-11-08.md`: bước tái hiện, mong đợi, thực tế, mức độ. Ghi cả khi **không** thấy lỗi ở bước nào.
- **Xong khi:** file có ít nhất mọi bước trên, lỗi nào chưa sửa thì ghi lý do.
- **Message:** `docs(demo): bug bash notes for the main flow (FE-16)`
- **Hash:** `5497776` — Ghi rõ mọi bước, lỗi và các bước không thấy lỗi. Đạt local, chờ PR/CI và nhóm review.

### 2. [x] Mọi mã lỗi API hiện thông báo tiếng Việt đọc được (FE-16)
- Lấy danh sách `error.code` từ `contracts/openapi.json`; test bảng ánh xạ đủ mã, không mã nào rơi về thông báo chung chung. Thiếu mã thì thêm.
- **Message:** `test(frontend): every API error code has a readable message (FE-16)`
- **Hash:** `73ff1a5` — 48 mã công bố có thông báo; 49 test catalog đạt, 28 mã đỏ trước sửa. Đạt local, chờ PR/CI và nhóm review.

### 3. [x] Bàn phím và nhãn truy cập cho luồng upload và tiến độ (FE-16)
- Dùng được bằng Tab/Enter; thanh tiến độ có `role="progressbar"` và `aria-valuenow`; trạng thái lỗi được đọc ra. Test bằng Testing Library.
- **Message:** `feat(frontend): keyboard and aria support on upload and progress (FE-16, FE-20)`
- **Hash:** `7c9e219` — Tab/Enter, progressbar upload và status hủy; job giữ role/nhãn/giá trị và alert. Đạt local, chờ PR/CI và nhóm review.

### 4. [x] Sửa các lỗi mức cao từ commit 1, mỗi lỗi một test hồi quy (FE-16)
- Test phải **đỏ trước** khi sửa; ghi trong thân commit tên test đỏ. Nếu commit 1 không ra lỗi mức cao thì chọn 2 lỗi mức vừa hoặc ghi rõ "không có" và đổi việc này sang chụp lại ảnh màn hình hẹp (≤ 400 px).
- **Message:** `fix(frontend): <mô tả lỗi thật> (FE-16)`
- **Hash:** `dd12780` — Sửa hai lỗi upload mức vừa; bốn test hồi quy đỏ trước sửa, đạt sau sửa. Đạt local, chờ PR/CI và nhóm review.

### 5. [x] Cập nhật ảnh demo và kịch bản, tick, hash (FE-16)
- Chụp lại ảnh nếu giao diện đổi; kịch bản 5 phút khớp với giao diện hiện tại. Không có dữ liệu thật trong ảnh.
- **Message:** `docs(demo): refresh screenshots and script after bug bash (FE-16)`
- **Hash:** `1519d05` — 14 ảnh mới, checklist và kịch bản 5 phút khớp app; README frontend cập nhật. Đạt local, chờ PR/CI và nhóm review.

## Cuối ngày
- [x] Tick và ghi hash cho phần đạt local.
- [ ] Chờ người dùng cho phép push `vantuong` và mở PR mới vào `main`.
- Không tự merge hoặc bật tự động merge. CI GitHub chỉ xác nhận sau khi push.

## Việc phát sinh và chuyển từ hôm trước

| Việc | Kết quả | Hash |
| --- | --- | --- |
| Docker Web lỗi build và PID Nginx (FE-19, BE-16) | Tái hiện trước sửa; build, khởi động và HTTP đạt sau sửa; B cần review phần infra/workflow | `36b1af4` |
| Xóa tài khoản chuyển từ 07/11 (FE-19) | API đã có; typed client và E2E xóa thật/phiên cũ/đăng nhập lại/user đối chứng đạt | `8153a75` (typed adapter nằm cùng `dd12780`) |
| Bộ chọn E2E recorder sau thêm status upload | Lần đầu 13 đạt/6 lỗi strict selector; giữ assertion privacy, scope vào recorder; chạy lại slow 19/19 đạt | `7641338` |

Năm commit theo phân công và ba commit phát sinh tách riêng theo nội dung;
commit ghi hash/trạng thái cuối không tính là task tính năng mới. Không chia
nhỏ giả tạo để tăng số commit.

## Chưa làm và giới hạn

- Review PR mới của B: chờ B mở PR, không bị chặn bởi backend để làm frontend.
- SH-01/pilot có consent là việc chung, không làm trong buổi này.
- Không dùng test pipeline fake để khẳng định chất lượng AI hoặc tải 239/247.
- Kiểm bàn phím/role bằng Testing Library/Chromium, viewport mobile giả lập;
  chưa kiểm screen reader hay thiết bị điện thoại vật lý.
- Nguy cơ worker native Windows `os.killpg` từng ghi ở FE-19 vẫn thuộc C;
  UI/API xóa đạt không thay thế kiểm chứng cleanup mọi nơi của backend/pipeline.
