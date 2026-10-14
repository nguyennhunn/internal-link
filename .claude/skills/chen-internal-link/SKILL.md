---
name: chen-internal-link
description: Quy tắc viết đoạn chuyển tiếp 2-3 câu chứa anchor text để chèn internal link vào một bài có sẵn sao cho khớp ngữ nghĩa với đoạn xung quanh, đặt ở cuối mục. Dùng khi có (bài cần chèn, anchor text, URL đích) và đã đọc context bài qua skill doc-bai; hoặc khi người dùng nói "viết đoạn chèn link", "viết câu dẫn internal link". Đầu ra là HTML `<p>` có thẻ `<a>` sẵn để dán.
---

# chen-internal-link

Viết **một đoạn 2-3 câu** để chèn vào **cuối một mục** của bài, sao cho người đọc thấy nó vốn thuộc về bài đó,
và trong đoạn có đúng một link `<a href="URL đích">anchor text</a>`.

## Đầu vào cần có trước khi viết

Từ `.tmp/bai-<hàng>.json` (skill `doc-bai`): `h1`, `dan_y`, ứng viên đã chọn (`muc`, `doan`, `sau`, `vi_tri`, `chen_sau`, `khoi_cuoi_la_danh_sach`).
Từ sheet: `Key mục tiêu`, `Anchor text`, `URL đích`.
Từ `.claude/CLAUDE.md`: tên thương hiệu chủ web, giọng xưng hô, từ cấm riêng.
Nếu biết bài đích nói gì (URL đủ rõ nghĩa, hoặc đã `doc_bai.py fetch`) thì dùng để câu dẫn hứa đúng thứ bài đích có.

## A. Vị trí — chèn ở cuối mục

- **Chèn ở cuối phần nội dung của một heading**, ngay trước heading kế tiếp. Nếu mục kết thúc bằng danh sách gạch đầu dòng (`khoi_cuoi_la_danh_sach: true`) thì chèn **sau danh sách**, không chèn giữa đoạn văn và danh sách.
- **Không chèn ngay sau heading** hay sau đoạn đầu tiên của mục — người dùng yêu cầu (09/10/2026). Chỉ chọn ứng viên nhãn **"cuối mục"**; bất đắc dĩ mới "giữa mục"; không bao giờ "ĐẦU MỤC".
- Tránh: sau đoạn mở bài, sau đoạn kết luận cuối bài, bên trong danh sách, sát một đoạn đã có link nội bộ khác (ứng viên khác đủ điểm thì chọn ứng viên khác).
- Ghi cột `Vị trí chèn` theo đúng mẫu:
  `Cuối mục "<tên heading>" — sau đoạn "<10-12 chữ đầu…>", ngay trước <H2/H3 kế tiếp>`
  hoặc khi mục kết thúc bằng danh sách: `Cuối mục "<tên heading>" — sau danh sách, ngay trước <H2/H3 kế tiếp>`.

## B. Độ dài và giọng

1. **2-3 câu, 35-60 tiếng, mỗi câu ≤ 30 tiếng.** Anchor dài (8-10 tiếng) có thể đẩy tổng lên ~65, chấp nhận; không bẻ anchor để đủ số.
2. **Mỗi câu một ý.** Không nối 2-3 vế bằng chấm phẩy, gạch ngang, "và… nên… nhưng…".
3. **Trật tự câu xuôi**: nguyên nhân/điều kiện đứng đầu câu ("Vì mốc 16 tuổi này, nhiều gia đình…"), không đẩy ra cuối.
4. **Không mở câu bằng** "Tất nhiên", "Thực tế", "Có thể thấy", "Điểm dễ nhầm là", "Vì vậy" — vào thẳng ý.
5. **Tự nhiên nhưng vẫn là văn web chuyên nghiệp.** Được dùng "cân nhắc", "lựa chọn", "tham khảo" khi câu ngắn; tránh từ suồng sã ("để ý", "tìm hẳn", "chốt", "xịn", "ngon", "y nguyên").
   Chuẩn do người dùng duyệt: *"nên cân nhắc thêm các yếu tố chiều cao yên và cách lên xuống xe cho an toàn"* ✔ — *"nên để ý thêm chiều cao yên"* ✘.
