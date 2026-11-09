# 2026-11-09 · Member A: CI smoke cho web, trạng thái giao diện, a11y (Đợt 4)

- **Người làm:** A (`@vantuong`), nhánh `vantuong`.
- **Số commit:** 5, **cộng việc review**.
- **Điều kiện bắt đầu:** PR #41 và #42 đã vào `main` (merge commit `775c7cc`, `a0906f0`).
- **Mục tiêu:** lỗi BB-02 (nginx không khởi động) từng lọt qua CI vì CI chỉ build image; đóng lỗ hổng đó, rồi kiểm các trạng thái giao diện còn chưa có test.

Kế hoạch: [`tasks/ROADMAP.md`](../ROADMAP.md), Đợt 4. Kiểm tra trong `frontend/`: `npm run lint && npm test && npm run build`.

## Việc đầu tiên (không tính commit): review PR của B
B mở PR `haquang` hôm nay. Review trong 18 giờ kể từ lúc mở; ghi nhận xét thật vào PR. Kiểm riêng: route nào đổi hành vi, test nào yếu, có thử làm nó fail không.

**Trạng thái review:** chưa có PR mới của B tại lần kiểm tra 09/11. Không
đăng nhận xét giả, không dùng review PR #41 hôm trước thay cho đợt mới.
Tiếp tục review trong 18 giờ kể từ khi B mở PR.

## Bước 0
```bash
git checkout vantuong && git fetch origin && git merge origin/main
```

## 5 commit

### 1. [x] CI chạy thật container web, không chỉ build (FE-19, BE-16)
- Thêm bước vào `.github/workflows/docker-images.yml`: chạy image web dưới user mặc định, `curl` `/` và `/settings` phải trả 200, `nginx -t` phải đạt. Dùng `--add-host api:127.0.0.1` như đã làm khi review #41.
- **Xong khi:** CI đỏ nếu đưa lại `pid /var/run/nginx.pid` (thử trên nhánh tạm, dán link run đỏ vào thân commit, rồi trả lại).
- **Message:** `ci(infra): start the web container and probe it, not only build it (BE-16)`
- **Hash:** `26677de` — đạt theo bằng chứng bên dưới; chưa merge PR của đợt này.

### 2. [x] Phiên hết hạn giữa chừng: 401 đưa về đăng nhập có thông báo (FE-16)
- Khi API trả 401 ở bất kỳ trang nào, người dùng về `/login` với thông báo tiếng Việt, không mất trắng màn hình. Test MSW cho ít nhất 3 trang (danh sách, chi tiết, upload). **Đỏ trước** khi sửa nếu hành vi chưa có.
- **Message:** `fix(frontend): expired session returns to login with a message (FE-16)`
- **Hash:** `697611f` — đạt theo bằng chứng bên dưới; chưa merge PR của đợt này.

### 3. [x] Test trạng thái rỗng, đang tải, lỗi cho từng trang (FE-16)
- Bảng trang × trạng thái trong `docs/demo/ux-checklist.md`; test cho ô nào còn trống. Không tạo test chỉ kiểm "render không lỗi".
- **Message:** `test(frontend): empty, loading and error states on every page (FE-16)`
- **Hash:** `720fae9` — đạt theo bằng chứng bên dưới; chưa merge PR của đợt này.

### 4. [x] Kiểm accessibility tự động bằng axe (FE-16, FE-20)
- Thêm `vitest-axe` (hoặc `axe-core` trực tiếp), chạy trên danh sách, chi tiết, upload, cài đặt. Vi phạm `serious`/`critical` phải sửa hoặc ghi lý do trong `docs/demo/bug-bash-2026-11-08.md`.
- **Message:** `test(frontend): axe checks on the main pages (FE-16)`
- **Hash:** `96c79af` — đạt theo bằng chứng bên dưới; chưa merge PR của đợt này.

### 5. [x] Tick, hash, cập nhật kịch bản demo (FE-16)
- Ghi hash vào file này; kịch bản demo khớp giao diện hiện tại; không có dữ liệu thật trong ảnh.
- **Message:** `docs(tasks): record 2026-11-09 member A results (G0)`
- **Hash:** `1a3c078` — tài liệu, tick/hash và tám ảnh tổng hợp ngày 09/11; hash này ghi bằng commit metadata sau khi commit task 5 tồn tại.

