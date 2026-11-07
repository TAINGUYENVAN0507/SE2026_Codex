# 2026-11-07 · Member A: E2E, xóa tài khoản, demo

- **Người làm:** A (`@mactuongmvt`), nhánh `vantuong`.
- **Số commit:** 5.
- **Điều kiện bắt đầu:** PR #33 (B) và PR #34 (A) đã vào `main`. Làm Bước 0 sau khi cả hai đã merge.
- **Mục tiêu:** E2E phủ đường người quản lý kiểm chứng biên bản; người dùng xóa được cả tài khoản; có kịch bản demo.

Kế hoạch: [`tasks/ROADMAP.md`](../ROADMAP.md), Đợt 2.

## Kết quả local ngày 07/11

- Đã cập nhật nhánh `vantuong` từ main `1a061b6`; PR #33/#34 đã merge.
- Mục 1, 2, 4 đạt local; mục 5 có checklist, ảnh thật và kịch bản demo.
  Các ô nghiệm thu E2E vẫn chờ CI vì chưa push.
- Mục 3 **chưa hoàn thành**: đã có UI/form/test nhưng main chưa có
  `DELETE /auth/me` của B. App khóa nút theo OpenAPI; không giả lập thành công
  trên giao diện để báo đã tích hợp. Cần E2E xóa user riêng và đăng nhập lại sai.
- Frontend: **183 test / 34 file đạt**; lint, format, typecheck và build đạt.
  E2E đầy đủ: **18 slow + 3 lỗi/retry/partial đạt**, không skip.
- Fixture retention chạy CLI thật trên DB E2E, kiểm đường dẫn trước khi xóa;
  Ruff đạt. Không sửa backend/pipeline ngoài phạm vi.
- 11 ảnh dữ liệu tổng hợp ở `docs/demo/screenshots/2026-11-07-*`, bản sao tiện
  duyệt ở `.preview-stitch/anh-duyet/2026-11-07/`; không có `pageerror` khi chụp.
- Local Windows vẫn có log `os.killpg` khi hủy job: đã ghi trong FE-19/checklist
  để C xử lý. Test UI/API đạt không được coi là worker đã cleanup hoàn hảo.
- Đã push `vantuong`, mở [PR #38](https://github.com/TAINGUYENVAN0507/SE2026_Codex/pull/38), chưa merge.
  CI trên commit cuối đang chờ xác nhận. Năm commit nội dung được ghi dưới
  từng mục; commit tài liệu sau đó chỉ ghi hash/trạng thái cuối và link PR.

## Bước 0

```bash
git checkout vantuong && git fetch origin && git merge origin/main
```

Lệnh kiểm tra mỗi commit, trong `frontend/`: `npm run lint && npm run format:check && npm run typecheck && npm test && npm run build && npx playwright test`.

## 5 commit

### 1. [ ] E2E tóm tắt và export trên stack thật (FE-18)
- Meeting `ready`: tóm tắt hiện, bấm evidence thì player tua đúng giây; export TXT/MD/JSON tải về được, không mock.
- **Xong khi:** `frontend/e2e/flows/export.spec.ts` xanh trên CI, không `waitForTimeout` cố định.
- **Message:** `test(frontend): summary evidence and export on the real stack (FE-18)`
- **Hash:** `49da803` — download TXT/MD/JSON và seek audio thật đạt local, chờ CI.

### 2. [ ] Evidence trong file tải về khớp giao diện (FE-18)
- Đọc file TXT/MD vừa tải, so từng mốc `hh:mm:ss` với link evidence trên giao diện.
- **Xong khi:** E2E khẳng định mỗi ý/action item có mốc tương ứng; ý không có evidence mang nhãn "Chưa có bằng chứng" ở cả hai nơi.
- **Message:** `test(frontend): exported evidence matches what the page shows (FE-18)`
- **Hash:** `8c236bb` — từng ý/công việc và nhãn thiếu evidence khớp UI/file, đạt local.

### 3. [ ] Giao diện xóa tài khoản (FE-19)
- Cần B xong `DELETE /auth/me` (commit 1 của B hôm nay). Trang cài đặt có nút, hộp xác nhận nêu rõ mọi cuộc họp sẽ bị xóa, gõ lại email để xác nhận.
- **Xong khi:** Vitest cho xác nhận, lỗi 5xx giữ nguyên trang; E2E: xóa xong về trang đăng nhập, đăng nhập lại bằng tài khoản cũ báo sai.
- **Message:** `feat(frontend): delete the account from settings (FE-19)`
- **Hash:** `1f154a2` — phần UI chuẩn bị; 7 test component đạt, chưa có E2E xóa tài khoản thật vì chờ API B.

### 4. [ ] Audio hết hạn: E2E trọn luồng (FE-19)
- Dựng meeting với `retention_until` đã qua + chạy `python -m app.scripts.cleanup`; trang chi tiết báo "Audio đã hết hạn lưu trữ", transcript vẫn đọc được.
- **Xong khi:** E2E xanh trên CI.
- **Message:** `test(frontend): expired audio keeps the transcript readable (FE-19)`
- **Hash:** `4330c64` — cleanup CLI/file thật + audio 410 + transcript không đổi, đạt local.

### 5. [x] Checklist UX và kịch bản demo
- `docs/demo/ux-checklist.md`: ảnh chụp thật từ app đang chạy cho upload, tiến độ, tóm tắt có evidence, export, xóa; kịch bản demo 5 phút. Ảnh chỉ dùng dữ liệu mẫu, không audio hay transcript thật.
- **Message:** `docs(demo): UX checklist with screenshots and a 5-minute script (FE-16)`
- **Hash:** `ae3ee3b` — 11 ảnh thật dữ liệu tổng hợp, checklist, kịch bản 5 phút; sửa nhãn bản ghi ngắn khi QA.

## Cuối ngày
- [x] Ghi hash và trạng thái local; giữ mục chờ CI/API chưa nghiệm thu.
- [x] Đã được người dùng cho phép push và mở [PR #38](https://github.com/TAINGUYENVAN0507/SE2026_Codex/pull/38) vào `main`. **Chưa merge.**
