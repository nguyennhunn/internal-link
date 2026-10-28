---
name: ra-doan-chen
description: Bước tự rà BẮT BUỘC trước khi ghi đoạn chèn internal link lên sheet — máy kiểm định dạng/link/anchor/độ dài/từ cấm/giá, rồi một người rà KHÁC người viết chấm từng đoạn theo 6 lỗi (nhảy logic, sai chỗ, sai sự thật, anchor sai nghĩa, lặp ý/trùng link, giọng), sửa tối đa 2 vòng, chỉ ghi đoạn đạt; đoạn vẫn khó nối thì gắn cờ "KHÓ NỐI". Dùng sau khi agent internal-link viết xong đoạn, hoặc khi người dùng nói "rà lại đoạn chèn", "đoạn nào không phù hợp".
---

# ra-doan-chen

Bài học 15/10/2026: 428 đoạn ghi thẳng lên sheet không qua rà → người dùng tự bắt lỗi (hàng 13 [2]), rà lại thì 208 đoạn không phù hợp. Từ nay: **viết → máy kiểm → rà → sửa → chỉ ghi đoạn đạt**.

```
K=.claude/skills/ra-doan-chen/scripts/kiem_doan.py
S=.claude/skills/sheet-internal-link/scripts/sheets.py
A=.claude/skills/sheet-internal-link/sheets-accounts.local.json
```

## Quy trình

1. **Gom đoạn** vào `.tmp/doan.json` (mỗi đoạn: rowIndex, n, anchor, url_dich, html, vi_tri, ghi_chu; kèm `chen_sau_i`/đoạn trước–sau nếu có để người rà khỏi tải lại bài).
2. **Máy kiểm**: `python $K kiem .tmp/doan.json` (thêm `--cam "…"` từ cấm riêng trong `.claude/CLAUDE.md`). Lỗi máy → người viết sửa ngay, chạy lại tới khi sạch.
3. **Rà theo tiêu chí** (dưới đây) — người rà KHÔNG phải người viết (agent con riêng; nhiều đoạn thì chia nhóm, mỗi nhóm thư mục nháp riêng). Đọc đoạn trong ngữ cảnh thật: bản tải bài (`doc_bai.py fetch`, khối `chen_sau_i` và khối kế tiếp). Ghi vào từng đoạn `ra_soat = {muc_do, loi, ly_do, goi_y, vong}`.
4. **Sửa**: "Không phù hợp" → chọn lại CHỖ trước rồi viết lại câu; "Sửa nhẹ" → sửa câu, đặt `ra_soat.da_sua = true`. Rà lại đoạn đã sửa (vòng 2). Tối đa 2 vòng.
5. **Ghi**: `python $K ghi .tmp/doan.json .tmp/sheet.json .tmp/changes.json` → `python $S write-rows $A <key> "<tab>" .tmp/changes.json --thu` → bỏ `--thu`.
   Chỉ đoạn máy đạt + rà "Đạt"/"Sửa nhẹ" được ghi. Đoạn vẫn "Không phù hợp" sau vòng 2: hỏi người dùng; nếu người dùng muốn vẫn chèn → `ghi … --cho-kho-noi` (Ghi chú tự có "KHÓ NỐI: lý do").
6. **Báo cáo**: số đoạn đạt / sửa nhẹ / khó nối, lỗi lặp nhiều, danh sách đoạn KHÓ NỐI (hàng thật trên sheet).

## Tiêu chí rà — "Không phù hợp" khi có ít nhất 1 lỗi

**Ví dụ chuẩn (người dùng bắt):** bài biển báo cửa chui, đoạn chèn đặt ngay sau ý "Cửa vòm" trong phần so sánh biển đường hầm. Câu 1: "Biển cửa chui và biển đường hầm dễ nhầm khi thi sát hạch…". Câu 2: "…phụ huynh có thể tham khảo bảng giá xe máy điện cho học sinh cấp 3 khi chọn xe cho con." → không có lý do nào nối việc phân biệt biển báo với giá xe = link bị nhét vào.

