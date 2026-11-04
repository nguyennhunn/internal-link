#!/usr/bin/env python3
"""Mô hình internal link "3 đến – 3 đi" của SEONGON.

Trong một NHÓM bài xếp theo STT, bài i đi 3 link tới 3 bài kế tiếp (quay vòng cuối nhóm):
  Inlink 1 → bài i+1, anchor = TỪ KHOÁ CHÍNH của bài i+1
  Inlink 2 → bài i+2, anchor = TỪ KHOÁ PHỤ CHƯA LÊN TOP của bài i+2
  Inlink 3 → bài i+3, anchor = TIÊU ĐỀ (title) của bài i+3
→ mỗi bài nhận đúng 3 link về (key chính / key phụ / title) từ 3 bài đứng trước.

Lệnh:
  xep <nhom.json> <out.json> [--top 10] [--lay-title]
      nhom.json = [{"stt":1,"nhom":"…","key_chinh":"…","tinh_trang":"Đã đăng|Chưa đăng","url":"…",
                    "title":"…"(tuỳ chọn), "key_phu":[{"key":"…","hang":12}, …]}, …]
      --top N      : key phụ "chưa lên TOP" = hạng > N hoặc chưa có hạng (mặc định 10)
      --lay-title  : bài thiếu title thì tải trang lấy H1 (cần mạng)
      out.json     = {"ket_qua":[{stt, nhom, url, mo_hinh, inlink:[{n, toi_stt, url_dich, anchor, loai, ghi_chu}]}],
                      "internal_link_rows":[[…]], "canh_bao":[…]}
  rows-sheet <out.json> <rows.json> [--sep ;]
      Xuất mảng dòng cho tab mô hình: [Mô hình, Inlink 1, Inlink 2, Inlink 3] mỗi ô là công thức
      =HYPERLINK("url"<sep>"anchor") (Google Sheet tiếng Việt dùng ; — đổi --sep , nếu sheet tiếng Anh).
"""
import json
import re
import sys
import unicodedata

sys.stdout.reconfigure(encoding="utf-8")


def strip_accents(s):
    return "".join(c for c in unicodedata.normalize("NFD", s or "") if unicodedata.category(c) != "Mn").lower().strip()


def chon_key_phu(bai, top):
    """Chọn 1 key phụ chưa lên TOP: ưu tiên hạng cao nhất trong nhóm chưa top (gần top nhất → dễ đẩy),
    không trùng key chính; không có hạng thì lấy key phụ đầu tiên."""
    kc = strip_accents(bai.get("key_chinh"))
    ds = [k for k in bai.get("key_phu", []) if strip_accents(k.get("key")) and strip_accents(k.get("key")) != kc]
    if not ds:
        return None, "bài không có key phụ"
    chua_top = [k for k in ds if k.get("hang") in (None, "", 0) or float(k["hang"]) > top]
    if chua_top:
        co_hang = [k for k in chua_top if k.get("hang") not in (None, "", 0)]
        pick = sorted(co_hang, key=lambda k: float(k["hang"]))[0] if co_hang else chua_top[0]
        return pick["key"], ""
    pick = sorted(ds, key=lambda k: float(k.get("hang") or 999))[-1]
    return pick["key"], f"mọi key phụ đều đã top {top} — dùng key hạng thấp nhất ({pick.get('hang')})"


def lay_title(url):
    try:
        sys.path.insert(0, __file__.rsplit("/", 1)[0].rsplit("\\", 1)[0] + "/../../doc-bai/scripts")
        import doc_bai
        d = doc_bai.build_doc(url)
        return d.get("h1") or d.get("title") or ""
    except Exception as e:  # noqa
        return ""


