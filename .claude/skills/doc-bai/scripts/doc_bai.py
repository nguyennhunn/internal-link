#!/usr/bin/env python3
"""Tải và đọc bài viết trên web để tìm chỗ chèn internal link. Chỉ dùng thư viện chuẩn.

Lệnh:
  fetch    <url> <out.json>
      → {url, title, h1, blocks:[{i, tag, text}], links:[href...]}
  chuan-bi <url_bai> "<key mục tiêu>" "<anchor>" <url_dich> <out.json>
      → tải bài + chấm điểm từng đoạn theo độ gần nghĩa với key/anchor, in ra bản TÓM TẮT
        (tiêu đề, dàn ý H2/H3, 5 đoạn ứng viên kèm đoạn trước/sau, bài đã có link tới đích chưa)
        để Claude chỉ phải đọc đúng phần cần — tiết kiệm token.
  chuan-bi-nhieu <url_bai> <yeu-cau.json> <out.json>
      → như trên nhưng cho NHIỀU link vào cùng một bài. yeu-cau.json = [{"stt","key","anchor","url_dich"}, ...]
        Tải bài 1 lần; các chỗ chèn được chia sao cho cách nhau >= 3 đoạn, không trùng nhau.
"""
import json
import re
import sys
import unicodedata
import urllib.request
import urllib.error
from html.parser import HTMLParser

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
SKIP_TAGS = {"script", "style", "noscript", "nav", "header", "footer", "aside", "form", "iframe", "svg", "template", "button"}
BLOCK_TAGS = {"h1", "h2", "h3", "h4", "p", "li", "blockquote"}
CONTENT_HINT = re.compile(r"entry-content|post-content|article-content|article-body|post-body|single-content|the-content|content-area|blog-content|td-post-content|elementor-widget-theme-post-content", re.I)
SKIP_CLASS = re.compile(r"comment|sidebar|related|breadcrumb|share|widget|menu|footer|header|toc|table-of-contents|author-box|tags", re.I)


class Node:
    __slots__ = ("tag", "attrs", "children", "parent", "text")

    def __init__(self, tag, attrs, parent):
        self.tag, self.attrs, self.parent = tag, dict(attrs), parent
        self.children, self.text = [], []


class P(HTMLParser):
    VOID = {"br", "img", "hr", "meta", "link", "input", "source", "wbr"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = Node("root", [], None)
        self.cur = self.root
        self.title = ""
        self._in_title = False

    def handle_starttag(self, tag, attrs):
        if tag == "title":
            self._in_title = True
        n = Node(tag, attrs, self.cur)
        self.cur.children.append(n)
        if tag not in self.VOID:
            self.cur = n

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False
        n = self.cur
        while n is not self.root and n.tag != tag:
            n = n.parent
        if n is not self.root:
            self.cur = n.parent

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        self.cur.children.append(data)


def fetch_html(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "vi,en;q=0.8"})
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            raw = r.read()
            ct = r.headers.get("Content-Type", "")
    except urllib.error.HTTPError as e:
        sys.exit(f"LỖI: {url} trả về HTTP {e.code}")
    except Exception as e:
        sys.exit(f"LỖI: không tải được {url}: {e}")
    m = re.search(r"charset=([\w-]+)", ct)
    enc = m.group(1) if m else "utf-8"
    try:
        return raw.decode(enc, errors="replace")
    except LookupError:
        return raw.decode("utf-8", errors="replace")


def cls(n):
    return (n.attrs.get("class", "") + " " + n.attrs.get("id", "")) if isinstance(n, Node) else ""


def text_of(n):
    if isinstance(n, str):
        return n
    if n.tag in SKIP_TAGS:
        return ""
    return "".join(text_of(c) for c in n.children)


def norm(s):
    return re.sub(r"\s+", " ", s).strip()


