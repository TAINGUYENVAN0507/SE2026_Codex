# Checklist UX và demo — 13/11/2026

Ảnh và test dùng tài khoản, text và WAV tổng hợp; API, worker và PostgreSQL thật,
pipeline fake. Mỗi phần ghi ngày và nguồn bằng chứng. Đây là kiểm thử luồng sản phẩm,
không phải đánh giá độ chính xác hay tốc độ AI trên cuộc họp thật.

## Đợt 8 — kịch bản demo gắn bằng chứng, 13/11/2026

Đây là kịch bản đang dùng. Các phần 08–10/11 phía dưới giữ lại làm lịch sử.
Lượt E2E mới trên main có cả #53 và #54 được ghi riêng ở
[báo cáo 13/11](../evidence/final/frontend-2026-11-13.md), có commit và số test thật.
Bốn ảnh dưới đây vẫn là ảnh **12/11**, có [manifest nguồn/hash](../evidence/vt-018/ui/manifest.json);
không ghi thành ảnh mới của lượt E2E 13/11.

### Chuẩn bị

- Dùng tài khoản và database E2E riêng, API/worker thật, `VITE_API_MOCK=0`, pipeline fake và LLM disabled.
- Chuẩn bị WAV tổng hợp 30 giây cho phần nghe evidence, như [export-evidence.spec.ts](../../frontend/e2e/flows/export-evidence.spec.ts); không dùng bản ghi cuộc họp thật.
- Chuẩn bị một meeting ready và một meeting có tóm tắt lỗi trên stack kiểm thử. Luồng lỗi được kiểm bằng [progress.spec.ts](../../frontend/e2e/evidence/progress.spec.ts) với fake scenario có kiểm soát; chưa có nút trên giao diện để tự tiêm lỗi.
- Khi trạng thái queued/running trôi qua nhanh, mở ảnh tương ứng và nói rõ đó là ảnh bằng chứng 12/11. Nếu chưa chuẩn bị được meeting lỗi, trình bày ảnh/test của luồng lỗi, không tuyên bố vừa chạy live thành công.
- [Hướng dẫn chạy lại bộ ảnh](../evidence/vt-018/ui/README.md). Kịch bản 5 phút là thời lượng trình bày, không phải số đo tốc độ xử lý.

### Kịch bản 5 phút và bằng chứng từng bước

