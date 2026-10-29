"""Compliance gate: only legal persons on impersonal addresses, opt-outs and the log are respected."""

import csv

import duckdb

from rcpro import outreach

SENDER = {k: "x" for k in ["signatory", "company_name", "address", "kbo_number", "fsma_number", "email", "phone",
                           "privacy_url"]}


def con_with_leads():
    con = duckdb.connect()
    con.execute("""CREATE TABLE leads (enterprise_number VARCHAR, start_date DATE, name VARCHAR, segment VARCHAR,
                   sales_angle VARCHAR, mandatory VARCHAR, legal_basis VARCHAR, postcode VARCHAR, legal_form_type VARCHAR,
                   juridical_form VARCHAR, email VARCHAR, site_email VARCHAR, deed_email VARCHAR)""")
    con.executemany("INSERT INTO leads VALUES (?, '2026-10-01', ?, 'architects', 'legal_obligation', 'yes', 'Act of 9 May 2019', ?, ?, ?, ?, ?, ?)", [
        ("1", "Studio A BV", "9000", "company", "610", "info@studioa.be", None, None),     # ok, KBO
        ("2", "Jan Peeters", "9000", "sole_trader", None, "info@peeters.be", None, None),  # sole trader
        ("3", "Studio C BV", "9000", "company", "610", "jan@studioc.be", None, None),      # personal address
        ("4", "Maatschap D", "9000", "company", "721", "info@d.be", None, None),           # no legal personality
        ("5", "Atelier E SRL", "1050", "company", "610", None, "Contact@ateliere.be", None),
        ("6", "Bureau F BV", "9000", "company", "610", "f@gmail.com", "jan@f.be; hallo@f.be", None),  # 2nd website address
        ("7", "Studio G BV", "9000", "company", "610", None, None, "kristof@g.be; info@g.be"),  # ok, deed  # ok, website, French
    ])
    return con


def test_gate_and_log(tmp_path, monkeypatch):
    monkeypatch.setattr(outreach, "sender", lambda: SENDER)
    con = con_with_leads()
    assert [(c["enterprise_number"], c["email"], c["source"], c["lang"]) for c in outreach.candidates(con)] == [
        ("1", "info@studioa.be", "kbo", "nl"), ("5", "contact@ateliere.be", "website", "fr"),
        ("6", "hallo@f.be", "website", "nl"), ("7", "info@g.be", "deed", "nl")]
    assert outreach.export(con, tmp_path / "m.csv") == 4
    rows = list(csv.DictReader((tmp_path / "m.csv").read_text(encoding="utf-8").splitlines()))
    assert rows[0]["subject"].startswith("Voorstel beroepsaansprakelijkheidsverzekering") and "de wet van 9 mei 2019" in rows[0]["body"] and "STOP" in rows[0]["body"]
    assert rows[1]["subject"].startswith("Proposition")
    assert "oprichtingsakte" in rows[3]["body"]
    assert outreach.candidates(con) == []  # logged: never twice


def test_optout_and_commercial_text(monkeypatch):
    con = con_with_leads()
    assert outreach.optout(con, " INFO@studioa.be ") == 1
    assert outreach.optout(con, "info@g.be") == 1  # deed address
    assert [c["enterprise_number"] for c in outreach.candidates(con)] == ["5", "6"]
    con.execute("UPDATE leads SET mandatory = 'likely'")
    _, _, body = outreach.render(outreach.candidates(con)[0], SENDER)
    assert "verplicht" not in body and "obligatoire" not in body  # no implied obligation without mandatory = yes


def test_sender_placeholders_block_export():
    import pytest
    with pytest.raises(SystemExit, match="sender.toml"):
        outreach.sender()  # the committed file still holds TODOs


def test_mx_columns_and_gate():
    con = con_with_leads()
    con.execute("CREATE TABLE mx_check (domain VARCHAR PRIMARY KEY, has_mx BOOLEAN, checked DATE)")
    con.executemany("INSERT INTO mx_check VALUES (?, ?, current_date)", [("studioa.be", False), ("f.be", True), ("gmail.com", True)])
    outreach.apply(con)
    got = dict(con.execute("SELECT enterprise_number, (email_mx_ok, outreach_email) FROM leads").fetchall())
    assert got["1"] == (False, None)  # domain without MX: not mailable
    assert got["6"] == (True, "hallo@f.be")
    assert got["5"] == (None, "contact@ateliere.be")  # not checked yet
    assert got["3"] == (None, None)  # personal address
    personal = dict(con.execute("SELECT enterprise_number, personal_email FROM leads").fetchall())
    assert personal["3"] == "jan@studioc.be" and personal["6"] == "f@gmail.com; jan@f.be"  # listed apart, never mailed
    assert personal["5"] is None and personal["4"] is None  # only impersonal / no legal personality
    assert "1" not in [c["enterprise_number"] for c in outreach.candidates(con)]


def test_mx_answer():
    # gmail.com MX query and answer with a compressed name; then the same with a null MX (RFC 7505)
    q = bytes.fromhex("1234 8180 0001 0001 0000 0000") + b"\x05gmail\x03com\x00" + bytes.fromhex("000f 0001")
    mx = bytes.fromhex("c00c 000f 0001 00000e10 0009 0005") + b"\x04mail\xc0\x0c"
    assert outreach.mx_answer(q + mx)
    assert not outreach.mx_answer(q + bytes.fromhex("c00c 000f 0001 00000e10 0003 0000 00"))
    assert not outreach.mx_answer(bytes.fromhex("1234 8183 0001 0000 0000 0000") + q[12:])
