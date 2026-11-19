#!/usr/bin/env python3
"""Dò link nội bộ trong thân bài: 404, chuyển hướng 301, tự trỏ về chính bài, cùng đích lặp nhiều lần.
Có lệnh đổi link 301 sang URL cuối trên WordPress (dùng chung kết nối của skill chen-wordpress). Chỉ dùng thư viện chuẩn.

Lệnh:
  quet <ds-url.txt | URL sitemap.xml> <out.json> [--lap 3] [--toi-da 300]
        đọc thân bài từng trang (bỏ menu/footer bằng doc_bai), kiểm mọi link nội bộ, in báo cáo
  doi-301 <key> <out.json> [--chi <url>...] [--gioi-han N] [--thu]
        trên WordPress: đổi href đang qua 301 sang URL cuối (chỉ đổi href, giữ #/?), sao lưu từng bài,
        kiểm phần còn lại y nguyên; --thu = chỉ đếm, không ghi
"""
import collections, json, os, re, subprocess, sys, time, urllib.parse, urllib.request, html as H
from concurrent.futures import ThreadPoolExecutor

sys.stdout.reconfigure(encoding="utf-8")
GOC = os.path.dirname(os.path.abspath(__file__))
DOC_BAI = os.path.join(GOC, "..", "..", "doc-bai", "scripts", "doc_bai.py")
sys.path.insert(0, os.path.join(GOC, "..", "..", "chen-wordpress", "scripts"))
import chen_wp as CW  # noqa: E402

TMP = ".tmp/kiem-link"


def chuan(u, goc=""):
    u = urllib.parse.urljoin(goc, H.unescape(u.strip()))
    u = u.split("#")[0].split("?")[0]
    return u.rstrip("/")


def ds_url(nguon):
    if nguon.startswith("http"):
        x = urllib.request.urlopen(urllib.request.Request(nguon, headers={"User-Agent": CW.UA}), timeout=60).read().decode("utf-8", "replace")
        locs = re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", x)
        con = [l for l in locs if l.endswith(".xml")]
        if con:
            out = []
            for c in con:
                out += ds_url(c)
            return out
        return locs
    return [l.strip() for l in open(nguon, encoding="utf-8") if l.strip().startswith("http")]


def doc_than(u, i):
    os.makedirs(f"{TMP}/bai", exist_ok=True)
    f = f"{TMP}/bai/{i}.json"
    r = subprocess.run([sys.executable, DOC_BAI, "fetch", u, f], capture_output=True, text=True, encoding="utf-8")
    try:
        return json.load(open(f, encoding="utf-8"))
    except Exception:
        return {"loi": (r.stderr or r.stdout or "")[-120:]}