| Thời gian | Thao tác / điều trình bày | Ảnh hoặc test chứng minh |
| --- | --- | --- |
| 00:00–00:30 | Giới thiệu dữ liệu tổng hợp và pipeline fake; đăng nhập, mở danh sách. | [login.spec.ts](../../frontend/e2e/flows/login.spec.ts): auth/me HTTP 200, đúng tài khoản E2E, không dùng service worker mock. Môi trường thật/fake ghi trong báo cáo 13/11. |
| 00:30–01:00 | Chọn WAV, đặt tên, xác nhận consent, bấm Tạo biên bản; mở Xem tiến độ. | [upload.spec.ts](../../frontend/e2e/flows/upload.spec.ts), ca Upload có consent qua đủ sáu stage tới ready; [meeting.ts](../../frontend/e2e/meeting.ts) kiểm POST tạo meeting HTTP 201. |
| 01:00–01:20 | Chỉ job đang chờ: 0%, chưa có giờ bắt đầu; bước sắp tới ghi Chờ bắt đầu. | [01-queued.png](../evidence/vt-018/ui/01-queued.png); E2E ảnh 12/11 kiểm queued trước khi bật worker. [JobStatusCard.test.tsx](../../frontend/src/features/jobs/JobStatusCard.test.tsx) có hai ca queued không ghi đang chạy. |
| 01:20–01:40 | Chỉ job đang chạy giữa chừng, phần trăm và sáu bước. Có thể reload để thấy vẫn là job cũ. | [02-running.png](../evidence/vt-018/ui/02-running.png) ở 60%; E2E ảnh chờ progress >=40%. Ca RT-11 trong upload.spec.ts kiểm reload, cùng latest_job_id, không POST thêm job. |
| 01:40–02:00 | Chỉ trạng thái hoàn tất: 100%, có giờ bắt đầu và hoàn thành. | [03-succeeded.png](../evidence/vt-018/ui/03-succeeded.png); E2E ảnh kiểm succeeded, started_at/finished_at và hai thẻ time. Upload E2E kiểm đủ sáu stage succeeded. |
| 02:00–02:30 | Mở meeting tóm tắt lỗi; transcript vẫn đọc được và có nút Tạo lại tóm tắt. | E2E ảnh 12/11 trong progress.spec.ts chạy summary_fail và đợi job failed trước khi tìm nút. [PartialSummaryRetry.test.tsx](../../frontend/src/features/meetings/PartialSummaryRetry.test.tsx) kiểm cả trường hợp API summary pending nhưng meeting partial. **Chưa có ảnh riêng màn lỗi được duyệt**; bằng chứng ở bước này là test. |
| 02:30–03:10 | Bấm Tạo lại tóm tắt; mở tiến độ của job mới. Giải thích chỉ chạy lại bước 6 nên giữ năm bước trước, bắt đầu khoảng 83%, lượt thử 1. | [04-retry-reset.png](../evidence/vt-018/ui/04-retry-reset.png); E2E ảnh kiểm POST HTTP 202, ID job mới, attempt=1, progress=5/6 và thời gian chưa bắt đầu khi queued. |
| 03:10–03:35 | Khi hoàn tất, quay về transcript và đối chiếu không có segment trùng. | E2E ảnh tiếp tục sau ảnh thứ tư tới succeeded; [capture.json](../evidence/vt-018/ui/capture.json) ghi mẫu đã kiểm: 6 segment trước/sau cùng toàn bộ ID, số hàng UI khớp. Đây là retry tóm tắt, không phải bằng chứng chạy lại toàn bộ ASR. |
| 03:35–04:00 | Giới thiệu việc nút retry bị khóa khi request còn chờ; bấm nhanh hai lần chỉ gửi một POST. | [RetryDoubleClick.test.tsx](../../frontend/src/features/meetings/RetryDoubleClick.test.tsx): **MSW/Vitest**, giữ POST pending, dblClick, kiểm đúng 1 POST có UUID Idempotency-Key và nút disabled. Không coi test này là kiểm concurrency của backend. |
| 04:00–05:00 | Sửa một đoạn transcript, lưu/reload và mở lịch sử; tải một file export, chỉ mốc evidence. | [edit.spec.ts](../../frontend/e2e/flows/edit.spec.ts) kiểm dữ liệu giữ sau reload và event; [export.spec.ts](../../frontend/e2e/flows/export.spec.ts) kiểm download; export-evidence.spec.ts đối chiếu từng evidence hoặc nhãn thiếu giữa UI và TXT/MD. |

### Giới hạn của kịch bản

- Nhận dạng đúng danh tính người nói từ giọng: **chưa có bằng chứng trong kịch bản này**; dữ liệu fake dùng Speaker N hoặc tên được sửa thủ công.
- Chất lượng ASR/diarization/LLM thật và chịu tải 239/247: **chưa có bằng chứng từ lượt demo/E2E này**; dùng báo cáo đánh giá riêng nếu cần trình bày.
- Điện thoại vật lý và screen reader thật: **chưa có bằng chứng trong lượt này**. Ảnh viewport giả lập và axe không thay kiểm thủ công.
- Bộ `npm run e2e` slow ngày 13/11 không bao gồm scenario summary_fail hay file evidence config. Luồng lỗi → retry dùng đúng bằng chứng 12/11 nêu ở bảng; không cộng gộp thành số E2E vừa chạy hôm nay.


## Đợt 5 — bận và thời gian job, 10/11/2026

Tám ảnh mới ở dưới chụp qua container web/nginx cổng 8080, với API, worker
và PostgreSQL thật, pipeline fake và WAV tổng hợp. Ba trạng thái bận dùng
Playwright chặn response để trả 503 có kiểm soát, không phải phép thử tải thật.
Ảnh job hoàn thành lấy timestamp từ job thật của stack kiểm thử.
Desktop 1280×900, mobile giả lập 360×900; không tràn ngang trong tám ảnh.
Manifest ghi viewport, SHA256 và trạng thái có giả lập mạng:
[2026-11-10-manifest.json](screenshots/2026-11-10-manifest.json).
Bản sao cùng SHA256 ở `.preview-stitch/anh-duyet/2026-11-10/` ngoài Git.

