---
name: mo-hinh-3-den-3-di
description: Lên mô hình internal link "3 đến – 3 đi" chuẩn SEONGON cho một nhóm bài cùng chủ đề — bài i đi 3 link tới bài i+1 (anchor = từ khoá chính), i+2 (anchor = từ khoá phụ chưa lên TOP), i+3 (anchor = tiêu đề bài), quay vòng cuối nhóm, nên mỗi bài nhận đúng 3 link về với 3 kiểu anchor. Điền cột Mô hình / Inlink 1-3 và sinh hàng cho tab Internal link để agent viết đoạn. Dùng khi người dùng nói "mô hình 3 đến 3 đi", "3 đến – 3 đi", "lên inlink theo nhóm bài", "điền cột Inlink 1 2 3", hoặc đưa sheet có cột STT / Nhóm / Từ khoá chính / URL / Mô hình Internal link.
---

# mo-hinh-3-den-3-di — chuẩn SEONGON (Nhung hướng dẫn 04/11/2026)

## Quy tắc

Trong **một nhóm** bài (cột `Nhóm`, vd "Phạt nguội"), xếp theo `STT`, bài **i** đi 3 link:

| Link | Tới | Anchor text |
|---|---|---|
| Inlink 1 | bài i+1 | **Từ khoá chính** của bài i+1 |
| Inlink 2 | bài i+2 | **Từ khoá phụ chưa lên TOP** của bài i+2 (lấy từ file content + file check top; "chưa TOP" = hạng > 10 hoặc chưa có hạng) |
| Inlink 3 | bài i+3 | **Tiêu đề bài** (title/H1) của bài i+3 |

- **Quay vòng cuối nhóm**: nhóm 10 bài → bài 9 - (10-1-2), bài 10 - (1-2-3). Cột `Mô hình Internal link` ghi dạng `1 - (2-3-4)`.
- Mỗi bài nhận đúng 3 link về từ 3 bài đứng trước: 1 key chính + 1 key phụ + 1 title → hồ sơ anchor tự nhiên.
- **Bài "Chưa đăng"** vẫn giữ chỗ trong chuỗi (STT không đổi): làm đích thì ô anchor/URL để trống kèm ghi chú, làm nguồn thì chưa viết đoạn; đăng xong chạy lại để fill.
- Nhóm < 4 bài: cảnh báo, vẫn xếp (sẽ có bài trùng đích).
- **Key phụ chọn 1 lần rồi cố định** (người dùng chốt 13/11/2026): ghi giá trị vào ô, KHÔNG để hàm tự chọn lại theo hạng mới
  của file check top — hạng đổi làm anchor trên sheet lệch anchor đã chèn lên web. Bài đã nhận link [2] thì key phụ = đúng anchor đã chèn.
  Title cũng vậy: chèn xong thì giữ title đã dùng làm anchor.
- **Các nhóm/chủ đề phải nằm liền khối** trong sheet; STT tăng dần từ 1 theo thứ tự chủ đề (dùng `=ROW()-1` thì thêm/bớt hàng không lệch).
- **Chạy lại khi có bài mới đăng**: đoạn chèn chỉ viết cho link đã có lúc chạy. Mỗi đợt, đối chiếu mô hình với nhật ký đã chèn
  (tab "Đoạn chèn" hoặc `.tmp/wp/<key>/chen-log.json`) để lấy đúng 2 loại việc mới: bài nguồn mới đăng (đủ 3 link) và
  link tới bài đích mới đăng ở các bài nguồn đã chèn trước đó. Không viết lại link đã chèn.
- Bài sắp đăng lại nội dung mới vào URL cũ: không viết đoạn ở vai bài nguồn cho tới khi bài mới lên.
- Ví dụ thật (OSAKAR phạt nguội): bài 1 Bình Dương → "camera đồng nai" (key chính bài 2) · "các tuyến đường có camera phạt nguội ở tphcm" (key phụ bài 3) · "21+ điểm lắp camera phạt nguội Nghệ An mới nhất 2026" (title bài 4).

## Đầu vào cần gom thành `.tmp/nhom.json`

```json
[{"stt":1,"nhom":"Phạt nguội","key_chinh":"camera phạt nguội bình dương","tinh_trang":"Đã đăng",
  "url":"https://…","title":"21+ điểm lắp…","key_phu":[{"key":"các tuyến đường có camera phạt nguội ở bình dương","hang":14}]}, …]
```
- `stt, nhom, key_chinh, tinh_trang, url`: đọc từ tab mô hình (`sheets.py read` / `read-public`).
- `key_phu` + `hang`: đọc **file content** (key phụ của từng bài) và **file check top** (hạng mới nhất) — người dùng chỉ sheet/tab nào; ghép theo URL hoặc key chính. Không có hạng → coi là chưa top.
- `title`: cột Tiêu đề nếu có; thiếu thì `--lay-title` tải H1 từ URL.

## Cách chạy

```
python .claude/skills/mo-hinh-3-den-3-di/scripts/ba_den_ba_di.py xep .tmp/nhom.json .tmp/3den3di.json --top 10 --lay-title
python .claude/skills/mo-hinh-3-den-3-di/scripts/ba_den_ba_di.py rows-sheet .tmp/3den3di.json .tmp/rows-mo-hinh.json --sep ";"
```
1. Đọc `canh_bao` + ghi chú thiếu key phụ/title → **hỏi người dùng** trước khi ghi nếu thiếu nhiều.
2. Ghi 4 cột `Mô hình Internal link`, `Inlink 1`, `Inlink 2`, `Inlink 3` vào tab mô hình (công thức HYPERLINK; sheet tiếng Việt dùng `;`), bằng `sheets.py write-rows` / `update-cell` theo tên cột — sao lưu trước, không đụng cột khác.
3. `internal_link_rows` trong file kết quả = hàng cho tab **Internal link** (mỗi bài nguồn 1 hàng, 3 bộ Key/URL/Anchor): `append-rows` vào tab đó (bỏ qua bài nguồn chưa đăng), rồi chạy agent `internal-link` viết đoạn như thường. Lưu ý Inlink 3 anchor là title dài — khi viết đoạn vẫn giữ nguyên chữ title.

## Không làm

- Không tự chọn key phụ ngoài file content/check top; không bịa title.
- Không đổi STT/thứ tự người dùng đã xếp.
- Không ghi đè cột Inlink đã có chữ nếu không được bảo "xếp lại".
