#!/usr/bin/env python3
"""Lên mô hình internal link theo NỘI DUNG bài: ai trỏ về đâu, mỗi anchor bao nhiêu lần. Chỉ dùng thư viện chuẩn.

Lệnh (thư mục làm việc mặc định .tmp/mo-hinh):
  nguon     <sheet.json> <nguon.json>
      → lấy danh sách "Bài cần chèn" (kèm rowIndex thật) từ file `sheets.py read` → nguon.json cho `doc_bai.py quet`.
  xem       <bai.json>
      → in gọn một bài đã tải (heading, đoạn văn rút gọn, loại khối, chỗ có link) để người chấm đọc nhanh.
  suc-chua  <dich.json> <quet.json> <thu-muc-cham>
      → ĐO TRƯỚC KHI XẾP: mỗi anchor có bao nhiêu bài hợp (điểm ≥2 / ≥1), xếp tối đa được bao nhiêu link
        ở mức "tự nhiên" (≥2) và "cho phép nối chung" (≥1) so với số lần yêu cầu. In bảng + ghi suc-chua.json.
  xep       <dich.json> <quet.json> <thu-muc-cham> <plan.json> [--min 2|1] [--toi-da 3] [--giu <sheet.json>]
      → xếp bằng luồng chi phí nhỏ nhất: ưu tiên điểm hợp cao; mỗi bài ≤ --toi-da link, mỗi anchor ≤ số lần;
        loại cặp đã có link trong câu văn / tự trỏ / bài nguồn chuyển hướng. --giu: giữ các cặp đang có trên sheet
        (khi xếp lại một phần) nếu vẫn hợp lệ.
  ghi-sheet <plan.json> <sheet.json> <changes.json>
      → tạo changes.json cho `sheets.py write-rows` (cột Key/URL/Anchor 1–3, anchor gắn link, kèm `expect`).

dich.json  = [{"id":"A1","anchor":"…","url":"https://…","so_lan":30,"mo_ta":"bài đích nói gì"}]
cham/<rowIndex>.json = {"rowIndex":5,"diem":{"A1":{"d":0-3,"cho":"chỗ gợi ý","ly_do":"…"}, …}}
"""
import json
import os
import re
import sys
from collections import Counter

sys.stdout.reconfigure(encoding="utf-8")