| Trạng thái | Desktop | Mobile |
| --- | --- | --- |
| Upload chờ máy chủ bận | [1280px](screenshots/2026-11-10-busy-upload-desktop.png) | [360px](screenshots/2026-11-10-busy-upload-mobile.png) |
| Poll lùi lại, giữ tiến độ | [1280px](screenshots/2026-11-10-busy-progress-desktop.png) | [360px](screenshots/2026-11-10-busy-progress-mobile.png) |
| Thời gian hàng đợi, bắt đầu, hoàn thành | [1280px](screenshots/2026-11-10-job-times-desktop.png) | [360px](screenshots/2026-11-10-job-times-mobile.png) |
| Sửa gặp bận, giữ bản nháp | [1280px](screenshots/2026-11-10-busy-edit-desktop.png) | [360px](screenshots/2026-11-10-busy-edit-mobile.png) |

Hành vi được kiểm riêng, ảnh không thay test: `BusyUpload.test.tsx` kiểm
2 lần 503 rồi 201 cùng key/đúng một meeting và hết lượt/hủy; `BusyPolling.test.tsx`
kiểm số request 30 giây, không chồng request, phục hồi và dừng với 404;
`BusyEdits.test.tsx` kiểm bản nháp và retry thủ công; `JobTimes.test.tsx`
kiểm queued/running/completed/thiếu thời gian. Flow `keyboard.spec.ts` đi bằng
Tab/Enter/Space, kiểm focus nhìn thấy và export đúng ID; hộp file OS được thay
bằng `filechooser.setFiles`, chưa phải kiểm screen reader hay điện thoại vật lý.

