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
