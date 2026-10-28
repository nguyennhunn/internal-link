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
        Tải bài 1 lần; các chỗ chèn được chia sao cho cách nhau >= 3 đoạn, mỗi mục tối đa 1 chỗ.
  quet <nguon.json> <dich.json> <out.json> [thư-mục-lưu-bài]
      → quét NHIỀU bài nguồn × NHIỀU URL đích (dùng khi lên mô hình): bài nào đã có link tới đích trong CÂU VĂN,
        link chỉ ở dòng liệt kê, bài nguồn chuyển hướng (301) về chính bài đích, bài nguồn = bài đích.
        nguon.json = [{"rowIndex", "url"}], dich.json = [{"id", "anchor", "url"}]. Lưu bản tải từng bài nếu có thư mục.

Mỗi khối có `loai`: tieu_de | van (câu văn thường) | danh_sach | bang | thong_so (dòng "Nhãn: giá trị" ngắn,
khối sản phẩm) | y_dam (ý in đậm "Nhãn: câu dài" nối tiếp nhau) | dan_vao (câu kết thúc bằng ":") | cta (">>>",
"TẠI ĐÂY", "Mua ngay") | thuong_hieu (khối giới thiệu/kênh OSAKAR cuối bài); cờ `faq`, `ket` (vùng kết bài),
`liet_ke` (link nằm ở dòng liệt kê/xem thêm chứ không phải câu văn).
"""
import json
import os
import re
import sys
import unicodedata
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor
from html.parser import HTMLParser

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
SKIP_TAGS = {"script", "style", "noscript", "nav", "header", "footer", "aside", "form", "iframe", "svg", "template", "button"}
BLOCK_TAGS = {"h1", "h2", "h3", "h4", "p", "li", "blockquote"}
CONTENT_HINT = re.compile(r"entry-content|post-content|article-content|article-body|post-body|single-content|the-content|content-area|blog-content|td-post-content|elementor-widget-theme-post-content|toc-content-generation", re.I)
SKIP_CLASS = re.compile(r"comment|sidebar|related|breadcrumb|share|widget|menu|footer|header|toc(?!-content)|table-of-contents|author-box|tags", re.I)


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


class TaiLoi(Exception):
    pass


def fetch_html(url):
    """Trả về (html, url_that) — url_that khác url nếu trang chuyển hướng."""
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "vi,en;q=0.8"})
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            raw = r.read()
            ct = r.headers.get("Content-Type", "")
            final = r.geturl()
    except urllib.error.HTTPError as e:
        raise TaiLoi(f"{url} trả về HTTP {e.code}")
    except Exception as e:
        raise TaiLoi(f"không tải được {url}: {e}")
    m = re.search(r"charset=([\w-]+)", ct)
    enc = m.group(1) if m else "utf-8"
    try:
        return raw.decode(enc, errors="replace"), final
    except LookupError:
        return raw.decode("utf-8", errors="replace"), final


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


# Dòng liệt kê/điều hướng: MỞ ĐẦU bằng các cụm này (không phải chỉ chứa "tham khảo" ở giữa câu văn)
LIET_KE_DAU = re.compile(r"^\s*(>{2,}|»|→|có thể bạn quan tâm|xem thêm|đọc thêm|tham khảo thêm\s*[:\-–]|bài viết liên quan|chi tiết tham khảo|tìm hiểu thêm\s*[:\-–]|xem ngay)", re.I)


def la_liet_ke(tag, text, inner):
    """Link nằm ở dòng liệt kê (không phải câu văn): li chỉ có link; dòng mở đầu '>>> / Xem thêm…';
    hoặc dòng ngắn mà chữ link chiếm phần lớn."""
    if not inner:
        return False
    link_txt = norm(" ".join(l["text"] for l in inner))
    if tag == "li" and link_txt == text:
        return True
    if LIET_KE_DAU.search(text):
        return True
    n = len(text.split())
    return n <= 14 and len(link_txt.split()) >= 0.6 * n


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
        blocks.append({"i": len(blocks), "tag": "p", "text": t, "links": inner, "liet_ke": la_liet_ke("p", t, inner)})

    def walk(n):
        if isinstance(n, str) or n.tag in SKIP_TAGS:
            return
        if SKIP_CLASS.search(cls(n)) and n.tag not in BLOCK_TAGS:
            return
        if n.tag == "table":
            # bảng: ghi 1 khối để biết vị trí (chèn SAU bảng, không chèn giữa câu dẫn và bảng)
            t = norm(text_of(n))
            inner = []
            links_in(n, inner)
            links.extend(l["href"] for l in inner)
            if t:
                blocks.append({"i": len(blocks), "tag": "table", "text": "[bảng] " + t[:200], "links": inner, "liet_ke": False})
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
                blocks.append({"i": len(blocks), "tag": n.tag, "text": t, "links": inner,
                               "liet_ke": (not n.tag.startswith("h")) and la_liet_ke(n.tag, t, inner)})
            return
        if n.tag == "a" and n.attrs.get("href"):
            links.append(n.attrs["href"])
        for c in n.children:
            walk(c)

    walk(container)
    return blocks, links


def build_doc(url):
    html, final = fetch_html(url)
    p = P()
    p.feed(html)
    container = pick_container(p.root)
    blocks, links = extract_blocks(container)
    h1 = next((b["text"] for b in blocks if b["tag"] == "h1"), "")
    if not h1:
        # H1 hay nằm ngoài container
        allb, _ = extract_blocks(p.root)
        h1 = next((b["text"] for b in allb if b["tag"] == "h1"), "")
    gan_nhan(blocks)
    return {"url": url, "url_that": final, "chuyen_huong": not same_url(url, final),
            "title": norm(p.title), "h1": h1, "blocks": blocks, "links": sorted(set(links))}


# ---------- nhận diện cấu trúc bài ----------

LA_TIEU_DE = ("h1", "h2", "h3", "h4")
CTA = re.compile(r"^\s*(>{2,}|»|→)|tại đây|mua ngay|liên hệ ngay|gọi ngay|hotline|đặt mua|đăng ký lái thử", re.I)
THUONG_HIEU = re.compile(r"OSAKAR tự hào là thương hiệu|nhanh tay theo dõi|hệ thống cửa hàng|danh sách sản phẩm truy cập|"
                         r"^\s*(fanpage|youtube|tiktok|zalo)\b|theo dõi .{0,40}(kênh|fanpage)", re.I)
NHAN = re.compile(r"^[^.!?:]{2,45}:\s*\S")  # "Giá bán: …", "Ưu điểm: …"
FAQ_HD = re.compile(r"câu hỏi thường gặp|hỏi đáp|giải đáp|\bFAQ\b|thắc mắc thường gặp", re.I)
KET_HD = re.compile(r"kết luận|lời kết|tổng kết|tạm kết", re.I)
KET_BAI = re.compile(r"^(trên đây|tóm lại|kết luận|như vậy|hy vọng|hi vọng|qua bài viết|bài viết trên)", re.I)
DS_LOAI = ("danh_sach", "bang", "thong_so", "y_dam")  # khối dạng danh sách: không chèn chen giữa


def gan_nhan(blocks):
    n = len(blocks)
    for b in blocks:
        t = b["text"]
        if b["tag"] in LA_TIEU_DE:
            b["loai"] = "tieu_de"
        elif b["tag"] == "li":
            b["loai"] = "danh_sach"
        elif b["tag"] == "table":
            b["loai"] = "bang"
        elif THUONG_HIEU.search(t):
            b["loai"] = "thuong_hieu"
        elif CTA.search(t) and len(t.split()) <= 40:
            b["loai"] = "cta"
        elif t.rstrip().endswith(":"):
            b["loai"] = "dan_vao"
        elif NHAN.search(t):
            b["loai"] = "thong_so" if len(t.split()) <= 25 else "y_dam"
        else:
            b["loai"] = "van"
    # vùng FAQ: từ heading FAQ tới heading cùng cấp/cao hơn kế tiếp
    faq_lv = None
    for b in blocks:
        if b["loai"] == "tieu_de":
            lv = int(b["tag"][1])
            if faq_lv is not None and lv <= faq_lv:
                faq_lv = None
            if faq_lv is None and FAQ_HD.search(b["text"]):
                faq_lv = lv
                continue
        b["faq"] = faq_lv is not None
        b["cau_hoi"] = b["faq"] and (b["loai"] == "tieu_de" or b["text"].rstrip().endswith("?"))
    # vùng kết bài: từ heading "Kết luận/Lời kết", đoạn mở "Tóm lại/Trên đây…" ở 30% cuối, hoặc khối thương hiệu → hết bài
    ket_tu = n
    for b in blocks:
        if (b["loai"] == "tieu_de" and KET_HD.search(b["text"])) or b["loai"] == "thuong_hieu" \
                or (b["loai"] == "van" and KET_BAI.search(b["text"]) and b["i"] >= 0.7 * n):
            ket_tu = b["i"]
            break
    for b in blocks:
        b["ket"] = b["i"] >= ket_tu


def muc_cua(blocks, i):
    """Chỉ số heading H2/H3 chứa khối i (-1 = mở bài)."""
    for j in range(i, -1, -1):
        if blocks[j]["tag"] in ("h2", "h3"):
            return j
    return -1


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


KHOANG_CACH = 3  # hai chỗ chèn trong cùng bài phải cách nhau ít nhất 3 đoạn văn
NOI_BO = re.compile(r"^(https?://(www\.)?osakar\.com\.vn)?/", re.I)


def co_link_noi_bo(b):
    return any(NOI_BO.search(l["href"]) and "/san-pham" not in l["href"] for l in b.get("links", []))


def diem_chen(blocks, i):
    """Đoạn văn i có làm chỗ chèn được không. Chỗ chèn thật = sau khối `chen_sau` (bỏ qua danh sách/bảng/thông số
    đi liền sau đoạn), trước heading kế / dòng CTA / câu hỏi FAQ kế. Trả về (nhãn, chen_sau, ghi_chu) hoặc None."""
    b = blocks[i]
    if b["loai"] != "van" or b["ket"] or b.get("liet_ke"):
        return None
    if b["faq"] and b["cau_hoi"]:
        return None
    j = i + 1
    while j < len(blocks) and blocks[j]["loai"] in DS_LOAI:
        j += 1
    run = blocks[i + 1:j]
    chen_sau, gc = j - 1, ""
    # danh sách "Xem thêm"/bài liên quan ở cuối mục → chèn TRƯỚC danh sách đó, không chèn sau
    k_lk = next((k for k, x in enumerate(run) if x.get("liet_ke")), None)
    if k_lk is not None:
        chen_sau = i + k_lk
        gc = f"chèn TRƯỚC dòng liệt kê \"{run[k_lk]['text'][:60]}\""
    so_thong_so = sum(1 for x in run[:chen_sau - i] if x["loai"] == "thong_so")
    if j >= len(blocks) or blocks[j]["loai"] == "tieu_de":
        nhan = "cuối mục"
        if j < len(blocks) and blocks[j]["ket"]:
            nhan = "cuối mục (mục kế là Kết bài)"
        if b["faq"]:
            nhan = "sau câu trả lời FAQ"
    elif blocks[j]["loai"] in ("cta", "thuong_hieu"):
        nhan = "cuối mục (trước dòng CTA/khối OSAKAR)"
        gc = gc or f"chèn TRƯỚC dòng \"{blocks[j]['text'][:60]}\""
    elif b["faq"] and blocks[j].get("cau_hoi"):
        nhan = "sau câu trả lời FAQ"
    else:
        return None  # còn câu văn của cùng mục phía sau → giữa mục, không dùng
    if so_thong_so >= 2:
        nhan = "sau khối thông số sản phẩm — tránh"  # toplist: chèn giữa các mẫu, người rà đánh "sai chỗ"
    return nhan, chen_sau, gc


def scored_paras(blocks, key, anchor):
    """Các đoạn văn làm chỗ chèn được, kèm điểm gần nghĩa với key/anchor."""
    key_t, anc_t = set(tokens(key)), set(tokens(anchor))
    phrases = {strip_accents(key.lower()), strip_accents(anchor.lower())}
    paras = [b for b in blocks if b["loai"] == "van"]
    pos_of = {b["i"]: k for k, b in enumerate(paras)}
    out = []
    for b in paras:
        pos = pos_of[b["i"]]
        if pos < 2:
            continue  # mở bài
        d = diem_chen(blocks, b["i"])
        if not d:
            continue
        nhan, chen_sau, gc = d
        s = score_block(b, key_t, anc_t, phrases)
        if blocks[b["i"] - 1]["loai"] == "tieu_de" and chen_sau == b["i"]:
            s *= 0.8  # mục chỉ có 1 đoạn — vẫn được, nhưng kém mục dài
        sat = co_link_noi_bo(blocks[chen_sau]) or (chen_sau + 1 < len(blocks) and co_link_noi_bo(blocks[chen_sau + 1]))
        if sat:
            s *= 0.7
        if nhan.startswith("sau câu trả lời FAQ"):
            s *= 0.8
        if nhan.endswith("tránh"):
            s *= 0.3
        out.append({"i": b["i"], "pos": pos, "score": round(s, 2), "nhan": nhan, "chen_sau": chen_sau,
                    "muc": muc_cua(blocks, b["i"]), "sat_link": sat, "gc": gc})
    return out


def make_candidate(blocks, n_para, c):
    def ctx(i):
        return blocks[i]["text"] if 0 <= i < len(blocks) else ""
    m = c["muc"]
    return {
        "i": c["i"], "score": c["score"],
        "vi_tri": f"đoạn {c['pos'] + 1}/{n_para} — {c['nhan']}",
        "chen_sau": blocks[c["chen_sau"]]["text"][:120],
        "chen_sau_i": c["chen_sau"],
        "khoi_cuoi_la_danh_sach": c["chen_sau"] != c["i"],
        "muc": blocks[m]["text"] if m >= 0 else "(mở bài)",
        "ke_tiep": ctx(c["chen_sau"] + 1)[:120],
        "sat_link_noi_bo": c["sat_link"],
        "ghi_chu_vi_tri": c["gc"],
        "truoc": ctx(c["i"] - 1)[:300],
        "doan": blocks[c["i"]]["text"],
        "sau": ctx(c["i"] + 1)[:300],
    }


def link_toi(blocks, url):
    """(có link trong câu văn, [dòng liệt kê có link])"""
    cau, lk = [], []
    for b in blocks:
        if any(same_url(l["href"], url) for l in b["links"]):
            (lk if b.get("liet_ke") else cau).append(b["text"][:120])
    return cau, lk


def summarize(doc, yeu_cau):
    """yeu_cau = [{stt, key, anchor, url_dich}] — nhiều link vào cùng một bài.
    Chia chỗ: yêu cầu có đoạn hợp nhất chọn trước; chỗ sau phải cách >= KHOANG_CACH đoạn văn và KHÁC mục."""
    blocks = doc["blocks"]
    n_para = sum(1 for b in blocks if b["loai"] == "van")
    full_text = strip_accents(" ".join(b["text"] for b in blocks).lower())
    tu_tro_ve = doc.get("url_that", doc["url"])
    for r in yeu_cau:
        r["_scored"] = scored_paras(blocks, r["key"], r["anchor"])
        r["_best"] = max((c["score"] for c in r["_scored"]), default=0)
    taken, taken_muc, results = [], set(), {}
    taken_muc_moi, taken_muc_cung_url = set(), {}  # cho_chung_muc: chỉ cấm mục có link CÙNG URL + mục của link mới
    # Chèn THÊM vào bài đã có link (vd anchor thứ 2 cho cùng URL): coi các đoạn đang có link tới các URL đích
    # và các mục trong `tranh_muc` (vị trí đoạn cũ chưa dán lên web) là chỗ đã chiếm → link mới cách xa, khác mục.
    para_pos = {b["i"]: k for k, b in enumerate([x for x in blocks if x["loai"] == "van"])}
    for r in yeu_cau:
        if not r.get("bo_qua_link_san"):
            continue
        urls = [y["url_dich"] for y in yeu_cau] + list(r.get("tranh_url", []))
        for b in blocks:
            if any(any(same_url(l["href"], u) for l in b["links"]) for u in urls) and not b.get("liet_ke"):
                taken_muc.add(muc_cua(blocks, b["i"]))
                for y in yeu_cau:
                    if any(same_url(l["href"], y["url_dich"]) for l in b["links"]):
                        taken_muc_cung_url.setdefault(y["url_dich"], set()).add(muc_cua(blocks, b["i"]))
                j = b["i"]
                while j >= 0 and j not in para_pos:
                    j -= 1
                if j >= 0:
                    taken.append(para_pos[j])
        for ten in r.get("tranh_muc", []):
            for b in blocks:
                if b["loai"] == "tieu_de" and ten and (ten.lower() in b["text"].lower() or b["text"].lower() in ten.lower()):
                    taken_muc.add(b["i"])
    for r in sorted(yeu_cau, key=lambda r: -r["_best"]):
        kc = int(r.get("khoang_cach", KHOANG_CACH))
        tm = taken_muc_cung_url.get(r["url_dich"], set()) | taken_muc_moi if r.get("cho_chung_muc") else taken_muc
        ok = [c for c in r["_scored"] if all(abs(c["pos"] - t) >= kc for t in taken) and c["muc"] not in tm]
        cands = sorted(ok, key=lambda c: -c["score"])[:5]
        if cands:
            taken.append(cands[0]["pos"]); taken_muc.add(cands[0]["muc"]); taken_muc_moi.add(cands[0]["muc"])
        cau, lk = link_toi(blocks, r["url_dich"])
        tu_tro = same_url(doc["url"], r["url_dich"]) or same_url(tu_tro_ve, r["url_dich"])
        results[r["stt"]] = {
            "stt": r["stt"], "key_muc_tieu": r["key"], "anchor": r["anchor"], "url_dich": r["url_dich"],
            # link tới đích trong CÂU VĂN thật, hoặc bài nguồn chính là/chuyển hướng về bài đích → không chèn
            "da_co_link_toi_dich": (bool(cau) and not r.get("bo_qua_link_san")) or tu_tro,
            "cau_da_co_link": cau[:3],
            "bai_nguon_la_bai_dich": tu_tro,
            "link_dang_liet_ke": lk,
            "link_ngoai_than_bai": any(same_url(l, r["url_dich"]) for l in doc["links"]) and not cau and not lk,
            "anchor_da_xuat_hien_trong_bai": strip_accents(r["anchor"].lower()) in full_text,
            "ung_vien": [make_candidate(blocks, n_para, c) for c in cands],
        }
    return {
        "url_bai": doc["url"], "url_that": tu_tro_ve, "chuyen_huong": doc.get("chuyen_huong", False),
        "title": doc["title"], "h1": doc["h1"],
        "so_doan": n_para, "so_tu": sum(len(b["text"].split()) for b in blocks),
        "dan_y": [f"{b['tag'].upper()}: {b['text']}" for b in blocks if b["tag"] in ("h2", "h3")],
        "so_link_can_chen": len(yeu_cau),
        "canh_bao": (f"{len(yeu_cau)} link vào bài {n_para} đoạn là dày — cân nhắc bớt" if len(yeu_cau) > max(2, n_para // 8) else ""),
        "yeu_cau": [results[r["stt"]] for r in yeu_cau],
    }


def report(summary, out):
    with open(out, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=1)
    print(f"'{summary['h1'] or summary['title']}' — {summary['so_doan']} đoạn văn, {summary['so_tu']} từ, "
          f"{summary['so_link_can_chen']} link cần chèn → {out}")
    if summary.get("chuyen_huong"):
        print(f"  CHÚ Ý: bài nguồn chuyển hướng sang {summary['url_that']}")
    for r in summary["yeu_cau"]:
        best = r["ung_vien"][0] if r["ung_vien"] else None
        if r["bai_nguon_la_bai_dich"]:
            st = "BÀI NGUỒN LÀ / CHUYỂN HƯỚNG VỀ BÀI ĐÍCH — không chèn (tự trỏ)"
        elif r["da_co_link_toi_dich"]:
            st = "ĐÃ có link tới đích trong câu văn — bỏ qua"
        elif best:
            st = f"ứng viên tốt nhất: {best['vi_tri']} (điểm {best['score']})" + (" | sát link nội bộ khác" if best["sat_link_noi_bo"] else "")
        else:
            st = "KHÔNG có chỗ cuối mục hợp lệ (bài toàn danh sách/FAQ/kết bài hoặc mục đã dùng hết)"
        print(f"  #{r['stt']} [{r['anchor']}] " + st
              + (f" | đang có link dạng liệt kê: {len(r['link_dang_liet_ke'])} chỗ" if r["link_dang_liet_ke"] else "")
              + (" | có link ở menu/bài liên quan (không tính)" if r["link_ngoai_than_bai"] else ""))
    if summary["canh_bao"]:
        print("  CẢNH BÁO: " + summary["canh_bao"])


def tai(url):
    try:
        return build_doc(url)
    except TaiLoi as e:
        sys.exit("LỖI: " + str(e))


def cmd_fetch(url, out):
    doc = tai(url)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    print(f"đã đọc '{doc['title']}' — {len(doc['blocks'])} khối, {len(doc['links'])} link → {out}"
          + (f" | chuyển hướng sang {doc['url_that']}" if doc["chuyen_huong"] else ""))


def cmd_chuan_bi(url_bai, key, anchor, url_dich, out):
    doc = tai(url_bai)
    summary = summarize(doc, [{"stt": "1", "key": key, "anchor": anchor, "url_dich": url_dich}])
    # một yêu cầu thì đưa các trường lên cấp cao nhất cho dễ đọc
    summary.update({k: v for k, v in summary["yeu_cau"][0].items() if k != "stt"})
    report(summary, out)


def cmd_chuan_bi_nhieu(url_bai, yeu_cau_file, out):
    with open(yeu_cau_file, encoding="utf-8") as f:
        yeu_cau = json.load(f)
    for r in yeu_cau:
        r["stt"] = str(r.get("stt", ""))
    doc = tai(url_bai)
    report(summarize(doc, yeu_cau), out)


def cmd_quet(nguon_file, dich_file, out, luu=None):
    """Quét n bài nguồn × m URL đích: trạng thái từng cặp = tu_tro | co_link (câu văn) | liet_ke | chua."""
    nguon = json.load(open(nguon_file, encoding="utf-8"))
    dich = json.load(open(dich_file, encoding="utf-8"))
    if luu:
        os.makedirs(luu, exist_ok=True)

    def mot(s):
        try:
            doc = build_doc(s["url"])
        except TaiLoi as e:
            return s, None, str(e)
        if luu:
            with open(os.path.join(luu, f"{s['rowIndex']}.json"), "w", encoding="utf-8") as f:
                json.dump(doc, f, ensure_ascii=False, indent=1)
        return s, doc, ""

    with ThreadPoolExecutor(8) as ex:
        res = list(ex.map(mot, nguon))
    kq, loi = {}, []
    for s, doc, err in res:
        if err:
            loi.append({"rowIndex": s["rowIndex"], "url": s["url"], "loi": err}); continue
        d = {}
        for t in dich:
            cau, lk = link_toi(doc["blocks"], t["url"])
            if same_url(s["url"], t["url"]) or same_url(doc["url_that"], t["url"]):
                d[t["id"]] = {"trang_thai": "tu_tro"}
            elif cau:
                d[t["id"]] = {"trang_thai": "co_link", "cau": cau[0]}
            elif lk:
                d[t["id"]] = {"trang_thai": "liet_ke", "dong": lk}
            else:
                d[t["id"]] = {"trang_thai": "chua"}
        kq[str(s["rowIndex"])] = {"url": s["url"], "url_that": doc["url_that"], "chuyen_huong": doc["chuyen_huong"],
                                  "so_doan": sum(1 for b in doc["blocks"] if b["loai"] == "van"), "dich": d}
    with open(out, "w", encoding="utf-8") as f:
        json.dump({"bai": kq, "loi": loi}, f, ensure_ascii=False, indent=1)
    from collections import Counter
    c = Counter(v["trang_thai"] for b in kq.values() for v in b["dich"].values())
    ch = [k for k, b in kq.items() if b["chuyen_huong"]]
    print(f"quét {len(kq)}/{len(nguon)} bài × {len(dich)} đích → {out} | "
          f"có link trong câu văn {c['co_link']}, chỉ ở dòng liệt kê {c['liet_ke']}, tự trỏ {c['tu_tro']}, chưa có {c['chua']}"
          + (f" | bài chuyển hướng: {ch}" if ch else "") + (f" | LỖI tải {len(loi)} bài" if loi else ""))


if __name__ == "__main__":
    a = sys.argv[1:]
    if len(a) == 3 and a[0] == "fetch":
        cmd_fetch(a[1], a[2])
    elif len(a) == 6 and a[0] == "chuan-bi":
        cmd_chuan_bi(*a[1:])
    elif len(a) == 4 and a[0] == "chuan-bi-nhieu":
        cmd_chuan_bi_nhieu(*a[1:])
    elif len(a) in (4, 5) and a[0] == "quet":
        cmd_quet(*a[1:])
    else:
        print(__doc__)
        sys.exit(1)
