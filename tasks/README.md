# tasks/

Phân công việc theo ngày cho cả 3 thành viên. **Đầu mỗi buổi làm việc, đọc file của mình trong thư mục của ngày hôm đó.**

## Cấu trúc

```text
tasks/
├── README.md                 # file này
└── <YYYY-MM-DD>/
    ├── member-a.md           # A: frontend (@mactuongmvt, nhánh vantuong)
    ├── member-b.md           # B: backend (@minhquangha)
    └── member-c.md           # C: pipeline, evaluation, nhóm trưởng (@TAINGUYENVAN0507, nhánh tainguyen)
```

## Quy tắc

- **Mỗi người làm 5 commit mỗi ngày.** Mỗi commit là một thay đổi có nghĩa, có test, theo format trong [`rules/git-workflow.md`](../rules/git-workflow.md). Merge commit (khi cập nhật nhánh theo `main`) không tính vào 5 commit.
- Mỗi commit trong file phân công ghi rõ: Task ID, việc cần làm, file chính, điều kiện xong, lệnh kiểm tra, message gợi ý. Message có thể đổi chữ nhưng phải giữ type, scope và Task ID.
- **Bước 0** (cập nhật nhánh, gỡ conflict) làm trước 5 commit và không tính vào 5 commit.
- Làm xong commit nào thì tick `[x]` và ghi hash commit vào file của mình, trên nhánh của mình. File đó đi vào `main` cùng PR cuối ngày.
- Cuối ngày mở PR (hoặc push thêm vào PR đang mở) từ nhánh cá nhân vào `main`. Nhóm trưởng review và merge.
- Việc chưa xong trong ngày được chuyển sang file của ngày hôm sau, ghi rõ "chuyển từ <ngày>".
- Nhóm trưởng tạo file phân công cho ngày mới. Muốn đổi việc: báo nhóm trưởng, hoặc sửa file của mình và ghi lý do.
- Việc trong file phân công phải theo kế hoạch triển khai và `structure/`, `rules/`. Khi khác nhau, theo `structure/` và `rules/`.
