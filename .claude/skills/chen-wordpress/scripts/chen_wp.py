#!/usr/bin/env python3
"""Chèn đoạn internal link thẳng lên WordPress qua REST API (Application Password), có sao lưu, kiểm tra, hoàn tác.
Chỉ dùng thư viện chuẩn.

Lệnh:
  kiem-quyen <key>                         đăng nhập thử, xem vai trò/quyền và các kiểu nội dung (chỉ đọc)
  thu <key> <doan.json> [--raw raw.json]   định vị chỗ chèn trên bản gốc hiện tại, KHÔNG ghi (raw.json: [{"bai","raw"}] để thử ngoại tuyến)
  chen <key> <doan.json> [--chi <url|stt>...] [--gioi-han N] [--cho-trung]
                                           chèn thật: đọc lại bài, định vị, sao lưu, ghi, đọc lại bản lưu + trang công khai
  hoan-tac <key> <file-sao-luu.json> [--ep] trả bài về bản đã sao lưu (từ chối nếu bài đã bị sửa sau lần chèn, trừ khi --ep)
  kiem-lai <doan.json> [--out kq.json]     không cần đăng nhập: mở trang công khai, kiểm từng đoạn có đúng 1 lần, đúng anchor + URL,
                                           URL đích có trả 200 thẳng không

doan.json = [{"bai":"URL bài nguồn","stt":"..","n":"1","anchor":"..","url_dich":"..","html":"<p>…</p>",
              "doan":"nguyên văn khối ngay trước chỗ chèn","sau":"khối ngay sau","vi_tri":"Cuối mục \\"<heading>\\" — …","muc":".."}]
Cấu hình: <thư mục skill>/../sheet-internal-link/wp-accounts.local.json hoặc --cfg <file>:
  {"<key>": {"site": "https://ten-mien.vn", "user": "<tên đăng nhập>", "app_password": "<mật khẩu ứng dụng>"}}
"""
import base64, collections, datetime, html, json, os, re, sys, time, urllib.error, urllib.parse, urllib.request

sys.stdout.reconfigure(encoding="utf-8")
GOC = os.path.dirname(os.path.abspath(__file__))
CFG_MAC_DINH = [os.path.join(GOC, "..", "wp-accounts.local.json"),
                os.path.join(GOC, "..", "..", "sheet-internal-link", "wp-accounts.local.json")]
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0 internal-link"
TMP = ".tmp/wp"

# ---------------- so khớp chữ ----------------
DOI = str.maketrans({'“': '"', '”': '"', '„': '"', '‘': "'", '’': "'", '–': '-', '—': '-', '−': '-', '…': '...',
                     '\xa0': ' ', '​': ''})


def ch(s):
    """Đưa chữ về một dạng: bỏ thực thể, đổi dấu do WordPress tự đổi, bỏ mọi khoảng trắng."""
    return re.sub(r"\s+", "", html.unescape(s or "").translate(DOI)).replace("--", "-")


THE = re.compile(r"<!--.*?-->|<[^>]+>|\[/?caption[^\]]*\]", re.S)


def phang(raw):
    """Chữ thuần (không khoảng trắng) + bản đồ vị trí từng chữ về raw."""
    ra, mp, i = [], [], 0
    for m in list(THE.finditer(raw)) + [None]:
        cuoi = m.start() if m else len(raw)
        for t in re.finditer(r"&#?\w+;|\S", raw[i:cuoi], re.S):
            for k in ch(t.group(0)):
                ra.append(k); mp.append(i + t.end() - 1)
        if m:
            i = m.end()
    return "".join(ra), mp


def hop_le(raw, v):
    t = raw[:v]
    for a in ("ul", "ol", "table", "blockquote"):
        if len(re.findall(rf"<{a}\b", t, re.I)) != len(re.findall(rf"</{a}>", t, re.I)):
            return f"vị trí nằm trong {a}"
    if len(re.findall(r"\[caption\b", t)) != len(re.findall(r"\[/caption\]", t)):
        return "vị trí nằm trong chú thích ảnh"
    if len(re.findall(r"<span\b", t, re.I)) != len(re.findall(r"</span>", t, re.I)):
        return "vị trí nằm trong thẻ span"
    return ""


