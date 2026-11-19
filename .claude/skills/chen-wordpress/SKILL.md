---
name: chen-wordpress
description: Chèn đoạn internal link đã duyệt thẳng lên website WordPress qua REST API bằng Application Password — đọc lại bài ngay trước khi ghi, định vị đúng chỗ trong mã gốc (cuối mục, sau danh sách/bảng, né chú thích ảnh), sao lưu từng bài, ghi, đọc lại bản lưu và trang công khai; có hoàn tác và lệnh kiểm lại không cần đăng nhập. Dùng khi người dùng nói "chèn lên web", "tự chèn inlink", "chạy inlink thực tế", "kiểm tra inlink còn trên trang không", "hoàn tác bài". Chỉ chạy với đoạn người dùng đã duyệt hoặc đã ra lệnh chèn.
---

# chen-wordpress

```
W=.claude/skills/chen-wordpress/scripts/chen_wp.py
```

## Kết nối (1 lần / dự án)

1. Người dùng (hoặc quản trị web) tạo **Application Password** trong *Người dùng → Hồ sơ → Mật khẩu ứng dụng*.
   Nếu thấy "Mật khẩu ứng dụng đã bị vô hiệu hoá bởi Wordfence": *Wordfence → Bảo vệ tấn công Brute Force* → bỏ tick
   *Disable WordPress application passwords* → Lưu. **Đây là cài đặt bảo mật — để người dùng tự làm, Claude không bấm hộ.**
   Nên tạo trên tài khoản **Biên tập viên**, không dùng Quản trị viên.
2. Người dùng lưu mật khẩu vào file trên máy, KHÔNG dán vào chat. Claude chuyển vào
   `.claude/skills/chen-wordpress/wp-accounts.local.json` (đã chặn commit) theo dạng
   `{"<key>": {"site": "https://ten-mien.vn", "user": "<tên đăng nhập>", "app_password": "<mật khẩu>"}}`,
   không in nội dung ra chat, rồi nhắc người dùng xoá file gốc (và thùng rác OneDrive nếu có).
3. `python $W kiem-quyen <key>` — chỉ đọc: đăng nhập được không, vai trò, quyền sửa, các kiểu nội dung sửa được.
4. Xong việc: nhắc người dùng **thu hồi mật khẩu** và bật lại tuỳ chọn Wordfence.

## Đầu vào `doan.json`

Mỗi đoạn: `bai` (URL bài nguồn), `stt`, `n`, `anchor`, `url_dich`, `html` (`<p>…</p>` đúng 1 link), `doan` (nguyên văn khối
ngay trước chỗ chèn — lấy từ `doc_bai`), `sau` (khối ngay sau), `vi_tri` (`Cuối mục "<heading>" — …`), `muc`.
Chỉ đưa vào đoạn **đã qua `ra-doan-chen`** và người dùng đã duyệt/ra lệnh chèn.

## Quy trình bắt buộc

1. `python $W thu <key> doan.json` — định vị trên bản gốc hiện tại, **không ghi**. Báo người dùng số đoạn định vị được và lý do vướng.
2. Chèn thử **1 bài** người dùng chọn: `python $W chen <key> doan.json --chi <url-bài>` → gửi link bài để người dùng xem.
3. Người dùng đồng ý mới chạy hàng loạt: `python $W chen <key> doan.json` (chạy nền nếu nhiều bài; tự dừng sau 3 bài lỗi liên tiếp,
   chạy lại được — đoạn đã có trên bài thì bỏ qua, không chèn lần 2).
4. `python $W kiem-lai doan.json --out kq.json` — mở trang công khai: mỗi đoạn có đúng 1 lần, đúng anchor + URL; URL đích 200 thẳng.
   Báo cáo bằng số thật; đồng bộ cột Trạng thái trên sheet theo kết quả.

## Công cụ tự chặn (không cần nhớ)

- Đọc lại bài ngay trước khi ghi; định vị trên bản mới nhất.
- Bỏ qua, ghi "cần dán tay" khi: không thấy đoạn trước, đoạn trước lặp mà không phân biệt được, vị trí rơi giữa đoạn văn,
  trong danh sách/bảng/chú thích ảnh/thẻ span, ngay sau heading, heading thực tế khác `Vị trí chèn`.
- Bỏ "bài đã có link tới URL đích" (trừ `--cho-trung`). Bỏ bài Elementor, trang danh mục (API không sửa được).
- Chỉ ghi khi bản mới = bản cũ + đúng các đoạn chèn. Ghi bị báo hết giờ thì đọc lại để biết đã lưu chưa — không ghi lại mù.
- Sao lưu `.tmp/wp/<key>/sao-luu/<id>-<thời điểm>.json` (có `modified_truoc`, `modified_sau`). Log: `.tmp/wp/<key>/chen-log.json`.

## Hoàn tác

`python $W hoan-tac <key> .tmp/wp/<key>/sao-luu/<file>.json` — trả bài về bản trước khi chèn. Từ chối nếu bài đã bị sửa sau lần chèn
(thêm `--ep` khi người dùng chấp nhận mất phần sửa đó). Bản ngay trước khi hoàn tác cũng được lưu lại.

## Không làm

- Không bấm đổi cài đặt bảo mật, không tạo mật khẩu, không đăng nhập wp-admin bằng mật khẩu.
- Không chèn đoạn chưa duyệt; không chạy hàng loạt khi chưa chèn thử 1 bài.
- Không xoá hay sửa nội dung khác của bài ngoài việc thêm đoạn (đổi link 301 dùng skill `kiem-link`).