def pick_container(root):
    best, best_score = root, -1

    def walk(n):
        nonlocal best, best_score
        if not isinstance(n, Node) or n.tag in SKIP_TAGS:
            return
        if n.tag in ("article", "main") or CONTENT_HINT.search(cls(n)):
            ps = count_p(n)
            bonus = 2 if n.tag == "article" or CONTENT_HINT.search(cls(n)) else 1
            score = ps * bonus
            if score > best_score:
                best, best_score = n, score
        for c in n.children:
            walk(c)

    def count_p(n):
        if not isinstance(n, Node) or n.tag in SKIP_TAGS:
            return 0
        return (1 if n.tag == "p" and len(norm(text_of(n))) > 40 else 0) + sum(count_p(c) for c in n.children)

    walk(root)
    return best


XEM_THEM = re.compile(r"(có thể bạn quan tâm|xem thêm|tham khảo|đọc thêm|bài viết liên quan|chi tiết tham khảo|xem ngay|tìm hiểu thêm)", re.I)


def extract_blocks(container):
    """Tách khối văn bản (h1-h4, p, li, blockquote) trong phần thân bài. Mỗi khối ghi kèm các link nằm bên trong nó,
    để phân biệt link trong câu văn với link ở menu/footer/bài liên quan (không thuộc khối nào)."""
    blocks, links = [], []

    def links_in(n, acc):
        if isinstance(n, str) or n.tag in SKIP_TAGS:
            return
        if n.tag == "a" and n.attrs.get("href"):
            acc.append({"href": n.attrs["href"], "text": norm(text_of(n))})
        for c in n.children:
            links_in(c, acc)

    def has_block_inside(n):
        if isinstance(n, str) or n.tag in SKIP_TAGS:
            return False
        return any(isinstance(c, Node) and (c.tag in BLOCK_TAGS or has_block_inside(c)) for c in n.children)

    def flush_direct(nodes):
        t = norm("".join(text_of(c) for c in nodes))
        if len(t) < 25:
            return
        inner = []
        for c in nodes:
            if isinstance(c, Node):
                links_in(c, inner)
        links.extend(l["href"] for l in inner)
        blocks.append({"i": len(blocks), "tag": "p", "text": t, "links": inner, "xem_them": bool(XEM_THEM.search(t))})

    def walk(n):
        if isinstance(n, str) or n.tag in SKIP_TAGS:
            return
        if SKIP_CLASS.search(cls(n)) and n.tag not in BLOCK_TAGS:
            return
        if n.tag in BLOCK_TAGS and has_block_inside(n):
            # HTML lỗi: <p> chưa đóng nuốt cả bài → không coi là 1 đoạn, đi tiếp vào trong;
            # phần chữ nằm trực tiếp trong nó (không thuộc khối con) gom thành các đoạn riêng
            direct = []
            for c in n.children:
                if isinstance(c, str) or (isinstance(c, Node) and c.tag not in BLOCK_TAGS and not has_block_inside(c)):
                    direct.append(c)
                else:
                    flush_direct(direct)
                    direct = []
                    walk(c)
            flush_direct(direct)
            return
        if n.tag in BLOCK_TAGS:
            t = norm(text_of(n))
            inner = []
            links_in(n, inner)
            links.extend(l["href"] for l in inner)
            if t and (n.tag.startswith("h") or len(t) >= 25 or (n.tag == "li" and inner)):
                # mục danh sách chỉ gồm đúng cái link (không có câu văn) = link liệt kê, không phải link trong ngữ cảnh
                chi_co_link = n.tag == "li" and bool(inner) and norm(" ".join(l["text"] for l in inner)) == t
                blocks.append({"i": len(blocks), "tag": n.tag, "text": t, "links": inner,
                               "xem_them": bool(XEM_THEM.search(t)) or chi_co_link})
            return
        if n.tag == "a" and n.attrs.get("href"):
            links.append(n.attrs["href"])
        for c in n.children:
            walk(c)

    walk(container)
    return blocks, links


def cmd_fetch(url, out):
    doc = build_doc(url)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    print(f"đã đọc '{doc['title']}' — {len(doc['blocks'])} khối, {len(doc['links'])} link → {out}")


def build_doc(url):
    html = fetch_html(url)
    p = P()
    p.feed(html)
    container = pick_container(p.root)
    blocks, links = extract_blocks(container)
    h1 = next((b["text"] for b in blocks if b["tag"] == "h1"), "")
    if not h1:
        # H1 hay nằm ngoài container
        allb, _ = extract_blocks(p.root)
        h1 = next((b["text"] for b in allb if b["tag"] == "h1"), "")
    return {"url": url, "title": norm(p.title), "h1": h1, "blocks": blocks, "links": sorted(set(links))}


