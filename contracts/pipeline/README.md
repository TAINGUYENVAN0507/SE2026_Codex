# Pipeline contracts

Contract giữa `meeting_pipeline` (C, producer) và worker của backend (B, consumer).

**Không sửa tay các file `*.schema.json` và fixtures.** Chúng được sinh từ Pydantic trong `pipeline/meeting_pipeline/schemas.py`:

```bash
cd pipeline
uv run python -m meeting_pipeline.contracts_export          # sinh lại
uv run python -m meeting_pipeline.contracts_export --check  # kiểm drift (CI cũng chạy)
```

## Các file

| Schema | File trong workdir của job | Ai ghi |
|---|---|---|
| `job.schema.json` | `job.json` | Worker (B), trước khi gọi pipeline |
| `preprocess.schema.json` | `preprocess.json` | stage `preprocess` |
| `vad.schema.json` | `vad.json` | stage `vad` |
| `asr.schema.json` | `asr.json` | stage `asr` |
| `diarization.schema.json` | `diarization.json` | stage `diarize` (hoặc runner khi fallback) |
| `transcript.schema.json` | `transcript.json` | stage `merge`. B persist đợt 1 từ file này. |
| `summary.schema.json` | `summary.json` | stage `summarize`. B persist đợt 2 từ file này. |
| `error.schema.json` | `<stage>.error.json` | CLI khi stage lỗi (exit 10 hoặc 20) |

Fixtures mẫu nằm ở `contracts/fixtures/pipeline/`. Tên fixture bắt đầu bằng tên schema, ví dụ `summary_disabled.json` validate theo `summary.schema.json`.

## Quy ước

- Thời gian tính bằng giây kể từ đầu file gốc, làm tròn ms. Bất biến `0 <= start_sec < end_sec <= duration_sec`.
- Output luôn có đủ field. Không biết thì `null`, rỗng thì `[]`.
- `speaker_label` dạng `SPEAKER_00`, hoặc `null` khi chưa xác định được speaker.
- Evidence của summary (`evidence_segment_indices`) là `index` của segment trong transcript, vì pipeline chưa có UUID. B ánh xạ sang `segment_id` khi persist.
- Khi chạy lại riêng `summarize` sau khi người dùng sửa, B ghi transcript hiện tại (theo `transcript.schema.json`, có thể điền `speakers[].display_name`) ra file rồi truyền đường dẫn qua `job.json` → `transcript_override_path`.
- `schema_version` dạng `1.x`. Thêm field là tăng minor; đổi hoặc xóa field là breaking, tăng major và cần B duyệt.
