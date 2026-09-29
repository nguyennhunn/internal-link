---
name: xuat-duyet
description: Xuất trang HTML (nhận diện SEONGON) để người duyệt xem từng đoạn internal link đã viết trong đúng ngữ cảnh đoạn trước/sau, kèm nút sao chép HTML để dán vào bài. Dùng ở bước cuối của agent internal-link hoặc khi người dùng nói "xuất file duyệt", "cho tôi xem các đoạn đã viết".
---

# xuat-duyet

## Cách chạy

1. Gom kết quả từng dòng vào `.tmp/ket-qua.json` (mảng), mỗi phần tử:

```json
{"stt":"3","key":"xe máy điện đẹp","url_dich":"https://...","anchor":"xe máy điện đẹp",
 "bai":"https://...","bai_tieu_de":"H1 bài cần chèn","muc":"H2 chứa đoạn",
 "doan":"đoạn gốc đứng trước","sau":"đoạn gốc đứng sau",
 "doan_html":"<p>... <a href=\"...\">...</a> ...</p>",
 "vi_tri":"Sau đoạn bắt đầu bằng: \"...\"","trang_thai":"Đã viết","ghi_chu":""}
```

2. ```
   python .claude/skills/xuat-duyet/scripts/xuat_duyet.py .tmp/ket-qua.json "duyet-internal-link-<ngày>.html" "<Tên dự án>"
   ```
3. Gửi file HTML cho người dùng (SendUserFile) — mở bằng trình duyệt, không cần mạng.

File HTML để ở thư mục gốc dự án (không phải `.tmp/`) để người dùng dễ tìm và gửi cho đồng nghiệp.

## Trang xuất ra có gì

- Mỗi dòng một thẻ: key mục tiêu, bài cần chèn, URL đích, trạng thái.
- Đoạn gốc phía trước (xám) → **đoạn chèn (khung xanh)** → đoạn gốc phía sau (xám): người duyệt thấy ngay có xuôi không.
- Nút *Sao chép HTML* (dán vào trình soạn thảo chế độ HTML/Code) và *Sao chép chữ thường* (dán vào trình soạn thảo thường rồi tự gắn link).
- Dòng `Bỏ qua` hiện mờ kèm lý do.

Logo lấy từ `assets/logo.png` trong thư mục skill (file logo gốc SEONGON, không vẽ lại).