## Kết quả local và đồng bộ main

- Bắt đầu tại main `a0906f0`; chỉ lấy file phân công từ `origin/tainguyen`
  `274df3d`, không nhập code chưa merge. Sau khi PR #43 merge, gộp main
  `b654a99` bằng commit `b08bf38`, không conflict. Bản task tạm trùng main
  được giữ ngoài repo trước merge, không ghi đè mất dữ liệu.
- Năm tick xác nhận phần triển khai/kiểm tra local và smoke CI nhánh thử,
  không phải toàn bộ DoD đã merge.
- **262 Vitest / 39 file**, lint, format, typecheck và production build đạt.
- **26 E2E**: 23 slow + 1 permanent + 1 transient_once + 1 summary_fail,
  không skip. API/worker/PostgreSQL thật, pipeline fake, dữ liệu tổng hợp.
- Axe: 4 Vitest + 4 browser test; browser quét 1280×900 và 360×900, tổng 8
  lượt đều 0 violation, 0 incomplete; không tắt contrast trong browser.
- Smoke CI đỏ đúng lỗi PID trên nhánh tạm `vantuong-smoke-red-20261109`:
  https://github.com/TAINGUYENVAN0507/SE2026_Codex/actions/runs/42572237499 .
  Sau trả PID đúng, CI xanh:
  https://github.com/TAINGUYENVAN0507/SE2026_Codex/actions/runs/42572536719 .
  Hai URL có trong thân commit 1. Không merge nhánh thử; bộ lọc nhánh thử
  và mutation không nằm trong `vantuong`.
- Image source cuối build và script smoke local đạt: non-root nginx -t,
  `/` và `/settings` 200, `/metrics` 404; container được dọn sau kiểm tra.
- 18 test chọn theo main mới (admission, evidence links, retention docs)
  đạt; không phải toàn bộ backend suite. Không sửa source backend/pipeline.
- 8 ảnh mới 09/11 khớp SHA256 bản preview, chỉ dữ liệu tổng hợp. Kịch bản
  demo và bảng trạng thái ở `docs/demo/ux-checklist.md` đã cập nhật.
- Docs: FE-16/17/19/20, README frontend, README infra, bug bash và bản tổng
  hợp axe. Không sửa README chung hoặc generated contract.

## Lỗi kiểm tra đã xử lý và giới hạn

- Bốn test 401 đỏ trước sửa vì thiếu alert; lỗi fixture import ở lần dựng
  test đầu được sửa trước khi lấy bằng chứng đỏ, không tính là lỗi sản phẩm.
- Bốn browser axe fail contrast trước sửa. Sau sửa còn mobile tabs, rồi
  xử lý cả gradient gây incomplete; kết quả cuối 8/8 quét đạt, không skip rule.
- Một lần full unit test có timeout chuyển trang 401 ở giới hạn mặc định
  1 giây khi chạy bộ kiểm tra nặng. Đặt giới hạn chờ điều kiện 5 giây, giữ đủ
  assertion và không sleep; bộ auth 14/14 và bộ đầy đủ 262/262 chạy lại đạt.
- Có lỗi format README frontend ở lượt kiểm tra giữa chừng; đã format và
  chạy lại thành công. Không sửa API hoặc bỏ test để làm xanh.
- Browser là Chromium desktop/mobile giả lập; chưa kiểm screen reader,
  điện thoại vật lý hay toàn bộ modal/tab ẩn. Không coi axe là chứng nhận WCAG.
- Detector nhắc Inter là font phổ biến; giữ đúng font người dùng đã duyệt.
- SH-01/pilot và đánh giá AI thật vẫn là việc chung, không làm trong đợt này.

## Bàn giao

- Chưa push `vantuong`, mở PR cho ngày 09/11 hoặc tự merge. Chỉ nhánh tạm
  CI negative control đã push theo điều kiện task 1 và đã trả PID an toàn.
- Kết quả CI nhánh thử không thay cho CI PR của toàn bộ phần frontend ngày này.
- Merge đồng bộ main không tính vào năm commit task. Commit metadata ghi
  hash cuối cũng không phải task tính năng mới; không chia nhỏ giả để tăng số.
