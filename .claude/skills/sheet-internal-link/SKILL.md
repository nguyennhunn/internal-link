---
name: sheet-internal-link
description: Đọc/ghi Google Sheet kế hoạch internal link (tab "Internal link" và tab "Cụm từ khoá") qua Google Sheets API v4 bằng script Python thuần. Dùng khi agent internal-link cần đọc danh sách bài cần chèn, ghi đoạn văn đã viết về sheet, thêm dòng kế hoạch mới, hoặc khi người dùng nói "kết nối sheet internal link", "đọc sheet internal link". Không viết nội dung, không sửa bài trên web.
---

# sheet-internal-link

Tay đọc/ghi sổ cho agent `internal-link`. Mọi thao tác đi qua **một script duy nhất**
`scripts/sheets.py` (đã allowlist trong `.claude/settings.json`) — KHÔNG gọi `curl`/`python -c` trực tiếp.

## Cấu trúc sheet mà skill này hiểu

### Tab `Internal link` (bắt buộc)

| Cột | Header đúng chữ | Ai điền |
|---|---|---|
| A | `STT` | người |
| B | `Key mục tiêu` | người |
| C | `URL đích` | người — bài muốn kéo link về |
| D | `Anchor text` | người |
| E | `Bài cần chèn` | người — URL bài sẽ chèn link vào |
| F | `Đoạn chèn` | **agent** — 2-3 câu, có sẵn thẻ `<a>` |
| G | `Vị trí chèn` | **agent** — "Sau đoạn: <10 chữ đầu…>" hoặc "Sau H2: …" |
| H | `Trạng thái` | agent ghi `Đã viết`; người sửa thành `Đã duyệt` / `Đã chèn` / `Bỏ qua` |
| I | `Ghi chú` | agent — vd "bài đã có link tới URL đích", "không tìm thấy đoạn hợp" |

Dòng cần xử lý = có `Bài cần chèn` + có `Anchor text` + `Đoạn chèn` trống + `Trạng thái` ≠ `Bỏ qua`.

### Tab `Cụm từ khoá` (chỉ khi chạy chế độ nhóm từ khoá chính/phụ)

| Cột | Header | Ghi chú |
|---|---|---|
| A | `Cụm` | tên cụm, vd "xe máy điện" |
| B | `Từ khoá` | |
| C | `Loại` | `Chính` hoặc `Phụ` — mỗi cụm đúng 1 dòng Chính |
| D | `URL bài` | bài đang giữ từ khoá đó |

## Lần đầu kết nối (làm 1 lần / máy)

1. Tạo OAuth Client ID (Desktop app) tại console.cloud.google.com/apis/credentials, bật **Google Sheets API**.
   Dùng Client ID **riêng** cho skill này (không dùng chung với skill Google khác — giới hạn 50 token/Client ID).
   Consent screen phải ở **In production**, nếu để Testing thì token chết sau 7 ngày.
2. ```
   python .claude/skills/sheet-internal-link/scripts/sheets.py set-client .claude/skills/sheet-internal-link/sheets-accounts.local.json <key> <client_id> <client_secret> <spreadsheet_id>
   python .claude/skills/sheet-internal-link/scripts/sheets.py oauth .claude/skills/sheet-internal-link/sheets-accounts.local.json <key>
   ```
   `<key>` = tên dự án gợi nhớ (vd `osakar`). `<spreadsheet_id>` = đoạn giữa `/d/` và `/edit` trên URL sheet.
3. Ghi `<key>` + tên tab vào `.claude/CLAUDE.md` (xem `CLAUDE.md.example`).

Mỗi người trong team tự làm bước này trên máy mình — file `*.local.json` không chia sẻ, không commit.

## Lệnh dùng hằng ngày

```
S=.claude/skills/sheet-internal-link/scripts/sheets.py
A=.claude/skills/sheet-internal-link/sheets-accounts.local.json
python $S tabs $A <key>                                  # xem tên tab thật
python $S read $A <key> "Internal link" .tmp/sheet.json  # đọc
python $S update-cell $A <key> "Internal link" F5 "<p>...</p>"
python $S append-rows $A <key> "Internal link" .tmp/rows.json
```

`read` xuất JSON `{headers:[{index,text,hyperlink}], rows:[{rowIndex, values{header: text}, hyperlinks{header: url}}]}`.
Ghi ô nào thì dùng đúng `rowIndex` từ JSON, không tự đếm.

## Không làm

- Không ghi đè ô `Đoạn chèn` đã có chữ trừ khi người dùng bảo viết lại.
- Không đoán tên cột: header sai chữ → dừng, báo tên header thật cho người dùng sửa sheet.
- Không in `client_secret`/`refresh_token` ra chat.
