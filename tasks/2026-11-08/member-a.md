# 2026-11-08 · Member A: bug bash giao diện (Đợt 3)

- **Người làm:** A (`@vantuong`), nhánh `vantuong`.
- **Số commit:** 5, **cộng việc review**.
- **Điều kiện bắt đầu:** PR #38 và #39 đã vào `main`.
- **Mục tiêu:** tìm và sửa lỗi giao diện bằng cách dùng thật; mỗi lỗi sửa có test hồi quy.

Kế hoạch: [`tasks/ROADMAP.md`](../ROADMAP.md), Đợt 3. Kiểm tra trong `frontend/`: `npm run lint && npm test && npm run build`.

## Việc đầu tiên (không tính commit): review PR của B
B mở PR `haquang` hôm nay. Bạn review (18 giờ từ lúc mở). Ghi nhận xét thật vào PR: có route nào bị đổi hành vi, có test nào yếu.

## Bước 0
```bash
git checkout vantuong && git fetch origin && git merge origin/main
```

## 5 commit

### 1. [ ] Bug bash luồng chính, ghi danh sách lỗi (FE-16)
- Chạy stack thật (Compose của B hoặc dev server), đi hết: đăng ký → upload → xem tiến độ → xem tóm tắt → export → xóa cuộc họp. Ghi mỗi lỗi vào `docs/demo/bug-bash-2026-11-08.md`: bước tái hiện, mong đợi, thực tế, mức độ. Ghi cả khi **không** thấy lỗi ở bước nào.
- **Xong khi:** file có ít nhất mọi bước trên, lỗi nào chưa sửa thì ghi lý do.
- **Message:** `docs(demo): bug bash notes for the main flow (FE-16)`

### 2. [ ] Mọi mã lỗi API hiện thông báo tiếng Việt đọc được (FE-16)
- Lấy danh sách `error.code` từ `contracts/openapi.json`; test bảng ánh xạ đủ mã, không mã nào rơi về thông báo chung chung. Thiếu mã thì thêm.
- **Message:** `test(frontend): every API error code has a readable message (FE-16)`

### 3. [ ] Bàn phím và nhãn truy cập cho luồng upload và tiến độ (FE-16)
- Dùng được bằng Tab/Enter; thanh tiến độ có `role="progressbar"` và `aria-valuenow`; trạng thái lỗi được đọc ra. Test bằng Testing Library.
- **Message:** `feat(frontend): keyboard and aria support on upload and progress (FE-16, FE-20)`

### 4. [ ] Sửa các lỗi mức cao từ commit 1, mỗi lỗi một test hồi quy (FE-16)
- Test phải **đỏ trước** khi sửa; ghi trong thân commit tên test đỏ. Nếu commit 1 không ra lỗi mức cao thì chọn 2 lỗi mức vừa hoặc ghi rõ "không có" và đổi việc này sang chụp lại ảnh màn hình hẹp (≤ 400 px).
- **Message:** `fix(frontend): <mô tả lỗi thật> (FE-16)`

### 5. [ ] Cập nhật ảnh demo và kịch bản, tick, hash (FE-16)
- Chụp lại ảnh nếu giao diện đổi; kịch bản 5 phút khớp với giao diện hiện tại. Không có dữ liệu thật trong ảnh.
- **Message:** `docs(demo): refresh screenshots and script after bug bash (FE-16)`

## Cuối ngày
- [ ] Tick và ghi hash. Push `vantuong`, mở PR vào `main`. **Không tự merge.**