def cmd_xep(nhom_file, out_file, *opts):
    o = dict(zip(opts[::2], opts[1::2]))
    top = float(o.get("--top", 10))
    lay = "--lay-title" in opts
    bai_all = json.load(open(nhom_file, encoding="utf-8"))
    nhoms = {}
    for b in bai_all:
        nhoms.setdefault(b.get("nhom", ""), []).append(b)
    ket, rows, canh_bao = [], [], []
    for ten, ds in nhoms.items():
        ds.sort(key=lambda b: float(b.get("stt") or 0))
        n = len(ds)
        if n < 4:
            canh_bao.append(f"nhóm '{ten}' chỉ có {n} bài — mô hình cần ≥ 4 bài để mỗi bài đi 3 link không trùng")
        for i, b in enumerate(ds):
            muc_tieu = [ds[(i + k) % n] for k in (1, 2, 3)] if n > 1 else []
            mo_hinh = f"{b['stt']} - (" + "-".join(str(t["stt"]) for t in muc_tieu) + ")"
            inl = []
            for k, t in enumerate(muc_tieu, start=1):
                ghi = ""
                if k == 1:
                    anchor = t.get("key_chinh", ""); loai = "key chính"
                elif k == 2:
                    anchor, ghi = chon_key_phu(t, top); loai = "key phụ chưa TOP"
                    if anchor is None:
                        anchor = t.get("key_chinh", ""); ghi = "bài đích không có key phụ → tạm dùng key chính, cần bổ sung"
                else:
                    anchor = t.get("title") or (lay_title(t["url"]) if lay and t.get("url") else ""); loai = "title"
                    if not anchor:
                        ghi = "chưa có title (bài chưa đăng hoặc không tải được) → điền sau"
                if t.get("tinh_trang", "").lower().startswith("chưa") and not t.get("url"):
                    ghi = (ghi + "; " if ghi else "") + "bài đích chưa đăng — để trống, đăng xong fill"
                inl.append({"n": k, "toi_stt": t["stt"], "url_dich": t.get("url", ""), "anchor": anchor, "loai": loai, "ghi_chu": ghi})
            nguon_chua_dang = b.get("tinh_trang", "").lower().startswith("chưa")
            ket.append({"stt": b["stt"], "nhom": ten, "url": b.get("url", ""), "key_chinh": b.get("key_chinh", ""),
                        "tinh_trang": b.get("tinh_trang", ""), "mo_hinh": mo_hinh, "inlink": inl,
                        "ghi_chu": "bài nguồn chưa đăng — giữ chỗ trong chuỗi, chưa viết đoạn" if nguon_chua_dang else ""})
            if not nguon_chua_dang and b.get("url"):
                row = [str(b["stt"])]
                for x in inl:
                    row += [x["anchor"], x["url_dich"], x["anchor"]]  # Key mục tiêu n | URL đích n | Anchor text n
                row += [b["url"], "", "", "", "", "; ".join(f"[{x['n']}] {x['ghi_chu']}" for x in inl if x["ghi_chu"])]
                rows.append(row)
    out = {"ket_qua": ket, "internal_link_rows": rows, "canh_bao": canh_bao,
           "internal_link_header": ["STT", "Key mục tiêu 1", "URL đích 1", "Anchor text 1", "Key mục tiêu 2", "URL đích 2", "Anchor text 2",
                                    "Key mục tiêu 3", "URL đích 3", "Anchor text 3", "Bài cần chèn", "HTML chèn", "Đoạn chèn (đọc duyệt)", "Vị trí chèn", "Trạng thái", "Ghi chú"]}
    json.dump(out, open(out_file, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{len(nhoms)} nhóm, {len(bai_all)} bài → {len(rows)} hàng sẵn sàng viết đoạn ({len(bai_all) - len(rows)} bài nguồn chưa đăng/thiếu URL)")
    for c in canh_bao:
        print("  CẢNH BÁO:", c)
    thieu = [(k["stt"], x["n"], x["ghi_chu"]) for k in ket for x in k["inlink"] if x["ghi_chu"]]
    for s, n, g in thieu[:30]:
        print(f"  bài {s} inlink {n}: {g}")
    if len(thieu) > 30:
        print(f"  … và {len(thieu) - 30} ghi chú nữa (xem {out_file})")


def cmd_rows_sheet(out_file, rows_file, *opts):
    o = dict(zip(opts[::2], opts[1::2]))
    sep = o.get("--sep", ";")
    d = json.load(open(out_file, encoding="utf-8"))
    rows = []
    for k in d["ket_qua"]:
        r = [k["mo_hinh"]]
        for x in k["inlink"]:
            if x["url_dich"] and x["anchor"]:
                a = x["anchor"].replace('"', '""')
                r.append(f'=HYPERLINK("{x["url_dich"]}"{sep}"{a}")')
            else:
                r.append(x["anchor"] or "")
        rows.append(r)
    json.dump(rows, open(rows_file, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{len(rows)} dòng [Mô hình, Inlink 1, Inlink 2, Inlink 3] → {rows_file} (HYPERLINK dùng '{sep}')")


if __name__ == "__main__":
    a = sys.argv[1:]
    if len(a) >= 3 and a[0] == "xep":
        cmd_xep(*a[1:])
    elif len(a) >= 3 and a[0] == "rows-sheet":
        cmd_rows_sheet(*a[1:])
    else:
        print(__doc__)
        sys.exit(1)
