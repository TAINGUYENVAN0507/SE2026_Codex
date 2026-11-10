# Ghi chú đối chiếu tải

- `queuepool/run1..3`: lượt đầu dùng QueuePool mặc định; 60/65/62 request đúng, p95 khoảng 31 giây, nhiều TimeoutError ở đường DB với 100 tác vụ.
- `unwired-option/run1..3`: agent khai báo cờ `--pool null` nhưng chưa truyền vào create_engine. env.json khi đó ghi cờ yêu cầu, không phải pool thực. Giữ dữ liệu lỗi này để công khai sai sót; không coi là kết quả NullPool.
- `run1..3`: đã nối cấu hình vào engine, ghi actual_pool=NullPool và kiểm tra tương ứng. Mỗi lượt 100/100 oracle đúng; p95 1,436/1,380/1,370 giây. Chỉ đổi adapter DB trong harness, không tối ưu production hoặc kết luận PostgreSQL đạt SLA.
- Không trộn các cấu hình thành một phân phối. Dữ liệu tổng hợp seed17017, ASGI TestClient và SQLite, không mạng, auth override. Các file raw.csv, summary.json, env.json giữ kết quả thực tế.
