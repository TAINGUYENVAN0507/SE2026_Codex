# 2026-10-21 · Member C: pipeline, nhóm trưởng

- **Người làm:** C (`@TAINGUYENVAN0507`), nhánh `tainguyen`.
- **Số commit:** 5.
- **Mục tiêu:** làm stage `vad` và `asr` thật (AI-06, critical path tới M2) theo đề xuất trong `docs/adr/0001-asr.md`: `large-v3-turbo` int8_float16, beam 5, `condition_on_previous_text=False`.
- **Vì sao chưa làm AI-02:** spike diarization cần audio họp nhiều người có RTTM (SH-01, SH-02). Hiện chưa có.

Đọc trước: `pipeline/README.md`, [`structure/architecture.md`](../../structure/architecture.md) (mục Pipeline, ranh giới: dịch vụ ngoài đi qua adapter có bản fake), `docs/adr/0001-asr.md`.

Lệnh kiểm tra cho mọi commit, chạy trong `pipeline/`:

```bash
uv run ruff check . && uv run ruff format --check . && uv run pytest -m "not model"
uv run python -m meeting_pipeline export-contracts --check
```

## 5 commit

### 1. [ ] Chuẩn hóa timestamp của ASR (AI-06)

- **Việc:** hàm thuần trong `stages/asr_post.py` nhận segment thô của engine: clamp vào `[0, duration]`, làm tròn ms, bảo đảm `start < end`, word sắp xếp và nằm trong `[0, duration]`, bỏ segment rỗng, sắp segment theo thời gian. Output luôn hợp lệ theo `AsrOutput`.
- **Xong khi:** property test bằng hypothesis: input lệch bất kỳ vẫn cho output qua validator của `AsrOutput`, không mất word nào có chữ.
- **Message:** `feat(pipeline): normalize raw ASR timestamps into valid segments (AI-06)`
- **Hash:**

### 2. [ ] Lọc hallucination của Whisper (AI-06)

- **Việc:** bỏ segment có `no_speech_prob` cao đi kèm `avg_logprob` thấp, hoặc `compression_ratio` quá cao; bỏ câu nằm trong blacklist (kiểu "hãy subscribe cho kênh"); gộp n-gram lặp liên tiếp. Ngưỡng là hằng số có ghi chú "giá trị khởi tạo". Có segment bị bỏ thì thêm warning `HALLUCINATION_FILTERED` kèm số lượng, không kèm nội dung.
- **Xong khi:** bảng test cho từng luật, và segment bình thường không bị đụng tới.
- **Message:** `feat(pipeline): filter Whisper hallucinations with thresholds, blacklist and repeats (AI-06)`
- **Hash:**

### 3. [ ] Adapter cho engine ASR và VAD (AI-06)

- **Việc:** `meeting_pipeline/engines/`: interface `AsrEngine` và `VadEngine`. Bản thật dùng faster-whisper (import trong hàm, nạp cuBLAS/cuDNN từ wheel `nvidia-*`, đọc `audio.wav` bằng `wave` nên không cần PyAV). Bản fake trả dữ liệu cố định cho test. Cấu hình qua `ASR_MODEL`, `ASR_COMPUTE_TYPE`, `ASR_DEVICE`. Cập nhật extra `asr` trong `pyproject.toml`. Thêm `engines/` vào `structure/repository.md`.
- **Xong khi:** CI không cài faster-whisper mà test vẫn chạy được (dùng engine fake).
- **Message:** `feat(pipeline): ASR and VAD engine adapters with faster-whisper and fakes (AI-06)`
- **Hash:**

### 4. [ ] Stage `vad` thật (AI-06)

- **Việc:** `stages/vad.py` đọc `audio.wav`, chạy Silero VAD, ghi `speech_regions` và `speech_ratio`. Không có lời nói (hoặc `speech_ratio` dưới ngưỡng) thì lỗi permanent `NO_SPEECH_DETECTED`. Đăng ký trong registry.
- **Xong khi:** test với engine fake (có tiếng, im lặng, region chạm biên). Test `@pytest.mark.model` chạy Silero thật trên audio im lặng sinh bằng ffmpeg.
- **Message:** `feat(pipeline): real vad stage with Silero VAD (AI-06)`
- **Hash:**

### 5. [ ] Stage `asr` thật (AI-06)

- **Việc:** `stages/asr.py` gọi engine, chuẩn hóa (commit 1), lọc hallucination (commit 2), ghi `asr.json`. CUDA OOM là lỗi transient `OUT_OF_MEMORY`; không load được model là lỗi permanent `MODEL_UNAVAILABLE`. Đăng ký trong registry, cập nhật bảng trạng thái stage trong `pipeline/README.md`.
- **Xong khi:** test với engine fake (thành công, OOM, model lỗi). Test `@pytest.mark.model` chạy trên GPU với một clip FLEURS (skip nếu chưa tải). Chạy pipeline `preprocess → vad → asr` thật qua CLI trên clip đó.
- **Message:** `feat(pipeline): real asr stage with post-processing and error mapping (AI-06)`
- **Hash:**

## Việc của nhóm trưởng (không phải commit)

- [ ] Review và merge PR của A và PR của B hôm nay.
- [ ] Nhắc A và B: không tự merge PR (PR #5, #7 hôm qua do chính tác giả merge). Cân nhắc bật branch protection cho `main`.
- [ ] SH-01: tổ chức buổi ghi âm pilot có consent. Audio để ở `evaluation/datasets/private/`, không commit.
