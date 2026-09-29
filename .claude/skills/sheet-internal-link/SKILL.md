---
name: sheet-internal-link
description: Đọc/ghi Google Sheet kế hoạch internal link (tab "Internal link") bằng script Python thuần — đọc không cần OAuth nếu sheet chia sẻ công khai, ghi ngược lại sheet thì cần OAuth. Dùng khi agent internal-link cần đọc danh sách bài cần chèn, ghi đoạn văn đã viết về sheet, hoặc khi người dùng nói "kết nối sheet internal link", "đọc sheet internal link". Không viết nội dung, không sửa bài trên web.
---

# sheet-internal-link

Tay đọc/ghi sổ cho agent `internal-link`. Mọi thao tác đi qua **một script duy nhất**
`scripts/sheets.py` (đã allowlist trong `.claude/settings.json`) — KHÔNG gọi `curl`/`python -c` trực tiếp.

## Cấu trúc sheet — mỗi hàng là MỘT bài cần chèn, tối đa 3 link

| Cột | Header đúng chữ | Ai điền |
|---|---|---|
| A | `STT` | người (có thể để trống, agent dùng số hàng) |
| B, C, D | `Key mục tiêu 1` · `URL đích 1` · `Anchor text 1` | người |
| E, F, G | `Key mục tiêu 2` · `URL đích 2` · `Anchor text 2` | người — để trống nếu chỉ 1 link |
| H, I, J | `Key mục tiêu 3` · `URL đích 3` · `Anchor text 3` | người — để trống nếu ≤ 2 link |
| K | `Bài cần chèn` | người — URL bài sẽ chèn link vào |
| L | `Đoạn cần chèn` | **agent** — nhiều link thì đánh số `[1]`, `[2]`, `[3]`, cách nhau một dòng trống |
| M | `Vị trí chèn` | **agent** — đánh số tương ứng |
| N | `Trạng thái` | agent ghi `Đã viết` (hoặc `Đã viết 2/3` khi có link bị bỏ qua); người sửa thành `Đã duyệt` / `Đã chèn` / `Bỏ qua` |
| O | `Ghi chú` | agent — vd "[2] bài đã có link tới URL đích" |

Một bộ link được tính là **có** khi cả `URL đích n` và `Anchor text n` đều có chữ (`Key mục tiêu n` trống → dùng anchor làm key).
Bộ có URL mà thiếu anchor (hoặc ngược lại) → không viết, ghi chú "[n] thiếu anchor/URL".

Hàng cần xử lý = có `Bài cần chèn` + ít nhất 1 bộ link đủ + `Đoạn cần chèn` trống + `Trạng thái` ≠ `Bỏ qua`.

## Hai cách đọc

**Cách 1 — sheet chia sẻ công khai (không cần cài gì):** sheet để *Share → Anyone with the link → Viewer*.
```
python .claude/skills/sheet-internal-link/scripts/sheets.py read-public <spreadsheet_id> <gid> .tmp/sheet.json
```
`<gid>` là số sau `#gid=` trên URL (tab đầu tiên là `0`). Chỉ đọc — kết quả ghi vào trang HTML duyệt, **không ghi được về sheet**; người dùng tự dán từ trang duyệt.

**Cách 2 — nối OAuth (đọc + ghi ngược lại sheet):** làm 1 lần / máy.
1. Tạo OAuth Client ID (Desktop app) tại console.cloud.google.com/apis/credentials, bật **Google Sheets API**.
   Client ID **riêng** cho skill này. Consent screen phải **In production** (Testing → token chết sau 7 ngày).
2. ```
   python .claude/skills/sheet-internal-link/scripts/sheets.py set-client .claude/skills/sheet-internal-link/sheets-accounts.local.json <key> <client_id> <client_secret> <spreadsheet_id>
   python .claude/skills/sheet-internal-link/scripts/sheets.py oauth .claude/skills/sheet-internal-link/sheets-accounts.local.json <key>
   ```
   `<key>` = tên dự án gợi nhớ (vd `osakar`). `<spreadsheet_id>` = đoạn giữa `/d/` và `/edit` trên URL sheet.
3. Ghi `<key>` + tên tab vào `.claude/CLAUDE.md`.

Mỗi người trong team tự làm trên máy mình — `*.local.json` không chia sẻ, không commit.

## Lệnh dùng hằng ngày (cách 2)

```
S=.claude/skills/sheet-internal-link/scripts/sheets.py
A=.claude/skills/sheet-internal-link/sheets-accounts.local.json
python $S tabs $A <key>                                  # xem tên tab thật
python $S read $A <key> "Internal link" .tmp/sheet.json  # đọc
python $S update-cell $A <key> "Internal link" L5 "<p>...</p>"
```

Cả hai cách đều xuất JSON `{headers:[{index,text}], rows:[{rowIndex, values{header: text}}]}` (cách 1 có thêm `read_only: true`).
Ghi ô nào thì dùng đúng `rowIndex` từ JSON, không tự đếm. Chữ cột suy từ `headers[].index` (0→A, 11→L).

## Không làm

- Không ghi đè ô `Đoạn cần chèn` đã có chữ trừ khi người dùng bảo viết lại.
- Không đoán tên cột: header sai chữ → dừng, báo tên header thật cho người dùng sửa sheet.
- Không in `client_secret`/`refresh_token` ra chat.
