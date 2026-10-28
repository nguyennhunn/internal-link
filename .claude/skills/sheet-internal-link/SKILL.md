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
| A | `STT` / `PIC` | người (agent không đọc, không ghi) |
| B, C, D | `Key mục tiêu 1` · `URL đích 1` · `Anchor text 1` | người |
| E, F, G | `Key mục tiêu 2` · `URL đích 2` · `Anchor text 2` | người — để trống nếu chỉ 1 link |
| H, I, J | `Key mục tiêu 3` · `URL đích 3` · `Anchor text 3` | người — để trống nếu ≤ 2 link |
| K | `Bài cần chèn` | người — URL bài sẽ chèn link vào |
| L | `Đoạn cần chèn` | **agent** — HTML `<p>` có `<a>`, để dán vào bài; nhiều link thì đánh số `[1]`, `[2]`, `[3]`, cách nhau một dòng trống |
| M | `Đoạn chèn (đọc duyệt)` | **agent** — cùng nội dung dạng chữ thường, anchor bọc «…», để người duyệt đọc. Sheet chưa có cột này → agent tự tạo bằng `insert-column` |
| N | `Vị trí chèn` | **agent** — đánh số tương ứng |
| O | `Trạng thái` | nếu là cột chữ: agent ghi `Đã viết` / `Đã viết 2/3`, người sửa thành `Đã duyệt` / `Đã chèn` / `Bỏ qua`. Nếu người dùng đổi thành **ô tick** → cột của người, agent KHÔNG ghi (script tự chặn) |
| P | `Ghi chú` | agent — vd "[2] bài đã có link tới URL đích" |

Chữ cột (A, B…) chỉ để minh hoạ — script tìm cột theo **tên header**, và tìm **dòng tiêu đề** = dòng đầu (trong 10 dòng đầu) có ô `Bài cần chèn`. Người dùng chèn dòng ghi chú/NOTE phía trên hay thêm cột vẫn chạy đúng.

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
python $S write-rows $A <key> "Internal link" .tmp/changes.json --thu   # xem trước
python $S write-rows $A <key> "Internal link" .tmp/changes.json         # ghi
python $S restore $A <key> .tmp/sao-luu/<key>-<thời-gian>.json          # trả lại ô cũ nếu ghi nhầm
python $S insert-column $A <key> "Internal link" L "Đoạn chèn (đọc duyệt)"   # chèn cột mới ngay sau L (1 lần/sheet)
```

Cả hai cách đều xuất JSON `{header_row, headers:[{index,cot,text,o_tick}], rows:[{rowIndex, values{header: text}, hyperlinks}]}` (cách 1 có thêm `read_only: true`). `rowIndex` = số hàng THẬT trên sheet.

## Ghi an toàn — luôn dùng `write-rows`

`changes.json` = `[{"rowIndex": 14, "expect": {"Bài cần chèn": "<url đang ở hàng đó>", "Đoạn cần chèn": "<giá trị lúc đọc>"}, "set": {"Đoạn cần chèn": "…", "Anchor text 1": {"text": "…", "link": "https://…"}, "URL đích 3": ""}}]`
- Tìm cột theo tên; `set` giá trị `""` = xoá ô; `{"text","link"}` = chữ có gắn link.
- `expect` lệch (người dùng sửa sheet, chèn/xoá dòng trong lúc agent chạy) → bỏ qua hàng đó, báo, không ghi.
- Cột ô tick → bỏ qua, không ghi chữ.
- Trước khi ghi tự sao lưu ô cũ vào `.tmp/sao-luu/<key>-<thời-gian>.json`; `restore` trả lại.
- Luôn chạy `--thu` trước, đọc số ô/hàng sẽ ghi và cảnh báo, rồi mới ghi thật.

## Không làm

- Không ghi đè ô `Đoạn cần chèn` đã có chữ trừ khi người dùng bảo viết lại.
- Không ghi bằng địa chỉ ô tự đếm (`update-cell L5`) cho việc ghi hàng loạt — dùng `write-rows`.
- Chỉ ghi đúng cột người dùng yêu cầu; không ghi cột người dùng tự quản (PIC, ô tick).
- Không đoán tên cột: header sai chữ → dừng, báo tên header thật cho người dùng sửa sheet.
- Không in `client_secret`/`refresh_token` ra chat.