6. **Không viết kiểu định nghĩa pháp lý gượng** ("Xe chỉ được miễn bằng lái khi…", "xe được xếp vào…", "thuộc nhóm miễn bằng"). Nói như người tư vấn: *"Mốc 4 kW và 50 km/h là ranh giới giữa xe máy điện và mô tô điện cần bằng A1."*
7. **Xưng hô theo bài gốc**: bài xưng "bạn" thì xưng "bạn"; "bố mẹ" / "phụ huynh" theo cách gọi trong bài.
8. **Câu nối trở lại bài** (nếu có) phải đủ chủ ngữ, trung tính: "Phần tiếp theo của bài tập trung vào…". Không viết cụt kiểu "Còn phần dưới đây chỉ nói về…". Không cần thì bỏ, 2 câu là đủ.
9. Không liệt kê quá 3 món trong một câu.
10. Đọc to lên thấy giống câu người viết bài gốc sẽ viết thì mới đạt.

## C. Nội dung và anchor

11. **Câu 1 nối tiếp ý cuối của mục** (đoạn văn cuối hoặc danh sách cuối) — nhắc lại một chi tiết trong đó, không chép nguyên câu, rồi mở ra vấn đề mà bài đích giải quyết.
12. **Anchor nằm giữa câu** (câu 2 hoặc 3), không mở đầu câu, không đứng một mình cuối câu kiểu "xem thêm: anchor".
13. **Anchor giữ nguyên từng chữ** trong sheet (dấu, thứ tự từ). Được thêm từ đệm quanh anchor cho xuôi ("các mẫu **xe máy điện cho dân công sở** có dáng tương tự"), không đổi chữ bên trong. Anchor không xuôi cách nào → vẫn dùng nguyên, ghi đề xuất anchor khác vào Ghi chú.
14. **Câu chứa anchor phải tự đủ nghĩa khi bỏ link**: nói rõ anchor là *gì* (danh sách mẫu, bài so sánh, hướng dẫn chọn…). **Cấm trỏ mơ hồ**: "bài này", "bài viết dưới đây", "ở đây", "tại đây", "click vào đây", "xem thêm tại".
    Người dùng chỉnh (09/10/2026): *"…bạn có thể tham khảo thêm bài này"* ✘ → *"…bạn có thể tham khảo các mẫu xe máy điện cho dân công sở có dáng tương tự nhưng tiết kiệm hơn xe xăng"* ✔.
15. **Giữ vị thế thương hiệu chủ web.** Bài nằm trên web của thương hiệu (vd OSAKAR) nên không đặt thương hiệu ngang hàng hay kém hơn đối thủ: cấm "Ngoài OSAKAR, mỗi hãng…", "OSAKAR không phải hãng duy nhất", "so sánh các hãng trước rồi quay lại". Link tới bài so sánh hãng thì dẫn theo hướng *cách đánh giá một hãng xe* (pin, bảo hành, độ bền), không khuyến khích đi xem hãng khác. Người dùng đã loại một đoạn vì lỗi này (09/10/2026).
16. **Không lặp thông tin** đã có trong đoạn trước/sau. **Không bịa** số liệu, giá, thông số — chỉ dùng thông tin có trong bài hoặc trong tiêu đề/URL bài đích.
17. **Cấm từ tuyệt đối** không chứng minh ("tốt nhất", "số 1", "hàng đầu") — trừ khi nằm trong anchor.
18. **Một đoạn = một link.** Bài có 2-3 link → 2-3 đoạn riêng, cách nhau ≥ 3 đoạn (script `doc-bai` đã chia), không nhắc tới nhau, không mở đầu giống nhau.

