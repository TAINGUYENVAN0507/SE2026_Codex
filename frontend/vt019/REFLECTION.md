# Reflection VT-019

Confidence của tôi tăng lên khi test đầu tiên thất bại đúng hành vi thiếu: sửa transcript rồi chờ nhưng chưa có request tự lưu. Sau patch, cùng test đó pass. Quan trọng hơn, tôi điều khiển response A hoàn tất sau khi textbox đã chứa C; test kiểm tra C vẫn còn và request tiếp theo dùng version mới. Oracle này xuất phát từ yêu cầu bảo vệ dữ liệu mới, không phụ thuộc tên biến hay cấu trúc hàng đợi do AI chọn.

Mutation làm rõ giá trị của negative tests. Khi bỏ validation độ dài, ba trường hợp rỗng, khoảng trắng và quá giới hạn đều thất bại. Coverage cao không tự chứng minh điều này. Tôi còn chạy lại test theo ba thứ tự cố định và kiểm tra timer, cleanup, shared state. Hai test Chromium xác nhận thao tác người dùng và hai tab với HTTP giả lập. Tuy vậy, fixture CAS chỉ mô phỏng contract; nó chưa chứng minh transaction PostgreSQL xử lý cạnh tranh đúng.

Điều chưa được chứng minh là tải thực của hệ thống. Harness tạo đủ 120 request đang chờ, nhưng adapter cố ý trì hoãn 20 ms và không chạy mạng, xác thực hay database. Vì thế p95 đo được chỉ là evidence cho controller. Draft đang giữ trong RAM cũng có thể mất khi refresh trước khi gửi. AI còn dễ đề nghị tự lấy version mới rồi retry 409, hoặc đánh giá test tốt chỉ vì nhiều dòng được chạy; cả hai cần được phản biện.

Test tiếp theo có giá trị cao nhất là chạy hai trình duyệt với API và PostgreSQL thật, ép cùng version tại điểm UPDATE, rồi xác nhận một bản được lưu, bản kia nhận 409 và audit không trùng. Tôi sẽ ưu tiên test này trước khi khẳng định autosave sẵn sàng cho production.
