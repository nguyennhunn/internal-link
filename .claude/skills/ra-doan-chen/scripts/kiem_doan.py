#!/usr/bin/env python3
"""Kiểm tự động đoạn chèn internal link và tạo bản ghi sheet CHỈ cho đoạn đã qua rà. Chỉ dùng thư viện chuẩn.

Lệnh:
  kiem <doan.json> [--cam "từ1,từ2"]
      → kiểm từng đoạn bằng máy (định dạng, link, anchor, độ dài, từ cấm, giá cụ thể). In lỗi, ghi lại `may` vào file.
  ghi  <doan.json> <sheet.json> <changes.json> [--cho-kho-noi]
      → gộp đoạn vào cột Đoạn cần chèn / Đoạn chèn (đọc duyệt) / Vị trí chèn / Ghi chú (giữ nguyên các đoạn [n]
        khác của hàng), CHỈ cho đoạn máy kiểm đạt VÀ `ra_soat.muc_do` = "Đạt" (hoặc "Sửa nhẹ" đã sửa).
        --cho-kho-noi: đoạn "Không phù hợp" sau 2 vòng sửa vẫn ghi, Ghi chú tự thêm "KHÓ NỐI: <lý do>".
        Kết quả là changes.json cho `sheets.py write-rows` (kèm expect: Bài cần chèn + ô Đoạn cần chèn hiện tại).

doan.json = [{"rowIndex":14,"n":2,"anchor":"…","url_dich":"https://…","html":"<p>…</p>","vi_tri":"Cuối mục …",
              "ghi_chu":"…","ra_soat":{"muc_do":"Đạt|Sửa nhẹ|Không phù hợp","loi":[1],"ly_do":"…","vong":1}}]
"""
import json
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

CAM = ["rẻ nhất", "số 1", "hàng đầu", "tốt nhất thị trường", "bài này", "tại đây", "ở đây", "bài viết dưới đây",
       "click", "xem thêm tại", "để ý", "xịn", "ngon", "chốt", "bảng giá giá"]
MO_CAM = re.compile(r"^(thực tế|tất nhiên|có thể thấy|điểm dễ nhầm là|vì vậy)\b", re.I)
GIA_MOC = re.compile(r"(dưới|trên|mốc|tầm|mức|khoảng|nhỉnh hơn mức|phân khúc)\s+(giá\s+)?(trị\s+)?\d[\d.,]*\s*(triệu|đồng)(\s+đồng)?", re.I)
GIA = re.compile(r"\d[\d.,]*\s*(triệu|nghìn|ngàn|đồng|vnđ|đ\b)", re.I)
MOI_DOC = re.compile(r"(đọc|tham khảo|xem|tìm hiểu|theo dõi)(\s+thêm|\s+qua|\s+ngay|\s+kỹ)?\s+(bài(\s+viết|\s+đánh giá|\s+so sánh|\s+hướng dẫn)?|nội dung)\s*$", re.I)


def plain(p):
    return re.sub(r"<[^>]+>", "", re.sub(r"<a [^>]*>(.*?)</a>", r"«\1»", p))


def kiem_mot(x, cam):
    p, anc, url = x["html"].strip(), x["anchor"], x["url_dich"]
    e = []
    if not (p.startswith("<p>") and p.endswith("</p>") and p.count("<p>") == 1):
        e.append("phải đúng 1 thẻ <p>")
    if re.search(r"(class|style|target)=", p):
        e.append("thẻ có class/style/target")
    a = re.findall(r'<a href="([^"]+)">([^<]+)</a>', p)
    if p.count("<a ") != 1 or len(a) != 1:
        e.append("phải đúng 1 thẻ <a>")
    elif a[0][0] != url:
        e.append(f"href sai: {a[0][0]}")
    elif a[0][1] != anc:
        e.append(f"anchor bị đổi chữ: «{a[0][1]}»")
    t = plain(p)
    bo = t.replace("«" + anc + "»", "")
    e += [f"từ cấm '{w}'" for w in cam if w in bo.lower()]
    if GIA.search(GIA_MOC.sub("", bo)):
        e.append("nêu giá cụ thể")
    if "Osakar" in bo or "osakar" in bo:
        e.append("viết OSAKAR sai hoa thường")
    sents = [s for s in re.split(r"(?<=[.!?])\s+", t) if s.strip()]
    w = len(t.replace("«", "").replace("»", "").split())
    if not 30 <= w <= 68:
        e.append(f"độ dài {w} tiếng (cần 35–60, anchor dài tới ~65)")
    if not 2 <= len(sents) <= 3:
        e.append(f"{len(sents)} câu (cần 2–3)")
    for s in sents:
        if len(s.split()) > 32:
            e.append(f"câu {len(s.split())} tiếng (> 30)")
        if MO_CAM.search(s.lstrip("«")):
            e.append(f"mở câu bằng '{MO_CAM.search(s.lstrip('«')).group(0)}'")
    if sents and sents[0].lstrip().startswith("«"):
        e.append("anchor đứng đầu đoạn")
    if sents and sents[-1].rstrip(".").rstrip().endswith("»") and len(sents[-1].split()) <= len(anc.split()) + 3:
        e.append("anchor đứng một mình cuối câu kiểu 'xem thêm: anchor'")
    # "mời đọc bài khô": câu chứa anchor chỉ là lời mời (đọc/tham khảo/xem + bài + anchor) và sau anchor không nói gì thêm
    for s in sents:
        if "«" not in s:
            continue
        truoc, sau = s.split("«", 1)[0], s.split("»", 1)[-1] if "»" in s else ""
        if MOI_DOC.search(truoc) and len(sau.strip(" .,!?").split()) <= 4:
            e.append("câu chứa anchor chỉ là lời mời đọc bài, không nói gì về nội dung")
            break
    if not str(x.get("vi_tri", "")).strip():
        e.append("thiếu vị trí chèn")
    return e


