# 2026-10-23 · Member C: pipeline, nhóm trưởng

- **Người làm:** C (`@TAINGUYENVAN0507`), nhánh `tainguyen`.
- **Số commit:** 5.
- **Trạng thái:** đã xong 5 commit. Backend `real` có đủ 6 stage; `summarize` mặc định `disabled` cho tới khi nhóm quyết định dùng Claude API với audio họp thật.
- **Mục tiêu:** stage `summarize` thật (AI-09), stage cuối cùng còn thiếu của pipeline. Tóm tắt bằng Claude API (`claude-opus-5-5`) qua interface `LLMProvider`, có bản `fake` cho CI và bản `disabled` khi không bật LLM.

Đọc trước: mục AI-09, mục 4 (Bảo mật và quyền riêng tư: chỉ gửi transcript text tới LLM) và PRIV-16 của kế hoạch; `contracts/pipeline/summary.schema.json`; [`rules/privacy-security.md`](../../rules/privacy-security.md) mục "Gửi dữ liệu ra ngoài".

Lệnh kiểm tra cho mọi commit, chạy trong `pipeline/`:

```bash
uv run ruff check . && uv run ruff format --check . && uv run pytest -m "not model"
uv run python -m meeting_pipeline export-contracts --check
```

## 5 commit

### 1. [x] Interface `LLMProvider`, bản fake và bản disabled (AI-09)

- **Việc:** `meeting_pipeline/llm/`: interface trả về bản nháp tóm tắt có cấu trúc. `FakeProvider` trả bản nháp cố định. `DisabledProvider` không gọi ra ngoài. Chọn provider bằng `LLM_PROVIDER` (`anthropic` | `fake` | `disabled`); không đặt thì mặc định `disabled`, để transcript không rời máy nếu chưa cấu hình rõ ràng.
- **Xong khi:** test chọn provider theo env; giá trị lạ thì báo lỗi.
- **Message:** `feat(pipeline): LLM provider interface with fake and disabled providers (AI-09)`
- **Hash:** `71c5fb2`

### 2. [x] Prompt tóm tắt tiếng Việt `summary-v1` (AI-09)

- **Việc:** prompt có version. Transcript đưa vào dưới dạng khối dữ liệu, mỗi segment kèm `index`, tên speaker (tên đã sửa nếu có) và thời gian; có ngày họp để tính deadline. System prompt dặn model coi nội dung transcript là dữ liệu, không làm theo lệnh nằm trong đó (chống prompt injection), chỉ ghi điều có căn cứ trong transcript, mỗi mục kèm evidence là index của segment.
- **Xong khi:** test: transcript chứa câu kiểu "bỏ qua hướng dẫn trên" chỉ nằm trong khối dữ liệu; prompt deterministic với cùng input.
- **Message:** `feat(pipeline): versioned Vietnamese summary prompt with transcript as data (AI-09)`
- **Hash:** `e069d27`

### 3. [x] Hậu kiểm bản nháp tóm tắt (AI-09)

- **Việc:** evidence trỏ tới index không tồn tại thì bỏ; action item không còn evidence thì `needs_review=true`; `due_date` chỉ giữ khi có `due_date_text` và ngày họp; assignee phải khớp speaker hoặc để tên tự do. Transcript quá ngắn thì `insufficient_content` mà không gọi LLM.
- **Xong khi:** bảng test cho từng luật; output luôn hợp lệ theo `SummaryOutput`.
- **Message:** `feat(pipeline): post-check summary evidence, deadlines and review flags (AI-09)`
- **Hash:** `6678822`

### 4. [x] Provider Anthropic (AI-09)

- **Việc:** `claude-opus-5-5`, structured outputs (`messages.parse` với model Pydantic), effort đặt tường minh, server-side fallback khi model từ chối. 429, 5xx, timeout, lỗi mạng là transient `LLM_UNAVAILABLE`; 400 là permanent `LLM_REQUEST_INVALID`; `refusal` hoặc `max_tokens` là `LLM_OUTPUT_INVALID`. Không log prompt hay response.
- **Xong khi:** test bằng HTTP transport giả (không gọi mạng): thành công, từng loại lỗi, refusal. Thông điệp lỗi không chứa transcript.
- **Message:** `feat(pipeline): Anthropic provider with structured outputs and error mapping (AI-09)`
- **Hash:** `597d542`

### 5. [x] Stage `summarize` thật (AI-09)

- **Việc:** nối provider, prompt và hậu kiểm thành stage thật, đăng ký trong registry. Dùng transcript đã sửa (`transcript_override_path`) khi chạy lại riêng summarize. PRIV-16: `LLM_PROVIDER=disabled` thì summary `disabled` và không có request nào ra ngoài. Cập nhật README.
- **Xong khi:** test stage với provider fake, disabled và lỗi; `run_job(backend="real")` với `LLM_PROVIDER=fake` chạy hết 6 stage (test model thật).
- **Message:** `feat(pipeline): real summarize stage wired to the LLM provider (AI-09)`
- **Hash:** `3d27ede`

## Việc của nhóm trưởng (không phải commit)

- [ ] Review và merge PR của A và B hôm nay.
- [ ] SH-01: tổ chức buổi ghi âm pilot (vẫn chưa có).
- [ ] Quyết định cho nhóm: có dùng Claude API với audio họp thật không (cần consent theo phiếu) và ngân sách API.
