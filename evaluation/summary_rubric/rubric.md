# Rubric chấm tóm tắt cuộc họp (AI-14)

Dùng để chấm output của stage `summarize` (prompt `summary-v1` trở đi). A và B chấm **độc lập**, mỗi cuộc họp 2 người chấm (SH-04). C tính độ đồng thuận bằng `agreement.py`.

## Cách chấm

1. Mở cuộc họp trên app. Nghe hoặc đọc **toàn bộ** transcript trước khi đọc tóm tắt. Nếu transcript sai nhiều thì sửa transcript trước, rồi chạy "Tạo lại tóm tắt", để điểm phản ánh chất lượng tóm tắt chứ không phải lỗi ASR.
2. Chấm từng tiêu chí theo thang 1–5 dưới đây. Mức 2 và 4 nằm giữa hai mức có mô tả. Không chắc giữa hai mức thì chọn mức thấp hơn.
3. Không trao đổi điểm với người chấm kia trước khi cả hai đã nộp.
4. Ghi một dòng cho mỗi cuộc họp vào `ratings.csv`.
   - **Không** chép câu nào từ transcript hay tóm tắt vào CSV hoặc cột `notes`, vì dữ liệu họp nội bộ chỉ dùng theo consent.
   - `notes` chỉ ghi loại lỗi, ví dụ "bịa hạn chót", "thiếu 1 quyết định", "evidence trỏ sai đoạn".

| Cột | Giá trị |
|---|---|
| `meeting_id` | id trong `datasets/manifest.csv` (ví dụ `meet-001`) |
| `rater` | `A` hoặc `B` |
| `prompt_version` | `prompt_version` trong summary (ví dụ `summary-v1`) |
| `coverage` … `language` | số nguyên 1–5 |
| `notes` | tùy chọn, không chứa nội dung cuộc họp |

## Tiêu chí

### `coverage`: đầy đủ

Tóm tắt có các ý chính của cuộc họp không.

| Điểm | Mô tả |
|---|---|
| 5 | Có mọi chủ đề chính và mọi ý quan trọng. Không có chủ đề nào mà người dự họp sẽ nói "sao không ghi cái này". |
| 3 | Có phần lớn ý chính, thiếu 1–2 ý quan trọng hoặc gộp quá mức làm mất ý. |
| 1 | Thiếu phần lớn nội dung, hoặc chỉ ghi chung chung ("nhóm thảo luận về dự án"). |

### `faithfulness`: đúng sự thật, không bịa

Mọi điều trong tóm tắt có căn cứ trong transcript không. Đây là tiêu chí quan trọng nhất: một chi tiết bịa (người, số, ngày) làm tóm tắt không dùng được.

| Điểm | Mô tả |
|---|---|
| 5 | Mọi câu đều có căn cứ. Không có tên, số, ngày hay kết luận nào do model tự suy ra. |
| 3 | Có 1 chi tiết không có căn cứ hoặc sai nhẹ (diễn đạt mạnh hơn lời nói gốc, ghép nhầm hai ý). |
| 1 | Có thông tin bịa ảnh hưởng tới quyết định hoặc việc cần làm (người nhận việc, hạn chót, con số). |

### `decisions`: quyết định

Các quyết định đã chốt có được ghi đúng không, và có bị nhầm với ý kiến chưa chốt không.

| Điểm | Mô tả |
|---|---|
| 5 | Ghi đủ và đúng mọi quyết định. Không ghi ý kiến hay đề xuất chưa chốt như thể đã quyết. Cuộc họp không có quyết định thì danh sách trống. |
| 3 | Thiếu 1 quyết định, hoặc có 1 đề xuất chưa chốt bị ghi là quyết định. |
| 1 | Thiếu phần lớn quyết định, hoặc ghi sai nội dung quyết định. |

### `action_items`: việc cần làm

Mỗi việc có đúng nội dung, người nhận và hạn chót không. Người nhận và hạn chót chỉ được điền khi có trong transcript; để trống khi không có căn cứ là **đúng**.

| Điểm | Mô tả |
|---|---|
| 5 | Đủ mọi việc được giao. Người nhận và hạn đúng, hoặc để trống khi không ai nói. Hạn tương đối ("thứ Sáu tuần này") được đổi đúng thành ngày theo ngày họp. Mục nào thiếu căn cứ thì có cờ "Cần kiểm tra". |
| 3 | Thiếu 1 việc, hoặc 1 việc sai người nhận, sai hạn, hoặc có hạn do model tự đặt. |
| 1 | Thiếu phần lớn việc, hoặc nhiều việc bị bịa người nhận hoặc hạn chót. |

### `evidence`: dẫn chứng

Click vào evidence của từng mục có tua tới đúng đoạn transcript nói về điều đó không.

| Điểm | Mô tả |
|---|---|
| 5 | Mọi mục có evidence, và evidence trỏ đúng đoạn. |
| 3 | Vài mục không có evidence hoặc trỏ tới đoạn gần đúng (lệch 1–2 đoạn). |
| 1 | Phần lớn evidence thiếu hoặc trỏ sai đoạn. |

### `language`: tiếng Việt

Tóm tắt có dễ đọc, ngắn gọn, đúng thuật ngữ không.

| Điểm | Mô tả |
|---|---|
| 5 | Tiếng Việt tự nhiên, ngắn gọn, không lặp. Thuật ngữ (kể cả tiếng Anh như API, deadline, sprint) dùng như người trong nhóm dùng. Tên người viết đúng. |
| 3 | Đọc hiểu được nhưng dài dòng, lặp ý, hoặc có câu dịch máy, sai chính tả tên riêng. |
| 1 | Khó hiểu, sai ngữ pháp nhiều, hoặc lẫn ngôn ngữ không cần thiết. |

## Độ đồng thuận

```bash
cd evaluation
uv run python summary_rubric/agreement.py summary_rubric/ratings.csv --tag summary-v1
```

Theo từng tiêu chí, script tính:
- tỉ lệ cặp điểm trùng nhau;
- tỉ lệ cặp lệch không quá 1 điểm;
- độ lệch tuyệt đối trung bình;
- điểm trung bình của từng người chấm.

Tiêu chí nào có tỉ lệ lệch không quá 1 điểm dưới 80 % thì A và B cùng đọc lại mô tả của tiêu chí đó và thống nhất cách hiểu. **Không sửa điểm đã nộp**: nếu chấm lại thì lưu sang file mới (ví dụ `ratings_round2.csv`).
