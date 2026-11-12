# VT-018 · AI sinh test, nhóm xóa hoặc sửa test yếu (2026-11-12)

Đọc theo thứ tự:

| File | Nội dung |
|---|---|
| `00-prompt.md` | Prompt nguyên văn, công cụ, code đích (`d9c2d50`) |
| `01-plan-raw.md` | Plan của AI, commit trước khi có test |
| `backend/tests/ai_raw/vt018_ai_raw.py` | Test thô, giữ nguyên như AI viết (không nằm trong bộ test mặc định) |
| `02-raw-run.log` | Lần chạy đầu: 44 passed, 1 failed (test sai, không phải app sai) |
| `mutants.json` | 24 mutant, đặt theo quy tắc trước khi chạy ma trận |
| `03-mutation-matrix.md` | Ma trận trên bản thô: 18/24 mutant bị giết; ứng viên test yếu và bằng chứng |
| `04-review.md` | Sửa 4, xóa 5, thêm 1; ma trận trên bản đã review: 24/24; giới hạn |
| `backend/tests/unit/test_vt018_ai_reviewed.py` | Bản đã review, có chú thích `REVIEW:` ở từng chỗ đổi |

Lệnh ma trận (từ gốc repo, working tree sạch):

```bash
python3 scripts/mutation_matrix.py docs/evidence/vt-018/ai-tests/mutants.json --cwd backend \
  --tests tests/unit/test_vt018_ai_reviewed.py --out /tmp/matrix.json
```

Commit theo thứ tự: plan `6c764ba` → test thô `1ed5df0` → ma trận `a045ed7` → review `3617a0b`.
