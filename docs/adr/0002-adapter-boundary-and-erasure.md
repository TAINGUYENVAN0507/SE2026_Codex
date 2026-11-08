# ADR 0002: Ranh giới adapter của bên thứ ba và xóa dữ liệu một cửa

- **Trạng thái:** Đề xuất (2026-11-08). Chờ review của B và A.
- **Người đề xuất:** C.
- **Task:** AI-17, BE-18. Phục vụ AD-018 (Modifiability) và RE-018.

## Bối cảnh

Hai rủi ro cùng một gốc: một quyết định nằm rải rác thì lúc đổi hoặc lúc xóa sẽ sót.

1. Hệ thống gọi bốn bên thứ ba: `faster-whisper`, `pyannote.audio`/`torch`, `huggingface_hub`, Claude API. Nếu SDK bị import ở nhiều nơi, đổi nhà cung cấp là sửa nhiều file và dữ liệu rời máy khó kiểm.
2. Dữ liệu của một cuộc họp nằm ở nhiều nơi: bảng nghiệp vụ, `idempotency_keys` (chứa tiêu đề), audio và artifact trên đĩa, log. Ngày 2026-11-06 đã tái hiện: xóa cuộc họp mà `idempotency_keys` còn tiêu đề.

## Quyết định

### 1. Mỗi bên thứ ba có đúng một adapter, ranh giới được test cưỡng chế

- Stage và backend chỉ biết interface (`AsrEngine`, `VadEngine`, `DiarizeEngine`, `LLMProvider`). SDK chỉ được import trong `engines/` và `llm/`.
- Ngoài `app/worker/` không file backend nào import `meeting_pipeline`; worker chỉ import `runner`, `schemas`, `errors`.
- Hai test duyệt AST (`pipeline/tests/unit/test_adapter_boundary.py`, `backend/tests/unit/test_adapter_boundary.py`) đỏ khi vi phạm. Bảng chi tiết: [`docs/pipeline/AI-17.md`](../pipeline/AI-17.md).
- Mỗi adapter có bản fake, nên CI chạy không cần model hay mạng.

### 2. Xóa dữ liệu đi qua một dịch vụ

- `app/services/erasure/service.py`: `erase_meeting` và `erase_user` xóa DB, `idempotency_keys`, audio và artifact trong cùng một đường. Route chỉ gọi dịch vụ, không tự xóa.
- Dọn theo hạn lưu trữ (`app/services/retention.py`) dùng cùng cách: `AUDIO_RETENTION_DAYS` = 14 cho audio và artifact, `OPERATIONAL_RETENTION_DAYS` = 28 cho `idempotency_keys`. Hai biến đặt bằng môi trường, đổi không cần sửa code.
- Log chỉ ghi ID và mã, không ghi tiêu đề, tên file hay text transcript (field dùng chung ở [`tasks/ROADMAP.md`](../../tasks/ROADMAP.md)).

## Phương án đã cân nhắc

| Phương án | Vì sao không chọn |
|---|---|
| Quy ước trong tài liệu, không test | Ranh giới đã bị phá một lần (`models.py` import API private của SDK); tài liệu không phát hiện được |
| Mỗi route tự xóa phần dữ liệu của nó | Đã sót `idempotency_keys`; thêm bảng mới là phải nhớ sửa nhiều route |
| Dùng `ON DELETE CASCADE` cho mọi thứ | Không phủ audio, artifact trên đĩa và dữ liệu trong JSON của `idempotency_keys` |
| Tách pipeline thành dịch vụ riêng | Vượt phạm vi MVP; không giải quyết bài toán sót dữ liệu |

## Hệ quả

- **Được:** đổi ASR hay LLM sửa một file; thêm nơi lưu dữ liệu thì chỉ thêm vào dịch vụ xóa, test privacy sẽ đỏ nếu quên.
- **Mất:** thêm SDK mới phải khai báo ở `RULES` trước; dịch vụ xóa là điểm tập trung, lỗi ở đó ảnh hưởng mọi đường xóa.

## Giới hạn

- Test ranh giới chỉ thấy import tĩnh; `importlib.import_module("...")` với chuỗi động không bị bắt.
- Bản sao ngoài tầm với của hệ thống (bản sao lưu của máy chủ, nhà cung cấp LLM nếu bật `LLM_PROVIDER`) không nằm trong phạm vi xóa. Mặc định `LLM_PROVIDER=disabled` nên không gửi gì ra ngoài.
- Dịch vụ xóa chạy đồng bộ trong một request; số lượng cuộc họp rất lớn của một tài khoản chưa được đo.
