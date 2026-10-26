"""Synthetic mini KBO extract: update logic (order, never twice, gaps), leads and classification."""

import duckdb
import pytest

from rcpro import classify, kbo, leads, outreach, staatsblad, websites

FULL = {
    "meta.csv": "Variable,Value\nExtractNumber,516\n",
    "enterprise.csv": (
        "EnterpriseNumber,Status,JuridicalSituation,TypeOfEnterprise,JuridicalForm,JuridicalFormCAC,StartDate\n"
        "0800.000.001,AC,000,2,610,,05-01-2026\n"  # architect company
        "0800.000.002,AC,000,1,,,06-01-2026\n"  # architect sole trader
        "0800.000.003,AC,000,2,610,,01-01-2020\n"  # architect, too old
        "0800.000.006,AC,000,2,610,,08-01-2026\n"  # architect via subcode
    ),
    "establishment.csv": "EstablishmentNumber,StartDate,EnterpriseNumber\n2.000.000.002,06-01-2026,0800.000.002\n",
    "activity.csv": (
        "EntityNumber,ActivityGroup,NaceVersion,NaceCode,Classification\n"
        "0800.000.001,001,2025,71111,MAIN\n"
        "0800.000.001,001,2025,71121,MAIN\n"  # second segment: must not create a second row
        "2.000.000.002,001,2025,71111,MAIN\n"  # activity on the establishment only
        "0800.000.003,001,2025,71111,MAIN\n"
        "0800.000.006,001,2025,7111102,MAIN\n"  # subcode of 71111
    ),
    "denomination.csv": (
        "EntityNumber,Language,TypeOfDenomination,Denomination\n"
        "0800.000.001,2,001,Studio A\n"
        "0800.000.002,2,001,Jan Peeters\n"
    ),
    "address.csv": "EntityNumber,TypeOfAddress,Zipcode,MunicipalityNL\n0800.000.001,REGO,9000,Gent\n2.000.000.002,BAET,2000,Antwerpen\n",
    "contact.csv": (
        "EntityNumber,EntityContact,ContactType,Value\n"
        "2.000.000.002,ESTB,EMAIL,jan@example.be\n"
        "0800.000.001,ENT,TEL,09 123 45 67\n"
    ),
    "code.csv": "Category,Code,Language,Description\nNace2025,71111,NL,Architecten\n",
}


def write(folder, files):
    folder.mkdir()
    for name, text in files.items():
        (folder / name).write_text(text)
    return folder


def update(tmp_path, number, files):
    return write(tmp_path / f"u{number}", {"meta.csv": f"Variable,Value\nExtractNumber,{number}\n", **files})


@pytest.fixture
def con(tmp_path):
    con = duckdb.connect()
    kbo.load_full(con, write(tmp_path / "full", FULL))
    return con


def names(con):
    return {r[0] for r in con.execute("SELECT Denomination FROM denomination").fetchall()}


def test_update_deletes_then_inserts_in_order_and_never_twice(con, tmp_path):
    u517 = update(tmp_path, 517, {
        "denomination_delete.csv": "EntityNumber\n0800.000.001\n",
        "denomination_insert.csv": "EntityNumber,Language,TypeOfDenomination,Denomination\n0800.000.001,2,001,Studio B\n",
    })
    u518 = update(tmp_path, 518, {
        "denomination_insert.csv": "EntityNumber,Language,TypeOfDenomination,Denomination\n0800.000.009,2,001,New BV\n",
    })
    assert kbo.apply_updates(con, [u518, u517]) == [True, True]  # given out of order, applied 517 then 518
    assert names(con) == {"Studio B", "Jan Peeters", "New BV"}
    assert kbo.apply_update(con, u518) is False  # second time: no-op
    assert kbo.apply_update(con, u517) is False
    assert con.execute("SELECT count(*) FROM denomination").fetchone()[0] == 3
    assert kbo.last_applied(con) == 518


def test_gap_warns(con, tmp_path):
    with pytest.warns(UserWarning, match="Gap"):
        kbo.apply_update(con, update(tmp_path, 520, {}))


