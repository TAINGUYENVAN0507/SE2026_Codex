# VT-018 · Bảng pairwise cho `POST /meetings/{id}/jobs`

Sinh bằng `allpairspy` từ `tests/unit/test_vt018_pairwise.py`; không sửa tay.
20 ca thay cho 120 tổ hợp đầy đủ.

| # | from_stage | job trước | có chỉnh sửa | Idempotency-Key | Kỳ vọng |
|---|---|---|---|---|---|
| 1 | None | failed | False | absent | 202 |
| 2 | asr | succeeded | True | absent | 409 HAS_USER_EDITS |
| 3 | diarize | queued | True | fresh | 409 JOB_ALREADY_ACTIVE |
| 4 | merge | cancelled | False | fresh | 202 |
| 5 | summarize | cancelled | True | replayed | 202 |
| 6 | summarize | queued | False | absent | 409 JOB_ALREADY_ACTIVE |
| 7 | merge | succeeded | False | replayed | 202 |
| 8 | diarize | failed | False | replayed | 202 |
| 9 | asr | failed | False | fresh | 202 |
| 10 | None | cancelled | True | fresh | 409 HAS_USER_EDITS |
| 11 | merge | failed | True | absent | 409 HAS_USER_EDITS |
| 12 | None | queued | False | replayed | 409 JOB_ALREADY_ACTIVE |
| 13 | asr | cancelled | False | replayed | 202 |
| 14 | diarize | cancelled | False | absent | 202 |
| 15 | summarize | succeeded | False | fresh | 202 |
| 16 | summarize | failed | False | fresh | 202 |
| 17 | diarize | succeeded | False | fresh | 202 |
| 18 | asr | queued | False | fresh | 409 JOB_ALREADY_ACTIVE |
| 19 | None | succeeded | False | fresh | 409 JOB_ALREADY_SUCCEEDED |
| 20 | merge | queued | False | fresh | 409 JOB_ALREADY_ACTIVE |
