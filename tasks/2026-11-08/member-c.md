# 2026-11-08 · Member C: ADR, canary pipeline, đồng bộ tài liệu, đo tải 239/247 (Đợt 3)

- **Người làm:** C (`@TAINGUYENVAN0507`), nhánh `tainguyen`.
- **Số commit:** 5.
- **Mục tiêu:** ADR 0002; log pipeline không lộ dữ liệu cá nhân; tài liệu khớp hiện trạng; số đo tải thật ở 239 và 247 (RE-018, AD-018).

| # | Việc | Hash |
|---|---|---|
| 1 | [ ] ADR `0002`: adapter boundary và xóa dữ liệu (AI-17, BE-18) | |
| 2 | [ ] Test canary: log pipeline không chứa dữ liệu cá nhân (AI-18) | |
| 3 | [ ] Đồng bộ `README.md`, `structure/`, `rules/` với hiện trạng (G0) | |
| 4 | [ ] Đo tải 239 đồng thời, RE-018 (AI-19) | |
| 5 | [ ] Đo tải 247 đồng thời so với p95 ≤ 2,0 s, AD-018 (AI-19) | |

Lệnh và giới hạn phép đo: [`docs/evidence/vt-018/README.md`](../../docs/evidence/vt-018/README.md). Không ghi hệ thống "chịu được N người dùng": chỉ ghi số đo, môi trường và giới hạn.