Kết quả local ngày 10/11: **284 Vitest / 46 file** và **27 E2E trên clone
sạch** đạt; lint/format/typecheck/build đạt. Một flow qua container web đã
đạt riêng, negative control proxy đỏ rồi khôi phục xanh ở local. CI workflow
nginx mới đã có [run đỏ](https://github.com/TAINGUYENVAN0507/SE2026_Codex/actions/runs/42786190434) và [run xanh](https://github.com/TAINGUYENVAN0507/SE2026_Codex/actions/runs/42786612344); task 5 đã tick. Báo cáo
[clone sạch](../frontend/clean-clone-2026-11-10.md) ghi rõ cảnh báo `os.killpg`
của worker native Windows; không coi test UI/API là xác nhận cleanup mọi nền tảng.

### Kịch bản demo 5 phút cập nhật

| Thời gian | Thao tác |
| --- | --- |
| 00:00–00:40 | Giới thiệu dữ liệu tổng hợp/pipeline fake. Dùng bàn phím đăng nhập và mở tạo cuộc họp. |
| 00:40–01:40 | Chọn WAV, consent, upload. Chỉ ảnh upload bận: chờ Retry-After, tối đa 3 lần thử lại cùng key; hết lượt có nút thử lại, có thể hủy. Không làm API thật quá tải để demo. |
| 01:40–02:30 | Mở tiến độ riêng: thời gian chờ, giờ bắt đầu/hoàn thành. Chỉ ảnh poll bận vẫn giữ phần trăm; lịch kiểm tra lùi tối đa 10 giây rồi về 2 giây khi API phục hồi. |
| 02:30–03:30 | Mở meeting ready, nghe evidence. Sửa transcript; dùng ảnh bận để chỉ bản nháp và nút thử lưu lại. Các thao tác ghi khác chỉ retry khi người dùng bấm. |
| 03:30–04:30 | Mở tóm tắt/công việc và lịch sử. Export JSON bằng bàn phím; chỉ đúng meeting ID và focus trở về menu sau khi tải. |
| 04:30–05:00 | Giới thiệu mobile và các giới hạn: fake pipeline không chứng minh chất lượng AI, ảnh mạng giả lập không chứng minh chịu tải. |

Khi chưa cài cơ chế tiêm lỗi trên máy demo, mở ảnh đã ghi rõ giả lập thay vì
đổi proxy hoặc cấu hình production. Kịch bản này thay bảng demo cũ cho đợt 5;
ảnh và kết quả ngày 08–09/11 phía dưới được giữ làm lịch sử.

## Checklist đã kiểm tra local

| Mục | Kết quả và bằng chứng |
| --- | --- |
| Upload có consent | Chỉ tạo meeting sau thao tác xác nhận; xem ảnh upload và `upload.spec.ts`, PRIV-01…09. |
| Theo dõi tiến độ | Sáu bước ở trang riêng; trang nội dung chỉ có dòng gọn. Reload vẫn theo job cũ; `upload.spec.ts`/RT-11. |
| Tóm tắt và audio | Bấm evidence tua đúng `currentTime` của audio thật; `export.spec.ts`. WAV đủ 30 giây để kiểm các mốc của pipeline fake. |
| Kiểm chứng từng ý/công việc | Tất cả timestamp khớp giữa API, UI và từng dòng TXT/MD; nội dung thiếu evidence có nhãn ở cả hai nơi; `export-evidence.spec.ts`. |
| Export | Nút tải TXT, Markdown, JSON gọi router thật; kiểm HTTP 200, tên file và nội dung đúng meeting. |
| Sửa và lịch sử | Sửa segment, speaker, CRUD công việc; reload và đối chiếu audit; `edit.spec.ts`. |
| Xóa cuộc họp | Có hộp xác nhận và hủy; E2E xóa khi job đang chạy rồi meeting/audio/job trả 404; `delete.spec.ts`. Không dùng kết quả UI để kết luận worker cleanup hoàn hảo. |
| Audio hết hạn | Chạy CLI cleanup thật: audio/artifact biến mất, GET audio trả 410, transcript DB/API/UI không đổi; `retention.spec.ts`. |
| Cài đặt tài khoản | Mở từ bánh răng, reload được; nút xóa bật theo contract. E2E xóa user tổng hợp riêng kiểm mất cookie/phiên cũ, đăng nhập lại thất bại và user khác còn hoạt động. |
| Form xác nhận tài khoản | Vitest: gõ lại email, hủy/Escape, focus, chống gửi lặp, lỗi mạng/5xx giữ email/cache, success xóa phiên. HTTP được giả lập riêng trong test component. |
| Desktop/mobile | 14 ảnh ở viewport 1280×900 và 360×800; không tràn ngang trong các màn đã chụp. Trang cài đặt còn được kiểm riêng ở 1280px/360px. |
| Bản ghi ngắn | Header hiện giây khi dưới một phút; không ghi 30 giây thành 0 phút. Chưa có thời lượng thì ghi rõ, không dựng số giả. |
| Lỗi khi chạy | Không có `pageerror` trong luồng chụp ảnh. Lỗi nghiệp vụ được kiểm riêng bằng E2E permanent/retry/partial và Vitest. |

Kết quả local 09/11 sau đồng bộ main `b654a99`: **262 Vitest / 39 file**,
**23 E2E slow + 3 E2E lỗi/retry/partial** đạt, không skip. Lint, format,
typecheck và production build đạt. Bốn ca axe browser quét tám viewport:
0 violation, 0 incomplete. Xem `accessibility-2026-11-09.json` và giới hạn
ở bug bash. PR #42 của đợt 08/11 đã merge; kết quả local ngày 09/11 không
thay cho CI của PR ngày 09/11 (chưa push nhánh `vantuong`).

## Ảnh cập nhật 09/11/2026

Ảnh Chromium trên stack thật với pipeline fake, user/meeting tổng hợp; desktop
1280×900 và mobile giả lập 360×900, không tràn ngang. Bản sao đúng SHA256 ở
`.preview-stitch/anh-duyet/2026-11-09/` ngoài Git. Không dùng ảnh/trace thật.

| Màn | Desktop | Mobile |
| --- | --- | --- |
| Danh sách | [1280px](screenshots/2026-11-09-list-desktop.png) | [360px](screenshots/2026-11-09-list-mobile.png) |
| Upload | [1280px](screenshots/2026-11-09-upload-desktop.png) | [360px](screenshots/2026-11-09-upload-mobile.png) |
| Chi tiết | [1280px](screenshots/2026-11-09-detail-desktop.png) | [360px](screenshots/2026-11-09-detail-mobile.png) |
| Cài đặt | [1280px](screenshots/2026-11-09-settings-desktop.png) | [360px](screenshots/2026-11-09-settings-mobile.png) |

## Ảnh bằng chứng 08/11/2026

Các ảnh sau giữ để đối chiếu những luồng không đổi; không thay cho ảnh giao diện
mới ở trên. Mobile của đợt này là 360×800.


| Màn | Desktop | Điện thoại |
| --- | --- | --- |
| Upload | [1280px](screenshots/2026-11-08-upload-desktop.png) | [360px](screenshots/2026-11-08-upload-mobile.png) |
| Tiến độ riêng | [1280px](screenshots/2026-11-08-progress-desktop.png) | [360px](screenshots/2026-11-08-progress-mobile.png) |
| Tóm tắt có evidence | [1280px](screenshots/2026-11-08-summary-desktop.png) | [360px](screenshots/2026-11-08-summary-mobile.png) |
| Công việc có evidence | [1280px](screenshots/2026-11-08-tasks-desktop.png) | — |
| Menu export | [1280px](screenshots/2026-11-08-export-desktop.png) | — |
| Xác nhận xóa cuộc họp | [1280px](screenshots/2026-11-08-delete-desktop.png) | — |
| Audio hết hạn, còn transcript | [1280px](screenshots/2026-11-08-expired-desktop.png) | — |
| Cài đặt tài khoản | [1280px](screenshots/2026-11-08-settings-desktop.png) | [360px](screenshots/2026-11-08-settings-mobile.png) |
| Xác nhận xóa tài khoản | [1280px](screenshots/2026-11-08-account-confirm-desktop.png) | [360px](screenshots/2026-11-08-account-confirm-mobile.png) |

Bản sao tiện duyệt ở `.preview-stitch/anh-duyet/2026-11-08/` (ngoài Git).
Ảnh ở `docs/demo/screenshots/` là dữ liệu tổng hợp, dùng làm bằng chứng của tài liệu.

## Kịch bản demo 5 phút

Chuẩn bị bản chạy `VITE_API_MOCK=0`, backend/worker và database test riêng,
`PIPELINE_BACKEND=fake`, `FAKE_SCENARIO=slow`; dùng tài khoản demo và WAV tổng
hợp. Không dùng tài khoản/cuộc họp thật để thử xóa. Tên người nói trong dữ liệu
fake chỉ là nhãn minh họa, không phải nhận dạng danh tính từ giọng nói.

| Thời gian | Thao tác và điểm cần nói |
| --- | --- |
| 00:00–00:30 | Giới thiệu mục tiêu: từ bản ghi đến transcript, tóm tắt và công việc có thể kiểm chứng. Nói rõ đang dùng dữ liệu/pipeline fake. |
| 00:30–01:10 | Vào Tạo cuộc họp, chọn WAV, nghe thử tại máy, đặt tên và xác nhận consent; bấm Tạo biên bản. |
| 01:10–01:40 | Mở Xem tiến độ để thấy sáu bước, phần trăm/thời gian; reload rồi trở về nội dung. |
| 01:40–02:40 | Đọc transcript và tóm tắt; bấm một mốc evidence để tua audio. Sửa một đoạn, lưu, reload và mở Lịch sử. |
| 02:40–03:40 | Mở Công việc, thử thêm/sửa một việc. Giải thích nhãn Chưa có bằng chứng với nội dung chưa có dẫn chứng. |
| 03:40–04:20 | Tải TXT/MD/JSON; mở file TXT/MD, chỉ mốc dẫn chứng trùng giao diện. Giới thiệu lựa chọn bản hiện tại/bản AI gốc. |
| 04:20–04:45 | Mở Xóa cuộc họp, đọc phạm vi dữ liệu, thử hủy rồi xác nhận xóa meeting tổng hợp. Mở lại link cũ để thấy không tìm thấy. |
| 04:45–05:00 | Chỉ ảnh audio hết hạn còn transcript; mở Cài đặt, giải thích phạm vi xóa tài khoản và thử hủy. Chỉ thử xóa thật với user tổng hợp riêng, không xóa tài khoản demo chung. |

Nếu máy xử lý chậm, dùng một meeting tổng hợp đã ready để trình bày phần đọc,
chỉnh sửa và export. Phân bố 5 phút là kịch bản trình bày, không phải benchmark.

## Chạy lại kiểm tra

Chuẩn bị PostgreSQL riêng có tên chứa `e2e`, đặt `E2E_DATABASE_URL` và mật khẩu
demo theo [FE-17](../frontend/FE-17.md). Từ `frontend/`:

```powershell
npm run lint
npm run format:check
npm run typecheck
npm test
npm run build
$env:FAKE_SCENARIO='slow'
npx playwright test
```

Chạy tiếp từng `FAKE_SCENARIO=permanent`, `transient_once`, `summary_fail` bằng
`npx playwright test`. Stack tự bật API/worker với pipeline fake và tắt khi xong;
không tái sử dụng API/database phát triển. Fixture retention chỉ chạy trên dữ
liệu E2E, kiểm đường dẫn rồi gọi CLI cleanup chính thức.

## Còn chờ hoặc cần nhóm xác nhận

- Xóa tài khoản đã vào main qua PR #42; E2E ngày 09/11 tiếp tục đạt. Bằng
  chứng UI/API không thay cho kiểm tra cleanup ở mọi nơi của backend/pipeline.
- PR #45 của B đã được nhận xét trên snapshot `d9eba806` ngày 09/11 và đã merge ngày 10/11; xem [bản review](../frontend/reviews/PR-45-2026-11-09.md). Từ ngày 10/11 review thành viên là tùy chọn, không chặn mở PR. Các kết quả ngày 09/11 phía trên là lịch sử.
- Native Windows từng có log `os.killpg` khi hủy job đang chạy. Pipeline thuộc C;
  cần xử lý riêng nếu hỗ trợ worker native Windows. Không giấu lỗi để báo sạch.
- Race worker Linux từng được ghi nhận ngày 06/11 cần B/C xác nhận lại trên main
  mới; xem [FE-19](../frontend/FE-19.md). Test UI/API không thay evidence backend.
- SH-01 ghi âm pilot có consent là việc chung, chưa được thực hiện trong đợt này.

## Bug bash và thay đổi 08/11

Chi tiết tái hiện, mong đợi/thực tế, mức độ và test hồi quy:
[`bug-bash-2026-11-08.md`](bug-bash-2026-11-08.md).

- API hiện không có tự đăng ký; tài khoản do CLI quản trị cung cấp.
- Upload dùng giới hạn/định dạng server, có trạng thái lỗi và thử tải lại config.
  Khi upload đang chạy không đổi nguồn hoặc bật micro; bàn phím vẫn hủy được.
- 48 mã lỗi công bố có thông báo riêng; không lộ raw message backend.
- Docker Web build/khởi động được sau sửa contract path và PID Nginx.
- Các ảnh chỉ xác nhận layout/overflow ở viewport giả lập Chromium; chưa kiểm
  điện thoại vật lý hoặc screen reader thực tế. Detector trên trang sửa trả []
  không đồng nghĩa toàn bộ ứng dụng đã đạt WCAG.

## Ma trận trang × trạng thái — 09/11/2026

Các ô dưới dẫn tới test hành vi, không chỉ kiểm render. MSW dùng dữ liệu tổng
hợp; response đang tải được giữ bằng promise rồi giải phóng, không sleep đoán.
N/A nghĩa là trạng thái không áp dụng, không phải đã kiểm một trạng thái giả.

| Trang / khu vực | Rỗng / thiếu dữ liệu | Đang tải | Lỗi và đường phục hồi |
| --- | --- | --- | --- |
| Đăng nhập | Form trống có required; không có danh sách để kiểm empty | `LoginPage.test.tsx`: khóa submit khi chờ | `LoginPage.test.tsx`: sai mật khẩu/mạng, giữ email, xóa password; `SessionExpiry.test.tsx`: hết phiên có alert |
| Danh sách | `MeetingListPage.test.tsx`: 0 meeting; `PageStates.test.tsx`: không có kết quả tìm và xóa bộ lọc khôi phục | `MeetingListPage.test.tsx`: skeleton → dữ liệu | `MeetingListPage.test.tsx`: thông báo lỗi/nút thử lại; không hiển thị raw backend |
| Upload | `PageStates.test.tsx`: chưa có file, có nút chọn, submit tắt | `PageStates.test.tsx`: chờ config, chọn file tắt → dùng đúng giới hạn; `NewMeetingPage.test.tsx`: progress/hủy | `NewMeetingPage.test.tsx`: config lỗi/thử lại, lỗi HTTP, hủy không đổi trang; `SessionExpiry.test.tsx`: 401 |
| Chi tiết | `PageStates.test.tsx`: transcript rỗng không chèn dữ liệu demo | `PageStates.test.tsx`: chưa hiện player khi meeting chưa về | `PageStates.test.tsx`: 503 có đường về danh sách; 404 không lộ dữ liệu meeting; `SessionExpiry.test.tsx`: 401 |
| Tiến độ | `MeetingProcessingPage.test.tsx`: chưa có job, không dựng % giả | `PageStates.test.tsx`: thông báo tải trước khi có dữ liệu | `MeetingProcessingPage.test.tsx`: lỗi meeting; `JobStatusCard.test.tsx`: lỗi job/retry; `SessionExpiry.test.tsx`: 401 |
| Cài đặt | `PageStates.test.tsx`: tên rỗng có fallback, vẫn giữ email thật | `PageStates.test.tsx`: guard chờ me, không hiện profile giả | `PageStates.test.tsx`: me 503 có thử lại, không nhầm thành hết phiên; `DeleteAccountSection.test.tsx`: lỗi xóa giữ form |
| Tab tóm tắt | `RemoteSummary.test.tsx`: disabled/insufficient/failed | `PanelStates.test.tsx`: HTTP chờ; `RemoteSummary.test.tsx`: pending nghiệp vụ | `PanelStates.test.tsx`: HTTP 500 có alert an toàn; `RemoteSummary.test.tsx`: 409 giữ bản nháp |
| Tab công việc | `PanelStates.test.tsx`: 0 việc, có form tạo thủ công | `PanelStates.test.tsx`: chờ HTTP → nội dung | `PanelStates.test.tsx`: HTTP 500 có alert, không raw text; `RemoteTasks.test.tsx`: 409 giữ draft |
| Tab lịch sử | `HistoryPanel.test.tsx`: kết quả rỗng theo bộ lọc | `HistoryPanel.test.tsx`: thông báo chờ HTTP | `HistoryPanel.test.tsx`: lỗi an toàn, thử lại thành công |
| Trang không tồn tại | `App.test.tsx` / scaffold: 404 có đường về danh sách | N/A: trang tĩnh không tải API | N/A: chính trang này là trạng thái phục hồi 404 |

`PageStates.test.tsx` bổ sung 11 ca và `PanelStates.test.tsx` bổ sung 5 ca.
Các test cũ được tái sử dụng khi đã kiểm đúng trạng thái; không thêm bản sao
để tăng số lượng. Kiểm màu và bố cục thực tế thuộc lượt browser/axe riêng.

## Lưu ý demo sau hardening 09/11

Giữ kịch bản 5 phút ở trên, ưu tiên ảnh 09/11 khi minh họa bốn trang chính.
Nếu phiên hết hạn, trang login có thông báo; đăng nhập lại trở về URL đích.
Đây là xử lý lỗi thật, không cố tình làm mất phiên giữa phần trình bày chính.
Axe là bằng chứng kiểm tra tự động, không đưa mã lỗi kỹ thuật lên luồng người dùng.
Giữ Inter/graphite/cam; thay đổi hiển thị ngày này là tương phản chữ và landmark.
