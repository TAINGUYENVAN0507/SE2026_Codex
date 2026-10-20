## Mục đích

<!-- Task ID và lý do. Ví dụ: AI-08, stage merge thật để có transcript cho M2. -->

Task:

## Thay đổi chính

| Phần | Nội dung |
|---|---|
| | |

## Cần người khác xem

<!-- Contract bị đổi, file trong thư mục của người khác, quyết định nhóm cần biết. Tag owner hoặc consumer. Không có thì ghi "Không". -->

## Test evidence

<!-- Lệnh đã chạy và output thật. Ví dụ: cd pipeline && uv run pytest -m "not model" → 176 passed -->

```text
```

## Chưa làm

<!-- Phần còn thiếu so với acceptance criteria, giới hạn đã biết. -->

## Checklist

- [ ] Đã đọc `structure/` và `rules/`; PR không vượt ranh giới module
- [ ] Mỗi commit theo format `<type>(<scope>): ... (<TaskID>)`
- [ ] Lint, format và test của module xanh trên máy; có test cho thay đổi
- [ ] Đổi contract: đã sinh lại file, tăng `schema_version` nếu cần, consumer đã xác nhận trong PR
- [ ] Không có secret, audio, transcript thật hay dữ liệu cá nhân trong diff và log
- [ ] Đã cập nhật README hoặc `docs/` nếu hành vi thay đổi
