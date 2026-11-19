# agent-internal-link — Agent viết internal link cho dự án SEO (Claude Code)

Bạn điền vào Google Sheet: **bài cần chèn – anchor text – URL đích**. Agent tự **đọc bài**, tìm **đoạn hợp nghĩa nhất**,
**viết 2-3 câu** chứa anchor sao cho khớp ngữ cảnh, ghi lại vào sheet và xuất **trang HTML để duyệt** (có nút sao chép).
Nếu sheet chưa có mô hình (chỉ có bảng *anchor + số lần cần chèn* và danh sách bài), agent **lên mô hình theo nội dung bài**: quét link sẵn có, chấm độ hợp từng cặp bài × anchor, đo xem đủ chỗ chèn tự nhiên không và **hỏi bạn trước khi xếp** nếu thiếu. Việc lập kế hoạch link theo cụm từ khoá chính/phụ vẫn thuộc agent khác.

Mặc định agent **không** sửa bài trên website — người duyệt dán vào. Với web WordPress, khi bạn cấp Application Password và ra lệnh, agent chèn thẳng lên web (chạy thử, chèn 1 bài, rồi mới chạy hàng loạt; sao lưu từng bài, hoàn tác được).

## Trong repo có gì

| Thành phần | Vai trò |
|---|---|
| `agent: internal-link` | Điều phối: (lên mô hình) → đọc sheet → từng dòng → viết → tự rà → ghi sheet → xuất trang duyệt |
| `skill: mo-hinh-3-den-3-di` | Mô hình chuẩn SEONGON: bài i đi 3 link tới i+1 (key chính), i+2 (key phụ chưa TOP), i+3 (title), quay vòng cuối nhóm; điền cột Inlink 1-3 và sinh hàng cho tab Internal link |
| `skill: len-mo-hinh` | Lên mô hình theo nội dung bài: quét, chấm độ hợp, đo sức chứa, xếp anchor, ghi cột Key/URL/Anchor |
| `skill: sheet-internal-link` | Đọc/ghi Google Sheet (Python thuần): tự tìm dòng tiêu đề, ghi theo tên cột, sao lưu, không ghi vào cột ô tick |
| `skill: doc-bai` | Tải bài, nhận diện cấu trúc (danh sách, bảng, FAQ, khối sản phẩm, kết bài), chọn chỗ cuối mục, kiểm tra link sẵn có và chuyển hướng |
| `skill: chen-internal-link` | Quy tắc viết đoạn 2-3 câu chứa anchor |
| `skill: ra-doan-chen` | Tự rà trước khi ghi: máy kiểm + rà theo 6 lỗi, chỉ ghi đoạn đạt, gắn cờ KHÓ NỐI |
| `skill: xuat-duyet` | Trang HTML duyệt theo nhận diện SEONGON |
| `skill: chen-wordpress` | Chèn đoạn đã duyệt thẳng lên WordPress (Application Password): chạy thử định vị, sao lưu từng bài, kiểm lại trên trang công khai, hoàn tác |
| `skill: kiem-link` | Dò link nội bộ 404 / 301 / tự trỏ / trùng đích trong thân bài; đổi link 301 sang URL cuối trên WordPress |

## Yêu cầu

