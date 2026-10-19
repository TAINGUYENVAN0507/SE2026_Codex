# Git workflow

## Nhánh

| Nhánh | Người dùng | Ghi chú |
|---|---|---|
| `main` | Chỉ nhóm trưởng merge vào | Luôn chạy được, CI xanh. Không ai push thẳng. |
| `tainguyen` | C, nhóm trưởng (`@TAINGUYENVAN0507`) | |
| `vantuong` | A (`@mactuongmvt`) | |
| Nhánh của B | B (`@minhquangha`) | Đặt tên không dấu, viết liền như hai nhánh trên, ví dụ `minhquang` |

- Mỗi người chỉ commit vào nhánh của mình. Không push vào nhánh của người khác.
- Đầu mỗi buổi làm việc, cập nhật theo `main`, giải quyết conflict ngay trên nhánh của mình:

  ```bash
  git fetch origin
  git merge origin/main
  ```

- Sau khi PR được merge: giữ nhánh, đưa nhánh về đúng `main` rồi làm tiếp:

  ```bash
  git fetch origin
  git merge --ff-only origin/main
  ```

- Không force-push lên `main`. Không force-push nhánh cá nhân khi đang có PR mở, vì người review sẽ mất lịch sử. Không rebase các commit đã push.

## Commit

```text
<type>(<scope>): <mô tả ngắn bằng tiếng Anh, dạng mệnh lệnh> (<TaskID>)

<Thân bằng tiếng Việt: làm gì, vì sao, test nào đã chạy.>
```

| Phần | Giá trị |
|---|---|
| `type` | `feat`, `fix`, `test`, `docs`, `refactor`, `perf`, `ci`, `chore`, `eval` |
| `scope` | `frontend`, `backend`, `worker`, `pipeline`, `eval`, `contracts`, `infra`, `ci`, `structure`, `rules` |
| `TaskID` | `FE-xx`, `BE-xx`, `AI-xx`, `SH-xx`, `G0`. Nhiều task thì ghi `(AI-08, AI-11)`. |

Ví dụ trong repo:

```text
feat(pipeline): assign speakers to ASR words by largest overlap (AI-08)
fix(pipeline): kill stage process group when runner exits abnormally (AI-04)
feat(eval): run_wer.py scores an ASR run against the manifest (AI-11)
```

- Mỗi commit là một thay đổi có nghĩa, và sau commit đó module vẫn lint, test xanh.
- Commit nhỏ và thường xuyên, không gom cả ngày làm việc vào một commit.
- Commit sửa lỗi: ghi tên test tái hiện lỗi trong thân commit.
- Code do AI sinh ra: đọc lại toàn bộ diff trước khi commit. Được phép thêm dòng `Co-Authored-By:` của công cụ AI.

## Pull request

- Mở PR từ nhánh cá nhân vào `main` khi xong một task, hoặc một nhóm task liên quan, đã có test. Việc còn đang làm thì mở ở chế độ Draft.
- Một PR gói gọn một chủ đề. PR lớn tới mức khó review thì tách ra.
- Tiêu đề theo format của commit, ví dụ `feat(pipeline,eval): stage merge thật và bộ chấm WER (AI-08, AI-11)`.
- Mô tả theo `.github/pull_request_template.md` (GitHub tự điền khi mở PR): Mục đích, Thay đổi chính, Cần người khác xem, Test evidence, Chưa làm, Checklist.
- Test evidence là lệnh đã chạy kèm output thật, ví dụ `uv run pytest → 176 passed`. Không ghi "chắc là pass".

## Review và merge

- **Nhóm trưởng (C, `@TAINGUYENVAN0507`) review và merge mọi PR.** File `.github/CODEOWNERS` tự thêm nhóm trưởng vào danh sách reviewer.
- Điều kiện merge:
  - CI xanh.
  - Mô tả có test evidence, checklist đã tick đủ.
  - Nếu đổi contract: consumer đã xác nhận trong PR ([contracts.md](../structure/contracts.md)).
  - Diff không có secret hay dữ liệu thật.
- Merge bằng **Create a merge commit**. Không dùng Squash hay Rebase, để giữ nguyên lịch sử commit của từng người.
- Khi được góp ý: sửa bằng commit mới trên cùng nhánh, push lên, trả lời từng góp ý trong PR.
- PR của chính nhóm trưởng: tự review diff, ghi trong mô tả những gì đã kiểm, chờ CI xanh rồi merge.
- Không xóa nhánh cá nhân sau khi merge.

## CI

| Workflow | Chạy khi | Kiểm tra | Trạng thái |
|---|---|---|---|
| `pipeline.yml` | PR, hoặc push vào `main`, có đổi `pipeline/` hay `contracts/pipeline/` | `ruff check`, `ruff format --check`, `pytest -m "not model"` (gồm test drift của contract) | ✓ |
| `evaluation.yml` | PR, hoặc push vào `main`, có đổi `evaluation/` | `ruff check`, `ruff format --check`, `pytest`, `check_manifest.py` | ✓ |
| `frontend.yml` | PR có đổi `frontend/`, push vào `main` hoặc `vantuong` | `lint`, `format:check`, `typecheck`, `test`, `build` | ◐ nhánh `vantuong` |
| `backend.yml`, `contracts.yml`, `e2e.yml`, `security.yml` | | | ○ B |

- CI đỏ thì tác giả PR sửa. Không merge khi CI đỏ. Không xóa hay skip test để CI xanh.
- Test cần GPU hoặc model thật gắn marker `model`. CI không chạy các test này ([testing.md](testing.md)).

## Tag theo mốc

Nhóm trưởng gắn tag trên `main` khi đạt mốc: `v0.1.0` (M1, tuần 4), `v0.2.0` (M2, tuần 6), `v0.3.0` (M3, tuần 8), `v1.0.0-rc.1` (M4, tuần 9), `v1.0.0` (demo).
