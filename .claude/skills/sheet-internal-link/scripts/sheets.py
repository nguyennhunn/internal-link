#!/usr/bin/env python3
"""Đọc/ghi Google Sheet cho agent internal-link. Chỉ dùng thư viện chuẩn của Python.

Lệnh:
  set-client  <accounts.json> <key> <client_id> <client_secret> <spreadsheet_id>
  oauth       <accounts.json> <key> [port]           # lần đầu: mở trình duyệt, lưu refresh_token
  tabs        <accounts.json> <key>                  # liệt kê tên tab thật
  read        <accounts.json> <key> <tab> <out.json> # tự tìm dòng tiêu đề; header (kèm chữ cột, cột ô tick) + rows
  read-public <spreadsheet_id> <gid> <out.json>      # sheet chia sẻ công khai, KHÔNG cần OAuth, chỉ đọc
  write-rows  <accounts.json> <key> <tab> <changes.json> [--thu]
      # CÁCH GHI CHÍNH. changes.json = [{"rowIndex":5, "expect":{"Bài cần chèn":"https://..."},
      #   "set":{"Đoạn cần chèn":"<p>…</p>", "Anchor text 1":{"text":"…","link":"https://…"}, "URL đích 3":""}}]
      # Tìm cột theo TÊN header; sao lưu ô cũ vào .tmp/sao-luu/; bỏ qua hàng mà `expect` không khớp
      # (sheet bị sửa/chèn dòng trong lúc agent chạy); KHÔNG ghi chữ vào cột ô tick. --thu = chỉ in, không ghi.
  restore     <accounts.json> <key> <backup.json>    # trả lại các ô đã ghi từ file sao lưu của write-rows
  update-cell <accounts.json> <key> <tab> <A1> <value>   # ghi 1 ô theo địa chỉ — chỉ dùng khi thật cần
  append-rows <accounts.json> <key> <tab> <rows.json>   # rows.json = [["a","b"],...]
  insert-column <accounts.json> <key> <tab> <sau-cột> "<tiêu đề>"  # chèn 1 cột mới sau cột chữ cái đã cho

Dòng tiêu đề = dòng đầu tiên (trong 10 dòng đầu) có ô "Bài cần chèn" — người dùng có thể chèn dòng ghi chú phía trên.
Mọi lệnh tự refresh access_token bằng refresh_token đã lưu.
"""
import json
import sys
import time
import urllib.parse
import urllib.request
import urllib.error
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

SCOPE = "https://www.googleapis.com/auth/spreadsheets"
API = "https://sheets.googleapis.com/v4/spreadsheets"


def die(msg):
    print("LỖI: " + msg, file=sys.stderr)
    sys.exit(1)