def tim_cho(raw, x):
    """Trả (vị trí, lý do). Vị trí = chỗ ngay sau khối 'doan', đã lùi ra ngoài danh sách/bảng."""
    p, mp = phang(raw)
    dau = ch(x.get("doan"))
    if len(dau) < 8:
        return None, "thiếu đoạn trước chỗ chèn"
    k, duoi = [], ""
    for dai in (60, 40, 25):
        duoi = dau[-dai:]
        k = [m.start() for m in re.finditer(re.escape(duoi), p)]
        if k:
            break
    if not k:
        return None, "không thấy đoạn trước trong bản gốc"
    if len(k) > 1:
        dh = dau[-120:]
        k3 = [m.start() + len(dh) - len(duoi) for m in re.finditer(re.escape(dh), p)]
        hd = ch(x.get("muc") or "")
        vt = p.find(hd) if hd else -1
        k2 = [a for a in k if a > vt] if vt >= 0 else []
        if len(k3) == 1:
            k = k3
        elif k2:
            k = k2[:1]
        else:
            return None, f"đoạn trước lặp {len(k)} lần"
    e = mp[k[0] + len(duoi) - 1] + 1
    if len(re.findall(r"<table\b", raw[:e], re.I)) > len(re.findall(r"</table>", raw[:e], re.I)):
        m = re.compile(r"</table>", re.I).search(raw, e)
        if not m:
            return None, "bảng không có thẻ đóng"
        cuoi = m.end()
    else:
        m = re.compile(r"</(p|li|div|td|th|h\d)>|\[/caption\]|\r?\n", re.I).search(raw, e)
        if not m:
            cuoi = len(raw)
        else:
            giua = THE.sub("", raw[e:m.start()]).replace("&nbsp;", " ").replace("\xa0", " ").strip(" \t\r.:;,!?)\"”")
            if giua:
                return None, "sau đoạn trước còn chữ trong cùng khối"
            tag = (m.group(1) or "").lower()
            cuoi = m.start() if m.group(0).endswith("\n") else m.end()
            if tag in ("td", "th"):
                return None, "nằm trong ô bảng"
            if tag.startswith("h"):
                return None, "nằm ngay sau heading"
    while True:
        m3 = re.compile(r"\s*</(li|ul|ol|blockquote)>", re.I).match(raw, cuoi)
        if not m3:
            break
        cuoi = m3.end()
    l = hop_le(raw, cuoi)
    if l:
        return None, l
    sau = ch(THE.sub(" ", raw[cuoi:cuoi + 6000]))
    moc = ch(x.get("sau") or "")[:22]
    if moc and sau and moc not in sau[:700]:
        return None, "khối sau không khớp"
    mv = re.search(r'Cuối mục "(.*?)"', x.get("vi_tri", ""))
    if mv:
        hs = [ch(THE.sub("", a)) for a in re.findall(r"<h[1-6][^>]*>(.*?)</h[1-6]>", raw[:cuoi], re.S | re.I)]
        hs = [a for a in hs if a]
        h, g = (hs[-1] if hs else ""), ch(mv.group(1))
        if not (h[:15] == g[:15] or g[:15] in h or h[:15] in g):
            return None, "heading thực tế khác Vị trí chèn"
    return cuoi, ""


def lap(raw, ds):
    vi = []
    for x in ds:
        v, l = tim_cho(raw, x)
        if v is None:
            return None, f"[{x.get('n')}] {l}", []
        vi.append((v, x))
    moi = raw
    for v, x in sorted(vi, key=lambda a: a[0], reverse=True):
        moi = moi[:v] + "\n\n" + x["html"] + "\n\n" + moi[v:]
    return moi, "", vi


def chi_them(cu, moi, ds):
    """Bản mới = bản cũ + đúng các đoạn chèn, không đổi gì khác."""
    kt = moi
    for x in ds:
        kt = kt.replace("\n\n" + x["html"] + "\n\n", "", 1)
    return kt == cu


