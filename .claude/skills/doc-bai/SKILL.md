---
name: doc-bai
description: Tải một bài viết trên web, tách thành tiêu đề / dàn ý H2-H3 / từng đoạn văn, kiểm tra bài đã có link tới URL đích chưa, và chấm điểm 5 đoạn gần nghĩa nhất với từ khoá mục tiêu để chọn chỗ chèn internal link. Dùng khi cần "đọc context bài", "tìm chỗ chèn link", hoặc khi agent internal-link chuẩn bị viết đoạn chèn. Chỉ đọc, không sửa bài.
---

# doc-bai

Mắt đọc bài cho agent `internal-link`. Script `scripts/doc_bai.py` làm phần nặng
(tải, lọc menu/footer/sidebar, tách đoạn, chấm điểm) — Claude chỉ đọc bản tóm tắt nhỏ.

## Lệnh chính — dùng cho mỗi dòng cần chèn

```
python .claude/skills/doc-bai/scripts/doc_bai.py chuan-bi "<URL bài cần chèn>" "<Key mục tiêu>" "<Anchor text>" "<URL đích>" .tmp/bai-<stt>.json
```

Sau đó **Read** file `.tmp/bai-<stt>.json`. Nội dung:

| Trường | Ý nghĩa |
|---|---|
| `h1`, `title`, `dan_y` | Hiểu bài đang nói gì, cấu trúc ra sao |
| `da_co_link_toi_dich` | `true` → bài đã có link tới URL đích **trong một câu văn thật**. Không chèn thêm, ghi chú lại |
| `link_dang_liet_ke` | các dòng "Có thể bạn quan tâm / Xem thêm" hoặc mục danh sách chỉ có tên bài đang trỏ tới đích. Vẫn viết đoạn mới; ghi chú để người duyệt bỏ dòng liệt kê |
| `link_ngoai_than_bai` | link tới đích chỉ có ở menu/footer/bài liên quan — không tính |
| `anchor_da_xuat_hien_trong_bai` | `true` → anchor đã có trong bài dạng chữ thường; có thể cân nhắc gắn link vào chỗ đó thay vì viết đoạn mới (nhưng mặc định vẫn viết đoạn mới vì người dùng yêu cầu) |
| `ung_vien[]` | 5 đoạn văn điểm cao nhất, mỗi cái có `muc` (H2/H3 chứa nó), `truoc`, `doan`, `sau`, `vi_tri` |

Chọn ứng viên theo thứ tự ưu tiên:
1. Điểm cao **và** nằm trong thân bài (không phải đoạn 1-2 mở bài, không phải 1-2 đoạn cuối).
2. Đoạn có ý "kết thúc một ý nhỏ" — sau nó đặt thêm 2-3 câu chuyển tiếp là tự nhiên.
3. Nếu tất cả điểm ≤ 1 (bài không liên quan gì tới key) → ghi chú "bài không có đoạn hợp ngữ nghĩa", vẫn đề xuất chèn vào cuối mục gần nhất, nhưng đánh dấu để người duyệt cân nhắc.

## Nhiều link vào cùng một bài

Khi 2-3 dòng trong sheet có cùng `Bài cần chèn`, **không** gọi `chuan-bi` nhiều lần (mỗi lần sẽ chọn cùng đoạn tốt nhất → trùng chỗ). Thay vào đó:

```
# .tmp/yc-1.json = [{"stt":"3","key":"...","anchor":"...","url_dich":"..."}, {"stt":"4",...}]
python .claude/skills/doc-bai/scripts/doc_bai.py chuan-bi-nhieu "<URL bài>" .tmp/yc-1.json .tmp/bai-1.json
```

Kết quả có `yeu_cau[]` — mỗi phần tử là một yêu cầu với `ung_vien[]` riêng, **đã loại các đoạn nằm trong vòng 3 đoạn quanh chỗ yêu cầu khác đã lấy** (yêu cầu có đoạn hợp nhất được chia chỗ trước). Chọn `ung_vien[0]` của từng yêu cầu là an toàn. `canh_bao` khác rỗng nghĩa là số link so với độ dài bài đang dày (quá 1 link / 8 đoạn) — vẫn viết, nhưng ghi chú cho người duyệt.

## Lệnh phụ

`python .claude/skills/doc-bai/scripts/doc_bai.py fetch <url> .tmp/x.json` — lấy toàn bộ khối, khi cần đọc kỹ cả bài (tốn token hơn, chỉ dùng khi bản tóm tắt không đủ).

## Giới hạn đã biết

- Trang chặn bot (403) hoặc render bằng JavaScript → không lấy được nội dung. Báo người dùng dán nội dung bài trực tiếp.
- Bộ lọc nhận diện phần thân bài theo `<article>`, `<main>`, class `entry-content`/`post-content`… Nếu `so_doan` quá ít so với thực tế, chạy `fetch` và xem `blocks` để kiểm tra.
