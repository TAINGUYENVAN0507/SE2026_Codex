# 2026-11-09 · Member A: CI smoke cho web, trạng thái giao diện, a11y (Đợt 4)

- **Người làm:** A (`@vantuong`), nhánh `vantuong`.
- **Số commit:** 5, **cộng việc review**.
- **Điều kiện bắt đầu:** PR #41 và #42 đã vào `main` (merge commit `775c7cc`, `a0906f0`).
- **Mục tiêu:** lỗi BB-02 (nginx không khởi động) từng lọt qua CI vì CI chỉ build image; đóng lỗ hổng đó, rồi kiểm các trạng thái giao diện còn chưa có test.

Kế hoạch: [`tasks/ROADMAP.md`](../ROADMAP.md), Đợt 4. Kiểm tra trong `frontend/`: `npm run lint && npm test && npm run build`.

## Việc đầu tiên (không tính commit): review PR của B
B mở PR `haquang` hôm nay. Review trong 18 giờ kể từ lúc mở; ghi nhận xét thật vào PR. Kiểm riêng: route nào đổi hành vi, test nào yếu, có thử làm nó fail không.

## Bước 0
```bash
git checkout vantuong && git fetch origin && git merge origin/main
```

## 5 commit

### 1. [ ] CI chạy thật container web, không chỉ build (FE-19, BE-16)
- Thêm bước vào `.github/workflows/docker-images.yml`: chạy image web dưới user mặc định, `curl` `/` và `/settings` phải trả 200, `nginx -t` phải đạt. Dùng `--add-host api:127.0.0.1` như đã làm khi review #41.
- **Xong khi:** CI đỏ nếu đưa lại `pid /var/run/nginx.pid` (thử trên nhánh tạm, dán link run đỏ vào thân commit, rồi trả lại).
- **Message:** `ci(infra): start the web container and probe it, not only build it (BE-16)`

### 2. [ ] Phiên hết hạn giữa chừng: 401 đưa về đăng nhập có thông báo (FE-16)
- Khi API trả 401 ở bất kỳ trang nào, người dùng về `/login` với thông báo tiếng Việt, không mất trắng màn hình. Test MSW cho ít nhất 3 trang (danh sách, chi tiết, upload). **Đỏ trước** khi sửa nếu hành vi chưa có.
- **Message:** `fix(frontend): expired session returns to login with a message (FE-16)`

### 3. [ ] Test trạng thái rỗng, đang tải, lỗi cho từng trang (FE-16)
- Bảng trang × trạng thái trong `docs/demo/ux-checklist.md`; test cho ô nào còn trống. Không tạo test chỉ kiểm "render không lỗi".
- **Message:** `test(frontend): empty, loading and error states on every page (FE-16)`

### 4. [ ] Kiểm accessibility tự động bằng axe (FE-16, FE-20)
- Thêm `vitest-axe` (hoặc `axe-core` trực tiếp), chạy trên danh sách, chi tiết, upload, cài đặt. Vi phạm `serious`/`critical` phải sửa hoặc ghi lý do trong `docs/demo/bug-bash-2026-11-08.md`.
- **Message:** `test(frontend): axe checks on the main pages (FE-16)`

### 5. [ ] Tick, hash, cập nhật kịch bản demo (FE-16)
- Ghi hash vào file này; kịch bản demo khớp giao diện hiện tại; không có dữ liệu thật trong ảnh.
- **Message:** `docs(tasks): record 2026-11-09 member A results (G0)`
