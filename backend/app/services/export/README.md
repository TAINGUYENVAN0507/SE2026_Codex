# Module export (FE-15)

Owner: A; B review việc gọi từ router. Hàm thuần `MeetingExport -> bytes` không
đọc DB, file hoặc mạng. Router của B tập hợp DTO, xác thực owner và transcript
ready trước khi gọi. Không đưa ORM, password, đường dẫn audio vào DTO.

`to_json(dto, variant)` xuất schema 1.0, UTF-8, thứ tự key cố định; speaker được
sắp theo ID, segment theo thời gian/ID, công việc theo ID. Không thêm timestamp
thời điểm tải. `ai_original` dùng text/speaker AI, tên speaker mặc định và summary
AI. Công việc người dùng thêm hoặc thiếu AI original không có trong bản AI gốc;
trạng thái công việc AI gốc là open. Không fallback sang nội dung đã sửa.

Sinh schema (từ `backend/`): `uv run python -m app.services.export`.
Kiểm drift: `uv run python -m app.services.export --check`.
CLI là nơi duy nhất đọc/ghi schema, không nằm trong serializer.

Test: `uv run pytest tests/unit/test_export*.py`. `jsonschema` (MIT, dev dependency)
xác nhận output hợp lệ theo schema; fixture golden chỉ chứa dữ liệu mẫu tự viết.
Endpoint export hiện là stub của B; module này không tự query DB hoặc thay router.
