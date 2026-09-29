#!/usr/bin/env python3
"""Tải và đọc bài viết trên web để tìm chỗ chèn internal link. Chỉ dùng thư viện chuẩn.

Lệnh:
  fetch    <url> <out.json>
      → {url, title, h1, blocks:[{i, tag, text}], links:[href...]}
  chuan-bi <url_bai> "<key mục tiêu>" "<anchor>" <url_dich> <out.json>
      → tải bài + chấm điểm từng đoạn theo độ gần nghĩa với key/anchor, in ra bản TÓM TẮT
        (tiêu đề, dàn ý H2/H3, 5 đoạn ứng viên kèm đoạn trước/sau, bài đã có link tới đích chưa)
        để Claude chỉ phải đọc đúng phần cần — tiết kiệm token.
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


def extract_blocks(container):
    blocks, links = [], []

    def walk(n):
        if isinstance(n, str) or n.tag in SKIP_TAGS:
            return
        if SKIP_CLASS.search(cls(n)) and n.tag not in BLOCK_TAGS:
            return
        if n.tag == "a" and n.attrs.get("href"):
            links.append(n.attrs["href"])
        if n.tag in BLOCK_TAGS:
            t = norm(text_of(n))
            if t and (n.tag.startswith("h") or len(t) >= 25):
                blocks.append({"i": len(blocks), "tag": n.tag, "text": t})
            # vẫn đi tiếp để gom link bên trong
            for c in n.children:
                if isinstance(c, Node):
                    collect_links(c)
            return
        for c in n.children:
            walk(c)

    def collect_links(n):
        if isinstance(n, str) or n.tag in SKIP_TAGS:
            return
        if n.tag == "a" and n.attrs.get("href"):
            links.append(n.attrs["href"])
        for c in n.children:
            collect_links(c)

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


def cmd_chuan_bi(url_bai, key, anchor, url_dich, out):
    doc = build_doc(url_bai)
    blocks = doc["blocks"]
    key_t, anc_t = set(tokens(key)), set(tokens(anchor))
    phrases = {strip_accents(key.lower()), strip_accents(anchor.lower())}
    for b in blocks:
        b["score"] = score_block(b, key_t, anc_t, phrases)
    paras = [b for b in blocks if b["tag"] == "p"]
    # mở bài (2 đoạn đầu) và kết bài (2 đoạn cuối) không phải chỗ chèn tốt → giảm nửa điểm
    ket_bai = re.compile(r"^(trên đây|tóm lại|kết luận|như vậy|hy vọng|hi vọng|qua bài viết|bài viết trên)", re.I)
    for pos, b in enumerate(paras):
        if pos < 2 or pos >= len(paras) - 3:
            b["score"] = round(b["score"] * 0.5, 2)
        if ket_bai.search(b["text"]):
            b["score"] = round(b["score"] * 0.2, 2)
    cands = sorted(paras, key=lambda b: -b["score"])[:5]

    def ctx(i):
        return blocks[i]["text"] if 0 <= i < len(blocks) else ""

    def heading_above(i):
        for j in range(i, -1, -1):
            if blocks[j]["tag"] in ("h2", "h3"):
                return blocks[j]["text"]
        return "(mở bài)"

    n_para = len(paras)
    candidates = []
    for b in cands:
        pos = paras.index(b)
        candidates.append({
            "i": b["i"], "score": b["score"],
            "vi_tri": f"đoạn {pos + 1}/{n_para}",
            "muc": heading_above(b["i"]),
            "truoc": ctx(b["i"] - 1)[:300],
            "doan": b["text"],
            "sau": ctx(b["i"] + 1)[:300],
        })
    da_co_link = any(same_url(l, url_dich) for l in doc["links"])
    anchor_da_dung = strip_accents(anchor.lower()) in strip_accents(" ".join(b["text"] for b in blocks).lower())
    summary = {
        "url_bai": url_bai, "title": doc["title"], "h1": doc["h1"],
        "so_doan": n_para, "so_tu": sum(len(b["text"].split()) for b in blocks),
        "dan_y": [f"{b['tag'].upper()}: {b['text']}" for b in blocks if b["tag"] in ("h2", "h3")],
        "da_co_link_toi_dich": da_co_link,
        "anchor_da_xuat_hien_trong_bai": anchor_da_dung,
        "key_muc_tieu": key, "anchor": anchor, "url_dich": url_dich,
        "ung_vien": candidates,
    }
    with open(out, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=1)
    print(f"'{doc['h1'] or doc['title']}' — {n_para} đoạn, {summary['so_tu']} từ; "
          f"{'ĐÃ có' if da_co_link else 'chưa có'} link tới đích; "
          f"ứng viên tốt nhất: điểm {cands[0]['score'] if cands else 0} → {out}")


if __name__ == "__main__":
    a = sys.argv[1:]
    if len(a) == 3 and a[0] == "fetch":
        cmd_fetch(a[1], a[2])
    elif len(a) == 6 and a[0] == "chuan-bi":
        cmd_chuan_bi(*a[1:])
    else:
        print(__doc__)
        sys.exit(1)
