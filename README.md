# agent-internal-link — Agent viết internal link cho dự án SEO (Claude Code)

Bạn điền vào Google Sheet: **bài cần chèn – anchor text – URL đích**. Agent tự **đọc bài**, tìm **đoạn hợp nghĩa nhất**,
**viết 2-3 câu** chứa anchor sao cho khớp ngữ cảnh, ghi lại vào sheet và xuất **trang HTML để duyệt** (có nút sao chép).
Agent chỉ làm việc theo **key mục tiêu đã có sẵn** — việc lập kế hoạch link theo cụm từ khoá chính/phụ thuộc agent khác.

Agent **không** tự sửa bài trên website — người duyệt dán vào. An toàn cho mọi dự án.

## Trong repo có gì

| Thành phần | Vai trò |
|---|---|
| `agent: internal-link` | Điều phối: đọc sheet → từng dòng → gọi các skill → ghi sheet → xuất trang duyệt |
| `skill: sheet-internal-link` | Đọc/ghi Google Sheet (Python thuần, không cần cài thêm gì) |
| `skill: doc-bai` | Tải bài, tách đoạn, chấm điểm đoạn hợp nghĩa, kiểm tra bài đã có link chưa |
| `skill: chen-internal-link` | Quy tắc viết đoạn 2-3 câu chứa anchor |
| `skill: xuat-duyet` | Trang HTML duyệt theo nhận diện SEONGON |

## Yêu cầu

- [Claude Code](https://claude.com/claude-code), Git, **Python 3.10+** (Windows: tải ở python.org, tích "Add to PATH").
- Một Google Sheet có tab `Internal link` (xem mẫu bên dưới) và quyền sửa sheet đó.

## Cài đặt (làm 1 lần / người)

1. Tải repo về máy:
   ```bash
   git clone https://github.com/<tài-khoản>/agent-internal-link.git
   ```
2. Mở Claude Code **đúng trong thư mục `agent-internal-link`** (script gọi bằng đường dẫn tương đối, mở sai thư mục sẽ không chạy).
3. Copy `CLAUDE.md.example` → `.claude/CLAUDE.md`, sửa sheet-key, spreadsheet ID, tên dự án, quy tắc riêng.
4. Kết nối Google Sheet — nói với Claude: **"kết nối sheet internal link"**. Claude dẫn từng bước:
   tạo OAuth Client ID (Desktop app, bật Google Sheets API, consent screen để *In production*), chạy lệnh `set-client` rồi `oauth`,
   bấm Cho phép trên trình duyệt. Token lưu vào `sheets-accounts.local.json` — file này đã bị chặn commit.

## Sheet mẫu

**Tab `Internal link`** — header đúng chữ, dòng 1:

| STT | Key mục tiêu | URL đích | Anchor text | Bài cần chèn | Đoạn chèn | Vị trí chèn | Trạng thái | Ghi chú |
|---|---|---|---|---|---|---|---|---|
| 1 | xe máy điện đẹp | https://…/xe-may-dien-dep/ | xe máy điện đẹp | https://…/xe-may-dien-nam/ | *(agent điền)* | *(agent điền)* | *(agent điền)* | |

Bạn điền 5 cột đầu. Agent điền 3 cột sau + ghi chú. Duyệt xong bạn đổi `Trạng thái` thành `Đã chèn`.

## Dùng hằng ngày

Trong Claude Code, nói:

- **"chạy agent internal link"** → viết đoạn cho mọi dòng chưa có `Đoạn chèn`, xuất `duyet-internal-link-<ngày>.html`.
- **"chạy internal link dòng 3, 5"** → chỉ làm các STT đó.
- **"viết lại dòng 4"** → viết lại một dòng đã có.

Mở file HTML bằng trình duyệt: mỗi thẻ hiện *đoạn trước → đoạn chèn (khung xanh) → đoạn sau*, bấm **Sao chép HTML** rồi dán vào bài ở chế độ soạn thảo HTML/Code.

## Chia sẻ cho team

1. Repo để **Private**, mời đồng nghiệp: GitHub → Settings → Collaborators → Add people.
2. Mỗi người tự làm mục *Cài đặt* trên máy mình. Client ID/Secret của Google có thể dùng chung (chủ repo gửi riêng, không commit); `refresh_token` là của từng người vì nó gắn với tài khoản Google của họ — họ cần quyền **Editor** trên sheet.
3. Sửa quy tắc viết → sửa `.claude/skills/chen-internal-link/SKILL.md`, commit và push; người khác `git pull` là có bản mới.
4. Sheet của dự án khác → thêm một sheet-key mới trong `sheets-accounts.local.json` và đổi `.claude/CLAUDE.md`.

## Một bài chèn 2-3 link thì sao?

Cứ tạo 2-3 dòng có cùng `Bài cần chèn`. Agent gom các dòng cùng bài lại, tải bài **một lần**, chia các chỗ chèn **cách nhau ít nhất 3 đoạn**, mỗi đoạn chỉ chứa **một** link và các đoạn không nhắc tới nhau. Nếu số link quá dày so với độ dài bài (hơn 1 link mỗi 8 đoạn), agent vẫn viết nhưng ghi cảnh báo vào cột Ghi chú để bạn cân nhắc bớt.

## ⚠ Những điều phải biết

- **Bảo mật:** `*.local.json` chứa token thật. `.gitignore` đã chặn — đừng gỡ, đừng gửi qua chat.
- **Google OAuth:** mỗi skill Google một Client ID riêng (giới hạn 50 token/Client ID); consent screen phải *In production*, để *Testing* thì token chết sau 7 ngày.
- **Trang chặn bot / render bằng JavaScript** → không đọc được bài; agent sẽ ghi `Lỗi` vào Trạng thái, bạn dán nội dung bài trực tiếp cho Claude.
- **Anchor text:** agent giữ nguyên từng chữ, chỉ thêm từ đệm xung quanh. Anchor không xuôi câu → agent ghi đề xuất vào Ghi chú, bạn quyết.
- **Nội dung:** agent không bịa số liệu, cấm từ tuyệt đối. Bạn vẫn là người duyệt cuối.