def load(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def save(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def http(method, url, headers=None, data=None, form=False):
    body = None
    headers = dict(headers or {})
    if data is not None:
        if form:
            body = urllib.parse.urlencode(data).encode()
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        else:
            body = json.dumps(data, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, json.loads(r.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode("utf-8"))
        except Exception:
            return e.code, {"error": str(e)}


def token(path, key):
    acc = load(path)
    a = acc.get(key)
    if not a:
        die(f"chưa có cấu hình '{key}' trong {path} — chạy set-client rồi oauth trước")
    if not a.get("refresh_token"):
        die(f"'{key}' chưa có refresh_token — chạy: python sheets.py oauth {path} {key}")
    # access_token sống ~1h; refresh nếu đã quá 50 phút hoặc chưa có
    if a.get("access_token") and time.time() - a.get("obtained_at", 0) < 50 * 60:
        return a["access_token"], a["spreadsheet_id"]
    st, r = http("POST", "https://oauth2.googleapis.com/token", data={
        "client_id": a["client_id"], "client_secret": a["client_secret"],
        "refresh_token": a["refresh_token"], "grant_type": "refresh_token"}, form=True)
    if st != 200 or "access_token" not in r:
        die(f"refresh token thất bại ({st}): {r} — có thể phải chạy lại oauth")
    a["access_token"] = r["access_token"]
    a["obtained_at"] = time.time()
    save(path, acc)
    return a["access_token"], a["spreadsheet_id"]


def auth_headers(tok):
    return {"Authorization": "Bearer " + tok}


def a1_tab(tab):
    if all(c.isalnum() or c == "_" for c in tab):
        return tab
    return "'" + tab.replace("'", "''") + "'"


# ---------- lệnh ----------

def cmd_set_client(path, key, cid, secret, sid):
    acc = load(path)
    acc.setdefault(key, {}).update({"client_id": cid, "client_secret": secret, "spreadsheet_id": sid})
    save(path, acc)
    print(f"đã lưu client cho '{key}'")


def cmd_oauth(path, key, port="8771"):
    acc = load(path)
    a = acc.get(key) or die(f"chưa có '{key}' — chạy set-client trước")
    port = int(port)
    redirect = f"http://127.0.0.1:{port}"
    url = "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode({
        "client_id": a["client_id"], "redirect_uri": redirect, "response_type": "code",
        "scope": SCOPE, "access_type": "offline", "prompt": "consent"})
    got = {}

    class H(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def do_GET(self):
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            got["code"] = q.get("code", [None])[0]
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write("<h2>Xong! Quay lại Claude Code được rồi.</h2>".encode("utf-8"))

    srv = HTTPServer(("127.0.0.1", port), H)
    print("Mở trình duyệt để cho phép truy cập Google Sheet. Nếu không tự mở, dán link này:\n" + url)
    webbrowser.open(url)
    srv.timeout = 300
    while "code" not in got:
        srv.handle_request()
    if not got["code"]:
        die("Google không trả về code (bạn bấm Từ chối?)")
    st, r = http("POST", "https://oauth2.googleapis.com/token", data={
        "client_id": a["client_id"], "client_secret": a["client_secret"], "code": got["code"],
        "grant_type": "authorization_code", "redirect_uri": redirect}, form=True)
    if st != 200 or "refresh_token" not in r:
        die(f"đổi code lấy token thất bại ({st}): {r}")
    a.update({"access_token": r["access_token"], "refresh_token": r["refresh_token"], "obtained_at": time.time()})
    save(path, acc)
    print(f"đã lưu refresh_token cho '{key}' — từ giờ chạy không cần đăng nhập lại")


def cmd_tabs(path, key):
    tok, sid = token(path, key)
    st, r = http("GET", f"{API}/{sid}?fields=sheets.properties(sheetId,title)", auth_headers(tok))
    if st != 200:
        die(f"{st}: {r}")
    for s in r.get("sheets", []):
        print(s["properties"]["title"])


def cell_text(c):
    return (c or {}).get("formattedValue", "") or ""


HEADER_MOC = "Bài cần chèn"  # ô dùng để nhận ra dòng tiêu đề


def col_letter(idx):
    s, n = "", idx + 1
    while n:
        n, rem = divmod(n - 1, 26)
        s = chr(65 + rem) + s
    return s


def find_header_row(rows_text):
    """rows_text = list các dòng (list chữ). Trả về chỉ số 0-based của dòng tiêu đề."""
    for k, row in enumerate(rows_text[:10]):
        if any(t.strip() == HEADER_MOC for t in row):
            return k
    return 0


def load_grid(tok, sid, tab):
    fields = "sheets(properties(title,sheetId),data(rowData(values(formattedValue,hyperlink,userEnteredValue,dataValidation.condition.type))))"
    url = f"{API}/{sid}?" + urllib.parse.urlencode({"ranges": a1_tab(tab), "fields": fields})
    st, r = http("GET", url, auth_headers(tok))
    if st != 200:
        die(f"đọc sheet thất bại {st}: {r.get('error', r)}")
    sheet = (r.get("sheets") or [{}])[0]
    rows_raw = ((sheet.get("data") or [{}])[0]).get("rowData") or []
    if not rows_raw:
        die("tab trống hoặc sai tên tab — chạy `tabs` để xem tên thật")
    return sheet.get("properties", {}), rows_raw


def parse_grid(rows_raw):
    texts = [[cell_text(c) for c in rr.get("values", [])] for rr in rows_raw]
    h = find_header_row(texts)
    hdr = rows_raw[h].get("values", [])
    headers = [{"index": i, "cot": col_letter(i), "text": cell_text(c).strip()} for i, c in enumerate(hdr)]
    # cột ô tick: phần lớn ô dữ liệu có kiểm tra dữ liệu kiểu BOOLEAN → không bao giờ ghi chữ vào
    for hd in headers:
        n_tick = n_all = 0
        for rr in rows_raw[h + 1:h + 41]:
            cells = rr.get("values", [])
            c = cells[hd["index"]] if hd["index"] < len(cells) else {}
            if c:
                n_all += 1
                n_tick += (c.get("dataValidation", {}).get("condition", {}).get("type") == "BOOLEAN")
        hd["o_tick"] = n_all > 0 and n_tick * 2 >= n_all
    rows = []
    for k, rr in enumerate(rows_raw[h + 1:], start=h + 2):
        cells = rr.get("values", [])
        vals, links = {}, {}
        for hd in headers:
            if not hd["text"]:
                continue
            c = cells[hd["index"]] if hd["index"] < len(cells) else None
            vals[hd["text"]] = cell_text(c).strip()
            if c and c.get("hyperlink"):
                links[hd["text"]] = c["hyperlink"]
        if any(v for kk, v in vals.items() if not next(x for x in headers if x["text"] == kk)["o_tick"]):
            rows.append({"rowIndex": k, "values": vals, "hyperlinks": links})
    return h + 1, headers, rows


def cmd_read(path, key, tab, out):
    tok, sid = token(path, key)
    props, rows_raw = load_grid(tok, sid, tab)
    header_row, headers, rows = parse_grid(rows_raw)
    save(out, {"tab": props.get("title", tab), "header_row": header_row, "headers": headers, "rows": rows})
    tick = [h["text"] for h in headers if h["o_tick"]]
    print(f"đã đọc tab '{tab}': tiêu đề ở dòng {header_row}, {len(headers)} cột, {len(rows)} dòng → {out}"
          + (f" | cột ô tick (không ghi chữ): {', '.join(tick)}" if tick else ""))


def cmd_write_rows(path, key, tab, changes_file, *flags):
    """Ghi theo TÊN cột, có kiểm `expect`, sao lưu, không ghi chữ vào cột ô tick."""
    thu = "--thu" in flags
    with open(changes_file, encoding="utf-8") as f:
        changes = json.load(f)
    tok, sid = token(path, key)
    props, rows_raw = load_grid(tok, sid, tab)
    header_row, headers, _ = parse_grid(rows_raw)
    by_name = {h["text"]: h for h in headers if h["text"]}

    def cur(row_idx, col_idx):
        k = row_idx - 1
        cells = rows_raw[k].get("values", []) if k < len(rows_raw) else []
        return cells[col_idx] if col_idx < len(cells) else {}

    reqs, backup, skipped, n_cells = [], [], [], 0
    for ch in changes:
        r = int(ch["rowIndex"])
        if r <= header_row:
            skipped.append((r, "hàng nằm trên/trùng dòng tiêu đề")); continue
        bad = [k for k in list(ch.get("set", {})) + list(ch.get("expect", {})) if k not in by_name]
        if bad:
            skipped.append((r, f"không có cột {bad}")); continue
        lech = [k for k, v in ch.get("expect", {}).items() if cell_text(cur(r, by_name[k]["index"])).strip() != str(v).strip()]
        if lech:
            skipped.append((r, f"ô hiện tại khác kỳ vọng ở cột {lech} — sheet đã đổi, không ghi")); continue
        for name, v in ch.get("set", {}).items():
            hd = by_name[name]
            if hd["o_tick"]:
                skipped.append((r, f"cột '{name}' là ô tick — bỏ qua, không ghi chữ")); continue
            old = cur(r, hd["index"])
            backup.append({"rowIndex": r, "cot": hd["cot"], "header": name, "cu": cell_text(old), "cu_link": old.get("hyperlink")})
            if isinstance(v, dict):
                cell = {"userEnteredValue": {"stringValue": v.get("text", "")}}
                if v.get("link"):
                    cell["textFormatRuns"] = [{"startIndex": 0, "format": {"link": {"uri": v["link"]}}}]
            else:
                cell = {"userEnteredValue": {"stringValue": str(v)}} if str(v) != "" else {}
            reqs.append({"updateCells": {"range": {"sheetId": props["sheetId"], "startRowIndex": r - 1, "endRowIndex": r,
                                                   "startColumnIndex": hd["index"], "endColumnIndex": hd["index"] + 1},
                                         "rows": [{"values": [cell]}], "fields": "userEnteredValue,textFormatRuns"}})
            n_cells += 1
    for r, why in skipped:
        print(f"  BỎ QUA hàng {r}: {why}")
    print(f"{'(thử) ' if thu else ''}{n_cells} ô sẽ ghi, {len({c['rowIndex'] for c in backup})} hàng; {len(skipped)} cảnh báo")
    if thu or not reqs:
        return
    import os
    os.makedirs(".tmp/sao-luu", exist_ok=True)
    bk = f".tmp/sao-luu/{key}-{time.strftime('%Y%m%d-%H%M%S')}.json"
    save(bk, {"tab": props.get("title", tab), "sheetId": props["sheetId"], "o": backup})
    for k in range(0, len(reqs), 500):
        st, res = http("POST", f"{API}/{sid}:batchUpdate", auth_headers(tok), data={"requests": reqs[k:k + 500]})
        if st != 200:
            die(f"ghi thất bại {st}: {res.get('error', res)} — các ô ghi trước đó đã sao lưu ở {bk}")
    print(f"đã ghi {n_cells} ô — sao lưu ô cũ: {bk} (khôi phục: restore {path} {key} {bk})")


def cmd_restore(path, key, backup_file):
    with open(backup_file, encoding="utf-8") as f:
        bk = json.load(f)
    tok, sid = token(path, key)
    reqs = []
    for o in bk["o"]:
        idx = 0
        for ch in o["cot"]:
            idx = idx * 26 + (ord(ch) - 64)
        cell = {"userEnteredValue": {"stringValue": o["cu"]}} if o["cu"] else {}
        if o["cu"] and o.get("cu_link"):
            cell["textFormatRuns"] = [{"startIndex": 0, "format": {"link": {"uri": o["cu_link"]}}}]
        reqs.append({"updateCells": {"range": {"sheetId": bk["sheetId"], "startRowIndex": o["rowIndex"] - 1, "endRowIndex": o["rowIndex"],
                                               "startColumnIndex": idx - 1, "endColumnIndex": idx},
                                     "rows": [{"values": [cell]}], "fields": "userEnteredValue,textFormatRuns"}})
    st, r = http("POST", f"{API}/{sid}:batchUpdate", auth_headers(tok), data={"requests": reqs})
    if st != 200:
        die(f"khôi phục thất bại {st}: {r.get('error', r)}")
    print(f"đã khôi phục {len(reqs)} ô từ {backup_file}")


def cmd_read_public(spreadsheet_id, gid, out):
    """Đọc sheet đang chia sẻ 'ai có link đều xem được' — không cần OAuth. gid lấy từ URL (#gid=...), tab đầu = 0.
    Chỉ đọc; muốn ghi ngược lại sheet vẫn phải nối OAuth."""
    import csv
    import io
    url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/export?format=csv&gid={gid}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            raw = r.read().decode("utf-8-sig")
    except urllib.error.HTTPError as e:
        die(f"không đọc được sheet công khai (HTTP {e.code}) — sheet phải ở chế độ 'Anyone with the link: Viewer'")
    data = list(csv.reader(io.StringIO(raw)))
    if not data:
        die("sheet trống")
    h0 = find_header_row(data)
    headers = [{"index": i, "cot": col_letter(i), "text": h.strip(), "o_tick": False} for i, h in enumerate(data[h0])]
    rows = []
    for i, r in enumerate(data[h0 + 1:], start=h0 + 2):
        vals = {h["text"]: (r[h["index"]].strip() if h["index"] < len(r) else "") for h in headers if h["text"]}
        if any(v for v in vals.values() if v not in ("TRUE", "FALSE")):
            rows.append({"rowIndex": i, "values": vals, "hyperlinks": {}})
    save(out, {"tab": f"gid={gid}", "header_row": h0 + 1, "headers": headers, "rows": rows, "read_only": True})
    print(f"đã đọc sheet công khai gid={gid}: {len(headers)} cột, {len(rows)} dòng (chỉ đọc) → {out}")


def cmd_update_cell(path, key, tab, a1, value):
    tok, sid = token(path, key)
    rng = urllib.parse.quote(f"{a1_tab(tab)}!{a1}", safe="")
    st, r = http("PUT", f"{API}/{sid}/values/{rng}?valueInputOption=USER_ENTERED",
                 auth_headers(tok), data={"values": [[value]]})
    if st != 200 or r.get("updatedCells") != 1:
        die(f"ghi ô thất bại {st}: {r.get('error', r)}")
    print(f"đã ghi {r['updatedRange']}")


def cmd_insert_column(path, key, tab, after_letter, header):
    """Chèn 1 cột mới ngay SAU cột <after_letter> (vd L) và ghi tiêu đề vào dòng 1."""
    tok, sid = token(path, key)
    st, r = http("GET", f"{API}/{sid}?fields=sheets.properties(sheetId,title)", auth_headers(tok))
    if st != 200:
        die(f"{st}: {r}")
    gid = next((s["properties"]["sheetId"] for s in r.get("sheets", []) if s["properties"]["title"] == tab), None)
    if gid is None:
        die(f"không thấy tab '{tab}'")
    idx = 0
    for ch in after_letter.upper():
        idx = idx * 26 + (ord(ch) - 64)
    body = {"requests": [{"insertDimension": {"range": {"sheetId": gid, "dimension": "COLUMNS", "startIndex": idx, "endIndex": idx + 1}, "inheritFromBefore": True}}]}
    st, r = http("POST", f"{API}/{sid}:batchUpdate", auth_headers(tok), data=body)
    if st != 200:
        die(f"chèn cột thất bại {st}: {r.get('error', r)}")
    new_letter = col_letter(idx)
    _, rows_raw = load_grid(tok, sid, tab)
    header_row = find_header_row([[cell_text(c) for c in rr.get("values", [])] for rr in rows_raw]) + 1
    cmd_update_cell(path, key, tab, f"{new_letter}{header_row}", header)
    print(f"đã chèn cột {new_letter} '{header}' sau cột {after_letter.upper()}")


def cmd_append_rows(path, key, tab, rows_file):
    tok, sid = token(path, key)
    with open(rows_file, encoding="utf-8") as f:
        rows = json.load(f)
    rng = urllib.parse.quote(f"{a1_tab(tab)}!A1", safe="")
    st, r = http("POST", f"{API}/{sid}/values/{rng}:append?valueInputOption=USER_ENTERED&insertDataOption=INSERT_ROWS",
                 auth_headers(tok), data={"values": rows})
    if st != 200:
        die(f"thêm dòng thất bại {st}: {r.get('error', r)}")
    print(f"đã thêm {len(rows)} dòng vào {r.get('updates', {}).get('updatedRange')}")


if __name__ == "__main__":
    cmds = {"set-client": cmd_set_client, "oauth": cmd_oauth, "tabs": cmd_tabs,
            "read": cmd_read, "read-public": cmd_read_public,
            "write-rows": cmd_write_rows, "restore": cmd_restore,
            "update-cell": cmd_update_cell, "append-rows": cmd_append_rows,
            "insert-column": cmd_insert_column}
    if len(sys.argv) < 2 or sys.argv[1] not in cmds:
        print(__doc__)
        sys.exit(1)
    try:
        cmds[sys.argv[1]](*sys.argv[2:])
    except TypeError:
        print(__doc__)
        die("sai số tham số cho lệnh " + sys.argv[1])
