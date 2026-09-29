---
name: internal-link-cum
description: Lập kế hoạch internal link theo nhóm từ khoá chính/phụ (mô hình bài trụ - bài vệ tinh) từ tab "Cụm từ khoá" trên Google Sheet, sinh ra các dòng (bài cần chèn, anchor, URL đích) vào tab "Internal link" để agent viết đoạn chèn. Dùng khi người dùng nói "lập kế hoạch internal link theo cụm", "link theo từ khoá chính phụ", "dựng cấu trúc link cho cụm".
---

# internal-link-cum

Biến bảng cụm từ khoá thành danh sách cặp link cụ thể. Không viết văn — chỉ **quyết định ai link tới ai với anchor gì**;
việc viết đoạn chèn giao cho `chen-internal-link` như mọi dòng khác.

## Mô hình mặc định: trụ – vệ tinh

Trong một cụm: 1 bài **Chính** (giữ từ khoá chính, volume lớn) + n bài **Phụ** (từ khoá dài, ý nhỏ).

| Chiều | Anchor | Mục đích |
|---|---|---|
| Phụ → Chính | từ khoá chính | dồn sức mạnh về bài trụ — quan trọng nhất |
| Chính → Phụ | từ khoá phụ | bài trụ thành mục lục của cụm, chia link ra vệ tinh |
| Phụ → Phụ kế tiếp (tuỳ chọn `--vong-tron`) | từ khoá phụ của bài kế | người đọc đi hết cụm, không bài nào là ngõ cụt |

Không tạo link chéo giữa các cụm khác nhau (muốn thì người dùng thêm tay vào tab Internal link).

## Cách chạy

```
S=.claude/skills/sheet-internal-link/scripts/sheets.py
A=.claude/skills/sheet-internal-link/sheets-accounts.local.json
python $S read $A <key> "Cụm từ khoá" .tmp/cum.json
python $S read $A <key> "Internal link" .tmp/il.json
python .claude/skills/internal-link-cum/scripts/ke_hoach_cum.py .tmp/cum.json .tmp/il.json .tmp/rows.json [--vong-tron] [--cum "xe máy điện"]
```

Script in ra danh sách cặp đề xuất. **Cho người dùng xem danh sách và xác nhận** trước khi:

```
python $S append-rows $A <key> "Internal link" .tmp/rows.json
```

Sau khi thêm dòng, chạy tiếp quy trình thường của agent `internal-link` để viết đoạn chèn cho từng dòng.

## Tự động bỏ qua

- Cặp (bài cần chèn → URL đích) đã có trong tab Internal link — không tạo trùng.
- Bài link tới chính nó.
- Cụm không có dòng Chính → cảnh báo, bỏ cụm đó.

## Khi anchor = từ khoá chính lặp quá nhiều

Nếu một cụm có > 5 bài phụ cùng dùng đúng một anchor về bài chính, nhắc người dùng: nên sửa tay 1/3 số anchor thành biến thể
(thêm từ đệm, đổi trật tự) để hồ sơ anchor tự nhiên. Script không tự đổi anchor.
