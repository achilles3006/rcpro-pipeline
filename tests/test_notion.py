"""Notion sync against a fake API: only new and changed rows are written."""

from datetime import date

import duckdb

from rcpro import notion

SCHEMA = {
    "enterprise_number": {"type": "title"},
    "name": {"type": "rich_text"},
    "postcode": {"type": "number"},
    "dm_allowed_from_kbo": {"type": "checkbox"},
    "legal_basis": {"type": "select", "select": {"options": [{"name": "Act of 17 March 2019, art. 44", "id": "a44"}]}},
    "start_date": {"type": "date"},
    "evidence": {"type": "rich_text"},
}


def page(ent, name, postcode, dm, basis, start, evidence):
    text = lambda s: [{"plain_text": s}] if s else []
    return {"id": f"p-{ent}", "properties": {
        "enterprise_number": {"type": "title", "title": text(ent)},
        "name": {"type": "rich_text", "rich_text": text(name)},
        "postcode": {"type": "number", "number": postcode},
        "dm_allowed_from_kbo": {"type": "checkbox", "checkbox": dm},
        "legal_basis": {"type": "select", "select": basis and {"name": basis}},
        "start_date": {"type": "date", "date": {"start": start}},
        "evidence": {"type": "rich_text", "rich_text": text(evidence)},
    }}


def test_sync_writes_only_new_and_changed(monkeypatch):
    con = duckdb.connect()
    con.execute("""CREATE TABLE leads (enterprise_number VARCHAR, name VARCHAR, postcode VARCHAR,
        dm_allowed_from_kbo BOOLEAN, legal_basis VARCHAR, start_date DATE, evidence VARCHAR[], founders VARCHAR)""")
    con.execute("""INSERT INTO leads VALUES
        ('0800.000.001', 'Studio A', '9000', true, NULL, '2026-01-05', ['71111 MAIN'], NULL),
        ('0800.000.002', 'Fiduciaire B', '2000', true, 'Act of 17 March 2019, art. 44', '2026-01-06', ['69200 MAIN'], 'X'),
        ('0800.000.003', 'New C', '1000', true, NULL, '2026-01-07', [], NULL)""")
    existing = [page("0800.000.001", "Studio A", 9000.0, True, None, "2026-01-05", "[71111 MAIN]"),  # unchanged
                page("0800.000.002", "Fiduciaire B", 2000.0, True, None, "2026-01-06", "")]  # basis and evidence new
    calls = []

    def fake(method, path, body=None):
        calls.append((method, path, body))
        if method == "GET":
            return {"properties": SCHEMA}
        if path.endswith("/query"):
            return {"results": existing, "has_more": False}
        return {}

    monkeypatch.setattr(notion, "_call", fake)
    assert notion.sync(con, "db") == {"created": 1, "updated": 1, "unchanged": 1, "skipped columns": ["founders"]}
    writes = {m: b for m, p, b in calls if m in ("PATCH", "POST") and not p.endswith("/query")}
    assert writes["PATCH"]["properties"] == {"legal_basis": {"select": {"id": "a44"}},  # by id: name has a comma
                                             "evidence": {"rich_text": [{"text": {"content": "[69200 MAIN]"}}]}}
    created = writes["POST"]["properties"]
    assert created["enterprise_number"] == {"title": [{"text": {"content": "0800.000.003"}}]}
    assert created["postcode"] == {"number": 1000.0} and created["start_date"] == {"date": {"start": "2026-01-07"}}
    assert notion.norm("date", date(2026, 1, 7)) == "2026-01-07"


def test_expired_oauth_token_is_refreshed_and_saved(tmp_path, monkeypatch):
    import io
    import json
    import urllib.error
    env = tmp_path / "rcpro.env"
    env.write_text("export NOTION_TOKEN=old\nexport NOTION_LEADS_DB=db1\n")
    monkeypatch.setattr(notion, "ENV_FILE", env)
    monkeypatch.setattr(notion, "DELAY", 0)
    for k, v in {"NOTION_TOKEN": "old", "NOTION_REFRESH_TOKEN": "r1", "NOTION_CLIENT_ID": "id", "NOTION_CLIENT_SECRET": "s"}.items():
        monkeypatch.setenv(k, v)
    seen = []

    def urlopen(req, timeout):
        seen.append((req.full_url.removeprefix(notion.API), req.headers["Authorization"]))
        if req.full_url.endswith("/oauth/token"):
            assert json.loads(req.data) == {"grant_type": "refresh_token", "refresh_token": "r1"}
            return io.BytesIO(b'{"access_token": "new", "refresh_token": "r2"}')
        if req.headers["Authorization"] == "Bearer old":
            raise urllib.error.HTTPError(req.full_url, 401, "expired", {}, io.BytesIO(b"{}"))
        return io.BytesIO(b'{"ok": true}')

    monkeypatch.setattr(notion.urllib.request, "urlopen", urlopen)
    assert notion._call("GET", "/users/me") == {"ok": True}
    assert [s[0] for s in seen] == ["/users/me", "/oauth/token", "/users/me"]
    assert seen[1][1].startswith("Basic ") and seen[2][1] == "Bearer new"
    assert env.read_text() == "export NOTION_TOKEN=new\nexport NOTION_LEADS_DB=db1\nexport NOTION_REFRESH_TOKEN=r2\n"
    assert env.stat().st_mode & 0o777 == 0o600