- [Claude Code](https://claude.com/claude-code), Git, **Python 3.10+** (Windows: tải ở python.org, tích "Add to PATH").
- Một Google Sheet có tab `Internal link` (xem mẫu bên dưới) và quyền sửa sheet đó.

## Cài đặt (làm 1 lần / người)

1. Tải repo về máy (mở Git Bash hoặc PowerShell ở thư mục muốn chứa, ví dụ `D:\`):
   ```bash
   git clone https://github.com/nguyennhunn/internal-link.git
   ```
   Lệnh này tạo thư mục `internal-link`.
2. Mở Claude Code **đúng trong thư mục `internal-link`** vừa tải (script gọi bằng đường dẫn tương đối, mở sai thư mục sẽ không chạy).
3. Copy `CLAUDE.md.example` → `.claude/CLAUDE.md`, sửa sheet-key, spreadsheet ID, tên dự án, quy tắc riêng.
4. *(Tuỳ chọn, chỉ khi muốn agent ghi ngược lại sheet)* Kết nối Google Sheet — nói với Claude: **"kết nối sheet internal link"**. Claude dẫn từng bước:
   tạo OAuth Client ID (Desktop app, bật Google Sheets API, consent screen để *In production*), chạy lệnh `set-client` rồi `oauth`,
   bấm Cho phép trên trình duyệt (Google hiện "ứng dụng chưa xác minh" → bấm *Nâng cao* → *Đi tới agent-internal-link* — app nội bộ, không sao). Token lưu vào `sheets-accounts.local.json` — file này đã bị chặn commit.

## Sheet mẫu

**Tab `Internal link`** — mỗi hàng là **một bài cần chèn**, tối đa 3 link. Header đúng chữ (dòng 1, hoặc thấp hơn nếu bạn chèn dòng ghi chú phía trên — agent tự tìm):

| STT | Key mục tiêu 1 | URL đích 1 | Anchor text 1 | Key mục tiêu 2 | URL đích 2 | Anchor text 2 | Key mục tiêu 3 | URL đích 3 | Anchor text 3 | Bài cần chèn | Đoạn cần chèn | Đoạn chèn (đọc duyệt) | Vị trí chèn | Trạng thái | Ghi chú |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|

Bạn điền các bộ (Key – URL đích – Anchor) và `Bài cần chèn`; chỉ 1 link thì để trống bộ 2, 3. Agent điền 5 cột cuối (nhiều link thì đánh số `[1]`, `[2]`, `[3]`): *Đoạn cần chèn* là HTML để dán vào bài, *Đoạn chèn (đọc duyệt)* là bản chữ thường để đọc, anchor bọc «…». Cột đọc duyệt chưa có thì agent tự tạo. Duyệt xong bạn đổi `Trạng thái` thành `Đã chèn`.

**Hai cách cho agent đọc sheet:**
- *Chỉ đọc, không cần cài gì:* sheet để *Share → Anyone with the link → Viewer*, đưa link cho agent. Kết quả nằm trong trang HTML duyệt, agent không ghi được về sheet.
- *Đọc + ghi về sheet:* nối OAuth theo bước 4 ở mục Cài đặt.

## Dùng hằng ngày

Trong Claude Code, nói:

- **"chạy agent internal link"** → viết đoạn cho mọi hàng chưa có `Đoạn cần chèn`, xuất `duyet-internal-link-<ngày>.html`.
- **"chạy internal link hàng 3, 5"** → chỉ làm các hàng đó.
- **"viết lại hàng 4"** → viết lại một hàng đã có.
- **"lên mô hình 3 đến 3 đi cho nhóm …"** → điền cột Mô hình / Inlink 1-3 theo chuẩn SEONGON rồi sinh hàng Internal link.
- **"lên mô hình internal link"** + bảng anchor/số lần → agent quét, chấm, báo đủ/thiếu chỗ, chờ bạn chọn rồi mới ghi cột Key/URL/Anchor.
- Ghi nhầm? **"khôi phục lần ghi vừa rồi"** → agent dùng file sao lưu trong `.tmp/sao-luu/`.

Mở file HTML bằng trình duyệt: mỗi thẻ hiện *đoạn trước → đoạn chèn (khung xanh) → đoạn sau*, bấm **Sao chép HTML** rồi dán vào bài ở chế độ soạn thảo HTML/Code.

## Chia sẻ cho team

1. Gửi link repo cho đồng nghiệp: `https://github.com/nguyennhunn/internal-link` (repo công khai, ai cũng tải được; muốn sửa code thì chủ repo mời vào Collaborators).
2. Mỗi người tự làm mục *Cài đặt* trên máy mình. Client ID/Secret của Google dùng chung (chủ repo gửi riêng qua Zalo/email, **không** đưa lên GitHub); `refresh_token` là của từng người vì nó gắn với tài khoản Google của họ — họ cần quyền **Editor** trên sheet.
3. Sửa quy tắc viết → sửa `.claude/skills/chen-internal-link/SKILL.md`, commit và push; người khác `git pull` là có bản mới.
4. Sheet của dự án khác → thêm một sheet-key mới trong `sheets-accounts.local.json` và đổi `.claude/CLAUDE.md`.

## Một bài chèn 2-3 link thì sao?

Điền bộ 2, bộ 3 trên cùng hàng. Agent tải bài **một lần**, chia các chỗ chèn **cách nhau ít nhất 3 đoạn**, mỗi đoạn chỉ chứa **một** link và các đoạn không nhắc tới nhau. Nếu số link quá dày so với độ dài bài (hơn 1 link mỗi 8 đoạn), agent vẫn viết nhưng ghi cảnh báo vào cột Ghi chú để bạn cân nhắc bớt.

## ⚠ Những điều phải biết

- **Bảo mật:** `*.local.json` chứa token thật. `.gitignore` đã chặn — đừng gỡ, đừng gửi qua chat.
- **Google OAuth:** mỗi skill Google một Client ID riêng (giới hạn 50 token/Client ID); consent screen phải *In production*, để *Testing* thì token chết sau 7 ngày.
- **Trang chặn bot / render bằng JavaScript** → không đọc được bài; agent sẽ ghi `Lỗi` vào Trạng thái, bạn dán nội dung bài trực tiếp cho Claude.
- **Anchor text:** agent giữ nguyên từng chữ, chỉ thêm từ đệm xung quanh. Anchor không xuôi câu → agent ghi đề xuất vào Ghi chú, bạn quyết.
- **Nội dung:** agent không bịa số liệu, cấm từ tuyệt đối. Bạn vẫn là người duyệt cuối.
