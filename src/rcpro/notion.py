"""Sync `leads` to a Notion database: one page per enterprise number (the title column).

Needs NOTION_TOKEN (an internal integration connected to the database, or an OAuth token from
`login`) and NOTION_LEADS_DB (the database id). With NOTION_REFRESH_TOKEN, NOTION_CLIENT_ID and
NOTION_CLIENT_SECRET set, an expired OAuth token is refreshed and saved back to the env file. Column types come from the database itself, so the CSV import in Notion
decides them; leads columns the database lacks are skipped. Each value is compared with what
Notion holds, so a run writes only new and changed rows. Pages are never deleted, so notes
added in Notion stay (ponytail: leads that drop out of `leads` stay as they were; archive
them when that list gets in the way). Notion allows about 3 requests a second.
"""

import base64
import http.server
import json
import os
import re
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from datetime import date
from pathlib import Path

API = "https://api.notion.com/v1"
VERSION = "2022-06-28"
DELAY = 0.35
KINDS = ("title", "rich_text", "number", "checkbox", "select", "date", "url")
_last = 0.0


def _call(method, path, body=None):
    global _last
    for attempt in range(5):
        time.sleep(max(0, _last + DELAY - time.monotonic()))
        _last = time.monotonic()
        req = urllib.request.Request(API + path, method=method,
                                     data=None if body is None else json.dumps(body).encode(),
                                     headers={"Authorization": f"Bearer {os.environ['NOTION_TOKEN']}",
                                              "Notion-Version": VERSION, "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 401 and attempt < 4 and os.environ.get("NOTION_REFRESH_TOKEN"):
                refresh()
                continue
            if e.code not in (429, 502, 503) or attempt == 4:
                raise RuntimeError(f"Notion {method} {path}: {e.code} {e.read().decode()[:300]}") from e
            time.sleep(float(e.headers.get("Retry-After") or 2 ** attempt))
        except OSError:  # timeout or dropped connection
            # ponytail: a create that timed out after Notion stored it is made twice; dedupe by hand if seen
            if attempt == 4:
                raise
            time.sleep(2 ** attempt)


ENV_FILE = Path(os.environ.get("RCPRO_ENV", "~/.config/rcpro.env")).expanduser()
REDIRECT = "http://localhost:8765/callback"


def save_env(values, path=None):
    """Set `export KEY=value` lines in the env file (readable by the owner only) and in os.environ."""
    path = path or ENV_FILE
    lines = path.read_text().splitlines() if path.exists() else []
    for key, value in values.items():
        line = f"export {key}={value}"
        hits = [i for i, l in enumerate(lines) if re.match(rf"\s*(export\s+)?{key}=", l)]
        if hits:
            lines[hits[0]] = line
        else:
            lines.append(line)
        os.environ[key] = value
    path.parent.mkdir(parents=True, exist_ok=True)
    path.touch(mode=0o600)
    path.chmod(0o600)
    path.write_text("\n".join(lines) + "\n")


def _token(body):
    """POST /oauth/token with the client credentials; stores the new access and refresh token."""
    basic = base64.b64encode(f"{os.environ['NOTION_CLIENT_ID']}:{os.environ['NOTION_CLIENT_SECRET']}".encode()).decode()
    req = urllib.request.Request(API + "/oauth/token", method="POST", data=json.dumps(body).encode(),
                                 headers={"Authorization": f"Basic {basic}", "Notion-Version": VERSION,
                                          "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            answer = json.load(r)
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Notion OAuth: {e.code} {e.read().decode()[:300]}") from e
    save_env({"NOTION_TOKEN": answer["access_token"],
              **({"NOTION_REFRESH_TOKEN": answer["refresh_token"]} if answer.get("refresh_token") else {})})
    return answer


def refresh():
    return _token({"grant_type": "refresh_token", "refresh_token": os.environ["NOTION_REFRESH_TOKEN"]})


def login():
    """One-time OAuth consent in the browser; the page picker decides which pages the token may use."""
    state = secrets.token_urlsafe(16)
    got = {}

    class Callback(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            if q.get("state") == [state]:
                got.update(code=q.get("code", [None])[0], error=q.get("error", [None])[0])
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write("rcpro: klaar, je mag dit venster sluiten.".encode())

        def log_message(self, *args):
            pass

    url = API + "/oauth/authorize?" + urllib.parse.urlencode({
        "client_id": os.environ["NOTION_CLIENT_ID"], "response_type": "code", "owner": "user",
        "redirect_uri": REDIRECT, "state": state})
    with http.server.HTTPServer(("localhost", 8765), Callback) as server:
        print("Opening Notion in the browser; if nothing opens, go to:\n" + url)
        webbrowser.open(url)
        while not got:
            server.handle_request()
    if not got.get("code"):
        raise SystemExit(f"Notion login refused: {got.get('error')}")
    answer = _token({"grant_type": "authorization_code", "code": got["code"], "redirect_uri": REDIRECT})
    return f"token for workspace {answer.get('workspace_name')!r} saved to {ENV_FILE}"


def norm(kind, value):
    """A value as Notion stores it, so a leads value and a Notion value compare equal."""
    if isinstance(value, date):
        value = value.isoformat()
    if kind == "checkbox":
        return bool(value)
    if value is None or value == "":
        return None
    if kind == "number":
        try:
            return float(value)
        except ValueError:
            return None
    if kind == "date":
        return str(value)[:10]
    return str(value)[:100 if kind == "select" else 2000]


def read(prop):
    kind = prop["type"]
    if kind in ("title", "rich_text"):
        return "".join(t["plain_text"] for t in prop[kind])
    if kind in ("select", "date"):
        return prop[kind] and prop[kind]["name" if kind == "select" else "start"]
    return prop[kind]


def write(kind, value, options):
    if kind in ("title", "rich_text"):
        return {kind: [] if value is None else [{"text": {"content": value}}]}
    if kind == "select":  # by id when the option exists: the API refuses commas in new option names
        return {"select": None if value is None else
                {"id": options[value]} if value in options else {"name": value.replace(",", "")}}
    if kind == "date":
        return {"date": value and {"start": value}}
    return {kind: value}


def sync(con, database=None, full=False):
    """Create or update a page per lead, mailable companies first. Returns {created, updated, unchanged, skipped columns}.

    What Notion holds is remembered in the table notion_pages, so a run sends only new and changed
    leads. Notion is read in full only on the first run or with full=True (`notion --full`), e.g.
    after pages were deleted or columns edited by hand in Notion.
    """
    database = database or os.environ["NOTION_LEADS_DB"]
    schema = _call("GET", f"/databases/{database}")["properties"]
    columns = [c[0] for c in con.execute("DESCRIBE leads").fetchall()]
    kinds = {c: schema[c]["type"] for c in columns if c in schema and schema[c]["type"] in KINDS}
    key = next(c for c, k in kinds.items() if k == "title")
    options = {c: {o["name"]: o["id"] for o in schema[c]["select"]["options"]} for c, k in kinds.items() if k == "select"}

    con.execute("CREATE TABLE IF NOT EXISTS notion_pages (enterprise_number VARCHAR PRIMARY KEY, page_id VARCHAR, data VARCHAR)")
    if full:
        con.execute("DELETE FROM notion_pages")
    known = {k: (pid, json.loads(d)) for k, pid, d in con.execute("SELECT * FROM notion_pages").fetchall()}
    if not known:  # first run or --full: read what Notion holds
        cursor = None
        while True:
            r = _call("POST", f"/databases/{database}/query", {"page_size": 100, **({"start_cursor": cursor} if cursor else {})})
            for p in r["results"]:
                have = {c: norm(k, read(p["properties"][c])) for c, k in kinds.items() if c in p["properties"]}
                known[have[key]] = (p["id"], have)
            if not r["has_more"]:
                break
            cursor = r["next_cursor"]
        con.executemany("INSERT INTO notion_pages VALUES (?, ?, ?)",
                        [[k, pid, json.dumps(have)] for k, (pid, have) in known.items()])

    counts = {"created": 0, "updated": 0, "unchanged": 0, "skipped columns": [c for c in columns if c not in kinds]}
    lists = {c[0] for c in con.execute("DESCRIBE leads").fetchall() if c[1].endswith("[]")}
    select = ", ".join(f"CAST({c} AS VARCHAR)" if c in lists else c for c in kinds)  # lists as leads.csv writes them
    first = "outreach_email IS NOT NULL DESC, " if "outreach_email" in columns else ""  # mailable rows first
    for row in con.execute(f"SELECT {select} FROM leads ORDER BY {first}start_date DESC").fetchall():
        want = {c: norm(k, v) for (c, k), v in zip(kinds.items(), row)}
        if want[key] in known:
            page_id, have = known[want[key]]
            changed = {c: v for c, v in want.items() if v != have.get(c)}
            if not changed:
                counts["unchanged"] += 1
                continue
            _call("PATCH", f"/pages/{page_id}",
                  {"properties": {c: write(kinds[c], v, options.get(c, {})) for c, v in changed.items()}})
            counts["updated"] += 1
        else:
            page_id = _call("POST", "/pages", {"parent": {"database_id": database},
                                               "properties": {c: write(kinds[c], v, options.get(c, {})) for c, v in want.items()}})["id"]
            counts["created"] += 1
        con.execute("INSERT OR REPLACE INTO notion_pages VALUES (?, ?, ?)", [want[key], page_id, json.dumps(want)])
    return counts
