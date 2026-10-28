---
name: doc-bai
description: Tải một bài viết trên web, nhận diện cấu trúc (đoạn văn, danh sách, bảng, khối thông số sản phẩm, FAQ, dòng CTA, kết bài, khối thương hiệu), kiểm tra bài đã có link tới URL đích trong câu văn chưa và có chuyển hướng không, rồi đưa ra các chỗ chèn hợp lệ ở cuối mục cho internal link. Có lệnh quét nhiều bài × nhiều đích để lên mô hình. Dùng khi cần "đọc context bài", "tìm chỗ chèn link", "bài đã có link chưa", hoặc khi agent internal-link chuẩn bị viết đoạn chèn. Chỉ đọc, không sửa bài.
---

# doc-bai

Mắt đọc bài cho agent `internal-link`. Script `scripts/doc_bai.py` làm phần nặng (tải, lọc menu/footer/sidebar, tách khối, gắn nhãn, chọn chỗ) — Claude chỉ đọc bản tóm tắt nhỏ.

## Lệnh chính — một lần cho mỗi bài cần chèn (1-3 link)

```
# .tmp/yc-<hàng>.json = [{"stt":"1","key":"...","anchor":"...","url_dich":"..."}, {"stt":"2",...}]
python .claude/skills/doc-bai/scripts/doc_bai.py chuan-bi-nhieu "<URL bài cần chèn>" .tmp/yc-<hàng>.json .tmp/bai-<hàng>.json
```
Rồi **Read** `.tmp/bai-<hàng>.json`:

| Trường | Ý nghĩa |
|---|---|
| `h1`, `title`, `dan_y` | Bài nói gì, cấu trúc ra sao |
| `chuyen_huong`, `url_that` | Bài nguồn bị chuyển hướng (301) — báo người dùng |
| `da_co_link_toi_dich` | `true` → bài đã có link tới đích trong **câu văn thật**, HOẶC bài nguồn là/chuyển hướng về chính bài đích (`bai_nguon_la_bai_dich`). Không chèn, ghi chú (`cau_da_co_link` = câu đó) |
| `link_dang_liet_ke` | link tới đích chỉ ở dòng liệt kê ("Xem thêm", ">>>", li chỉ có link). Vẫn viết; ghi chú bỏ dòng đó khi dán |
| `link_ngoai_than_bai` | link chỉ ở menu/footer/bài liên quan — không tính |
| `anchor_da_xuat_hien_trong_bai` | anchor đã có dạng chữ thường — có thể gắn link vào đó (mặc định vẫn viết đoạn mới) |
| `ung_vien[]` | tối đa 5 chỗ HỢP LỆ, mỗi chỗ: `i`, `vi_tri` (nhãn), `muc`, `chen_sau` (khối mà đoạn chèn đứng ngay sau), `chen_sau_i`, `ke_tiep` (khối ngay sau chỗ chèn), `khoi_cuoi_la_danh_sach`, `sat_link_noi_bo`, `ghi_chu_vi_tri`, `truoc`/`doan`/`sau` |

**Chỗ hợp lệ** = sau một đoạn văn thường mà sau nó (bỏ qua danh sách/bảng/thông số đi liền) là heading kế, dòng CTA/khối thương hiệu (chèn TRƯỚC dòng đó), hoặc câu hỏi FAQ kế. Nhãn:
- `cuối mục` — chuẩn. `cuối mục (trước dòng CTA/khối OSAKAR)` — ghi Vị trí chèn kèm `ghi_chu_vi_tri` ("chèn TRƯỚC dòng …").
- `sau câu trả lời FAQ` — chỉ dùng khi câu trả lời cùng chủ đề với anchor.
- `sau khối thông số sản phẩm — tránh` — toplist: chèn giữa các mẫu bị người rà đánh "sai chỗ"; chỉ dùng khi không còn chỗ khác, ghi chú.
- Mục kết thúc bằng danh sách "Xem thêm" → `chen_sau` đã lùi lên TRƯỚC danh sách đó (`ghi_chu_vi_tri`).

Script đã **loại**: đoạn mở bài (2 đoạn đầu), giữa mục (còn câu văn phía sau), câu dẫn kết thúc bằng ":", dòng CTA ">>>", vùng Kết luận/Lời kết và khối giới thiệu thương hiệu, giữa danh sách/bảng/các ý in đậm, câu hỏi FAQ. Nhiều link cùng bài: chỗ sau cách chỗ trước ≥ 3 đoạn văn VÀ khác mục. `ung_vien` rỗng → bài không có chỗ hợp lệ cho link đó — không ép, báo "KHÓ NỐI".

Ưu tiên `ung_vien[0]`; tự đổi sang ứng viên khác thì vẫn phải giữ khoảng cách và khác mục với các link còn lại. `sat_link_noi_bo` = khối trước/sau chỗ chèn đã có link nội bộ → chọn chỗ khác nếu điểm gần bằng, không thì ghi chú.

## Lệnh phụ

- `fetch <url> <out.json>` — toàn bộ khối kèm nhãn (`loai`, `faq`, `ket`, `liet_ke`, `links`) khi cần đọc kỹ cả bài. Nhãn `loai`: tieu_de, van, danh_sach, bang, thong_so, y_dam, dan_vao, cta, thuong_hieu.
- `quet <nguon.json> <dich.json> <out.json> [thư-mục-lưu-bài]` — nhiều bài × nhiều đích (dùng ở skill `len-mo-hinh`): mỗi cặp `co_link` / `liet_ke` / `tu_tro` / `chua`, kèm bài chuyển hướng. Chạy song song 8 luồng.

## Giới hạn đã biết

- Trang chặn bot (403) hoặc render bằng JavaScript → không lấy được nội dung. Báo người dùng dán nội dung bài trực tiếp.
- Bảng chỉ ghi 1 khối `[bảng] …` (không tách ô). Ảnh/nút "Mua ngay" dạng hình không đọc được — khối sản phẩm nhận ra qua các dòng "Nhãn: giá trị" ngắn.
- Nhãn dựa trên mẫu câu tiếng Việt thường gặp (">>>", "TẠI ĐÂY", "Câu hỏi thường gặp", "Kết luận", "OSAKAR tự hào…"); site khác mẫu → xem `fetch` và báo để bổ sung mẫu trong script.