def test_failed_update_rolls_back(con, tmp_path):
    bad = update(tmp_path, 517, {
        "denomination_delete.csv": "EntityNumber\n0800.000.001\n",
        "nosuchtable_insert.csv": "x\n1\n",
    })
    with pytest.raises(duckdb.CatalogException):
        kbo.apply_update(con, bad)
    assert "Studio A" in names(con)
    assert kbo.last_applied(con) == 516


def test_leads(con):
    assert leads.build_leads(con, "2025-10-01") == 3
    rows = {r[0]: r[1:] for r in con.execute(
        "SELECT enterprise_number, segment, legal_form_type, name, postcode, has_email, dm_allowed_from_kbo FROM leads"
    ).fetchall()}
    assert rows["0800.000.001"] == ("architects", "company", "Studio A", "9000", False, True)
    assert rows["0800.000.002"] == ("architects", "sole_trader", "Jan Peeters", "2000", True, False)  # owner name, establishment postcode
    contact = {r[0]: r[1:] for r in con.execute("SELECT enterprise_number, phone, email, has_email FROM leads").fetchall()}
    assert contact["0800.000.001"] == ("09 123 45 67", None, False)
    assert con.execute("SELECT juridical_form_label FROM leads WHERE enterprise_number = '0800.000.001'").fetchone()[0] == "BV"
    assert contact["0800.000.002"] == (None, "jan@example.be", True)  # sole trader: value shown, dm still false
    classify.classify(con)
    assert con.execute("SELECT DISTINCT mandatory, evidence, needs_review FROM leads ORDER BY ALL").fetchall() == [
        ("yes", ["71111 MAIN"], False), ("yes", ["7111102 MAIN"], False)
    ]


def test_leads_only_grow(con):
    leads.build_leads(con, "2025-10-01")
    classify.classify(con)  # enrichment columns on the old table must not break the rebuild
    con.execute("UPDATE enterprise SET Status = 'ST' WHERE EnterpriseNumber = '0800.000.001'")
    assert leads.build_leads(con, "2025-10-01") == 3
    assert con.execute("SELECT name FROM leads WHERE enterprise_number = '0800.000.001'").fetchone() == ("Studio A",)


def test_codes_flags_unknown_code(con):
    found = {code: desc for _, code, desc in leads.codes(con)}
    assert found["71111"] == "Architecten"
    assert found["71121"] is None


def test_llm_round_trip(con, tmp_path):
    con.execute("""INSERT INTO enterprise (EnterpriseNumber, Status, TypeOfEnterprise, StartDate) VALUES
        ('0800.000.004', 'AC', '2', '07-01-2026'), ('0800.000.005', 'AC', '1', '07-01-2026')""")
    con.execute("""INSERT INTO activity (EntityNumber, NaceVersion, NaceCode, Classification) VALUES
        ('0800.000.004', '2025', '71121', 'MAIN'), ('0800.000.004', '2025', '70200', 'SECO'),
        ('0800.000.005', '2025', '71121', 'MAIN')""")
    con.execute("INSERT INTO denomination VALUES ('0800.000.004', '2', '001', 'Stabiliteit BV'), "
                "('0800.000.005', '2', '001', 'Piet Janssens')")
    leads.build_leads(con, "2025-10-01")
    classify.classify(con)

    out = tmp_path / "unknown.jsonl"
    assert classify.export_unknown(con, out) == 1
    text = out.read_text()
    assert "Stabiliteit BV" in text and "0800.000.005" not in text  # never a sole trader, not even its codes

    answers = tmp_path / "llm.jsonl"
    answers.write_text(
        "```json\n"
        '{"enterprise_number": "0800.000.004", "mandatory": "likely", "evidence": ["name: Stabiliteit"]}\n'
        '{"enterprise_number": "0800.000.005", "mandatory": "unlikely", "evidence": []}\n'  # no evidence
        "```\n"
    )
    bad = tmp_path / "bad.jsonl"
    bad.write_text('{"enterprise_number": "0800.000.001", "mandatory": "yes"}\n')
    with pytest.raises(ValueError, match="Nothing imported"):
        classify.import_llm(con, bad)

    assert classify.import_llm(con, answers) == 2
    leads.build_leads(con, "2025-10-01")
    classify.classify(con)
    rows = {r[0]: r[1:] for r in con.execute(
        "SELECT enterprise_number, mandatory, evidence, legal_basis FROM leads WHERE segment = 'engineers'").fetchall()}
    assert rows["0800.000.004"] == ("likely", ["llm: name: Stabiliteit"], classify.ACT_2019)
    assert rows["0800.000.005"] == ("unknown", [], None)
    assert classify.export_unknown(con, out) == 0  # already seen by the LLM


