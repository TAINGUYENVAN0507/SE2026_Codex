# 2026-11-12 · Member A: kiểm frontend trên clone sạch, bằng chứng giao diện tiến độ cho VT-018 (Đợt 7, đóng băng code)

- **Người làm:** A (`@vantuong`), nhánh `vantuong`.
- **Số commit:** tối đa 5. Hôm nay **đóng băng code**: chỉ sửa lỗi tìm thấy khi kiểm, không thêm tính năng. Không tìm thấy lỗi thì ghi "0 lỗi" và không tạo commit sửa.
- **Điều kiện bắt đầu:** #50 (A) và #51 (B) đã vào `main` (C review diff, CI xanh, merge ngày 2026-11-12, `d9c2d50`). Đợt 6 không còn việc chuyển sang.
- **Hạn:** mở PR trong ngày 11-12. Ngày 11-13 đóng băng bằng chứng.

## Bước 0
```bash
git checkout vantuong && git fetch origin && git merge origin/main
```

## Việc

### 1. [x] Frontend chạy được từ clone sạch (G0)
- `git clone` vào thư mục mới, làm đúng theo `README.md` và `frontend/README.md`. Chạy `npm ci && npm run lint && npm run typecheck && npm run test:coverage && npm run build && npm run e2e`.
- Ghi lệnh, commit, số test, coverage lines/branches và mọi bước README sai hoặc thiếu vào `docs/evidence/final/frontend-2026-11-12.md`. README sai thì sửa luôn trong commit này.
- **Message:** `test(frontend): clean-clone run on the frozen main (G0)`

### 2. [x] Ảnh giao diện tiến độ cho VT-018 (FE-20, VT-018)
- Playwright với fake pipeline, chụp 4 ảnh vào `docs/evidence/vt-018/ui/`: job `queued`, `running` ở giữa chừng (có %), `succeeded` (có thời gian bắt đầu và kết thúc), và sau khi bấm chạy lại một job `failed` (tiến độ bắt đầu lại, không có segment trùng trên trang transcript).
- Chỉ dữ liệu tổng hợp. Ghi lệnh tạo ảnh và commit trong `docs/evidence/vt-018/ui/README.md`.
- **Message:** `test(frontend): progress screenshots for the async job flow (VT-018)`

### 3. [x] Bấm "Chạy lại" hai lần không tạo hai job (VT-018, FE-20)
- Test MSW: bấm nhanh hai lần nút chạy lại job failed thì chỉ có 1 `POST` (hoặc 2 `POST` với cùng `Idempotency-Key`). Đỏ thì sửa trong commit này, ghi log đỏ trước khi sửa.
- **Message:** `test(frontend): double-clicking retry starts one job (VT-018)`

### 4. [x] Sửa lỗi tìm thấy ở việc 1–3 (chỉ khi có)
- Mỗi lỗi một test đỏ trước. Không có lỗi thì không tạo commit, ghi "0 lỗi" ở việc 5.
- **Message:** `fix(frontend): <lỗi> (G0)`

### 5. [x] Tick, hash (G0)
- Ghi hash từng commit vào file này. Việc chưa xong ghi lý do, không tick.
- **Message:** `docs(tasks): record 2026-11-12 member A results (G0)`

## Kết quả local — 12/11/2026

Đã cập nhật main `101f17e` trước khi làm; #50 và #51 đã merge.
Hôm nay không thêm tính năng. Các ô trên đánh dấu công việc local đã thực hiện;
chưa push, mở PR, xác nhận CI hoặc merge cho đợt này.

| Việc | Commit | Kết quả |
| --- | --- | --- |
| 1 — clone sạch | `e2a0d71` | npm ci thật từ clone mới; sau sửa checkout sạch add08c2 đạt 297 test/48 file và 24 E2E |
| 2 — ảnh progress | `434b9f0` | 4 PNG, API/worker/Postgres thật + fake pipeline; running giữa chừng, succeeded có hai thời điểm, retry failed giữ nguyên 6 segment |
| 3 — double-click | `434b9f0` | MSW giữ POST pending; dblClick chỉ 1 POST có UUID Idempotency-Key, nút khóa đến khi xong |
| 4 — lỗi tìm thấy | `add08c2`, `b3c1775` | Cache còn lại ở login; partial/pending làm mất retry và giữ job cũ; queued bị ghi đang chạy. Có regression đỏ trước sửa. Sửa thêm thời gian chờ UI/axe/upload không ổn định |
| 5 — phân công/kết quả cuối | commit này | Tick/hash và JSON đối chiếu source đã kiểm |

