# wer

Chấm WER cho output của một lần chạy ASR (AI-11). Dùng cho spike chọn model (AI-01) và mỗi khi đổi model hoặc tham số ASR.

## Chạy

```bash
cd evaluation
uv run python wer/run_wer.py --hyp runs/whisper-small/hyp.jsonl --tag whisper-small-int8 \
  --asr-meta runs/whisper-small/meta.json
```

Kết quả nằm ở `wer/results/<YYYY-MM-DD>_<tag>/`. Sinh lại riêng report:

```bash
uv run python wer/make_report.py wer/results/2026-10-19_whisper-small-int8
```

## Input

| Tham số | Nội dung |
|---|---|
| `--hyp` | JSONL, mỗi dòng `{"id": "<id trong manifest>", "text": "<output của ASR>"}`. Field khác bị bỏ qua. |
| `--tag` | Tên lần chạy: chữ thường, số, `.`, `_`, `-`. |
| `--manifest` | Mặc định `datasets/manifest.csv`. Chỉ chấm dòng có purpose `wer` và có `ref_path`. Manifest phải hợp lệ theo `check_manifest.py`. |
| `--source`, `--kind`, `--split` | Chỉ chấm các dòng khớp. Hypothesis của dòng bị lọc ra thì bỏ qua. |
| `--asr-meta` | JSON mô tả lần chạy ASR, được chép nguyên vào `env.json`. Nên có: `model`, `compute_type`, `device`, `gpu`, `beam_size`, `vad_filter`, các ngưỡng chống hallucination. |
| `--allow-missing` | Sample thiếu hypothesis được chấm như hypothesis rỗng, thay vì báo lỗi. |
| `--out`, `--date`, `--force` | Đổi thư mục kết quả, ngày trong tên thư mục, cho phép ghi đè. |

## Output

| File | Nội dung |
|---|---|
| `per_sample.csv` | Mỗi sample một dòng: số token, hits/S/D/I, WER, CER, WER không dấu, cờ `missing`. Không chứa text. |
| `summary.json` | WER cấp corpus cho **từng `kind`**, kèm bộ lọc đã dùng. |
| `env.json` | Thời điểm chạy, git SHA (và file đã track có bị sửa mà chưa commit không), version Python/jiwer, sha256 của manifest, hypothesis và normalizer, metadata ASR. |
| `report.md` | Bảng tóm tắt, 10 sample nhiều lỗi nhất, môi trường, lệnh chạy lại. Sinh từ ba file trên. |

`per_sample.csv` và `summary.json` chỉ phụ thuộc input, nên chạy lại cho cùng byte.

## Định nghĩa

- Reference và hypothesis đều qua `normalizer/vi_normalize.normalize()` (quy tắc ở `normalizer/RULES.md`).
- **WER** = (S + D + I) / N, với N là số token của reference. Token là chuỗi tách bởi khoảng trắng, xấp xỉ âm tiết.
- **CER**: như WER nhưng tính trên ký tự của text đã chuẩn hóa, kể cả khoảng trắng giữa các token (cùng định nghĩa với jiwer).
- **WER không dấu**: WER sau khi bỏ dấu cả hai bên. Chỉ dùng để chẩn đoán lỗi thanh điệu.
- **Cấp corpus**: cộng số lỗi và số token của mọi sample rồi mới chia. Trung bình WER của từng sample được báo riêng.
- Reference rỗng: WER không định nghĩa được, ghi rỗng trong CSV và `null` trong JSON.
- Căn chỉnh dùng jiwer (Levenshtein của rapidfuzz).

## Quy tắc để số liệu trung thực

- Sample thiếu hypothesis là lỗi. Không âm thầm bỏ file khó để WER đẹp hơn. Nếu ASR lỗi trên một file, chạy với `--allow-missing` để file đó được tính là toàn lỗi xóa.
- Không gộp các `kind` thành một con số: giọng đọc (`read_speech`) không đại diện cho cuộc họp.
- Chạy trên code đã commit, để git SHA trong `env.json` đủ để tái tạo. Report cảnh báo khi code có thay đổi chưa commit.
- Commit cả thư mục kết quả (vài KB). Không sửa tay file kết quả. Muốn sửa thì chạy lại.
- Không sửa reference sau khi đã xem output của model (`datasets/CONVENTIONS.md`, mục 3).
- Kết quả không chứa text của transcript, vì dữ liệu họp nội bộ chỉ được dùng theo consent.
