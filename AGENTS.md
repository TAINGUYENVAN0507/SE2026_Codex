# AGENTS.md

Hướng dẫn cho AI coding assistant (Codex, Claude Code, Cursor,Antigravity…) khi làm việc trong repo này.

## Trước khi sửa code

1. Đọc `structure/README.md`, `structure/repository.md`, `structure/architecture.md`, `structure/contracts.md`.
2. Đọc `rules/README.md` và các file còn lại trong `rules/`.
3. Đọc file phân công trong ngày của người dùng: `tasks/<YYYY-MM-DD>/member-<a|b|c>.md`. Làm đúng các commit được giao, tick việc đã xong và ghi hash commit vào file đó.
4. Đọc README của module sắp sửa.

## Quy tắc tối thiểu

Chi tiết nằm trong `rules/`. Khi nghi ngờ, theo `rules/` và hỏi người dùng.

- Chỉ sửa trong module của task. Không vượt ranh giới module ghi trong `structure/architecture.md`.
- Không sửa tay file được sinh ra: `contracts/pipeline/*`, `contracts/openapi.json`. Sửa nguồn rồi sinh lại.
- Commit theo format `<type>(<scope>): <mô tả bằng tiếng Anh> (<TaskID>)`, thân commit bằng tiếng Việt.
- Chạy lint và test của module (`rules/coding.md`) trước khi commit. Báo kết quả thật, không đoán.
- Repo là public: không commit secret, audio, transcript cuộc họp hay dữ liệu cá nhân (`rules/privacy-security.md`).
- Không push vào `main`, không force-push. PR vào `main` do nhóm trưởng review và merge.
- Comment, docstring và tài liệu viết bằng tiếng Việt có dấu. Tên trong code bằng tiếng Anh.
- Không bịa số liệu đánh giá hay benchmark.
