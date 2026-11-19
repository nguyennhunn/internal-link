---
name: kiem-link
description: Dò link nội bộ trong thân bài (bỏ menu/footer) của một danh sách trang hoặc sitemap — link 404, link đi qua chuyển hướng 301/302, link tự trỏ về chính bài qua chuyển hướng, bài trỏ cùng một đích quá nhiều lần — và đổi link 301 sang URL cuối trên WordPress (sao lưu từng bài, chỉ đổi href). Dùng khi người dùng nói "check link 404", "dò link 301", "link nội bộ lỗi", "đổi link cũ sang URL mới", hoặc sau khi chuyển web / 301 gộp bài.
---

# kiem-link

```
K=.claude/skills/kiem-link/scripts/kiem_link.py
```

## Dò (không cần đăng nhập)

`python $K quet <ds-url.txt | https://site/sitemap.xml> .tmp/kiem-link/kq.json [--lap 3] [--toi-da 300]`

- Đọc thân bài bằng `doc_bai` (bỏ menu, footer, sidebar), lấy mọi link cùng tên miền.
- Theo chuyển hướng từng link (giữ đúng dạng href gốc, nên `/x` → `/x/` do thiếu dấu gạch cuối không bị tính là 301).
- In: link 404 (kèm số trang), link qua chuyển hướng (→ URL cuối), link tự trỏ về chính bài, trang trỏ cùng 1 đích ≥ `--lap` lần.
- Báo người dùng bằng số thật; ghi rõ phạm vi (chỉ các trang đã quét, không phải toàn site).
- Muốn ghi lên sheet: tạo tab riêng (vd "Link 404") cạnh tab inlink, cột: bài chứa link lỗi | link | anchor | mã | chuyển tới | ngày kiểm.

## Tìm URL thay cho link 404

Không có lệnh tự động — tìm theo slug + tiêu đề + anchor trong danh sách bài đang đăng (REST `/wp-json/wp/v2/<kiểu>?per_page=100`),
kiểm URL đề xuất trả 200 thẳng, ghi độ khớp Cao / Trung bình / Thấp / Không có kèm căn cứ. **Người dùng chốt rồi mới thay.**

## Đổi link 301 sang URL cuối (WordPress)

Cần kết nối của skill `chen-wordpress` (cùng `<key>`).

1. `python $K doi-301 <key> .tmp/kiem-link/kq.json --thu` — chỉ đếm số bài, số lượt sẽ đổi.
2. Người dùng đồng ý → bỏ `--thu`. Mỗi bài: sao lưu, đổi đúng phần href (giữ `#…`, `?…`), kiểm phần còn lại y nguyên rồi mới ghi.
3. Chạy lại `quet` để xác nhận không còn link 301 trong các bài đã đổi.

## Lưu ý

- Link 301 về **trang danh mục** hoặc **trang chủ** (bài cũ đã xoá) — liệt kê riêng cho người dùng, không coi là "đúng bài".
- Link tự trỏ về chính bài: báo người dùng, đề xuất bỏ link (không tự xoá).
- Bài trỏ cùng đích nhiều lần: báo, đề xuất bỏ dòng "Xem thêm"/liệt kê trùng; không tự xoá nội dung.
