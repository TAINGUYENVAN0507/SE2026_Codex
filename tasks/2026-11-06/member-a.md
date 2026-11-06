# 2026-11-06 · Member A: frontend, export

- **Người làm:** A (`@mactuongmvt`), nhánh `vantuong`.
- **Số commit:** 5.
- **Mục tiêu:** người quản lý kiểm chứng được biên bản: mỗi ý trong tóm tắt và action item dẫn về đúng đoạn audio, kể cả trong file export. Người dùng xóa được cuộc họp từ giao diện và thấy tiến độ xử lý.

Kế hoạch các đợt sau: [`tasks/ROADMAP.md`](../ROADMAP.md).

## Kết quả local ngày 06/11

- Đã triển khai đủ 5 phần, tách 5 commit đúng nội dung; hash ghi dưới từng mục.
- Frontend: lint, format, typecheck, build đạt; **172 test / 32 file đạt**.
  Nhóm xóa/audio/job chạy lại **30 test đạt** sau chỉnh UI cuối.
- Backend: ruff check/format toàn module đạt; **21 test export** và **64 test
  action API/contract** đạt. Schema export 1.1 sinh từ model, drift check đạt.
- E2E trên stack thật: **17 test đạt** — 14 test slow gồm edit, delete, upload,
  RT-11, login và PRIV-01…09; thêm 3 luồng permanent/transient_once/summary_fail.
  Test delete chạy lại trên API/worker Linux thật đạt.
- QA ảnh desktop 1280px và mobile 360px: không tràn ngang; đã kiểm tra task
  evidence, xác nhận xóa, header và bố cục tiến độ. Ảnh chỉ lưu local ngoài Git.
- Các ô nghiệm thu giữ `[ ]` vì chưa push/chưa chạy CI cho code mới. Không tự merge.

### Những điểm cần phối hợp/review

- B review bản sửa nhỏ `serialize_action_item()` ở commit FE-17: snapshot worker
  có metadata ngoài schema làm GET action-items trả 500. Test đã fail trước sửa,
  pass sau sửa; chỉ chiếu field theo contract, không sửa dữ liệu AI gốc/OpenAPI.
- B review contract export **1.1**, truyền đủ evidence/needs_review từ DB.
  Chữ ký serializer không đổi. E2E tóm tắt/export DB vẫn để đợt 2.
- Native Windows: pipeline hủy process dùng `os.killpg`, chưa hỗ trợ Windows.
  Không sửa pipeline của C. QA delete đã đối chiếu thêm trên Linux.
- Linux worker còn log race khi job bị xóa: `MISSING_INPUT`/UPDATE không còn row.
  UI/API delete/404 đạt nhưng không suy ra cleanup mọi nơi lưu đã hoàn hảo;
  B/C cần xử lý ở BE-18/BE-17. Chi tiết trong FE-19.md.
- `started_at` thật và invariant tiến độ không tụt chờ BE-17 của C; UI không
  dựng timestamp giả hoặc giữ max tiến độ ở client.

Đọc trước:
- `backend/app/services/export/README.md` và `serializers.py`: TXT và Markdown chưa in evidence (`serializers.py:125`, `:131`).
- `frontend/src/features/meetings/RemoteSummary.tsx:98`: hàm `evidence()` và `onSeek`, phần sẽ dùng chung.
- `frontend/src/features/meetings/RemoteTasks.tsx:280`: action item mới có nhãn `needs_review`, chưa có evidence.
- `frontend/src/features/jobs/JobStatusCard.tsx`: chưa hiện `job.progress`.
- `tasks/2026-10-29/member-a.md`, mục 3: việc chuyển sang hôm nay.

Lệnh kiểm tra cho mọi commit, chạy trong `frontend/` (trên máy cần Postgres: `docker compose up -d db` ở gốc repo):

```bash
npm run lint && npm run format:check && npm run typecheck && npm test && npm run build
npx playwright test
```

Commit 2 đổi module export, chạy thêm trong `backend/`:

```bash
uv run ruff check . && uv run ruff format --check . && uv run pytest tests/unit/test_export_json.py tests/unit/test_export_text.py
```

## Bước 0 (không tính vào số commit)

```bash
git checkout vantuong
git fetch origin
git merge origin/main
```

Phối hợp với B: commit 1 của B nối router export với module của bạn. Hai bạn không đổi chữ ký `to_txt`, `to_markdown`, `to_json`, `filename`. Field mới trong model phải có giá trị mặc định.

## 5 commit

### 1. [ ] Sửa segment, đổi tên speaker, action item, lịch sử (FE-17)

Chuyển từ 2026-10-29. PR #28 đã vào `main` nên không còn bị chặn.

- **Việc:** thêm `frontend/e2e/flows/edit.spec.ts`. Trên meeting đã `ready`:
  - sửa text một segment;
  - đổi tên speaker;
  - thêm, sửa, xóa action item;
  - reload trang: mọi thay đổi vẫn còn;
  - tab Lịch sử có đúng các event vừa tạo.
