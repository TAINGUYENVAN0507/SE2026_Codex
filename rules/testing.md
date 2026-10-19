# Kiểm thử và Definition of Done

## Test bắt buộc

- Mỗi PR có test cho phần thay đổi. Tính năng mới: test happy path và các lỗi chính. Sửa lỗi: test tái hiện lỗi, phải fail trước khi sửa.
- Test phải deterministic: không gọi mạng, không phụ thuộc giờ hệ thống (dùng clock giả) hay thứ tự chạy. Dữ liệu ngẫu nhiên dùng seed cố định.
- Không xóa hay skip test để CI xanh. Test chập chờn (flaky): báo nhóm trưởng, sửa ngay hoặc tạm skip kèm Task ID và lý do.

## Test đặt ở đâu

| Loại | Thư mục | Công cụ | CI |
|---|---|---|---|
| Frontend: component, logic | `frontend/src/**/*.test.ts(x)` | Vitest, React Testing Library | ◐ `frontend.yml` |
| Frontend: E2E, gồm PRIV-01…09 | `frontend/e2e/{flows,privacy}/` | Playwright | ○ `e2e.yml` |
| Backend: unit, API | `backend/tests/{unit,api}/` | pytest, httpx, Postgres trong CI | ○ `backend.yml` |
| Liên module: API + worker + fake pipeline + DB | `tests/{integration,audit,reliability,privacy}/` | pytest, `FAKE_SCENARIO` | ○ |
| Pipeline | `pipeline/tests/unit/`; `pipeline/tests/edge/` (audio sinh bằng ffmpeg) | pytest, hypothesis | ✓ `pipeline.yml` |
| Pipeline cần model thật hoặc GPU | `pipeline/tests/model/`, gắn `@pytest.mark.model` | pytest | Không: chạy thủ công trên máy có GPU |
| Evaluation | `evaluation/*/tests/` | pytest | ✓ `evaluation.yml` |

## Kịch bản evidence có ID

Các bộ evidence trong kế hoạch triển khai (mục 10.4) có ID cho từng kịch bản. Tên test bắt đầu bằng ID để dò ngược từ yêu cầu tới test.

| Bộ | ID | Thư mục | Owner |
|---|---|---|---|
| Edit audit | AUD-01…12 | `tests/audit/` | B |
| Timeout và retry | RT-01…15 | `tests/reliability/` (B). Phần cấp stage ở `pipeline/tests/unit/test_runner.py` (C). RT-11 là E2E (A). | B, C, A |
| No secret recording và privacy | PRIV-01…09 (frontend), PRIV-10…17 (backend) | `frontend/e2e/privacy/`, `tests/privacy/` | A, B |

Ví dụ đã có: `test_rt01_stage_timeout_kills_subprocess`, `test_rt02_diarize_failure_falls_back_on_last_attempt`, `test_rt14_summary_failure_then_regenerate_without_asr`, `test_rt15_cancel_between_stages`.

## Dữ liệu test

- Không commit audio thật. Audio cho test được sinh lúc chạy bằng ffmpeg (xem `pipeline/tests/edge/conftest.py`), hoặc là fixture nhỏ có license cho phép (tổng dưới 5 MB).
- Text mẫu do nhóm tự viết, không lấy từ cuộc họp thật. Fixture JSON lấy từ `contracts/fixtures/`.
- Test privacy dùng chuỗi canary (ví dụ `CANARY_TRANSCRIPT_7f3a`) để chứng minh dữ liệu người dùng không lọt vào log hay file lỗi.

## Test evidence trong PR

- Ghi lệnh đã chạy và output thật: số test pass, fail, skip. CI trên PR phải xanh.
- Có test bị skip thì ghi lý do, ví dụ máy thiếu ffmpeg.
- Số liệu đánh giá (WER, DER, latency): commit cả thư mục kết quả có `env.json`, không chép số bằng tay (`evaluation/wer/README.md`).

## Definition of Done

Một task chỉ được coi là xong khi:

1. Code và test nằm trong cùng PR. CI xanh: lint, format, type, test, kiểm drift contract.
2. Đáp ứng acceptance criteria của task trong kế hoạch, có bằng chứng trong PR: tên test, output, ảnh chụp.
3. Nhóm trưởng đã merge PR vào `main`.
4. Diff không có secret, audio, transcript thật hay dữ liệu cá nhân.
5. README hoặc `docs/` được cập nhật nếu hành vi thay đổi. Migration DB có downgrade.
6. Task có nhiều acceptance criteria hoặc cần hướng dẫn chạy riêng: có `docs/<khu vực>/<TaskID>.md` đối chiếu từng tiêu chí (ví dụ `docs/frontend/FE-01.md`).
