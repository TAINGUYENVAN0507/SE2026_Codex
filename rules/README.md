# rules/

Quy tắc làm việc chung của nhóm. Áp dụng cho mọi thành viên, kể cả code do AI coding assistant sinh ra: người commit chịu trách nhiệm như code tự viết.

Đọc [`structure/`](../structure/README.md) trước để biết thư mục nào của ai và các module nối với nhau thế nào.

## Trước khi bắt đầu code

- [ ] Đã đọc `structure/` và các file trong `rules/`.
- [ ] Đã đọc README của module sắp sửa.
- [ ] Đã đọc file phân công của mình hôm nay: `tasks/<YYYY-MM-DD>/member-<a|b|c>.md` (5 commit mỗi ngày, [`tasks/README.md`](../tasks/README.md)).
- [ ] Biết Task ID đang làm, theo kế hoạch triển khai. Việc nằm ngoài kế hoạch thì hỏi nhóm trưởng để có ID.
- [ ] Đang ở nhánh cá nhân, đã cập nhật theo `main`: `git fetch origin && git merge origin/main`.
- [ ] Việc này đụng contract hoặc thư mục của người khác: đã báo owner hoặc consumer.
- [ ] Chạy được lệnh lint và test của module trên máy mình ([coding.md](coding.md)).

## Trước khi mở PR

- [ ] Lint, format và test của module xanh trên máy.
- [ ] Có test cho thay đổi ([testing.md](testing.md)).
- [ ] Diff không có secret, audio, transcript thật hay dữ liệu cá nhân ([privacy-security.md](privacy-security.md)).
- [ ] README hoặc `docs/` đã cập nhật nếu hành vi thay đổi.
- [ ] Mô tả PR theo template, test evidence là output thật ([git-workflow.md](git-workflow.md)).

## Các file

| File | Nội dung |
|---|---|
| [git-workflow.md](git-workflow.md) | Nhánh, commit, PR, review và merge, CI, tag |
| [coding.md](coding.md) | Ngôn ngữ, đặt tên, công cụ và lệnh kiểm tra của từng module, nguyên tắc viết code |
| [testing.md](testing.md) | Test bắt buộc, dữ liệu test, test evidence, Definition of Done |
| [privacy-security.md](privacy-security.md) | Secret, dữ liệu người dùng và dữ liệu họp, log, ghi âm, gửi dữ liệu ra ngoài |

## Khi các tài liệu nói khác nhau

Theo thứ tự ưu tiên:

1. `rules/` và `structure/` trên `main`.
2. README của module.
3. Kế hoạch triển khai (report 001).

Gặp mâu thuẫn thì báo nhóm trưởng để sửa tài liệu xếp sau, đừng tự chọn một bên rồi làm.

## Đổi quy tắc

Mở PR sửa file trong `rules/`, ghi rõ lý do. Quy tắc mới chỉ có hiệu lực sau khi nhóm trưởng merge và báo cả nhóm.
