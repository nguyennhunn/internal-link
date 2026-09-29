---
name: chen-internal-link
description: Quy tắc viết đoạn chuyển tiếp 2-3 câu chứa anchor text để chèn internal link vào một bài có sẵn sao cho khớp ngữ nghĩa với đoạn xung quanh. Dùng khi có (bài cần chèn, anchor text, URL đích) và đã đọc context bài qua skill doc-bai; hoặc khi người dùng nói "viết đoạn chèn link", "viết câu dẫn internal link". Đầu ra là HTML `<p>` có thẻ `<a>` sẵn để dán.
---

# chen-internal-link

Viết **một đoạn 2-3 câu** để chèn vào bài, sao cho người đọc thấy nó vốn thuộc về bài đó,
và trong đoạn có đúng một link `<a href="URL đích">anchor text</a>`.

## Đầu vào cần có trước khi viết

Từ `.tmp/bai-<stt>.json` (skill `doc-bai`): `h1`, `dan_y`, ứng viên đã chọn (`muc`, `truoc`, `doan`, `sau`).
Từ sheet: `Key mục tiêu`, `Anchor text`, `URL đích`.
Nếu biết bài đích nói gì (đã đọc qua `doc_bai.py fetch` hoặc URL đủ rõ nghĩa) thì dùng để câu dẫn hứa đúng thứ bài đích có.

## Quy tắc viết — bắt buộc

1. **2-3 câu, 40-80 từ.** Không dài hơn: đoạn chèn mà dài hơn đoạn gốc là lộ.
2. **Câu 1 nối tiếp ý của đoạn `doan` vừa đọc** — nhắc lại một chi tiết/ý trong đó (không chép nguyên câu), rồi mở ra vấn đề mà bài đích giải quyết.
3. **Câu 2 (hoặc 3) chứa anchor** — anchor nằm **giữa câu**, không mở đầu câu, không đứng một mình cuối câu kiểu "xem thêm: anchor".
4. **Anchor giữ nguyên từng chữ** trong sheet (cả dấu, cả thứ tự từ). Được thêm từ đệm quanh anchor cho xuôi câu ("bài **xe máy điện cho nam** dưới đây", "những mẫu **xe máy điện đẹp** tầm 20 triệu"), không được đổi chữ bên trong anchor. Anchor không hợp ngữ pháp cách nào cũng không xuôi → ghi chú đề xuất anchor khác, vẫn viết bằng anchor gốc.
5. **Giọng văn theo bài gốc**: bài xưng "bạn" thì đoạn chèn xưng "bạn"; bài dùng "anh em" thì theo. Đọc `truoc`/`doan`/`sau` để bắt giọng.
6. **Không lặp thông tin** đã có trong `doan` hoặc `sau`. Không bịa số liệu, giá, thông số. Chỉ dùng thông tin có trong bài hoặc trong tiêu đề/URL bài đích.
7. **Cấm** từ tuyệt đối không chứng minh ("tốt nhất", "số 1", "hàng đầu"), cấm "click vào đây", "tại đây", "xem thêm tại", "bài viết sau".
8. **Một đoạn = một link.** Không nhét thêm link khác. Bài có 2-3 link cần chèn → viết 2-3 đoạn **riêng**, mỗi đoạn ở một chỗ cách nhau ≥ 3 đoạn (script `doc-bai` đã chia), các đoạn không nhắc tới nhau và không mở đầu giống nhau.
9. Bài **đã có link tới URL đích trong câu văn thật** (`da_co_link_toi_dich: true`) → **không viết**, ghi chú "[n] bài đã có link tới URL đích trong câu văn". Link chỉ nằm ở dòng liệt kê kiểu "Có thể bạn quan tâm / Xem thêm" hoặc mục danh sách chỉ có tên bài (`link_dang_liet_ke` khác rỗng) → **vẫn viết** đoạn có ngữ cảnh, và ghi chú "chèn xong có thể bỏ dòng liệt kê để tránh trùng link". Link ở menu/footer/bài liên quan (`link_ngoai_than_bai`) không tính.
10. Bài **xa chủ đề** với key (điểm ứng viên cao nhất ≤ 4) → vẫn viết bằng một cầu nối hợp lý (đối tượng liên quan, tình huống sử dụng), nhưng ghi chú "điểm khớp thấp, người duyệt cân nhắc".

## Chọn vị trí

- Mặc định: **ngay sau** đoạn ứng viên đã chọn. Ghi cột `Vị trí chèn` dạng:
  `Sau đoạn bắt đầu bằng: "<10-12 chữ đầu của đoan>…" (mục H2: <muc>)`
- Tránh: sau H1/đoạn mở bài đầu tiên, sau đoạn kết luận cuối cùng, bên trong danh sách `<li>`, ngay trước/sau một đoạn đã có link nội bộ khác (nếu `truoc`/`sau` chứa `<a` hoặc ứng viên khác cũng đủ điểm thì chọn ứng viên khác).

## Định dạng đầu ra (ghi vào cột `Đoạn chèn`)

```html
<p>Câu nối ý với đoạn trước. Câu có <a href="URL đích">anchor text</a> đặt giữa câu. Câu kết ngắn (nếu cần).</p>
```

Chỉ một thẻ `<p>`, không class, không style, không `target="_blank"` (link nội bộ mở cùng tab).

## Ví dụ

Đoạn gốc (`doan`): *"Với quãng đường đi học 5-10 km mỗi ngày, pin 48V-20Ah là đủ dùng 2-3 ngày mới phải sạc."*
Key: `xe máy điện cho học sinh cấp 3` — Anchor: `xe máy điện cho học sinh cấp 3` — Đích: `/tin-tuc/xe-may-dien-cho-hoc-sinh-cap-3/`

Đoạn chèn:
```html
<p>Quãng đường ngắn và ổn định như vậy cũng là lý do phụ huynh thường không cần chọn xe pin quá lớn. Thay vào đó, nên ưu tiên các mẫu <a href="https://osakar.com.vn/tin-tuc/xe-may-dien-cho-hoc-sinh-cap-3/">xe máy điện cho học sinh cấp 3</a> có trọng lượng nhẹ, tốc độ tối đa dưới 50 km/h để các em dễ điều khiển và đúng quy định không cần bằng lái.</p>
```

## Tự kiểm trước khi ghi

- [ ] 2-3 câu, 40-80 từ?
- [ ] Anchor y nguyên chữ trong sheet, nằm giữa câu, có đúng 1 thẻ `<a>`?
- [ ] Câu đầu có bám vào ý của đoạn trước không? (đọc lại `doan`)
- [ ] Không có số liệu tự bịa, không từ cấm?
- [ ] Giọng xưng hô khớp bài?
