# License của dữ liệu đánh giá

Kiểm tra lại license trên trang gốc mỗi khi tải. Bảng này ghi điều kiện nhóm đã đọc lúc thêm nguồn.

| Nguồn | License | Trang gốc | Được dùng cho | Hạn chế |
|---|---|---|---|---|
| FLEURS (`vi_vn`) | CC BY 4.0 | https://huggingface.co/datasets/google/fleurs | WER trên giọng đọc sạch, nền cho noisy synthetic | Phải ghi nguồn (xem bên dưới). Đây là giọng đọc, không đại diện cho hội thoại họp. |
| Common Voice (vi) | CC0 | https://commonvoice.mozilla.org/vi/datasets | WER, đa dạng giọng | Phải tự tải trên trang Mozilla (cần đồng ý điều khoản). Không được tìm cách xác định danh tính người đọc. |
| VIVOS | CC BY-NC-SA 4.0 | https://huggingface.co/datasets/AILAB-VNUHCM/vivos (trang cũ ailab.hcmus.edu.vn/vivos không truy cập được ngày 2026-10-18) | WER, chỉ cho mục đích học thuật | **Phi thương mại.** Không dùng trong demo công khai. Sản phẩm phái sinh phải cùng license. |
| MUSAN (nhiễu) | Tùy từng phần, kiểm tra từng thư mục | https://www.openslr.org/17/ | Tạo dữ liệu noisy synthetic | Chỉ dùng phần có license cho phép, ghi rõ phần đã dùng. |
| Cuộc họp tự ghi (SH-01) | Theo consent form | — | WER hội thoại, DER, noisy thật, rubric | Mặc định chỉ dùng nội bộ. **Không commit audio, không phân phối.** |

Hiện mới có checksum cho FLEURS trong `sources.json`. Các nguồn khác phải tải thủ công, sau đó ghi vào `manifest.csv`.

## Ghi nguồn FLEURS

> FLEURS: Few-shot Learning Evaluation of Universal Representations of Speech. Conneau et al., 2022. https://arxiv.org/abs/2205.12446. Dữ liệu dùng theo CC BY 4.0, không chỉnh sửa nội dung audio ngoài việc chuyển định dạng và thêm nhiễu cho bộ noisy synthetic.

## Quy tắc chung

- Không commit audio, trừ fixture test nhỏ có license cho phép (tổng dưới 5 MB).
- Audio tải về nằm trong `datasets/raw/` (đã ignore).
- Mỗi file dùng để đánh giá phải có một dòng trong `manifest.csv`, chạy `check_manifest.py` trước khi commit.