def cmd_quet(nguon, out, lap=3, toi_da=300):
    urls = ds_url(nguon)[:toi_da]
    if not urls:
        sys.exit("Không có URL nào.")
    mien = urllib.parse.urlparse(urls[0]).netloc.replace("www.", "")
    with ThreadPoolExecutor(6) as ex:
        bais = list(ex.map(lambda p: (p[1], doc_than(p[1], p[0])), enumerate(urls)))
    lk, goc = {}, {}
    for u, d in bais:
        if "blocks" not in d:
            continue
        for b in d["blocks"]:
            for x in (b.get("links") or []):
                h = x.get("href") if isinstance(x, dict) else x
                if not h or h.startswith(("mailto:", "tel:", "#", "javascript:")):
                    continue
                c = chuan(h, u)
                if urllib.parse.urlparse(c).netloc.replace("www.", "") == mien:
                    lk.setdefault(u, []).append((c, b.get("text", "")[:60]))
                    goc.setdefault(c, urllib.parse.urljoin(u, H.unescape(h.strip())).split("#")[0])
    tat = sorted({c for v in lk.values() for c, _ in v})
    print(f"{len(urls)} trang, {len(tat)} link nội bộ khác nhau — đang kiểm…", flush=True)
    with ThreadPoolExecutor(8) as ex:
        tt = dict(zip(tat, ex.map(lambda c: CW.lay_url_cuoi(goc[c]), tat)))
    kq = []
    for u, d in bais:
        mot = dict(trang=u, loi_tai=d.get("loi", ""), so_404=[], so_301=[], tu_tro=[], lap=[])
        dem = collections.Counter(c for c, _ in lk.get(u, []))
        for c in dem:
            cuoi, st, nb = tt[c]
            if st == 404 or (isinstance(st, int) and st >= 400):
                mot["so_404"].append(dict(link=c, ma=st))
            elif nb > 0 and chuan(cuoi) != c:
                if chuan(cuoi) == chuan(u):
                    mot["tu_tro"].append(dict(link=c, ve=cuoi))
                else:
                    mot["so_301"].append(dict(link=c, ve=cuoi, buoc=nb))
        for c, k in dem.items():
            if k >= lap and chuan(c) not in (chuan(u), chuan(f"https://{mien}")):
                mot["lap"].append(dict(link=c, lan=k))
        kq.append(mot)
    json.dump(dict(mien=mien, trang=kq, url=tt), open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    t404 = collections.Counter(x["link"] for k in kq for x in k["so_404"])
    t301 = collections.Counter(x["link"] for k in kq for x in k["so_301"])
    for k in kq:
        for x in k["so_301"]:
            x["href"] = goc[x["link"]]
    print(f"\nLink 404: {len(t404)} link khác nhau, ở {sum(1 for k in kq if k['so_404'])} trang")
    for l, n in t404.most_common(15):
        print(f"  {l}  ({n} trang)")
    print(f"Link qua chuyển hướng: {len(t301)} link khác nhau, {sum(len(k['so_301']) for k in kq)} lượt")
    for l, n in t301.most_common(10):
        print(f"  {l} → {tt[l][0]}  ({n} trang)")
    tu = [(k["trang"], x["link"]) for k in kq for x in k["tu_tro"]]
    print(f"Tự trỏ về chính bài qua chuyển hướng: {len(tu)}")
    for a in tu[:10]:
        print("  ", a)
    print(f"Trang trỏ cùng 1 đích ≥ {lap} lần: {sum(len(k['lap']) for k in kq)} cặp")
    for k in sorted((dict(trang=k['trang'], **x) for k in kq for x in k['lap']), key=lambda a: -a["lan"])[:10]:
        print(f"  {k['trang']} → {k['link']} ×{k['lan']}")
    loi = [k["trang"] for k in kq if k["loi_tai"]]
    if loi:
        print("Không đọc được:", loi[:10])
    print("Kết quả đầy đủ:", out)


def cmd_doi_301(key, f, chi=None, gioi_han=None, thu=False):
    d = json.load(open(f, encoding="utf-8"))
    M = {}
    for k in d["trang"]:
        for x in k["so_301"]:
            M[x["link"]] = x["ve"]
    if not M:
        sys.exit("Không có link 301 nào để đổi.")
    w = CW.WP(key)
    RE = re.compile(r'(<a\b[^>]*?\bhref=")([^"]+)(")', re.I)

    def doi(raw, goc):
        n = [0]

        def f2(m):
            h = H.unescape(m.group(2)); duoi = re.search(r"[?#].*$", h)
            c = M.get(chuan(h, goc))
            if not c:
                return m.group(0)
            n[0] += 1
            return m.group(1) + c + (duoi.group(0) if duoi else "") + m.group(3)
        return RE.sub(f2, raw), n[0]

    trang = [k["trang"] for k in d["trang"] if k["so_301"] and (not chi or k["trang"] in chi)]
    os.makedirs(f"{CW.TMP}/{key}/sao-luu", exist_ok=True)
    tong, so = 0, 0
    for u in trang:
        if gioi_han and so >= gioi_han:
            break
        b = w.tim(u)
        if not b:
            print("Không tìm thấy qua API:", u); continue
        moi, n = doi(b["raw"], b["link"])
        bo = lambda t: RE.sub(r"\1\3", t)
        if not n:
            continue
        if bo(moi) != bo(b["raw"]):
            print("BỎ (khác ngoài href):", u); continue
        if thu:
            print(f"{u}: sẽ đổi {n} link"); tong += n; so += 1; continue
        ten = f"{CW.TMP}/{key}/sao-luu/{b['id']}-truoc-doi301-{time.strftime('%Y%m%d-%H%M%S')}.json"
        json.dump(dict(bai=u, base=b["base"], id=b["id"], slug=b["slug"], link=b["link"], modified_truoc=b["modified"], raw=b["raw"]),
                  open(ten, "w", encoding="utf-8"), ensure_ascii=False)
        ok, st, sau, _ = w.ghi(b, moi)
        if ok:
            sl = json.load(open(ten, encoding="utf-8")); sl["modified_sau"] = sau["modified"]
            json.dump(sl, open(ten, "w", encoding="utf-8"), ensure_ascii=False)
        print(f"{u}: {'đổi' if ok else 'LỖI'} {n} link", flush=True)
        if ok:
            tong += n; so += 1
        time.sleep(2)
    print(f"Tổng: {so} bài, {tong} lượt link" + (" (chạy thử, chưa ghi)" if thu else ""))


def main(a):
    if len(a) < 3:
        sys.exit(__doc__)
    o = lambda f: a[a.index(f) + 1] if f in a else None
    if a[1] == "quet":
        cmd_quet(a[2], a[3], int(o("--lap") or 3), int(o("--toi-da") or 300))
    elif a[1] == "doi-301":
        chi = [x for x in a[a.index("--chi") + 1:] if not x.startswith("--")] if "--chi" in a else None
        cmd_doi_301(a[2], a[3], chi, int(o("--gioi-han")) if o("--gioi-han") else None, "--thu" in a)
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main(sys.argv)