1. **Nhảy logic / cầu nối gượng** — câu chứa anchor không phải hệ quả tự nhiên của ý ngay trước. Câu nối chung ("nếu đang chọn xe…", "ngoài X, kiểu dáng cũng quan trọng…", "trên đường đi học, đi làm…") = gượng. Đổi đối tượng đột ngột (người mất bằng → sinh viên; tước bằng → con dưới 16) = gượng.
2. **Sai chỗ** — giữa danh sách/gạch đầu dòng, ngay sau dòng thông số, trong khối sản phẩm (trước ảnh/nút "Mua ngay"), giữa hỏi–đáp FAQ hoặc giữa 2 phần của một câu trả lời, giữa các bước quy trình, ngay sau dòng ">>>"/"Xem thêm", trong Lời kết/khối giới thiệu thương hiệu, sát đoạn đã có link mua xe khác (2–3 lời mời liền nhau), làm đứt hai đoạn gốc liền ý.
3. **Sai / không chắc sự thật** — chi tiết không có trong bài nguồn/bài đích (kể cả "quy định chung" người viết tự thêm); với OSAKAR: xe máy điện chỉ cho người đủ 16 tuổi, bằng A1 cần đủ 18, người 16–<18 vi phạm chỉ bị phạt tối đa 1/2 mức người lớn, danh mục xe có bàn đạp có mẫu 38–45 km/h (không nói cả danh mục hợp học sinh dưới 16), người sinh 2008 đã 18 tuổi.
4. **Anchor dùng sai nghĩa / câu không tự đủ nghĩa** — "bảng giá giá…", anchor "cho nam" khi bài không có ngữ cảnh nam, câu hứa điều bài đích không có, trỏ mơ hồ.
5. **Lặp ý / trùng link** — câu 1 chép lại đoạn ngay trước; đứng sát link có sẵn trỏ CÙNG URL đích; cùng một khuôn câu lặp gần nguyên văn ở nhiều bài.
6. **Giọng sai** — hô hào, quảng cáo lộ, khen hãng khác/hạ vị thế thương hiệu chủ web, từ suồng sã.
7. **Mời đọc bài khô / câu cụt** (người dùng yêu cầu 28/10/2026) — câu chứa anchor chỉ là lời mời ("đọc bài…", "tham khảo bài…", "xem thêm…" + anchor) không nói gì về nội dung; câu thiếu chủ ngữ/vị ngữ, cụt ngủn, đọc không rõ nghĩa; đoạn không nhắc được chi tiết cụ thể nào của nội dung ngay trước/sau chỗ chèn. Xếp "Sửa nhẹ" nếu chỗ chèn đúng và chỉ cần viết lại câu; "Không phù hợp" nếu không có chi tiết nào để bám.

**"Sửa nhẹ"** — ý ổn, chỗ ổn, nhưng câu vụng/lặp nhẹ/1 chi tiết nhỏ. **"Đạt"** — không lỗi.
Bài xa chủ đề KHÔNG tự động bị loại — chỉ loại khi câu nối thật sự gượng. Đoạn có ghi chú "NỐI CHUNG:" (người dùng đã chấp nhận câu nối chung cho cặp đó) vẫn chấm, nhưng nối chung có lý do đọc được → "Sửa nhẹ"; nhảy logic như ví dụ → vẫn "Không phù hợp".

## Không làm

- Người viết không tự rà bài của mình rồi ghi luôn.
- Không ghi đoạn chưa có `ra_soat` hoặc máy kiểm còn lỗi.
- Không xoá link người dùng yêu cầu chèn chỉ vì khó nối — hỏi người dùng (đổi bài nguồn ở skill `len-mo-hinh`, hoặc ghi kèm KHÓ NỐI).