def cmd_kiem(f, *opts):
    o = dict(zip(opts[::2], opts[1::2]))
    cam = CAM + [w.strip().lower() for w in o.get("--cam", "").split(",") if w.strip()]
    ds = json.load(open(f, encoding="utf-8"))
    loi = 0
    for x in ds:
        x["may"] = kiem_mot(x, cam)
        if x["may"]:
            loi += 1
            print(f"  hàng {x['rowIndex']} [{x['n']}]: " + "; ".join(x["may"]))
    # cùng hàng: không mở đầu giống nhau
    by = {}
    for x in ds:
        by.setdefault(x["rowIndex"], []).append(x)
    for r, xs in by.items():
        dau = {}
        for x in xs:
            k = " ".join(plain(x["html"]).split()[:4]).lower()
            if k in dau:
                x["may"].append(f"mở đầu giống đoạn [{dau[k]}]"); print(f"  hàng {r} [{x['n']}]: mở đầu giống đoạn [{dau[k]}]")
            dau[k] = x["n"]
    json.dump(ds, open(f, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"máy kiểm {len(ds)} đoạn: {len(ds) - loi} đạt, {loi} lỗi → đã ghi trường `may` vào {f}")


def thay(cell, n, moi, sep):
    cell = cell or ""
    # dòng KHÔNG đánh số ở đầu ô (vd "LỖI BÀI GỐC…", "Bài mới thêm…") được giữ nguyên ở đầu
    m0 = re.search(r"^\[\d\] ", cell, re.M)
    dau = cell[:m0.start()].strip() if m0 else cell.strip()
    parts = {int(m.group(1)): m.group(2) for m in re.finditer(r"^\[(\d)\] (.*?)(?=\n+\[\d\] |\Z)", cell, re.M | re.S)}
    if moi is None:
        parts.pop(n, None)
    else:
        parts[n] = moi
    than = sep.join(f"[{k}] {parts[k]}" for k in sorted(parts))
    return (dau + "\n" + than) if dau and than else (dau or than)


def cmd_ghi(f, sheet_file, out, *flags):
    cho_kho = "--cho-kho-noi" in flags
    ds = json.load(open(f, encoding="utf-8"))
    rows = {r["rowIndex"]: r for r in json.load(open(sheet_file, encoding="utf-8"))["rows"]}
    cur, bo = {}, []
    for x in ds:
        r = x["rowIndex"]
        rv = x.get("ra_soat") or {}
        md = rv.get("muc_do", "")
        if x.get("may") is None:
            bo.append((r, x["n"], "chưa chạy `kiem`")); continue
        if x["may"]:
            bo.append((r, x["n"], "máy kiểm còn lỗi")); continue
        kho = False
        if md in ("Đạt", "Sửa nhẹ"):
            pass
        elif md == "Không phù hợp" and cho_kho and int(rv.get("vong", 1)) >= 2:
            kho = True
        else:
            bo.append((r, x["n"], f"chưa qua rà (muc_do='{md or 'trống'}')")); continue
        if r not in rows:
            bo.append((r, x["n"], "hàng không có trên sheet")); continue
        v = rows[r]["values"]
        c = cur.setdefault(r, {"L": v.get("Đoạn cần chèn", ""), "M": v.get("Đoạn chèn (đọc duyệt)", ""),
                               "N": v.get("Vị trí chèn", ""), "P": v.get("Ghi chú", ""), "L0": v.get("Đoạn cần chèn", "")})
        p = x["html"].strip()
        c["L"] = thay(c["L"], x["n"], p, "\n\n")
        c["M"] = thay(c["M"], x["n"], plain(p), "\n\n")
        c["N"] = thay(c["N"], x["n"], x["vi_tri"].strip(), "\n")
        g = re.sub(rf"^\[{x['n']}\]\s*", "", str(x.get("ghi_chu", "")).strip())
        if md == "Sửa nhẹ" and rv.get("ly_do") and not rv.get("da_sua"):
            g = (g + " | " if g else "") + "Rà: " + rv["ly_do"]
        if kho and not g.startswith("KHÓ NỐI"):
            g = "KHÓ NỐI: " + (rv.get("ly_do") or "") + (" | " + g if g else "")
        c["P"] = thay(c["P"], x["n"], g, "\n") if g else c["P"]
    changes = [{"rowIndex": r, "expect": {"Bài cần chèn": rows[r]["values"]["Bài cần chèn"], "Đoạn cần chèn": c["L0"]},
                "set": {"Đoạn cần chèn": c["L"], "Đoạn chèn (đọc duyệt)": c["M"], "Vị trí chèn": c["N"], "Ghi chú": c["P"]}}
               for r, c in cur.items()]
    json.dump(changes, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    for r, n, why in bo:
        print(f"  KHÔNG GHI hàng {r} [{n}]: {why}")
    print(f"{len(changes)} hàng sẽ ghi, {len(bo)} đoạn bị giữ lại → {out} (chạy sheets.py write-rows … --thu trước)")


if __name__ == "__main__":
    a = sys.argv[1:]
    cmds = {"kiem": cmd_kiem, "ghi": cmd_ghi}
    if not a or a[0] not in cmds:
        print(__doc__); sys.exit(1)
    cmds[a[0]](*a[1:])