**Cách chia commit:** tổng 5 commit, không tính cập nhật main. Vì việc 2 tìm thêm lỗi
tích hợp thật, dành một commit sửa lỗi riêng; bằng chứng ảnh và test double-click
(việc 2–3 cùng luồng retry) được gộp một commit. Không tạo commit rỗng hay thêm tính năng.

### Kiểm tra cuối

- `npm run lint`, `npm run format:check`, `npm run typecheck`, `npm run test:coverage`, `npm run build`: exit 0.
- Source/test cuối tại `434b9f0`: **301 passed / 50 file**, **0 skip**; lines **86.78%**, branches **81.63%**. Giữ floors 84.53/79.11.
- Clone code sạch tại `add08c2`: **297 passed / 48 file**, lines 86.68%, branches 81.37%; `npm run e2e` slow **24 passed**, retries=0. Source này có sửa cache/thời gian chờ, chưa có sửa progress phát hiện sau đó.
- E2E progress sau các sửa mới: **1 passed**, queued 0%, running giữa chừng, succeeded 100%, retry summary từ 5/6 (~83%), attempt 1; 6 segment trước/sau cùng ID, số hàng hiển thị khớp.
- Hai lượt coverage trên main nguyên bản có 4 và 2 lỗi; được giữ trong báo cáo. Lượt một worker đạt 296 test chỉ dùng chẩn đoán, không che lượt đỏ.
- Nút chạy lại đang kiểm là **Tạo lại tóm tắt**, không phải retry toàn bộ ASR. API trả 202; giữ năm bước trước nên không ép progress về 0.
- Database E2E có nhãn riêng đã dừng/xóa; mật khẩu tổng hợp đã xóa; cổng 14173/18000/55452 không còn listener của QA.

### Bằng chứng

- [Clone sạch, lệnh và số đo](../../docs/evidence/final/frontend-2026-11-12.md).
- [Cache login và thời gian chờ test, log đỏ](../../docs/evidence/final/frontend-fixes-2026-11-12.md).
- [Partial/retry, nhãn queued và test đỏ](../../docs/evidence/final/frontend-progress-fixes-2026-11-12.md).
- [Bốn ảnh, lệnh chụp, manifest và double-click](../../docs/evidence/vt-018/ui/README.md).
- [JSON kiểm cuối gắn commit/source SHA256](../../docs/evidence/final/frontend-release-2026-11-12.json).
- Ảnh xem nhanh local: `.preview-stitch/anh-duyet/2026-11-12/` (ngoài Git).

### Còn lưu ý / cần backend theo dõi

- **B:** GET summary có thể trả pending khi meeting partial và chưa có row Summary
  (`backend/app/api/v1/summary.py`). Frontend đã xử lý dựa trên partial để người dùng
  tạo lại được; API gốc chưa được sửa trong phần A. Không đổi contract hay code backend.
- npm ci báo **9 moderate advisories** của dependency hiện tại; không chạy audit fix/force trong ngày đóng băng.
- E2E clone có **1 cảnh báo os.killpg native Windows** đã biết của pipeline khi hủy job.
  Assertion UI/API qua không thay kiểm chứng cleanup subprocess mọi trường hợp.
- Chỉ dữ liệu tổng hợp, pipeline fake; không khẳng định AI thật, screen reader thật hay tải 239/247.
- Manifest ảnh ghi cả lượt đỏ do sản phẩm, hai giả định sai của harness (201/0%) và lượt chụp lại để running ở giữa chừng. Không coi đó là phép đo flaky cùng source.
- Hoàn thành Definition of Done của nhóm vẫn cần được phép push/PR, CI xanh và nhóm trưởng merge.