## D. Khi nào không viết / viết kèm ghi chú

19. Bài **đã có link tới URL đích trong câu văn thật** (`da_co_link_toi_dich: true`) → không viết, ghi chú "[n] bài đã có link tới URL đích trong câu văn".
20. Link chỉ nằm ở dòng liệt kê "Có thể bạn quan tâm / Xem thêm" hoặc mục danh sách chỉ có tên bài (`link_dang_liet_ke` khác rỗng) → **vẫn viết**, ghi chú "chèn xong nên bỏ dòng liệt kê để tránh trùng link". Link ở menu/footer/bài liên quan (`link_ngoai_than_bai`) không tính.
21. Bài **xa chủ đề** với key (điểm ứng viên cao nhất ≤ 4) → vẫn viết bằng một cầu nối hợp lý (đối tượng liên quan, tình huống sử dụng), ghi chú "điểm khớp thấp, người duyệt cân nhắc".
22. Bài đã đổi cấu trúc so với lần chạy trước (số đoạn/heading khác hẳn) → ghi chú "bài đã cập nhật, vị trí chọn theo bản hiện tại".

## Định dạng đầu ra (ghi vào cột `Đoạn cần chèn`)

```html
<p>Câu nối ý cuối mục. Câu có <a href="URL đích">anchor text</a> đặt giữa câu, nói rõ anchor là gì. Câu kết ngắn (nếu cần).</p>
```

Chỉ một thẻ `<p>`, không class, không style, không `target="_blank"` (link nội bộ mở cùng tab).

## Ví dụ

Cuối mục *"4.1. OSAKAR Mandi Plus S"*, đoạn cuối: *"…với những người có nhu cầu sử dụng phương tiện ở độ tuổi trưởng thành…, có thể tham khảo thêm xe máy điện cho người lớn."*
Anchor: `xe điện cho người lớn tuổi` — Đích: `/tin-tuc/xe-dien-cho-nguoi-lon/`

Đoạn chèn (người dùng đã duyệt):
```html
<p>Nhờ xe nhẹ, yên thấp và chạy chậm, nhiều gia đình mua Mandi Plus S còn để ông bà đi đón cháu. Nếu đang tìm <a href="https://osakar.com.vn/tin-tuc/xe-dien-cho-nguoi-lon/">xe điện cho người lớn tuổi</a>, bạn nên cân nhắc thêm các yếu tố chiều cao yên và cách lên xuống xe cho an toàn.</p>
```

Sai giọng (tránh): *"Thực tế nhiều gia đình mua Mandi Plus S còn để ông bà dùng chung khi đưa đón cháu, vì xe nhẹ, yên thấp và tốc độ chậm nên người lớn tuổi cũng điều khiển thoải mái. Nếu bạn đang tìm riêng một chiếc … thì nên xem thêm các tiêu chí về chiều cao yên, trọng lượng xe và cách lên xuống an toàn trước khi chọn."* — mở bằng "Thực tế", câu 40 tiếng nhiều vế, "vì" ở cuối, liệt kê 3 món.

## Tự kiểm trước khi ghi

- [ ] Vị trí là **cuối mục**, trước heading kế (sau danh sách nếu mục kết thúc bằng danh sách)?
- [ ] 2-3 câu, 35-60 tiếng, không câu nào quá 30 tiếng, mỗi câu một ý?
- [ ] Nguyên nhân đứng đầu câu, không mở bằng "Tất nhiên/Thực tế/Vì vậy"?
- [ ] Tự nhiên nhưng chuyên nghiệp — không từ suồng sã, không định nghĩa pháp lý gượng?
- [ ] Anchor y nguyên, nằm giữa câu, đúng 1 thẻ `<a>`, câu tự đủ nghĩa khi bỏ link, không "bài này/dưới đây"?
- [ ] Không hạ thương hiệu chủ web?
- [ ] Câu đầu bám vào ý cuối mục? Không bịa số liệu, không từ cấm, xưng hô khớp bài?