# ---------- chấm điểm đoạn ----------

def strip_accents(s):
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


STOP = set("và là của có cho các những một được với trong khi để từ này đó về như không thì hay hoặc bạn mình nên rất cũng đã sẽ tại theo bị ở đến".split())


def tokens(s):
    s = strip_accents(s.lower())
    return [w for w in re.findall(r"[a-z0-9đ]+", s) if w not in STOP and len(w) > 1]


def score_block(b, key_tokens, anchor_tokens, phrases):
    t = strip_accents(b["text"].lower())
    tt = set(tokens(b["text"]))
    s = 0.0
    for ph in phrases:  # trùng nguyên cụm → điểm cao
        if ph and ph in t:
            s += 3
    s += 1.0 * len(tt & key_tokens) + 0.8 * len(tt & anchor_tokens)
    if b["tag"] != "p":
        s *= 0.6  # ưu tiên chèn sau đoạn văn, không phải tiêu đề/li
    return round(s, 2)


def same_url(a, b):
    f = lambda u: re.sub(r"^https?://(www\.)?", "", u.strip()).rstrip("/").split("#")[0].split("?")[0].lower()
    return f(a) == f(b)


KET_BAI = re.compile(r"^(trên đây|tóm lại|kết luận|như vậy|hy vọng|hi vọng|qua bài viết|bài viết trên)", re.I)
KHOANG_CACH = 3  # hai chỗ chèn trong cùng bài phải cách nhau ít nhất 3 đoạn


def scored_paras(blocks, key, anchor):
    """Trả về danh sách đoạn <p> kèm điểm hợp nghĩa với key/anchor (điểm riêng cho từng yêu cầu)."""
    key_t, anc_t = set(tokens(key)), set(tokens(anchor))
    phrases = {strip_accents(key.lower()), strip_accents(anchor.lower())}
    paras = [b for b in blocks if b["tag"] == "p"]
    out = []
    for pos, b in enumerate(paras):
        s = score_block(b, key_t, anc_t, phrases)
        if pos < 2 or pos >= len(paras) - 3:
            s *= 0.5  # mở bài / kết bài không phải chỗ chèn tốt
        if KET_BAI.search(b["text"]) or b.get("xem_them"):
            s *= 0.2
        out.append({"i": b["i"], "pos": pos, "score": round(s, 2)})
    return out


def make_candidate(blocks, n_para, c):
    def ctx(i):
        return blocks[i]["text"] if 0 <= i < len(blocks) else ""

    muc = "(mở bài)"
    for j in range(c["i"], -1, -1):
        if blocks[j]["tag"] in ("h2", "h3"):
            muc = blocks[j]["text"]
            break
    return {
        "i": c["i"], "score": c["score"],
        "vi_tri": f"đoạn {c['pos'] + 1}/{n_para}",
        "muc": muc,
        "truoc": ctx(c["i"] - 1)[:300],
        "doan": blocks[c["i"]]["text"],
        "sau": ctx(c["i"] + 1)[:300],
    }