- **Xong khi:** test xanh trên CI với backend thật, không mock, không dùng `waitForTimeout` cố định.
- **Message:** `test(frontend): edits persist across reloads and show in history (FE-17)`
- **Hash:** `a3d759e` — E2E thật và regression snapshot; đạt local, chờ CI/B review.

### 2. [ ] File export có dẫn chứng (FE-18)

- **Việc:**
  - `ExportAction` thêm `evidence_segment_ids` và `needs_review`, mặc định rỗng và `false`; lấy từ `ai_original` khi `variant=ai_original`.
  - TXT và Markdown in sau mỗi key point, decision, action item: `(Bằng chứng: 00:12:03 Speaker 1; 00:13:40 Speaker 2)`.
  - Không có evidence, hoặc id trỏ tới segment không còn: in `(Chưa có bằng chứng, cần kiểm tra)`.
  - Sinh lại `contracts/export.schema.json` bằng lệnh trong README của module, không sửa tay. Tag B trong PR vì đổi contract.
- **Xong khi:**
  - golden test cập nhật cho cả 2 biến thể;
  - có test cho id không tồn tại;
  - RT-13 vẫn đúng: 3 lần xuất ra cùng byte.
- **Message:** `feat(backend): exports cite the evidence of each summary claim and action item (FE-18)`
- **Hash:** `849cb9c` — 21 test export/golden/schema đạt; chờ consumer review 1.1.

### 3. [ ] Action item có link evidence, ý không có evidence bị đánh dấu (FE-18)

- **Việc:**
  - Tách `evidence()` trong `RemoteSummary.tsx` thành component `EvidenceLinks` dùng chung.
  - `RemoteTasks.tsx` hiện link evidence, bấm thì tua audio tới segment.
  - Key point, decision, action item không có evidence: hiện nhãn "Chưa có bằng chứng", không ẩn đi.
  - Id evidence không còn trong transcript: hiện nhãn đó, không crash.
- **Xong khi:** Vitest cho 3 trường hợp: có evidence (bấm thì gọi `onSeek` đúng giây), không có evidence, id không tồn tại.
- **Message:** `feat(frontend): action items link to their evidence and flag unverified claims (FE-18)`
- **Hash:** `b9574e6` — EvidenceLinks dùng chung; seek/rỗng/id mất và task API được kiểm tra.

### 4. [ ] Xóa cuộc họp từ giao diện và hiện hạn lưu trữ (FE-19)

Hiện chưa có UI gọi `DELETE /meetings/{id}`; API đã có từ BE-14.

- **Việc:**
  - Nút "Xóa cuộc họp" có hộp xác nhận, ghi rõ sẽ xóa audio, transcript, tóm tắt, action item và lịch sử sửa.
  - Xóa xong về danh sách, cache TanStack Query được xóa.
  - Lỗi mạng hoặc 5xx: giữ nguyên trang, báo lỗi, không báo đã xóa.
  - Hiện `audio.retention_until` theo ngày giờ địa phương trên trang chi tiết.
  - `audio.available=false` hoặc `GET /audio` trả 410: player hiện "Audio đã hết hạn lưu trữ", transcript vẫn đọc được.
- **Xong khi:**
  - Vitest cho hộp xác nhận, lỗi khi xóa và audio hết hạn;
  - E2E `frontend/e2e/flows/delete.spec.ts`: xóa khi job đang chạy (`FAKE_SCENARIO=slow`, RT-15), sau đó trang chi tiết báo không tìm thấy (PRIV-13).
- **Message:** `feat(frontend): delete a meeting from the UI and show its retention date (FE-19)`
- **Hash:** `d1a4abe` — xác nhận/cache/lỗi/audio hết hạn, E2E delete đạt local; giới hạn backend ghi ở trên.

### 5. [ ] Thanh tiến độ và thời gian đã chạy (FE-20)

- **Việc:**
  - `JobStatusCard` thêm thanh tiến độ `role="progressbar"`, `aria-valuenow` lấy từ `job.progress`.
  - Hiện thời gian đã chạy từ `job.started_at`. Giá trị `null` thì ẩn: hiện backend luôn trả `null`, C đang sửa ở BE-17 và schema không đổi.
  - Không clamp tiến độ ở client. Sau reload client mất giá trị cũ, nên việc không tụt lùi là của backend (BE-17).
- **Xong khi:** Vitest cho 0 %, giữa chừng, 100 %, `started_at=null`; E2E `upload.spec.ts` khẳng định có thanh tiến độ khi job đang chạy.
- **Message:** `feat(frontend): progress bar with elapsed time on the job status card (FE-20)`
- **Hash:** `6406830` — progress/elapsed không clamp, unit và E2E có thanh khi running đạt local.

## Việc chung (không phải commit)

- [ ] SH-01: ghi âm buổi họp pilot có consent (vẫn chưa có).

## Cuối ngày

- [x] Đã ghi hash và kết quả local; các ô nghiệm thu ở trên chờ CI/review.
- [ ] Push `vantuong`, mở PR vào `main`. **Không tự merge.**
- [ ] E2E tóm tắt và export chưa làm hôm nay vì chờ commit 1 của B: đã có trong đợt 2 của `tasks/ROADMAP.md`.
