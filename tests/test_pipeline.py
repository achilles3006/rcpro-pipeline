"""Synthetic mini KBO extract: update logic (order, never twice, gaps), leads and classification."""

import duckdb
import pytest

from rcpro import classify, kbo, leads

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
    "address.csv": "EntityNumber,TypeOfAddress,Zipcode\n0800.000.001,REGO,9000\n",
    "contact.csv": "EntityNumber,EntityContact,ContactType,Value\n2.000.000.002,ESTB,EMAIL,jan@example.be\n",
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
    assert rows["0800.000.002"] == ("architects", "sole_trader", None, None, True, False)  # no name for sole traders
    classify.classify(con)
    assert con.execute("SELECT DISTINCT mandatory, evidence, needs_review FROM leads ORDER BY ALL").fetchall() == [
        ("yes", ["71111 MAIN"], False), ("yes", ["7111102 MAIN"], False)
    ]


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
    assert classify.export_unknown(con, out) == 2
    text = out.read_text()
    assert "Stabiliteit BV" in text and "Piet Janssens" not in text  # never a sole trader's name

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
