# Quy tắc chuẩn hóa text khi tính WER

`vi_normalize.normalize()` áp dụng **giống hệt** cho reference và hypothesis, theo đúng thứ tự dưới đây. Mỗi quy tắc có test trong `tests/test_vi_normalize.py`. Đổi quy tắc nghĩa là đổi cách tính WER, nên phải ghi changelog ở cuối file và chạy lại mọi report.

## 1. Unicode và chữ thường

- Đưa về Unicode **NFC**. Text gõ bằng bộ gõ khác nhau (NFC/NFD) cho cùng kết quả.
- Chuyển về chữ thường.

## 2. Bỏ tag chú thích

Bỏ mọi đoạn trong ngoặc vuông, ví dụ `[không rõ]` (quy ước gõ reference, xem `datasets/CONVENTIONS.md`).

## 3. Số, ngày, giờ, phần trăm

Chuyển sang chữ bằng hàm cố định `num_to_words()`, không dùng thư viện ngoài để kết quả không đổi theo version.

| Dạng viết | Đọc thành | Ví dụ |
|---|---|---|
| Số nguyên | Cách đọc chuẩn | `25` → `hai mươi lăm`, `105` → `một trăm linh năm`, `21` → `hai mươi mốt` |
| Bắt đầu bằng 0 | Đọc từng chữ số | `0912` → `không chín một hai` |
| Lớn hơn 999.999.999.999 | Đọc từng chữ số | |
| Dấu chấm phân cách hàng nghìn | Bỏ dấu chấm | `1.000.000` → `một triệu` |
| Dấu phẩy thập phân | `phẩy` | `3,5` → `ba phẩy năm` |
| Dấu chấm với 1–2 chữ số sau | `chấm` | `2.5` → `hai chấm năm` |
| `%` | `phần trăm` | `25%` → `hai mươi lăm phần trăm` |
| `9h`, `9h30`, `9:30` | `<giờ> giờ <phút>` | `9h30` → `chín giờ ba mươi`; `10:00` → `mười giờ` |
| `d/m/yyyy` | `<d> tháng <m> năm <yyyy>` | `15/10/2026` → `mười lăm tháng mười năm hai nghìn hai mươi sáu` |
| `d/m` | `<d> tháng <m>` | `15/10` → `mười lăm tháng mười` |

Không thêm chữ "ngày" hay "phút": nếu người nói có nói thì chữ đó nằm sẵn trong text.

Số dính liền chữ cái (`mp3`, `4G`, `v2`) giữ nguyên ở dạng chữ thường.

## 4. Gom các cách đọc số về một dạng

Chỉ áp dụng trong ngữ cảnh số, để không đụng tới từ thường như "tư vấn", "thứ tư", "số lẻ".

| Biến thể | Dạng chuẩn | Điều kiện |
|---|---|---|
| `tư` | `bốn` | Sau `mươi` (`hai mươi tư`) hoặc sau `tháng` (`tháng tư`) |
| `một` | `mốt` | Sau `mươi` (`hai mươi một` → `hai mươi mốt`) |
| `nhăm` | `lăm` | Sau `mươi` hoặc `mười` |
| `lẻ` | `linh` | Sau `trăm`/`nghìn`/`triệu`/`tỷ` và trước một chữ số |
| `giêng` | `một` | Sau `tháng` |
| `không trăm` | bỏ | Sau `nghìn`/`triệu`/`tỷ`, khi theo sau là phần số còn lại: `hai nghìn không trăm hai mươi bốn` = `hai nghìn hai mươi bốn` |

## 5. Bỏ dấu câu và ký hiệu

- `-`, `/`, `_` và các loại gạch ngang đổi thành khoảng trắng: `front-end` → `front end`.
- Mọi ký tự Unicode thuộc nhóm P (dấu câu) và S (ký hiệu) bị bỏ.

## 6. Kiểu đặt dấu thanh

Đưa về **kiểu cũ** (dấu trên nguyên âm đầu với âm tiết mở `oa`, `oe`, `uy`), vì đây là kiểu phổ biến nhất trong văn bản và output của Whisper:

- `hoà` → `hòa`, `khoẻ` → `khỏe`, `thuỷ` → `thủy`, `uỷ ban` → `ủy ban`.
- Không đổi khi có phụ âm cuối (`hoàng`, `toán`, `khuyết`) hoặc với `qu` (`quý`, `quỷ`).

## 7. Biến thể chính tả

| Biến thể | Dạng chuẩn |
|---|---|
| `ngàn` | `nghìn` |
| `tỉ` | `tỷ` |
| `kĩ` | `kỹ` |
| `lí` | `lý` |
| `mĩ` | `mỹ` |
| `sỹ` | `sĩ` |

## 8. Lexicon thuật ngữ (`lexicon.tsv`)

Ánh xạ cách viết phiên âm sang dạng gốc tiếng Anh, ví dụ `a pi ai` → `api`, `ô kê` → `ok`. Từ tiếng Anh khác giữ nguyên chính tả gốc ở dạng chữ thường.

**Không** thêm lỗi nhận dạng của model vào lexicon (ví dụ `áp lốt` → `upload`), vì như vậy là che lỗi và làm WER đẹp giả.

## 9. Bỏ từ đệm

Danh sách cố định: `ờ`, `ơ`, `à`, `ừm`, `ưm`, `hừm`, `uhm`, `um`, `hmm`.

`ừ` **không** bị bỏ vì thường mang nghĩa đồng ý ("ừ, được").

## 10. Tách token

Token là chuỗi tách bởi khoảng trắng, xấp xỉ âm tiết. Không dùng word segmentation.

## 11. WER không dấu

`strip_diacritics()` bỏ dấu thanh và dấu phụ (`đ` → `d`) **sau khi** đã chuẩn hóa. WER không dấu chỉ dùng để chẩn đoán lỗi thanh điệu, không thay cho WER chính.

## Giới hạn đã biết

- `d/m` luôn được đọc là ngày, nên phân số `1/2` thành `một tháng hai`.
- Phân số Unicode (`½`, `¾`) và số dính phân số (`29¾`) được giữ nguyên.
- Số La Mã, đơn vị viết tắt (`km`, `kg`) và ký hiệu tiền tệ (`$`, `€`) không được đọc thành chữ; ký hiệu bị bỏ.
- Đã thử trên 857 câu FLEURS `vi_vn` test: `normalize(câu gốc)` trùng với `normalize(cột normalized của FLEURS)` ở cả 857 câu (ngày 2026-10-18). Đây chỉ là kiểm tra tính nhất quán, không phải đánh giá ASR.

## Changelog

| Ngày | Thay đổi | Người |
|---|---|---|
| 2026-10-18 | Phiên bản đầu | C |