# ---------------- WordPress ----------------
class WP:
    def __init__(self, key, cfg=None):
        f = cfg or next((p for p in CFG_MAC_DINH if os.path.exists(p)), None)
        if not f:
            sys.exit("Chưa có file cấu hình wp-accounts.local.json (xem SKILL.md).")
        c = json.load(open(f, encoding="utf-8")).get(key)
        if not c:
            sys.exit(f"Không có key '{key}' trong {f}.")
        self.key, self.site = key, c["site"].rstrip("/")
        self.h = {"User-Agent": UA, "Content-Type": "application/json",
                  "Authorization": "Basic " + base64.b64encode(f"{c['user']}:{c['app_password']}".encode()).decode()}
        self._bases = None

    def api(self, path, data=None, timeout=90):
        r = urllib.request.Request(self.site + path, headers=self.h, method="POST" if data is not None else "GET",
                                   data=json.dumps(data).encode() if data is not None else None)
        try:
            x = urllib.request.urlopen(r, timeout=timeout)
            return x.status, json.loads(x.read().decode("utf-8", "replace") or "{}")
        except urllib.error.HTTPError as e:
            try:
                return e.code, json.loads(e.read().decode("utf-8", "replace"))
            except Exception:
                return e.code, {}

    def bases(self):
        if self._bases is None:
            st, t = self.api("/wp-json/wp/v2/types?context=edit")
            self._bases = ["posts", "pages"] + [v["rest_base"] for k, v in (t.items() if st == 200 else [])
                                                if v.get("rest_base") and v.get("viewable", True) and k not in
                                                ("post", "page", "attachment", "nav_menu_item", "wp_block", "wp_template",
                                                 "wp_template_part", "wp_navigation", "wp_global_styles", "wp_font_family",
                                                 "wp_font_face")]
        return self._bases

    def tim(self, url):
        """Tìm bài theo URL (đi theo chuyển hướng trước). Trả dict hoặc None."""
        that = lay_url_cuoi(url)[0] or url
        path = urllib.parse.urlparse(that).path.rstrip("/")
        slug = path.split("/")[-1]
        for b in self.bases():
            st, a = self.api(f"/wp-json/wp/v2/{b}?slug={urllib.parse.quote(slug)}&context=edit&status=publish"
                             "&_fields=id,slug,link,modified,status,content,type")
            if st == 200 and isinstance(a, list):
                for y in a:
                    if urllib.parse.urlparse(y["link"]).path.rstrip("/") == path:
                        return dict(base=b, id=y["id"], link=y["link"], modified=y["modified"], status=y["status"],
                                    slug=y["slug"], raw=(y.get("content") or {}).get("raw") or "")
        return None

    def doc(self, b):
        st, y = self.api(f"/wp-json/wp/v2/{b['base']}/{b['id']}?context=edit&_fields=id,slug,link,modified,status,content")
        if st != 200:
            return None
        return dict(b, link=y["link"], modified=y["modified"], status=y["status"], slug=y["slug"], raw=y["content"]["raw"])

    def ghi(self, b, raw):
        """Ghi rồi đọc lại. Hết giờ chờ phản hồi vẫn đọc lại để biết đã lưu chưa."""
        try:
            st, w = self.api(f"/wp-json/wp/v2/{b['base']}/{b['id']}", {"content": raw}, timeout=120)
        except Exception as e:
            st, w = "hết giờ", {"code": str(e)[:60]}
            time.sleep(15)
        sau = self.doc(b)
        ok = bool(sau) and sau["raw"].replace("\r\n", "\n") == raw.replace("\r\n", "\n") and sau["status"] == "publish" \
            and sau["slug"] == b["slug"]
        return ok, st, sau, w


