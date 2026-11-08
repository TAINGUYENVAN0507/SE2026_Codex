# 2026-11-08 · Member C: ADR, canary pipeline, đồng bộ tài liệu, đo tải 239/247 (Đợt 3)

- **Người làm:** C (`@TAINGUYENVAN0507`), nhánh `tainguyen`.
- **Số commit:** 5.
- **Mục tiêu:** ADR 0002; log pipeline không lộ dữ liệu cá nhân; tài liệu khớp hiện trạng; số đo tải thật ở 239 và 247 (RE-018, AD-018).

| # | Việc | Hash |
|---|---|---|
| 1 | [x] ADR `0002`: adapter boundary và xóa dữ liệu (AI-17, BE-18) | `18fbfd1` |
| 2 | [x] Test canary: log pipeline không chứa dữ liệu cá nhân (AI-18). Tìm ra rò thật: stderr của stage bị chép vào log DEBUG; đã sửa | `b266800` |
| 3 | [x] Đồng bộ `README.md`, `structure/`, `rules/` với hiện trạng (G0) | `51c5588` |
| 4 | [x] Đo tải 239 đồng thời, RE-018 (AI-19). **Không đạt**: 101 lỗi 500 do cạn pool DB; sửa harness bị treo | `e1165c9` |
| 5 | [x] Đo tải 247 so với p95 ≤ 2,0 s, AD-018 (AI-19). **Không đạt** (p95 63,3 s); pool cấu hình được, quá tải trả 503 thay vì 500 | `8166dc1` |

Lệnh và giới hạn phép đo: [`docs/evidence/vt-018/README.md`](../../docs/evidence/vt-018/README.md). Không ghi hệ thống "chịu được N người dùng": chỉ ghi số đo, môi trường và giới hạn.

## Kết quả và điều còn mở
- Cả hai lần đo tải **không đạt** mục tiêu. Số đo, nguyên nhân đã biết và giả thuyết chưa kiểm ở [`docs/evidence/load-239/analysis.md`](../../docs/evidence/load-239/analysis.md) và [`load-247/analysis.md`](../../docs/evidence/load-247/analysis.md). Chưa biết vì sao upload mất ~63 s ở 247 client.
- 40 client vẫn đạt sau khi đổi pool (p95 0,86 s, một lần chạy; lần trước 0,67 s).
- Đợt 2 của C (5 commit, PR #37) đã bị bỏ sót khỏi `main` vì #37 merge vào nhánh `tainguyen-vt018` sau khi #35 đã vào `main`. PR hôm nay gộp lại bằng merge commit từ `origin/tainguyen-vt018`.
- Chuyển sang ngày sau: B profile `POST /meetings` và thử nhiều worker uvicorn; đo lại 247. DER chưa làm (chưa có SH-01).
