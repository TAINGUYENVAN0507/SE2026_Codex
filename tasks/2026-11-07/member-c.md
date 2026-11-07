# 2026-11-07 · Member C: VT-018 (Đợt 2)

- **Người làm:** C (`@TAINGUYENVAN0507`). 5 commit trên `tainguyen-vt018-tests`, xếp trên `tainguyen-vt018` (PR #35).
- **Mục tiêu:** pairwise, mutation, tải 40 đồng thời, coverage và flaky cho BT3.

| # | Việc | Hash |
|---|---|---|
| 1 | [x] Pairwise 20 ca cho `POST /meetings/{id}/jobs` (BE-17) | `95ce14d` |
| 2 | [x] `Job.can_retry` dùng chung và test biên 3/3 (BE-17) | `64ce5df` |
| 3 | [x] Script mutation `>` → `>=`; một mutant sống sót rồi được bắt (BE-17) | `4d6721b` |
| 4 | [x] Harness tải 40 client; sửa engine DB dùng chung (AI-19) | `992fe76` |
| 5 | [x] Coverage, flaky, README chạy test (BE-17) | `7654790` |

Kết quả và cách chạy lại: [`docs/evidence/vt-018/README.md`](../../docs/evidence/vt-018/README.md).

## Còn lại cho BT3 (việc cá nhân, không commit)
- [ ] Bước 0 của hôm qua: plan AI trước code, test AI thô, bác bỏ ≥ 2 điểm, xóa/sửa ≥ 2 test yếu, lưu ở `reports/bt3/`.
- [ ] Mở PR `tainguyen-vt018-tests` vào `tainguyen-vt018` hoặc vào `main` sau khi #35 merge.
- [ ] Reflection 250–350 từ, tự viết.
