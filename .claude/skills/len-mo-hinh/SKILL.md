---
name: len-mo-hinh
description: Lên mô hình internal link — quyết định bài nguồn nào chèn link tới bài đích nào, mỗi anchor bao nhiêu lần — dựa trên NỘI DUNG từng bài chứ không dựa vào chữ trong URL. Quét link sẵn có và chuyển hướng, chấm độ hợp từng cặp bài × anchor, đo sức chứa so với số lần yêu cầu và HỎI người dùng khi thiếu, rồi xếp và ghi cột Key/URL/Anchor vào sheet. Dùng khi người dùng đưa bảng anchor + số lần cần chèn và danh sách bài, nói "lên mô hình internal link", "phân bổ anchor", "mỗi bài chèn 3 inlink", hoặc khi cần xếp lại vì nhiều đoạn khó nối.
---

# len-mo-hinh

Bài học 15/10/2026 (sheet OSAKAR 1510): mô hình xếp theo chữ trong URL ép bài camera phạt nguội, biển báo, cung hoàng đạo nhận 3 link → 208/428 đoạn bị chấm không phù hợp, phải sửa 3 vòng. 143 bài thật ra chỉ có ~291 chỗ chèn tự nhiên cho 429 link — biết sớm thì người dùng đã chọn thêm bài nguồn. Skill này làm đúng thứ tự: **quét → chấm → đo sức chứa → hỏi → xếp → ghi**.

```
M=.claude/skills/len-mo-hinh/scripts/mo_hinh.py
D=.claude/skills/doc-bai/scripts/doc_bai.py
S=.claude/skills/sheet-internal-link/scripts/sheets.py
A=.claude/skills/sheet-internal-link/sheets-accounts.local.json
W=.tmp/mo-hinh            # mkdir -p $W/cham
```

## 1. Đầu vào

- **Bảng đích** (người dùng đưa: ảnh, sheet, chat) → ghi `$W/dich.json`:
  `[{"id":"A1","anchor":"…nguyên chữ…","url":"https://…","so_lan":30,"mo_ta":"bài đích nói gì, dành cho ai"}]`.
  `mo_ta` đọc từ tiêu đề/H1 bài đích (`doc_bai.py fetch`) — người chấm cần biết bài đích hứa gì. Ghi chú bất thường (vd anchor "dưới 10 triệu" nhưng URL là bài dưới 12 triệu) → báo người dùng ngay.
- **Bài nguồn**: `python $S read $A <key> "<tab>" $W/sheet.json` rồi `python $M nguon $W/sheet.json $W/nguon.json` (lấy cột "Bài cần chèn" kèm số hàng thật).
- So nhanh: tổng `so_lan` vs số bài × 3. Lệch → nói luôn với người dùng.

## 2. Quét (máy)

```
python $D quet $W/nguon.json $W/dich.json $W/quet.json $W/bai
```
Mỗi cặp bài × đích: `co_link` (đã có link trong CÂU VĂN — không chèn nữa), `liet_ke` (chỉ ở dòng "Xem thêm" — vẫn chèn được, nhắc bỏ dòng đó), `tu_tro` (bài nguồn là / chuyển hướng 301 về bài đích), `chua`. Bài nguồn chuyển hướng → báo người dùng thay URL.

## 3. Chấm độ hợp (người đọc — không dùng máy)

Mỗi bài: `python $M xem $W/bai/<rowIndex>.json` (in gọn heading, đoạn văn, loại khối, chỗ có link). Đọc CẢ BÀI rồi chấm từng anchor, ghi `$W/cham/<rowIndex>.json`:
```json
{"rowIndex":14,"diem":{"A1":{"d":2,"cho":"cuối mục 5 'Đi xe gì không cần bằng lái'","ly_do":"…"}, "A2":{…}}}
```
| Điểm | Nghĩa |
|---|---|
| 3 | Có một chỗ cuối mục mà ý của bài TỰ DẪN tới chủ đề bài đích (bài "đi xe gì không cần bằng" ↔ xe cho học sinh; bài màu xe hợp tuổi ↔ xe đẹp; bài sạc/pin ↔ xe tốt nhất). |
| 2 | Nối hợp lý qua đối tượng người đọc CỤ THỂ có trong bài (học sinh, phụ huynh, sinh viên, người mua xe…). |
| 1 | Chỉ nối được bằng câu chung ("nếu đang chọn xe…", "kiểu dáng cũng quan trọng…") — người đọc thấy gượng. |
| 0 | Không nối được, hoặc bài đã có link tới đích trong câu văn. |

Nghiêm như người duyệt. Ví dụ HỎNG (điểm 1 hoặc 0): bài biển báo hầm đang so sánh biển thì nhảy sang "phụ huynh tham khảo bảng giá xe cho học sinh cấp 3". Bài camera phạt nguội thường chỉ có MỘT mục chọn phương tiện → chỉ 1 anchor điểm cao ở mục đó; anchor khác phải có chỗ riêng (mỗi mục chỉ nhận 1 đoạn, các đoạn cách nhau ≥ 3 đoạn văn) — ghi rõ chỗ cho từng anchor điểm cao. Kiểm sự thật về đối tượng (vd xe máy điện chỉ cho người đủ 16 tuổi; người sinh 2008 đã 18).
Nhiều bài (> 30) → chia nhóm cho agent con chấm song song; mỗi nhóm thư mục nháp riêng; giao bảng tiêu chí này + `dich.json`.

## 4. Đo sức chứa — BẮT BUỘC trước khi xếp

```
python $M suc-chua $W/dich.json $W/quet.json $W/cham
```
In theo từng anchor: số bài hợp ≥2 / ≥1, xếp được bao nhiêu ở mức tự nhiên (≥2) và mức cho phép nối chung (≥1), so với số lần cần. **Thiếu ở mức ≥2 → DỪNG, hỏi người dùng** (bảng số + 3 lựa chọn):
(a) thêm bài nguồn (gợi ý loại bài còn thiếu cho anchor nào), (b) cho phép câu nối chung (xếp được X), (c) chỉ giữ link tự nhiên (chấp nhận thiếu).

## 5. Xếp

```
python $M xep $W/dich.json $W/quet.json $W/cham $W/plan.json --min 2      # hoặc --min 1 nếu người dùng chọn (b)
# xếp lại khi sheet đã có mô hình: thêm --giu $W/sheet.json  (giữ cặp đang có nếu còn hợp; cặp đã dán lên web tính là xong)
```
Đọc kết quả: tổng/anchor thiếu, bài ít hơn 3 link, phân bố điểm. Báo người dùng trước khi ghi.

## 6. Ghi sheet (chỉ cột Key/URL/Anchor 1–3)

```
python $M ghi-sheet $W/plan.json $W/sheet.json $W/changes.json $W/dich.json
python $S write-rows $A <key> "<tab>" $W/changes.json --thu      # xem trước
python $S write-rows $A <key> "<tab>" $W/changes.json            # ghi: tự sao lưu, kiểm `expect`, anchor gắn link
```
Không đụng cột đoạn chèn, trạng thái, PIC. Cặp điểm 1 → khi viết đoạn phải ghi chú "NỐI CHUNG:".

## Không làm

- Không xếp theo chữ trong URL/slug. Không xếp trước khi đo sức chứa và hỏi khi thiếu.
- Không tính link ở trang sản phẩm (`/xe-ban-dap/velux/`) là link tới danh mục (`/xe-ban-dap/`).
- Không ghi chữ vào cột ô tick; không ghi khi `expect` lệch (sheet bị sửa trong lúc chạy).
