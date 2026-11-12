# Prompt cho AI sinh test (VT-018)

- **Ngày:** 2026-11-12, trước khi có test nào trong thư mục này.
- **Công cụ:** Claude Code, model Claude Opus 5.5 (`claude-opus-5-5`). Người giao: C.
- **Code đích:** `main` tại `d9c2d50`.

Prompt, nguyên văn:

> Sinh bộ test pytest cho phần retry và hàng đợi job của backend: `backend/app/worker/retry.py`, `backend/app/worker/queue.py`, `backend/app/worker/reaper.py` và `Job.can_retry` trong `backend/app/db/models/job.py`. Rủi ro cần nhắm tới (VT-018): retry tạo bản ghi trùng, job vượt số lần thử tối đa, job treo không bao giờ được thu hồi. Chỉ đọc code đích, không đọc các test có sẵn. Không sửa code app. Viết một lần vào `backend/tests/unit/test_vt018_ai_raw.py`, chạy một lần, không sửa lại sau khi chạy: bản này là bản thô để nhóm đánh giá. Trước khi viết, ghi plan.

Plan AI trả lời nằm ở `01-plan-raw.md`, test ở `backend/tests/unit/test_vt018_ai_raw.py`, log chạy ở `02-raw-run.log`.
