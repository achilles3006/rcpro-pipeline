"""Sync `leads` to a Notion database: one page per enterprise number (the title column).

Needs NOTION_TOKEN (an internal integration, connected to the database) and NOTION_LEADS_DB
(the database id). Column types come from the database itself, so the CSV import in Notion
decides them; leads columns the database lacks are skipped. Each value is compared with what
Notion holds, so a run writes only new and changed rows. Pages are never deleted, so notes
added in Notion stay (ponytail: leads that drop out of `leads` stay as they were; archive
them when that list gets in the way). Notion allows about 3 requests a second.
"""

import json
import os
import time
import urllib.error
import urllib.request
from datetime import date

API = "https://api.notion.com/v1"
VERSION = "2022-06-28"
DELAY = 0.35
KINDS = ("title", "rich_text", "number", "checkbox", "select", "date")
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
            if e.code not in (429, 502, 503) or attempt == 4:
                raise RuntimeError(f"Notion {method} {path}: {e.code} {e.read().decode()[:300]}") from e
            time.sleep(float(e.headers.get("Retry-After") or 2 ** attempt))


def norm(kind, value):
    """A value as Notion stores it, so a leads value and a Notion value compare equal."""
    if isinstance(value, list):
        value = "[" + ", ".join(map(str, value)) + "]"  # as in leads.csv
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


def sync(con, database=None):
    """Create or update a page per lead. Returns {created, updated, unchanged, skipped columns}."""
    database = database or os.environ["NOTION_LEADS_DB"]
    schema = _call("GET", f"/databases/{database}")["properties"]
    columns = [c[0] for c in con.execute("DESCRIBE leads").fetchall()]
    kinds = {c: schema[c]["type"] for c in columns if c in schema and schema[c]["type"] in KINDS}
    key = next(c for c, k in kinds.items() if k == "title")
    options = {c: {o["name"]: o["id"] for o in schema[c]["select"]["options"]} for c, k in kinds.items() if k == "select"}

    pages, cursor = {}, None
    while True:
        r = _call("POST", f"/databases/{database}/query", {"page_size": 100, **({"start_cursor": cursor} if cursor else {})})
        pages.update({read(p["properties"][key]): p for p in r["results"]})
        if not r["has_more"]:
            break
        cursor = r["next_cursor"]

    counts = {"created": 0, "updated": 0, "unchanged": 0, "skipped columns": [c for c in columns if c not in kinds]}
    for row in con.execute(f"SELECT {', '.join(kinds)} FROM leads ORDER BY start_date DESC").fetchall():
        want = {c: norm(k, v) for (c, k), v in zip(kinds.items(), row)}
        page = pages.get(want[key])
        if page:
            changed = {c: v for c, v in want.items() if v != norm(kinds[c], read(page["properties"][c]))}
            if not changed:
                counts["unchanged"] += 1
                continue
            _call("PATCH", f"/pages/{page['id']}",
                  {"properties": {c: write(kinds[c], v, options.get(c, {})) for c, v in changed.items()}})
            counts["updated"] += 1
        else:
            _call("POST", "/pages", {"parent": {"database_id": database},
                                     "properties": {c: write(kinds[c], v, options.get(c, {})) for c, v in want.items()}})
            counts["created"] += 1
    return counts
