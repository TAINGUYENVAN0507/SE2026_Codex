# Chạy lại bài cá nhân VT-017

Nhánh bài tập độc lập, baseline `2dea2bfdfea220d0492cedbd56d30340ed41f0b6`.
Giữ lịch sử plan -> RED -> patch -> bằng chứng. Không merge khi chưa review.

## Cài đặt và test

Từ repository root, vào `backend`, dùng Python 3.12 và lockfile:

```powershell
uv sync --locked
$env:DEBUG='false'
uv run pytest tests/api/test_meeting_search_pagination.py tests/api/test_vt017_evidence.py tests/unit/test_vt017_load.py -q
uv run pytest tests/contract -q
uv run ruff check .
uv run ruff format --check .
uv run pytest -q
```

Test tích hợp PostgreSQL cần DB riêng dành cho test; fixture có migration/downgrade.
Không trỏ DATABASE_URL tới DB đang sử dụng. Log ngày 10/11 công bố rõ môi trường,
skip và lỗi phát sinh; không lấy kết quả của thành viên khác.

## Coverage, mutation và tải

Nếu môi trường đã có coverage/pytest-cov, chạy:

```powershell
uv run pytest tests/api/test_meeting_search_pagination.py tests/api/test_vt017_evidence.py --cov=app.services.meeting_search --cov-branch --cov-report=term-missing
```

Coverage là công cụ test tùy chọn, không thêm dependency sản phẩm. Mutation chỉ chạy
trên checkout sạch hoặc bản sao riêng: script sửa file service tạm thời rồi restore
trong finally; không chạy song song với test khác trong cùng checkout.

```powershell
uv run python -m scripts.check_vt017_mutations
uv run pytest tests/api/test_meeting_search_pagination.py tests/api/test_vt017_evidence.py tests/unit/test_vt017_load.py -q
uv run python -m scripts.run_load_test --output evidence/vt017/load/recheck
```

Harness có 100 tác vụ đồng bộ bằng barrier, 200 bản ghi tổng hợp, seed 17017,
kiểm tra status và kết quả bằng oracle Python độc lập. `raw.csv`, `summary.json`
và `env.json` được lưu trong output; chương trình trả exit code khác 0 nếu lỗi
hoặc p95 >3 giây. Phân vị nearest-rank: ceil(n*p)-1.

Đây là ASGI TestClient + SQLite, auth override; không đo nginx, mạng, PostgreSQL
hoặc pipeline AI. Peak là số tác vụ phía client, không phải số worker server.
`--pool queue` tái hiện cấu hình pool hữu hạn; mặc định dùng NullPool cho adapter
SQLite của mô phỏng. Không suy ra hệ thống production đạt SLA từ kết quả này.

## Contract và ranh giới

Schema response cũ đóng băng từ OpenAPI baseline trong
`tests/fixtures/vt017/legacy-response.schema.json`. TC25 chủ động làm hỏng field
để chứng minh legacy oracle từ chối payload. TC08/TC19 kiểm ID có thứ tự cụ thể,
không chỉ kiểm tra các trang rời nhau.

OpenAPI sinh từ FastAPI, type frontend sinh bằng openapi-typescript + Prettier;
không sửa tay file sinh. Thay đổi ngoài backend chỉ là generated contract/type,
cần owner A review trước tích hợp; không đổi UI, pipeline hoặc framework.

Chỉ cam kết thứ tự khi dữ liệu không thay đổi giữa các lần lấy trang. Offset
pagination chưa bảo đảm snapshot khi có concurrent insert/delete/update.
