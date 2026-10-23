"""Compliance gate: only legal persons on impersonal addresses, opt-outs and the log are respected."""

import csv

import duckdb

from rcpro import outreach

SENDER = {k: "x" for k in ["signatory", "company_name", "address", "kbo_number", "fsma_number", "email", "phone",
                           "optout_email", "privacy_url"]}


def con_with_leads():
    con = duckdb.connect()
    con.execute("""CREATE TABLE leads (enterprise_number VARCHAR, start_date DATE, name VARCHAR, segment VARCHAR,
                   sales_angle VARCHAR, mandatory VARCHAR, legal_basis VARCHAR, postcode VARCHAR, legal_form_type VARCHAR,
                   juridical_form VARCHAR, email VARCHAR, site_email VARCHAR)""")
    con.executemany("INSERT INTO leads VALUES (?, '2026-10-01', ?, 'architects', 'legal_obligation', 'yes', 'Act of 9 May 2019', ?, ?, ?, ?, ?)", [
        ("1", "Studio A BV", "9000", "company", "610", "info@studioa.be", None),     # ok, KBO
        ("2", "Jan Peeters", "9000", "sole_trader", None, "info@peeters.be", None),  # sole trader
        ("3", "Studio C BV", "9000", "company", "610", "jan@studioc.be", None),      # personal address
        ("4", "Maatschap D", "9000", "company", "721", "info@d.be", None),           # no legal personality
        ("5", "Atelier E SRL", "1050", "company", "610", None, "Contact@ateliere.be"),  # ok, website, French
    ])
    return con


def test_gate_and_log(tmp_path, monkeypatch):
    monkeypatch.setattr(outreach, "sender", lambda: SENDER)
    con = con_with_leads()
    assert [(c["enterprise_number"], c["email"], c["source"], c["lang"]) for c in outreach.candidates(con)] == [
        ("1", "info@studioa.be", "kbo", "nl"), ("5", "contact@ateliere.be", "website", "fr")]
    assert outreach.export(con, tmp_path / "m.csv") == 2
    rows = list(csv.DictReader((tmp_path / "m.csv").read_text(encoding="utf-8").splitlines()))
    assert rows[0]["subject"].startswith("Reclame:") and "de wet van 9 mei 2019" in rows[0]["body"] and "STOP" in rows[0]["body"]
    assert rows[1]["subject"].startswith("Publicité")
    assert outreach.candidates(con) == []  # logged: never twice


def test_optout_and_commercial_text(monkeypatch):
    con = con_with_leads()
    assert outreach.optout(con, " INFO@studioa.be ") == 1
    assert [c["enterprise_number"] for c in outreach.candidates(con)] == ["5"]
    con.execute("UPDATE leads SET mandatory = 'likely'")
    _, _, body = outreach.render(outreach.candidates(con)[0], SENDER)
    assert "verplicht" not in body and "obligatoire" not in body  # no implied obligation without mandatory = yes


def test_sender_placeholders_block_export():
    import pytest
    with pytest.raises(SystemExit, match="sender.toml"):
        outreach.sender()  # the committed file still holds TODOs
