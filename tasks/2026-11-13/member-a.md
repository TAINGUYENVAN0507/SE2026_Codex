# 2026-11-13 · Member A: chạy lại E2E trên `main` cuối, kịch bản demo khớp bằng chứng (Đợt 8, đóng băng bằng chứng)

- **Người làm:** A (`@vantuong`), nhánh `vantuong`.
- **Số commit:** tối đa 3. Hôm nay **đóng băng bằng chứng**: không thêm tính năng. Chỉ sửa lỗi nếu E2E đỏ, mỗi lỗi một test đỏ trước.
- **Điều kiện bắt đầu:** #53 (A) đã vào `main` ngày 2026-11-13 (`a75853d`, CI xanh 12/12). #54 (B) merge khi CI xanh.
- **Hạn:** mở PR trong ngày 11-13. Ngày 11-14 nộp bài.

## Bước 0
```bash
git checkout vantuong && git fetch origin && git merge origin/main
```

## Việc

### 1. [x] E2E trên `main` có cả #53 và #54 (G0)
- Chạy `npm run e2e` (slow, `retries=0`) trên `main` sau khi #54 vào. PR #53 ghi rõ 24 E2E là của `add08c2`, chưa có sửa progress; lượt này đóng khoảng trống đó.
- Ghi commit, số passed/failed, thời gian vào `docs/evidence/final/frontend-2026-11-13.md`. Đỏ thì giữ log đỏ, không chạy lại cho tới khi xanh rồi chỉ ghi lượt xanh.
- **Message:** `test(frontend): e2e on the final main (G0)`

### 2. [x] Kịch bản demo khớp bằng chứng (FE-20, VT-018)
- `docs/demo/ux-checklist.md`: thêm luồng tiến độ job dùng 4 ảnh ở `docs/evidence/vt-018/ui/`, và luồng tóm tắt lỗi → "Tạo lại tóm tắt" (sửa ở #53). Mỗi bước ghi ảnh hoặc test chứng minh nó.
- Bước nào không có ảnh hoặc test thì ghi "chưa có bằng chứng".
- **Message:** `docs(demo): demo script tied to the VT-018 progress evidence (FE-20, VT-018)`

### 3. [x] Tick, hash (G0)
- Ghi hash từng commit vào file này. Việc chưa xong ghi lý do, không tick.
- **Message:** `docs(tasks): record 2026-11-13 member A results (G0)`

## Kết quả local — 13/11/2026

| Việc | Commit | Kết quả |
| --- | --- | --- |
| 1 — E2E trên main có #53/#54 | `ddecd73` | Một lượt slow trên `7b99a7a`: 24 passed / 0 failed / 0 skipped, retries=0, 304.22 giây gồm chuẩn bị stack |
| 2 — demo gắn bằng chứng | `9bc5eab` | Thêm kịch bản 13/11 với từng bước dẫn ảnh/test; giữ bốn ảnh 12/11 đúng nguồn, có luồng lỗi → Tạo lại tóm tắt |
| 3 — tick/hash | commit này | Bảng kết quả và kiểm cuối; tổng 3 commit theo phân công |

### Kiểm đã chạy

- Source E2E: `7b99a7a83e068155887160fd7ec3fabf8f069ee8` (main có #53/#54/#55), working tree sạch khi bắt đầu/kết thúc. Đây là lượt mới có đủ sửa progress của #53, không lấy lượt add08c2 cũ thay thế.
- `npm run lint`, `npm run format:check`, `npm run typecheck`, `npm run test:coverage`, `npm run build`: exit 0.
- Vitest **301 passed / 50 file**, 0 skip; coverage **86.78% lines / 81.63% branches**, giữ ngưỡng 84.53/79.11.
- `npm run e2e`, slow: **24/24 đạt**, chỉ một lượt; không có E2E đỏ cần sửa. **0 lỗi E2E mới**, không tạo commit fix.
- Source frontend/backend/pipeline/contract/infra không đổi sau lượt kiểm; chỉ thêm bằng chứng, sửa demo và phân công. README chung giữ nguyên.
- Database tổng hợp se-day8-e2e-db đã dừng/xóa theo đúng nhãn. Cổng 14173/18000/55453 không còn listener của QA; không dừng dịch vụ người dùng.

### Bằng chứng và giới hạn

- [Báo cáo E2E 13/11](../../docs/evidence/final/frontend-2026-11-13.md), [JSON lệnh/commit/exit code/thời gian](../../docs/evidence/final/frontend-2026-11-13.json), [trích 24 ca](../../docs/evidence/final/frontend-e2e-2026-11-13.log).
- [Kịch bản demo hiện dùng](../../docs/demo/ux-checklist.md): từng bước có ảnh hoặc test; thiếu bằng chứng AI thật/danh tính người nói, điện thoại và screen reader được ghi rõ.
- Bốn ảnh progress vẫn là [bằng chứng 12/11](../../docs/evidence/vt-018/ui/README.md), không chụp lại hay đổi ngày ảnh. Source/hash vẫn khớp.
- Slow không chạy scenario summary_fail hay evidence config; E2E lỗi → retry dẫn đúng lượt 12/11, không cộng vào 24 ca hôm nay. Các regression MSW nằm trong 301 Vitest chạy lại hôm nay.
- API/worker/DB thật, pipeline fake; WAV và tài khoản tổng hợp, micro giả của Chromium. Chưa chứng minh AI thật hay phần cứng thực tế.
- Có **1 cảnh báo os.killpg native Windows** đã biết khi hủy job; ghi nguyên giới hạn, không coi UI/API đạt là chứng minh cleanup subprocess mọi trường hợp.
- Hoàn thành local; **chưa push, mở PR, xác nhận CI hoặc merge** của đợt 13/11. Definition of Done còn cần CI phù hợp và nhóm trưởng merge.
