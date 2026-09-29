#!/usr/bin/env python3
"""Lập kế hoạch internal link theo cụm từ khoá chính/phụ.

  python ke_hoach_cum.py <cum.json> <internal-link.json> <out-rows.json> [--vong-tron] [--cum "tên cụm"]

<cum.json>           = kết quả `sheets.py read` tab "Cụm từ khoá"
<internal-link.json> = kết quả `sheets.py read` tab "Internal link" (để không tạo trùng cặp bài→đích)
<out-rows.json>      = mảng dòng [[STT, Key mục tiêu, URL đích, Anchor text, Bài cần chèn, "", "", "", ghi chú], ...]
                       sẵn sàng đưa vào `sheets.py append-rows`

Quy tắc mặc định (mô hình trụ - vệ tinh):
  1. Mỗi bài PHỤ  → link về bài CHÍNH cùng cụm   (anchor = từ khoá chính)
  2. Bài CHÍNH    → link tới từng bài PHỤ         (anchor = từ khoá phụ)
  3. --vong-tron: bài phụ i → bài phụ i+1 (khép vòng) (anchor = từ khoá phụ của bài kế)
"""
import json
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")


def load(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def norm_url(u):
    return re.sub(r"^https?://(www\.)?", "", (u or "").strip()).rstrip("/").lower()


def col(row, *names):
    v = row["values"]
    for n in names:
        for k in v:
            if k.strip().lower() == n.lower():
                return v[k].strip()
    return ""


def main(cum_file, il_file, out_file, *flags):
    vong_tron = "--vong-tron" in flags
    chi_cum = None
    if "--cum" in flags:
        chi_cum = flags[flags.index("--cum") + 1].strip().lower()

    cum = load(cum_file)["rows"]
    il = load(il_file)["rows"]
    da_co = {(norm_url(col(r, "Bài cần chèn")), norm_url(col(r, "URL đích"))) for r in il}
    stt_max = 0
    for r in il:
        s = col(r, "STT")
        if s.isdigit():
            stt_max = max(stt_max, int(s))

    groups = {}
    for r in cum:
        ten = col(r, "Cụm")
        kw, loai, url = col(r, "Từ khoá", "Từ khóa"), col(r, "Loại"), col(r, "URL bài")
        if not (ten and kw and url):
            continue
        if chi_cum and ten.lower() != chi_cum:
            continue
        groups.setdefault(ten, {"chinh": None, "phu": []})
        item = {"kw": kw, "url": url}
        if loai.lower().startswith("ch"):
            if groups[ten]["chinh"]:
                print(f"CẢNH BÁO: cụm '{ten}' có 2 dòng Chính — dùng dòng đầu ({groups[ten]['chinh']['kw']})")
            else:
                groups[ten]["chinh"] = item
        else:
            groups[ten]["phu"].append(item)

    rows, bo_qua = [], 0

    def add(key, url_dich, anchor, bai, ghi_chu):
        nonlocal stt_max, bo_qua
        if norm_url(bai) == norm_url(url_dich):
            return
        if (norm_url(bai), norm_url(url_dich)) in da_co:
            bo_qua += 1
            return
        da_co.add((norm_url(bai), norm_url(url_dich)))
        stt_max += 1
        rows.append([str(stt_max), key, url_dich, anchor, bai, "", "", "", ghi_chu])

    for ten, g in groups.items():
        c, phu = g["chinh"], g["phu"]
        if not c:
            print(f"CẢNH BÁO: cụm '{ten}' không có dòng Chính — bỏ qua")
            continue
        for p in phu:
            add(c["kw"], c["url"], c["kw"], p["url"], f"Cụm {ten}: phụ → chính")
        for p in phu:
            add(p["kw"], p["url"], p["kw"], c["url"], f"Cụm {ten}: chính → phụ")
        if vong_tron and len(phu) >= 2:
            for i, p in enumerate(phu):
                q = phu[(i + 1) % len(phu)]
                add(q["kw"], q["url"], q["kw"], p["url"], f"Cụm {ten}: phụ → phụ (vòng)")

    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=1)
    print(f"{len(groups)} cụm → {len(rows)} dòng kế hoạch mới (bỏ {bo_qua} cặp đã có) → {out_file}")
    for r in rows:
        print(f"  {r[0]}. {r[4]}  →  {r[2]}  [{r[3]}]")


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print(__doc__)
        sys.exit(1)
    main(*sys.argv[1:])
