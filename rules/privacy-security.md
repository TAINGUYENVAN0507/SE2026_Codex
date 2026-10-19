# Privacy và bảo mật

> Repo này là **public**. Thứ gì đã push lên GitHub thì coi như đã công khai, kể cả khi sau đó xóa commit.

## Secret

- Không commit `.env`, API key, token hay mật khẩu. `.env.example` chỉ chứa placeholder và chú thích.
- `ANTHROPIC_API_KEY` và `HF_TOKEN` chỉ cấp cho container worker. Không đặt secret trong biến `VITE_*`, vì Vite đưa các biến này vào bundle phía client.
- Lỡ push secret: báo nhóm trưởng ngay. Thu hồi key và tạo key mới trước, sau đó mới xóa khỏi lịch sử git. Chỉ xóa commit thì không đủ.
- CI sẽ chạy gitleaks (`security.yml`, B làm).

## Dữ liệu ghi âm và cuộc họp

| Dữ liệu | Commit? | Để ở đâu |
|---|---|---|
| Audio của bất kỳ ai | Không | Máy cá nhân. Audio dùng để đánh giá để ở `evaluation/datasets/private/audio/`. |
| Transcript và RTTM của cuộc họp nội bộ | Không | `evaluation/datasets/private/refs/` |
| Phiếu consent đã ký | Không | Ngoài repo. `manifest.csv` chỉ ghi mã phiếu. |
| Transcript tham chiếu của dữ liệu public (FLEURS…) | Có, kèm ghi nguồn | `evaluation/datasets/refs/` |
| Kết quả đánh giá | Có | Chỉ số đếm và metric, không chứa text transcript |
| Dữ liệu demo, fixture | Có | Text do nhóm tự viết. Chỉ dùng tên thành viên nhóm khi người đó đồng ý. |

- Chỉ dùng audio có consent theo `evaluation/datasets/consent_form.md`, hoặc dữ liệu public đúng license (`evaluation/datasets/LICENSES.md`).
- Không dùng cuộc họp của người dùng để đánh giá khi họ chưa đồng ý (opt-in).
- Người tham gia rút consent: xóa audio, transcript, nhãn liên quan, và không dùng trong các lần đánh giá sau.
- Dùng dữ liệu thật của người ngoài nhóm: tự rà soát nghĩa vụ theo Nghị định 13/2023/NĐ-CP và Luật Bảo vệ dữ liệu cá nhân 2025.

## Log và thông báo lỗi

- Chỉ log ID, kích thước, thời lượng, mã lỗi và thời gian xử lý.
- **Cấm log:** transcript, nội dung audio, prompt và response của LLM, header `Authorization`, cookie, mật khẩu.
- Thông điệp lỗi và stack trace trả về client không chứa transcript, key hay đường dẫn tuyệt đối.
- Exception không lường trước: chỉ ghi loại lỗi và vị trí, không ghi message, vì message có thể chứa dữ liệu người dùng. Xem cách làm ở `pipeline/meeting_pipeline/cli.py`.
- Mỗi quy tắc trên có test canary (PRIV-10, PRIV-11).

## Ghi âm trên trình duyệt

Yêu cầu "no secret recording", kiểm chứng bằng PRIV-01…09:

- Chỉ gọi `getUserMedia` trong handler của nút bấm, sau khi người dùng đã tick consent. Không gọi khi mở trang.
- Trong lúc ghi: indicator đỏ, đồng hồ đếm, `aria-live` "Đang ghi âm".
- Dừng hoặc hủy: gọi `track.stop()` cho mọi track. Rời trang thì cleanup.
- Không tự upload. Chỉ gửi khi người dùng bấm "Tải lên".

## Gửi dữ liệu ra ngoài

- Chỉ gửi transcript dạng text tới LLM, không gửi audio, và chỉ khi đã cấu hình key và có consent. UI thông báo rõ việc này.
- Không có key (`LLM_PROVIDER=disabled` hoặc thiếu key): summary ở trạng thái `disabled`, không có request nào ra ngoài (PRIV-16).
- Dịch vụ bên ngoài đi qua adapter ([coding.md](coding.md)), để dữ liệu gửi đi được kiểm soát ở một chỗ.

## Quyền truy cập và xóa dữ liệu

- Mọi truy vấn lọc theo `owner_id`. Tài nguyên của user khác trả 404, không trả 403, để không lộ việc tài nguyên đó tồn tại.
- File lưu ngoài web root, đặt tên bằng UUID, chỉ phục vụ qua endpoint có auth. Kiểm tra file bằng ffprobe, không tin MIME do client gửi.
- Xóa meeting là xóa ngay audio, artifact và các row liên quan. Log của thao tác xóa chỉ ghi ID.
- Audio tự xóa sau `AUDIO_RETENTION_DAYS` (đề xuất 30 ngày, nhóm chốt).
- **Thêm chỗ lưu dữ liệu mới** (bảng, thư mục, cache, file log): cập nhật quy trình xóa và test PRIV-13 trong cùng PR.
- Chính sách dữ liệu đầy đủ: `docs/privacy/data-policy.md` (B viết, chưa có).