def test_view_html(con, tmp_path):
    leads.build_leads(con, "2025-10-01")
    classify.classify(con)
    websites.apply(con)
    staatsblad.apply(con)
    outreach.apply(con)
    from rcpro import view
    assert view.write_html(con, tmp_path / "leads.html") == 3
    html = (tmp_path / "leads.html").read_text()
    assert "Studio A" in html and "Jan Peeters" in html and "jan@example.be" in html


def test_websites_apply_is_repeatable_and_skips_none(con):
    leads.build_leads(con, "2025-10-01")
    classify.classify(con)
    websites.apply(con)  # creates website_matches
    con.execute("""INSERT INTO website_matches VALUES
        ('0800.000.001', 'probable', 'studio-a.be', 'name_guess', 'info@studio-a.be', '+3291234567', now()),
        ('0800.000.006', 'none', NULL, NULL, NULL, NULL, now())""")
    websites.apply(con)
    websites.apply(con)  # twice: no duplicate columns
    rows = dict(con.execute("SELECT enterprise_number, site FROM leads").fetchall())
    assert rows == {"0800.000.001": "studio-a.be", "0800.000.002": None, "0800.000.006": None}


DEED = """Objet de l'acte : CONSTITUTION
1. CONSTITUANT Monsieur HERNANDEZ VAZQUEZ Nicolas, domicilié à 6010 Charleroi.
Article 4 – Objet: études de stabilité et techniques spéciales pour bâtiments."""


def test_deeds_round_trip(con, tmp_path):
    con.execute("""INSERT INTO enterprise (EnterpriseNumber, Status, TypeOfEnterprise, StartDate) VALUES
        ('0800.000.004', 'AC', '2', '07-01-2026'), ('0800.000.005', 'AC', '1', '07-01-2026')""")
    con.execute("""INSERT INTO activity (EntityNumber, NaceVersion, NaceCode, Classification) VALUES
        ('0800.000.004', '2025', '71121', 'MAIN'), ('0800.000.005', '2025', '71121', 'MAIN')""")
    leads.build_leads(con, "2025-10-01")
    classify.classify(con)
    staatsblad.tables(con)
    con.execute("INSERT INTO deeds VALUES ('0800.000.004', 'https://x/a.pdf', '2026-01-20', ?, now()), "
                "('0800.000.001', NULL, NULL, NULL, now()), ('0800.000.005', 'https://x/b.pdf', NULL, 'sole trader deed', now())",
                [DEED])

    out = tmp_path / "deeds.jsonl"
    assert staatsblad.export_deeds(con, out) == 1  # no text, and never a sole trader
    assert "stabilité" in out.read_text() and "sole trader deed" not in out.read_text()

    bad = tmp_path / "bad.jsonl"
    bad.write_text('{"enterprise_number": "0800.000.004", "construction_related": "maybe"}\n')
    with pytest.raises(ValueError, match="Nothing imported"):
        staatsblad.import_deeds(con, bad)
    bad.write_text('{"enterprise_number": "0800.000.001", "construction_related": "no", "evidence": "x"}\n')
    with pytest.raises(ValueError, match="no deed text"):
        staatsblad.import_deeds(con, bad)

    answers = tmp_path / "answers.jsonl"
    answers.write_text('{"enterprise_number": "0800000004", "founders": [{"name": "Nicolas Hernandez Vazquez", '  # no dots
                       '"role": "founder"}], "activity_summary": "Stability studies for buildings", '
                       '"construction_related": "yes", "evidence": "études de stabilité ... pour bâtiments"}\n')
    assert staatsblad.import_deeds(con, answers) == 1
    leads.build_leads(con, "2025-10-01")
    classify.classify(con)
    websites.apply(con)
    staatsblad.apply(con)
    staatsblad.apply(con)  # twice: no duplicate columns
    rows = {r[0]: r[1:] for r in con.execute(
        "SELECT enterprise_number, mandatory, evidence, founders, activity_summary FROM leads WHERE segment = 'engineers'").fetchall()}
    assert rows["0800.000.004"] == ("likely", ["deed: études de stabilité ... pour bâtiments"],
                                    "Nicolas Hernandez Vazquez (founder)", "Stability studies for buildings")
    assert rows["0800.000.005"] == ("unknown", [], None, None)
    assert staatsblad.export_deeds(con, out) == 0  # already read