def load(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def save(p, d):
    os.makedirs(os.path.dirname(p) or ".", exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=1)


def norm_url(u):
    return re.sub(r"^https?://(www\.)?", "", (u or "").strip()).rstrip("/").split("#")[0].split("?")[0].lower()


# ---------- nguon / xem ----------

def cmd_nguon(sheet_file, out):
    sh = load(sheet_file)
    nguon = [{"rowIndex": r["rowIndex"], "url": r["values"].get("Bài cần chèn", "").strip()}
             for r in sh["rows"] if r["values"].get("Bài cần chèn", "").strip().startswith("http")]
    dup = [u for u, c in Counter(norm_url(x["url"]) for x in nguon).items() if c > 1]
    save(out, nguon)
    print(f"{len(nguon)} bài nguồn → {out}" + (f" | TRÙNG URL: {dup}" if dup else ""))


def cmd_xem(bai_file):
    d = load(bai_file)
    print(f"# {d.get('h1') or d.get('title')}  ({d['url']})" + ("  [CHUYỂN HƯỚNG → " + d["url_that"] + "]" if d.get("chuyen_huong") else ""))
    for b in d["blocks"]:
        t = b["text"]
        if b["loai"] == "tieu_de":
            print(f"\n[{b['i']}] {b['tag'].upper()}: {t}")
            continue
        co = " 🔗" + ",".join(l["href"].rstrip("/").split("/")[-1][:30] for l in b["links"]) if b["links"] else ""
        flag = "".join([" FAQ" if b.get("faq") else "", " KẾT" if b.get("ket") else "", " liệt-kê" if b.get("liet_ke") else ""])
        print(f"  [{b['i']}] ({b['loai']}{flag}) {t[:220]}{'…' if len(t) > 220 else ''}{co}")


# ---------- dữ liệu điểm ----------

def bang_diem(dich, quet, cham_dir):
    """diem[(row, id)] = số điểm (None = không được chèn) + lý do loại."""
    diem, loai, thieu = {}, {}, []
    for row, b in quet["bai"].items():
        f = os.path.join(cham_dir, f"{row}.json")
        c = load(f)["diem"] if os.path.exists(f) else None
        if c is None:
            thieu.append(row)
        for t in dich:
            st = b["dich"][t["id"]]["trang_thai"]
            if b.get("chuyen_huong"):
                diem[(row, t["id"])] = None; loai[(row, t["id"])] = "bài nguồn chuyển hướng"
            elif st in ("tu_tro", "co_link"):
                diem[(row, t["id"])] = None; loai[(row, t["id"])] = "tự trỏ" if st == "tu_tro" else "đã có link trong câu văn"
            elif c is None or t["id"] not in c:
                diem[(row, t["id"])] = None; loai[(row, t["id"])] = "chưa chấm"
            else:
                d = int(c[t["id"]].get("d", 0))
                diem[(row, t["id"])] = d if d > 0 else None
                if d <= 0:
                    loai[(row, t["id"])] = "điểm 0"
    return diem, loai, thieu


def flow(rows, dich, diem, min_d, toi_da, giu=None, giu_bonus=4, cam=None):
    """Luồng chi phí nhỏ nhất: S → bài (≤ toi_da, số hoặc dict theo bài) → anchor (1) → T (≤ so_lan).
    Chi phí = -(điểm*10 + thưởng giữ). `cam` = các cặp không được chọn thêm (đã chèn rồi)."""
    giu, cam = giu or set(), cam or set()
    nodes = ["S"] + [f"r{r}" for r in rows] + [f"a{t['id']}" for t in dich] + ["T"]
    idx = {v: k for k, v in enumerate(nodes)}
    g = [[] for _ in nodes]

    def add(u, v, cap, cost):
        g[u].append([v, cap, cost, len(g[v])]); g[v].append([u, 0, -cost, len(g[u]) - 1])
    for r in rows:
        add(idx["S"], idx[f"r{r}"], toi_da[r] if isinstance(toi_da, dict) else toi_da, 0)
        for t in dich:
            d = diem.get((r, t["id"]))
            if d is None or d < min_d or (r, t["id"]) in cam:
                continue
            add(idx[f"r{r}"], idx[f"a{t['id']}"], 1, -(d * 10 + (giu_bonus * 10 if (r, t["id"]) in giu else 0)))
    for t in dich:
        add(idx[f"a{t['id']}"], idx["T"], int(t["so_lan"]), 0)
    S, T, f = idx["S"], idx["T"], 0
    while True:
        dist = [float("inf")] * len(nodes); prev = [None] * len(nodes); inq = [False] * len(nodes)
        dist[S] = 0; q = [S]
        while q:
            u = q.pop(0); inq[u] = False
            for k, (v, cap, cost, _) in enumerate(g[u]):
                if cap > 0 and dist[u] + cost < dist[v]:
                    dist[v] = dist[u] + cost; prev[v] = (u, k)
                    if not inq[v]:
                        inq[v] = True; q.append(v)
        if dist[T] == float("inf"):
            break
        v = T
        while v != S:
            u, k = prev[v]; g[u][k][1] -= 1; g[v][g[u][k][3]][1] += 1; v = u
        f += 1
    pick = {r: [nodes[v][1:] for v, cap, cost, _ in g[idx[f"r{r}"]] if nodes[v].startswith("a") and cap == 0 and cost < 0] for r in rows}
    return f, pick


# ---------- suc-chua ----------

def cmd_suc_chua(dich_file, quet_file, cham_dir):
    dich, quet = load(dich_file), load(quet_file)
    diem, loai, thieu = bang_diem(dich, quet, cham_dir)
    rows = sorted(quet["bai"], key=int)
    need = sum(int(t["so_lan"]) for t in dich)
    print(f"{len(rows)} bài nguồn, {len(dich)} anchor, cần {need} link (tối đa {3 * len(rows)} chỗ nếu 3 link/bài)")
    if thieu:
        print(f"CHƯA CHẤM {len(thieu)} bài: {thieu[:20]}")
    ch = [r for r in rows if quet["bai"][r].get("chuyen_huong")]
    if ch:
        print(f"Bài nguồn CHUYỂN HƯỚNG (không chèn được, nên thay URL): {ch}")
    kq = {}
    for md in (2, 1):
        f, pick = flow(rows, dich, diem, md, 3)
        cnt = Counter(a for p in pick.values() for a in p)
        kq[md] = {"tong": f, "theo_anchor": {t["id"]: cnt[t["id"]] for t in dich}}
    print(f"\n{'anchor':42} {'cần':>4} {'bài ≥2':>7} {'bài ≥1':>7} {'xếp ≥2':>7} {'xếp ≥1':>7}")
    for t in dich:
        s2 = sum(1 for r in rows if (diem.get((r, t['id'])) or 0) >= 2)
        s1 = sum(1 for r in rows if (diem.get((r, t['id'])) or 0) >= 1)
        print(f"{t['anchor'][:42]:42} {t['so_lan']:>4} {s2:>7} {s1:>7} {kq[2]['theo_anchor'][t['id']]:>7} {kq[1]['theo_anchor'][t['id']]:>7}")
    print(f"{'TỔNG':42} {need:>4} {'':>7} {'':>7} {kq[2]['tong']:>7} {kq[1]['tong']:>7}")
    zero = [r for r in rows if all((diem.get((r, t['id'])) or 0) == 0 for t in dich)]
    da_du = [r for r in zero if sum(loai.get((r, t["id"])) == "đã có link trong câu văn" for t in dich) >= 3]
    if da_du:
        print(f"Bài đã có link (trong câu văn) tới ≥3 đích, không còn anchor nào để chèn: {da_du}")
    kho = [r for r in zero if r not in da_du and r not in ch]
    if kho:
        print(f"Bài nội dung không nối được anchor nào (điểm 0): {kho}")
    save(os.path.join(os.path.dirname(quet_file) or ".", "suc-chua.json"),
         {"can": need, "xep_tu_nhien": kq[2], "xep_cho_phep_noi_chung": kq[1], "bai_khong_noi_duoc": zero, "bai_chuyen_huong": ch})
    if kq[2]["tong"] < need:
        print(f"\n→ THIẾU {need - kq[2]['tong']} link nếu chỉ dùng chỗ tự nhiên. HỎI NGƯỜI DÙNG trước khi xếp: "
              f"(a) thêm bài nguồn, (b) cho phép câu nối chung (xếp được {kq[1]['tong']}), (c) chỉ giữ link tự nhiên.")


# ---------- xep / ghi-sheet ----------

def cmd_xep(dich_file, quet_file, cham_dir, out, *opts):
    o = dict(zip(opts[::2], opts[1::2]))
    min_d, toi_da = int(o.get("--min", 2)), int(o.get("--toi-da", 3))
    dich, quet = load(dich_file), load(quet_file)
    diem, loai, _ = bang_diem(dich, quet, cham_dir)
    rows = sorted(quet["bai"], key=int)
    giu, da_chen = set(), {}
    if "--giu" in o:
        url2id = {norm_url(t["url"]): t["id"] for t in dich}
        for r in load(o["--giu"])["rows"]:
            for n in (1, 2, 3):
                a = url2id.get(norm_url(r["values"].get(f"URL đích {n}", "")))
                if not a:
                    continue
                k = (str(r["rowIndex"]), a)
                if quet["bai"].get(k[0], {}).get("dich", {}).get(a, {}).get("trang_thai") == "co_link":
                    da_chen[k] = True  # cặp của mô hình cũ ĐÃ dán lên web → tính là xong, giữ nguyên
                else:
                    giu.add(k)
    # cặp đã chèn trên web: trừ vào số lần của anchor và số chỗ của bài
    dich_con = [dict(t, so_lan=max(0, int(t["so_lan"]) - sum(1 for (_, a) in da_chen if a == t["id"]))) for t in dich]
    cho = Counter(r for (r, _) in da_chen)
    rows_con = [r for r in rows if toi_da - cho[r] > 0]
    pick = {r: [] for r in rows}
    f, pick_con = flow(rows_con, dich_con, diem, min_d, {r: toi_da - cho[r] for r in rows_con}, giu,
                       cam={k for k in da_chen})
    for r in rows:
        pick[r] = [a for (rr, a) in da_chen if rr == r] + pick_con.get(r, [])
    need = sum(int(t["so_lan"]) for t in dich)
    plan = {}
    for r in rows:
        ds = sorted(pick[r], key=lambda a: (not da_chen.get((r, a), False), -(diem.get((r, a)) or 0)))
        plan[r] = [{"id": a, "diem": diem.get((r, a)), **({"da_chen": True} if da_chen.get((r, a)) else {})} for a in ds]
    f += len(da_chen)
    if da_chen:
        print(f"  {len(da_chen)} cặp của mô hình cũ đã có trên web → giữ nguyên, trừ vào số lần")
    cnt = Counter(a for p in pick.values() for a in p)
    save(out, {"min": min_d, "toi_da": toi_da, "plan": plan,
               "theo_anchor": {t["id"]: {"xep": cnt[t["id"]], "can": int(t["so_lan"])} for t in dich}})
    print(f"xếp {f}/{need} link (điểm tối thiểu {min_d}, tối đa {toi_da} link/bài) → {out}")
    for t in dich:
        if cnt[t["id"]] < int(t["so_lan"]):
            print(f"  THIẾU {t['anchor']}: {cnt[t['id']]}/{t['so_lan']}")
    print("  điểm các cặp:", dict(Counter(x["diem"] for p in plan.values() for x in p)))
    it = {r: len(p) for r, p in plan.items() if len(p) < toi_da}
    if it:
        print(f"  bài ít hơn {toi_da} link: {it}")
    if giu:
        giu_lai = sum(1 for r, p in plan.items() for x in p if (r, x["id"]) in giu)
        print(f"  giữ lại {giu_lai}/{len(giu)} cặp đang có trên sheet")


def cmd_ghi_sheet(plan_file, sheet_file, out, dich_file=None):
    plan = load(plan_file)
    dich = {t["id"]: t for t in load(dich_file or os.path.join(os.path.dirname(plan_file) or ".", "dich.json"))}
    rows = {str(r["rowIndex"]): r for r in load(sheet_file)["rows"]}
    changes = []
    for r, p in plan["plan"].items():
        if r not in rows:
            print(f"  BỎ QUA hàng {r}: không còn trên sheet"); continue
        s = {}
        for n in (1, 2, 3):
            if n <= len(p):
                t = dich[p[n - 1]["id"]]
                s.update({f"Key mục tiêu {n}": t["anchor"], f"URL đích {n}": t["url"],
                          f"Anchor text {n}": {"text": t["anchor"], "link": t["url"]}})
            else:
                s.update({f"Key mục tiêu {n}": "", f"URL đích {n}": "", f"Anchor text {n}": ""})
        changes.append({"rowIndex": int(r), "expect": {"Bài cần chèn": rows[r]["values"]["Bài cần chèn"]}, "set": s})
    save(out, changes)
    print(f"{len(changes)} hàng → {out} (chạy: sheets.py write-rows … {out} --thu, rồi bỏ --thu)")


if __name__ == "__main__":
    a = sys.argv[1:]
    cmds = {"nguon": cmd_nguon, "xem": cmd_xem, "suc-chua": cmd_suc_chua, "xep": cmd_xep, "ghi-sheet": cmd_ghi_sheet}
    if not a or a[0] not in cmds:
        print(__doc__); sys.exit(1)
    try:
        cmds[a[0]](*a[1:])
    except TypeError:
        print(__doc__); sys.exit("sai số tham số cho lệnh " + a[0])