def summarize(doc, yeu_cau):
    """yeu_cau = [{stt, key, anchor, url_dich}] — nhiều link vào cùng một bài.
    Chia chỗ: yêu cầu có đoạn hợp nhất được chọn trước, các yêu cầu sau phải cách chỗ đã lấy >= KHOANG_CACH đoạn."""
    blocks = doc["blocks"]
    n_para = sum(1 for b in blocks if b["tag"] == "p")
    full_text = strip_accents(" ".join(b["text"] for b in blocks).lower())
    for r in yeu_cau:
        r["_scored"] = scored_paras(blocks, r["key"], r["anchor"])
        r["_best"] = max((c["score"] for c in r["_scored"]), default=0)
    taken = []  # pos đã chiếm
    results = {}
    for r in sorted(yeu_cau, key=lambda r: -r["_best"]):  # yêu cầu chắc chắn nhất chọn trước
        ok = [c for c in r["_scored"] if all(abs(c["pos"] - t) >= KHOANG_CACH for t in taken)]
        cands = sorted(ok, key=lambda c: -c["score"])[:5]
        if cands:
            taken.append(cands[0]["pos"])
        results[r["stt"]] = {
            "stt": r["stt"], "key_muc_tieu": r["key"], "anchor": r["anchor"], "url_dich": r["url_dich"],
            # link tới đích nằm trong câu văn thật → đã có, bỏ qua; nằm ở dòng "Có thể bạn quan tâm/Xem thêm" → vẫn viết, ghi chú
            "da_co_link_toi_dich": any(not b["xem_them"] and any(same_url(l["href"], r["url_dich"]) for l in b["links"]) for b in blocks),
            "link_dang_liet_ke": [b["text"][:120] for b in blocks if b["xem_them"] and any(same_url(l["href"], r["url_dich"]) for l in b["links"])],
            "link_ngoai_than_bai": any(same_url(l, r["url_dich"]) for l in doc["links"]) and not any(any(same_url(l["href"], r["url_dich"]) for l in b["links"]) for b in blocks),
            "anchor_da_xuat_hien_trong_bai": strip_accents(r["anchor"].lower()) in full_text,
            "ung_vien": [make_candidate(blocks, n_para, c) for c in cands],
        }
    return {
        "url_bai": doc["url"], "title": doc["title"], "h1": doc["h1"],
        "so_doan": n_para, "so_tu": sum(len(b["text"].split()) for b in blocks),
        "dan_y": [f"{b['tag'].upper()}: {b['text']}" for b in blocks if b["tag"] in ("h2", "h3")],
        "so_link_can_chen": len(yeu_cau),
        "canh_bao": (f"{len(yeu_cau)} link vào bài {n_para} đoạn là dày — cân nhắc bớt" if len(yeu_cau) > max(2, n_para // 8) else ""),
        "yeu_cau": [results[r["stt"]] for r in yeu_cau],
    }


def report(summary, out):
    with open(out, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=1)
    print(f"'{summary['h1'] or summary['title']}' — {summary['so_doan']} đoạn, {summary['so_tu']} từ, "
          f"{summary['so_link_can_chen']} link cần chèn → {out}")
    for r in summary["yeu_cau"]:
        best = r["ung_vien"][0] if r["ung_vien"] else None
        print(f"  #{r['stt']} [{r['anchor']}] "
              + ("ĐÃ có link tới đích trong câu văn — bỏ qua" if r["da_co_link_toi_dich"]
                 else f"ứng viên tốt nhất: {best['vi_tri']} (điểm {best['score']})" if best else "không có ứng viên")
              + (f" | đang có link dạng liệt kê: {len(r['link_dang_liet_ke'])} chỗ" if r["link_dang_liet_ke"] else "")
              + (" | có link ở menu/bài liên quan (không tính)" if r["link_ngoai_than_bai"] else ""))
    if summary["canh_bao"]:
        print("  CẢNH BÁO: " + summary["canh_bao"])


def cmd_chuan_bi(url_bai, key, anchor, url_dich, out):
    doc = build_doc(url_bai)
    summary = summarize(doc, [{"stt": "1", "key": key, "anchor": anchor, "url_dich": url_dich}])
    # một yêu cầu thì đưa các trường lên cấp cao nhất cho dễ đọc
    summary.update({k: v for k, v in summary["yeu_cau"][0].items() if k != "stt"})
    report(summary, out)


def cmd_chuan_bi_nhieu(url_bai, yeu_cau_file, out):
    with open(yeu_cau_file, encoding="utf-8") as f:
        yeu_cau = json.load(f)
    for r in yeu_cau:
        r["stt"] = str(r.get("stt", ""))
    doc = build_doc(url_bai)
    report(summarize(doc, yeu_cau), out)


if __name__ == "__main__":
    a = sys.argv[1:]
    if len(a) == 3 and a[0] == "fetch":
        cmd_fetch(a[1], a[2])
    elif len(a) == 6 and a[0] == "chuan-bi":
        cmd_chuan_bi(*a[1:])
    elif len(a) == 4 and a[0] == "chuan-bi-nhieu":
        cmd_chuan_bi_nhieu(*a[1:])
    else:
        print(__doc__)
        sys.exit(1)
