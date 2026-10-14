#!/usr/bin/env python3
"""Xuất trang HTML để duyệt các đoạn internal link đã viết.

  python xuat_duyet.py <ket-qua.json> <out.html> ["Tên dự án"]

<ket-qua.json> = [{"stt","key","url_dich","anchor","bai","bai_tieu_de","muc","truoc","doan_html","vi_tri","ghi_chu","trang_thai"}, ...]
Trang có nút "Sao chép HTML" từng đoạn, mở bằng trình duyệt, không cần mạng (font Google tải nếu có mạng).
"""
import base64
import html
import json
import os
import re
import sys
from datetime import date

sys.stdout.reconfigure(encoding="utf-8")

LOGO = os.path.join(os.path.dirname(__file__), "..", "assets", "logo.png")


def esc(s):
    return html.escape(str(s or ""))


def main(inp, out, ten="Dự án"):
    with open(inp, encoding="utf-8") as f:
        items = json.load(f)
    logo = ""
    if os.path.exists(LOGO):
        with open(LOGO, "rb") as f:
            logo = "data:image/png;base64," + base64.b64encode(f.read()).decode()
    # các đoạn cùng một bài đứng cạnh nhau, theo thứ tự xuất hiện trong bài (vi_tri "đoạn 8/82")
    def order(i):
        if i.get("thu_tu") is not None:
            return (i.get("bai") or "", int(i["thu_tu"]))
        m = re.search(r"đoạn (\d+)", i.get("vi_tri") or "")
        return (i.get("bai") or "", int(m.group(1)) if m else 10**6)
    items.sort(key=order)
    n_ok = sum(1 for i in items if (i.get("trang_thai") or "Đã viết") == "Đã viết")
    cards = []
    for i in items:
        tt = i.get("trang_thai") or "Đã viết"
        bo = tt == "Bỏ qua"
        cards.append(f"""
<article class="card{' skip' if bo else ''}">
  <header>
    <span class="stt">#{esc(i.get('stt'))}</span>
    <div>
      <div class="key">{esc(i.get('key'))}</div>
      <div class="meta">Chèn vào: <a href="{esc(i.get('bai'))}" target="_blank">{esc(i.get('bai_tieu_de') or i.get('bai'))}</a>
      &nbsp;→&nbsp; Đích: <a href="{esc(i.get('url_dich'))}" target="_blank">{esc(i.get('url_dich'))}</a></div>
    </div>
    <span class="badge">{esc(tt)}</span>
  </header>
  {f'<p class="note">⚠ {esc(i.get("ghi_chu"))}</p>' if i.get('ghi_chu') else ''}
  {'' if bo else f'''
  <div class="ctx">
    <div class="lbl">Vị trí: {esc(i.get('vi_tri'))}{(' · Mục: ' + esc(i.get('muc'))) if i.get('muc') else ''}</div>
    <p class="before">{esc(i.get('doan'))}</p>
    <div class="insert">{i.get('doan_html') or ''}</div>
    <p class="after">{esc(i.get('sau'))}</p>
  </div>
  <div class="tools">
    <button onclick="copyText(this)" data-t="{esc(i.get('doan_html'))}">Sao chép HTML</button>
    <button class="sec" onclick="copyPlain(this)" data-t="{esc(i.get('doan_html'))}">Sao chép chữ thường</button>
    <span class="anchor">Anchor: <b>{esc(i.get('anchor'))}</b></span>
  </div>'''}
</article>""")

    page = f"""<!doctype html>
<html lang="vi"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Duyệt internal link — {esc(ten)}</title>
<link href="https://fonts.googleapis.com/css2?family=Be+Vietnam+Pro:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
:root{{--xanh:#004AEF;--mint:#07EF9C;--den:#151515;--xam:#F3F3F6;--nen:#fff}}
*{{box-sizing:border-box}}body{{margin:0;font-family:'Be Vietnam Pro',system-ui,sans-serif;color:var(--den);background:var(--xam);line-height:1.6}}
.top{{background:linear-gradient(135deg,#042CB2,#0175DA);color:#fff;padding:28px 16px}}
.wrap{{max-width:960px;margin:0 auto}}
.top img{{height:28px;margin-bottom:14px}}.top h1{{margin:0;font-size:22px;font-weight:700}}.top p{{margin:6px 0 0;opacity:.85}}
.top b{{color:var(--mint)}}
main{{padding:20px 16px 60px}}
.card{{background:var(--nen);border-radius:16px;padding:18px 20px;margin-bottom:16px;box-shadow:0 1px 3px rgba(0,0,0,.06)}}
.card.skip{{opacity:.6}}
.card header{{display:flex;gap:14px;align-items:flex-start;flex-wrap:wrap}}
.card header>div{{flex:1 1 240px;min-width:0}}
.stt{{background:var(--xanh);color:#fff;border-radius:9999px;padding:2px 12px;font-weight:600;font-size:14px;white-space:nowrap}}
.key{{font-weight:600;font-size:17px}}.meta{{font-size:13px;color:#555;word-break:break-all}}.meta a{{color:var(--xanh)}}
.badge{{margin-left:auto;background:var(--xam);border-radius:9999px;padding:2px 12px;font-size:13px;white-space:nowrap}}
.note{{background:#FFF8E1;border-radius:8px;padding:8px 12px;font-size:14px;margin:12px 0 0}}
.ctx{{margin-top:14px;border-left:3px solid #ddd;padding-left:14px}}
.lbl{{font-size:12px;color:#777;margin-bottom:8px;text-transform:uppercase;letter-spacing:.04em}}
.before,.after{{color:#666;font-size:14px;margin:0}}
.insert{{margin:10px 0;padding:12px 14px;background:#F0FCFF;border:1.5px dashed var(--xanh);border-radius:10px;font-size:15px}}
.insert p{{margin:0}}.insert a{{color:var(--xanh);font-weight:600}}
.tools{{display:flex;gap:10px;align-items:center;margin-top:14px;flex-wrap:wrap}}
button{{font:inherit;font-weight:600;font-size:14px;border:0;border-radius:9999px;padding:8px 18px;background:var(--xanh);color:#fff;cursor:pointer}}
button.sec{{background:var(--xam);color:var(--den)}}button:active{{transform:scale(.97)}}
.anchor{{font-size:13px;color:#555;margin-left:auto}}
.copied{{background:var(--mint)!important;color:var(--den)!important}}
</style></head><body>
<div class="top"><div class="wrap">{f'<img src="{logo}" alt="SEONGON">' if logo else ''}
<h1>Duyệt internal link — {esc(ten)}</h1>
<p>Ngày {date.today().strftime('%d/%m/%Y')} · <b>{n_ok}</b> đoạn chờ duyệt · {len(items) - n_ok} dòng bỏ qua. Đoạn trong khung xanh là phần cần dán vào bài, ngay dưới đoạn màu xám phía trên nó.</p>
</div></div>
<main><div class="wrap">{''.join(cards)}</div></main>
<script>
function flash(b){{const t=b.textContent;b.classList.add('copied');b.textContent='Đã sao chép ✓';setTimeout(()=>{{b.classList.remove('copied');b.textContent=t}},1500)}}
function copyText(b){{navigator.clipboard.writeText(b.dataset.t).then(()=>flash(b))}}
function copyPlain(b){{const d=document.createElement('div');d.innerHTML=b.dataset.t;navigator.clipboard.writeText(d.textContent).then(()=>flash(b))}}
</script></body></html>"""
    with open(out, "w", encoding="utf-8") as f:
        f.write(page)
    print(f"đã xuất {len(items)} dòng ({n_ok} chờ duyệt) → {out}")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    main(*sys.argv[1:4])
