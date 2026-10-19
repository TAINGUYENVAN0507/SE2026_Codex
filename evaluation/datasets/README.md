# datasets

Dữ liệu dùng để đánh giá ASR, diarization và tóm tắt (AI-10).

| File | Nội dung |
|---|---|
| `manifest.csv` | Mỗi file đánh giá một dòng: nguồn, loại, license, mục đích, điều kiện ghi, consent |
| `sources.json` | Nguồn public tải được tự động, kèm URL và sha256 |
| `download.py` | Tải nguồn trong `sources.json` vào `raw/`, kiểm tra sha256 |
| `check_manifest.py` | Kiểm tra `manifest.csv` trước khi commit |
| `LICENSES.md` | License và hạn chế của từng nguồn |
| `CONVENTIONS.md` | Quy ước gõ transcript tham chiếu và gán nhãn RTTM (SH-02) |
| `consent_form.md` | Mẫu phiếu đồng ý cho các buổi ghi âm của nhóm (SH-01) |
| `refs/` | Transcript tham chiếu `<id>.txt` và nhãn speaker `<id>.rttm` của dữ liệu public, kèm `CHANGELOG.md` |
| `private/` | Audio, transcript, RTTM của cuộc họp nội bộ theo consent, **không commit** (repo public) |
| `raw/` | Audio đã tải, **không commit** |

## Dùng nhanh

```bash
cd evaluation
uv run python datasets/download.py --list
uv run python datasets/download.py fleurs_vi_test_tsv     # khoảng 0.6 MB
uv run python datasets/download.py fleurs_vi_test_audio   # khoảng 544 MB
uv run python datasets/check_manifest.py --check-files
```

## Cột của `manifest.csv`

| Cột | Bắt buộc | Giá trị |
|---|---|---|
| `id` | Có | Chữ thường, số, `-`, `_`. Không trùng. |
| `source` | Có | `fleurs`, `common_voice`, `vivos`, `internal`, `musan` |
| `kind` | Có | `read_speech`, `meeting`, `noisy_real`, `noisy_synthetic`. Report luôn tách riêng từng loại. |
| `split` | Không | Ví dụ `test`, `dev`, `pilot` |
| `audio_path`, `ref_path`, `rttm_path` | `audio_path` bắt buộc | Đường dẫn tương đối từ thư mục `datasets/` |
| `duration_sec` | Có | Số giây, lớn hơn 0 |
| `num_speakers` | Không | Số nguyên ≥ 1 |
| `language` | Có | `vi` |
| `license` | Có | Mã SPDX, ví dụ `CC-BY-4.0`, hoặc `internal-consent` |
| `purpose` | Có | Một hoặc nhiều giá trị `wer`, `der`, `noisy`, `rubric`, `edge`, `demo`, ngăn cách bằng `;` |
| `condition` | Bắt buộc với `noisy_*` | Ví dụ `quán cà phê, micro laptop cách 2 m` |
| `consent_ref` | Bắt buộc với `internal` | Mã phiếu đồng ý, ví dụ `CF-2026-001` |
| `ref_reviewed_by` | Bắt buộc khi có `ref_path` | Tên người soát transcript |
| `notes` | Không | Ghi chú |
