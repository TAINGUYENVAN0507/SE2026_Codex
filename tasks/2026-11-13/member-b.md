# 2026-11-13 · Member B: sửa `GET summary` trả `pending` khi cuộc họp `partial` (Đợt 8, đóng băng bằng chứng)

- **Người làm:** B (`@minhquangha`), nhánh `haquang`.
- **Số commit:** 3.
- **Điều kiện bắt đầu:** #54 (việc 11-12 của B) đã vào `main`. B chưa mở PR cho nhánh `haquang` ngày 11-12; nhóm trưởng mở thay (#54) và merge khi CI xanh. **Từ nay mở PR khi push xong.**
- **Hạn:** mở PR trong ngày 11-13. Ngày 11-14 nộp bài.

## Bước 0
```bash
git checkout haquang && git fetch origin && git merge origin/main
```

## Việc

### 1. [x] `GET /meetings/{id}/summary` trả `failed` khi meeting `partial` và chưa có row Summary (G0, BE-05)
- Lỗi A báo ở #53: `backend/app/api/v1/summary.py:65` chỉ coi `meeting.status == "failed"` là lỗi, nên meeting `partial` (transcript xong, tóm tắt lỗi) trả `pending` mãi. Frontend đã vá tạm bằng `summaryFailed`, API gốc vẫn sai.
- Test đỏ trước trong `backend/tests/api/`: meeting `partial`, không có Summary → `status == "failed"`. Ghi log đỏ vào `docs/evidence/final/summary-partial-red-2026-11-13.log`, rồi sửa. Kiểm `openapi.json` không drift (`status` đã có `failed`).
- **Commit:** `08a7cad`
- **Message:** `fix(backend): report failed summary for partial meetings (G0, BE-05)`

### 2. [x] Bằng chứng xóa dữ liệu dùng được trên GitHub (AD-018)
- Nhóm trưởng sẽ đổi `docs/evidence/ad-018/deletion-2026-11-12.log` sang UTF-8 và đối chiếu bảng trong `docs/evidence/ad-018/README.md` với assert thật (PR của C ngày 11-13). B đọc lại bảng sau khi C sửa: dòng nào C ghi "chưa có test" mà thật ra có test thì chỉ ra test và dòng assert.
- Đã đối chiếu toàn bộ bảng trong `docs/evidence/ad-018/README.md`: **0 sai**. Bảng phản ánh chính xác hiện trạng kiểm thử thực tế (log file Docker và uvicorn access chưa có test assert). Không tạo commit.

### 3. [x] Tick, hash (G0)
- Ghi hash từng commit. Hash của chính commit này không ghi được trong commit đó (11-12 ghi `f9adce1` nhưng commit thật là `2ff21e5`), ghi "commit này".
- **Commit:** commit này
- **Message:** `docs(tasks): record 2026-11-13 member B results (G0)`
