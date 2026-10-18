# Quy ước gõ transcript tham chiếu và gán nhãn speaker (SH-02)

Cả 3 thành viên cùng làm theo quy ước này. Mỗi file do một người gõ và một người khác soát lại. Người soát ghi tên vào cột `ref_reviewed_by` trong `manifest.csv`.

## 1. Transcript tham chiếu (`refs/<id>.txt`)

- **Mã hóa:** UTF-8, Unicode NFC. Bộ gõ Unikey/EVKey để mặc định là đúng.
- **Bố cục:** mỗi câu hoặc lượt nói một dòng. Không ghi tên speaker, không ghi timestamp.
- **Viết đúng những gì nghe được,** có dấu, có dấu câu bình thường. Không sửa câu cho "hay hơn", không tóm tắt.
- **Từ tiếng Anh và thuật ngữ:** viết đúng chính tả gốc, ví dụ `deploy`, `sprint`, `API`, `upload`. Không phiên âm kiểu "đi-ploi".
- **Số, ngày, giờ:** viết như cách thông thường, ví dụ `25`, `9 giờ 30`, `15/10`. Normalizer sẽ đổi số sang chữ cho cả reference và output của model.
- **Từ đệm** (`ờ`, `à`, `ừm`): cứ ghi lại. Normalizer bỏ chúng theo danh sách công bố.
- **Đoạn không nghe rõ:** ghi `[không rõ]`. Không đoán.
- **Nói chồng lấn:** ghi lời của người nói chính trước, rồi đến người chen vào, mỗi người một dòng.
- **Tiếng ồn, tiếng cười:** không ghi.
- **Tên riêng của người thật trong cuộc họp nội bộ:** ghi như nghe được. File chỉ dùng nội bộ, theo consent form.

## 2. Nhãn speaker (`refs/<id>.rttm`)

Định dạng RTTM chuẩn, mỗi dòng là một lượt nói liên tục của một người:

```text
SPEAKER <id> 1 <start_sec> <duration_sec> <NA> <NA> <speaker> <NA> <NA>
```

Ví dụ:

```text
SPEAKER meet-001 1 0.840 5.360 <NA> <NA> spk1 <NA> <NA>
SPEAKER meet-001 1 6.120 3.050 <NA> <NA> spk2 <NA> <NA>
```

- `start_sec`, `duration_sec` tính bằng giây, 3 chữ số thập phân.
- Tên speaker ẩn danh: `spk1`, `spk2`... theo thứ tự xuất hiện. Không ghi tên thật.
- Các lượt nói được phép chồng lấn nhau.
- Khoảng lặng ngắn hơn 0.5 s giữa hai câu của cùng một người thì gộp thành một lượt.
- Cách làm gợi ý: mở audio bằng Audacity, tạo label track, mỗi lượt nói một label có tên `spk1`/`spk2`, rồi export labels. C sẽ viết script chuyển file label của Audacity sang RTTM.

## 3. Không sửa reference sau khi đã xem output của model

Mọi chỉnh sửa reference sau lần commit đầu phải ghi vào `refs/CHANGELOG.md`: ngày, file, lý do, người sửa. Lý do hợp lệ là gõ sai so với audio, không phải "model nghe khác".

## 4. Đặt tên file

| Loại | Mẫu id | Ví dụ |
|---|---|---|
| Cuộc họp tự ghi | `meet-NNN` | `meet-001` |
| Đoạn cắt từ cuộc họp | `meet-NNN-cK` | `meet-001-c2` |
| Thu thật trong môi trường ồn | `noisy-NNN` | `noisy-003` |
| Clip public | `<nguồn>-<id gốc>` | `fleurs-1921-7702082596424665893` |