def test_deed_without_evidence_is_unknown(con, tmp_path):
    leads.build_leads(con, "2025-10-01")
    staatsblad.tables(con)
    con.execute("INSERT INTO deeds VALUES ('0800.000.001', 'https://x/a.pdf', NULL, 'text', now())")
    answers = tmp_path / "a.jsonl"
    answers.write_text('{"enterprise_number": "0800.000.001", "founders": [], "construction_related": "yes"}\n')
    staatsblad.import_deeds(con, answers)
    assert con.execute("SELECT construction_related FROM deed_extraction").fetchone()[0] == "unknown"


def test_unknown_engineers_get_their_deed_first(con, monkeypatch):
    con.execute("INSERT INTO enterprise (EnterpriseNumber, Status, TypeOfEnterprise, StartDate) VALUES "
                "('0800.000.004', 'AC', '2', '01-01-2026')")  # oldest lead, but an engineer without code evidence
    con.execute("INSERT INTO activity (EntityNumber, NaceVersion, NaceCode, Classification) VALUES "
                "('0800.000.004', '2025', '71121', 'MAIN')")
    leads.build_leads(con, "2025-10-01")
    classify.classify(con)
    asked = []
    monkeypatch.setattr(staatsblad, "fetch_one", lambda ent: asked.append(ent) or (None, None, None))
    staatsblad.fetch(con)
    assert asked == ["0800.000.004", "0800.000.006", "0800.000.001"]


def test_no_deed_is_retried_only_while_recent(con, monkeypatch):
    leads.build_leads(con, "2025-10-01")
    classify.classify(con)
    staatsblad.tables(con)
    con.execute("""INSERT INTO deeds VALUES ('0800.000.001', NULL, NULL, NULL, '2026-01-10'),
        ('0800.000.006', NULL, NULL, NULL, '2026-06-01')""")  # started 5 and 8 January 2026
    asked = []
    monkeypatch.setattr(staatsblad, "fetch_one", lambda ent: asked.append(ent) or (None, None, None))
    staatsblad.fetch(con)
    assert asked == ["0800.000.001"]  # sole trader 0800.000.002 never, 0800.000.006 gave up after 60 days
    staatsblad.fetch(con)
    assert asked == ["0800.000.001"]  # just checked: not again within a week


def test_web_search_round_trip(con, tmp_path, monkeypatch):
    leads.build_leads(con, "2025-10-01")
    classify.classify(con)
    websites.apply(con)
    out = tmp_path / "search.jsonl"
    assert websites.export_search(con, out) == 2  # both companies (KBO phone only counts as missing), never the sole trader
    assert "0800.000.006" in out.read_text() and "0800.000.002" not in out.read_text()

    bad = tmp_path / "bad.jsonl"
    bad.write_text('{"enterprise_number": "0800.000.002", "website": "jan.be"}\n')
    with pytest.raises(ValueError, match="not a company lead"):
        websites.import_search(con, bad)

    monkeypatch.setattr(websites, "check_answer", lambda c, w, e, s: ("probable", "found.be", {"info@found.be"}, set()))
    answers = tmp_path / "answers.jsonl"
    answers.write_text('Here you go:\n{"enterprise_number": "0800.000.006", "website": "found.be", "email": null, "source": null}\n')
    assert websites.import_search(con, answers) == {"probable": 1}
    websites.apply(con)
    assert con.execute("SELECT site, site_email FROM leads WHERE enterprise_number = '0800.000.006'").fetchone() == (
        "found.be", "info@found.be")
    assert websites.export_search(con, out) == 1  # 0800.000.006 searched once, 0800.000.001 still to do
