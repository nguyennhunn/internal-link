#!/usr/bin/env python3
"""Đọc/ghi Google Sheet cho agent internal-link. Chỉ dùng thư viện chuẩn của Python.

Lệnh:
  set-client  <accounts.json> <key> <client_id> <client_secret> <spreadsheet_id>
  oauth       <accounts.json> <key> [port]           # lần đầu: mở trình duyệt, lưu refresh_token
  tabs        <accounts.json> <key>                  # liệt kê tên tab thật
  read        <accounts.json> <key> <tab> <out.json> # header (kèm hyperlink) + rows
  read-public <spreadsheet_id> <gid> <out.json>      # sheet chia sẻ công khai, KHÔNG cần OAuth, chỉ đọc
  update-cell <accounts.json> <key> <tab> <A1> <value>
  append-rows <accounts.json> <key> <tab> <rows.json>   # rows.json = [["a","b"],...]
  insert-column <accounts.json> <key> <tab> <sau-cột> "<tiêu đề>"  # chèn 1 cột mới sau cột chữ cái đã cho

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


def cmd_read(path, key, tab, out):
    tok, sid = token(path, key)
    fields = "sheets(properties(title),data(rowData(values(formattedValue,hyperlink,userEnteredValue))))"
    url = f"{API}/{sid}?" + urllib.parse.urlencode({"ranges": a1_tab(tab), "fields": fields})
    st, r = http("GET", url, auth_headers(tok))
    if st != 200:
        die(f"đọc sheet thất bại {st}: {r.get('error', r)}")
    sheet = (r.get("sheets") or [{}])[0]
    rows_raw = ((sheet.get("data") or [{}])[0]).get("rowData") or []
    if not rows_raw:
        die("tab trống hoặc sai tên tab — chạy `tabs` để xem tên thật")
    hdr = rows_raw[0].get("values", [])
    headers = [{"index": i, "text": cell_text(c).strip(), "hyperlink": (c or {}).get("hyperlink")} for i, c in enumerate(hdr)]
    rows = []
    for i, rr in enumerate(rows_raw[1:], start=2):
        cells = rr.get("values", [])
        vals, links = {}, {}
        for h in headers:
            if not h["text"]:
                continue
            c = cells[h["index"]] if h["index"] < len(cells) else None
            vals[h["text"]] = cell_text(c).strip()
            if c and c.get("hyperlink"):
                links[h["text"]] = c["hyperlink"]
        if any(vals.values()):
            rows.append({"rowIndex": i, "values": vals, "hyperlinks": links})
    save(out, {"tab": sheet.get("properties", {}).get("title", tab), "headers": headers, "rows": rows})
    print(f"đã đọc tab '{tab}': {len(headers)} cột, {len(rows)} dòng → {out}")


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
    headers = [{"index": i, "text": h.strip(), "hyperlink": None} for i, h in enumerate(data[0])]
    rows = []
    for i, r in enumerate(data[1:], start=2):
        vals = {h["text"]: (r[h["index"]].strip() if h["index"] < len(r) else "") for h in headers if h["text"]}
        if any(vals.values()):
            rows.append({"rowIndex": i, "values": vals, "hyperlinks": {}})
    save(out, {"tab": f"gid={gid}", "headers": headers, "rows": rows, "read_only": True})
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
    new_letter = ""
    n = idx + 1
    while n:
        n, rem = divmod(n - 1, 26)
        new_letter = chr(65 + rem) + new_letter
    cmd_update_cell(path, key, tab, f"{new_letter}1", header)
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
