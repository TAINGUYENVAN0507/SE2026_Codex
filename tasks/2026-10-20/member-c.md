# 2026-10-20 · Member C: pipeline, evaluation, nhóm trưởng

- **Người làm:** C (`@TAINGUYENVAN0507`), nhánh `tainguyen`.
- **Mục tiêu:** spike ASR (AI-01) để có số liệu cho Gate G1.
- **Trạng thái:** đã xong cả 5 commit, merge vào `main` qua PR #4 (merge commit `cc5ec25`), CI `evaluation` xanh với 151 test pass.

## 5 commit

### 1. [x] Tập con FLEURS cố định trong manifest (AI-10)

- `datasets/import_fleurs.py`: 40 câu FLEURS vi test (seed 2026, mỗi câu một clip, 9.0 phút), ghi `manifest.csv` và `refs/`.
- **Hash:** `4cd8c4b`

### 2. [x] Script chạy spike ASR (AI-01)

- `spikes/asr/run_asr.py`: chạy một cấu hình faster-whisper, ghi `hyp.jsonl` và `meta.json`. Có dependency group `asr-spike`; audio được decode bằng ffmpeg.
- **Hash:** `268873e`

### 3. [x] Output ASR của 3 cấu hình (AI-01)

- `small` int8, `medium` int8, `large-v3-turbo` int8_float16 trên GTX 1650 Ti. 40/40 file không lỗi.
- **Hash:** `2073be9`

### 4. [x] Sửa cờ `dirty` trong `env.json` (AI-11)

- Không tính file chưa track, để kết quả của lần chấm trước không làm lần sau bị báo "chạy trên code chưa commit".
- **Hash:** `3f0edb8`

### 5. [x] Kết quả WER và đề xuất ADR-0001 (AI-01)

- WER trên 40 câu: `small` 19.21 %, `medium` 9.46 %, `large-v3-turbo` 6.66 %. `docs/adr/0001-asr.md` ở trạng thái Đề xuất.
- **Hash:** `bc832c5`

## Việc của nhóm trưởng (không tính vào 5 commit)

- [ ] Review và merge PR #5 (FE-01 của A), sau khi A gỡ xong conflict `.gitignore`.
- [ ] Review và merge PR backend của B (BE-01, BE-02 v0).
- [ ] Xem lại contract v0 của B ở phía pipeline: mã lỗi trong `errors.py` phải có mặt trong `contracts/error_codes.md` khi B tạo file này.

## Chuyển sang ngày sau

- Spike diarization (AI-02) bằng pyannote `community-1`. Model đã có trong HF cache của máy C.
- Chạy lại spike ASR trên audio họp pilot khi có SH-01, SH-02 (cả nhóm ghi âm có consent), rồi chốt ADR-0001 ở G1.