# ---------------- trang công khai ----------------
class _KhongTheo(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


def lay_url_cuoi(u, buoc=6):
    """Theo chuyển hướng: (URL cuối, mã cuối, số bước)."""
    op, c, n = urllib.request.build_opener(_KhongTheo), u, 0
    for _ in range(buoc):
        try:
            r = op.open(urllib.request.Request(c, headers={"User-Agent": UA}), timeout=40)
            return c, r.status, n
        except urllib.error.HTTPError as e:
            if e.code in (301, 302, 307, 308) and e.headers.get("Location"):
                c, n = urllib.parse.urljoin(c, e.headers["Location"]), n + 1
                continue
            return c, e.code, n
        except Exception as e:
            return c, str(e)[:40], n
    return c, "quá nhiều bước", n


def tai_trang(u):
    t = int(time.time())
    q = u + ("&" if "?" in u else "?") + f"kt={t}"
    return urllib.request.urlopen(urllib.request.Request(q, headers={"User-Agent": UA}), timeout=90).read().decode("utf-8", "replace")


def link_tren_trang(h):
    return [(a, ch(re.sub(r"<[^>]+>", "", b))) for a, b in re.findall(r'<a\b[^>]*href="([^"]+)"[^>]*>(.*?)</a>', h, re.S)]


def co_link(links, x):
    u = x["url_dich"].rstrip("/")
    return any(html.unescape(a).rstrip("/") == u and b == ch(x["anchor"]) for a, b in links)


def so_lan_doan(h, x):
    """Số lần chữ của đoạn chèn xuất hiện trên trang."""
    p = ch(re.sub(r"<[^>]+>", "", x["html"]))[:80]
    return ch(re.sub(r"<[^>]+>", "", h)).count(p) if p else 0


# ---------------- lệnh ----------------
def nap(f):
    ds = json.load(open(f, encoding="utf-8"))
    by = collections.OrderedDict()
    for x in ds:
        if x.get("html") and x.get("bai"):
            by.setdefault(x["bai"], []).append(x)
    return ds, by


def cmd_kiem_quyen(key, cfg=None):
    w = WP(key, cfg)
    st, u = w.api("/wp-json/wp/v2/users/me?context=edit")
    if st != 200:
        sys.exit(f"Đăng nhập lỗi {st}: {u.get('code')} — kiểm tra tên đăng nhập, mật khẩu ứng dụng, và Wordfence có tắt Application Password không.")
    cap = u.get("capabilities", {})
    print("Đăng nhập OK | vai trò:", u.get("roles"))
    print("Quyền sửa bài:", {k: cap.get(k) for k in ("edit_posts", "edit_others_posts", "edit_published_posts", "edit_pages", "edit_published_pages")})
    if "administrator" in (u.get("roles") or []):
        print("CẢNH BÁO: tài khoản Quản trị viên — nên dùng Biên tập viên và thu hồi mật khẩu khi xong.")
    print("Kiểu nội dung sửa được qua API:", w.bases())


def cmd_thu(key, f, raw_file=None, cfg=None):
    ds, by = nap(f)
    nguon = {}
    if raw_file:
        nguon = {x["bai"]: x["raw"] for x in json.load(open(raw_file, encoding="utf-8"))}
    else:
        w = WP(key, cfg)
    kq, ly = [], collections.Counter()
    for bai, xs in by.items():
        raw = nguon.get(bai) if raw_file else (lambda b: b and b["raw"])(w.tim(bai))
        if not raw:
            for x in xs:
                kq.append(dict(bai=bai, n=x.get("n"), ok=False, ly_do="không đọc được bài qua API"))
            ly["không đọc được bài"] += len(xs); continue
        for x in xs:
            if x["html"] in raw:
                kq.append(dict(bai=bai, n=x.get("n"), ok=True, ly_do="đã có trên bài")); continue
            v, l = tim_cho(raw, x)
            kq.append(dict(bai=bai, n=x.get("n"), ok=v is not None, ly_do=l))
            if v is None:
                ly[l] += 1
    dat = sum(1 for k in kq if k["ok"])
    print(f"Định vị được {dat}/{len(kq)} đoạn trên {len(by)} bài.")
    if ly:
        print("Vướng:", dict(ly))
        for k in kq:
            if not k["ok"]:
                print(f"  {k['bai']} [{k['n']}]: {k['ly_do']}")
    os.makedirs(f"{TMP}/{key}", exist_ok=True)
    json.dump(kq, open(f"{TMP}/{key}/thu.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def cmd_chen(key, f, chi=None, gioi_han=None, cho_trung=False, cfg=None):
    w = WP(key, cfg)
    ds, by = nap(f)
    if chi:
        by = collections.OrderedDict((b, xs) for b, xs in by.items() if b in chi or any(str(x.get("stt")) in chi for x in xs))
    os.makedirs(f"{TMP}/{key}/sao-luu", exist_ok=True)
    logf = f"{TMP}/{key}/chen-log.json"
    log = json.load(open(logf, encoding="utf-8")) if os.path.exists(logf) else {}
    loi_lien, so_bai = 0, 0
    for bai, xs in by.items():
        if gioi_han and so_bai >= gioi_han:
            break
        try:
            b = w.tim(bai)
            if not b:
                raise ValueError("không tìm thấy bài qua API (trang danh mục, Elementor hoặc kiểu nội dung lạ)")
            if "elementor" in b["raw"]:
                raise ValueError("bài dựng bằng Elementor, chèn qua API có thể bị ghi đè — dán tay")
            raw, lam = b["raw"], []
            for x in xs:
                k = f"{bai}#{x.get('n')}"
                if x["html"] in raw:
                    log[k] = dict(tt="đã có", luc=str(datetime.datetime.now())); continue
                if not cho_trung and x["url_dich"] in raw:
                    log[k] = dict(tt="bỏ: bài đã có link tới URL đích"); continue
                v, l = tim_cho(raw, x)
                if v is None:
                    log[k] = dict(tt="cần dán tay", ly_do=l); continue
                lam.append(x)
            if not lam:
                continue
            moi, l, _ = lap(raw, lam)
            if moi is None or not chi_them(raw, moi, lam):
                raise ValueError("bản mới khác bản cũ ngoài phần chèn: " + (l or ""))
            ten = f"{TMP}/{key}/sao-luu/{b['id']}-{datetime.datetime.now():%Y%m%d-%H%M%S}.json"
            json.dump(dict(bai=bai, base=b["base"], id=b["id"], slug=b["slug"], link=b["link"], modified_truoc=b["modified"],
                           raw=raw, luc=str(datetime.datetime.now())), open(ten, "w", encoding="utf-8"), ensure_ascii=False)
            ok, st, sau, resp = w.ghi(b, moi)
            if not ok:
                raise RuntimeError(f"ghi không thành công ({st} {resp.get('code', '')})")
            sl = json.load(open(ten, encoding="utf-8")); sl["modified_sau"] = sau["modified"]
            json.dump(sl, open(ten, "w", encoding="utf-8"), ensure_ascii=False)
            try:
                h = tai_trang(sau["link"]); links = link_tren_trang(h)
            except Exception:
                h, links = "", []
            for x in lam:
                log[f"{bai}#{x.get('n')}"] = dict(tt="đã chèn" if co_link(links, x) else "đã chèn, chưa thấy trên trang (cache?)",
                                                  sao_luu=ten, luc=str(datetime.datetime.now()))
            print(f"{bai}: chèn {len(lam)} đoạn | sao lưu {ten}", flush=True)
            loi_lien, so_bai = 0, so_bai + 1
        except Exception as e:
            loi_lien += 1
            for x in xs:
                log.setdefault(f"{bai}#{x.get('n')}", dict(tt="lỗi", ly_do=str(e)[:150]))
            print(f"LỖI {bai}: {str(e)[:150]}", flush=True)
            if loi_lien >= 3:
                print("DỪNG: 3 bài lỗi liên tiếp", flush=True)
                break
        json.dump(log, open(logf, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        time.sleep(2)
    json.dump(log, open(logf, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("Tổng:", dict(collections.Counter(v["tt"] for v in log.values())), "| log:", logf)


def cmd_hoan_tac(key, f, ep=False, cfg=None):
    w = WP(key, cfg)
    sl = json.load(open(f, encoding="utf-8"))
    b = w.doc(dict(base=sl["base"], id=sl["id"], slug=sl["slug"]))
    if not b:
        sys.exit("Không đọc được bài.")
    if not ep and sl.get("modified_sau") and b["modified"] != sl["modified_sau"]:
        sys.exit(f"Bài đã bị sửa sau lần chèn ({sl['modified_sau']} → {b['modified']}). Hoàn tác sẽ mất phần sửa đó; thêm --ep nếu vẫn muốn.")
    ten = f"{TMP}/{key}/sao-luu/{sl['id']}-truoc-hoan-tac-{datetime.datetime.now():%Y%m%d-%H%M%S}.json"
    json.dump(dict(sl, raw=b["raw"], modified_truoc=b["modified"]), open(ten, "w", encoding="utf-8"), ensure_ascii=False)
    ok, st, sau, _ = w.ghi(b, sl["raw"])
    print("Hoàn tác", "xong" if ok else f"KHÔNG thành công ({st})", "| bản trước khi hoàn tác:", ten)


def cmd_kiem_lai(f, out=None):
    ds, by = nap(f)
    kq, dich = [], {}
    for bai, xs in by.items():
        try:
            h = tai_trang(bai); links = link_tren_trang(h)
        except Exception as e:
            for x in xs:
                kq.append(dict(bai=bai, n=x.get("n"), anchor=x["anchor"], ket_qua="không tải được trang: " + str(e)[:40]))
            continue
        for x in xs:
            n_doan = so_lan_doan(h, x)
            n_link = sum(1 for a, b in links if html.unescape(a).rstrip("/") == x["url_dich"].rstrip("/") and b == ch(x["anchor"]))
            if n_doan == 0 and n_link == 0:
                k = "không có trên trang"
            elif n_doan > 1:
                k = f"đoạn bị lặp {n_doan} lần"
            elif n_link == 0:
                k = "có đoạn nhưng mất link / sai anchor"
            elif n_link > 1:
                k = f"anchor gắn {n_link} lần tới cùng URL"
            else:
                k = "đúng"
            if x["url_dich"] not in dich:
                dich[x["url_dich"]] = lay_url_cuoi(x["url_dich"])
            c, st, nb = dich[x["url_dich"]]
            kq.append(dict(bai=bai, stt=x.get("stt"), n=x.get("n"), anchor=x["anchor"], ket_qua=k,
                           dich=("200" if st == 200 and nb == 0 else f"{st} sau {nb} chuyển hướng → {c}")))
        time.sleep(0.5)
    c = collections.Counter(k["ket_qua"] for k in kq)
    print(f"Kiểm {len(kq)} đoạn trên {len(by)} bài:", dict(c))
    for k in kq:
        if k["ket_qua"] != "đúng" or k.get("dich", "200") != "200":
            print(f"  {k['bai']} [{k['n']}] «{k['anchor']}»: {k['ket_qua']} | đích {k.get('dich')}")
    if out:
        json.dump(kq, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def main(a):
    if len(a) < 2:
        sys.exit(__doc__)
    o = lambda f: a[a.index(f) + 1] if f in a else None
    cfg = o("--cfg")
    if a[1] == "kiem-quyen":
        cmd_kiem_quyen(a[2], cfg)
    elif a[1] == "thu":
        cmd_thu(a[2], a[3], o("--raw"), cfg)
    elif a[1] == "chen":
        chi = a[a.index("--chi") + 1:] if "--chi" in a else None
        if chi:
            chi = [x for x in chi if not x.startswith("--")]
        cmd_chen(a[2], a[3], chi, int(o("--gioi-han")) if o("--gioi-han") else None, "--cho-trung" in a, cfg)
    elif a[1] == "hoan-tac":
        cmd_hoan_tac(a[2], a[3], "--ep" in a, cfg)
    elif a[1] == "kiem-lai":
        cmd_kiem_lai(a[2], o("--out"))
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main(sys.argv)
