"""Classify leads: is professional liability insurance mandatory (yes, likely, unlikely, unknown)?

Rules on activity codes (main and secondary, NACE-BEL 2025, enterprise plus
establishments). Adds to `leads`: mandatory, evidence (codes used), legal_basis,
needs_review, and corrects sales_angle for engineers outside construction.

LLM step, run by hand in Claude Code (no API key): export_unknown writes the
unknown engineers to JSONL, Claude classifies them with prompts/classify_engineers.md,
import_llm stores the answers in `llm_classification`, and the next classify run
uses them for leads the rules left unknown. No evidence means "unknown".
Sole traders' names are never exported.
"""

import json

from rcpro.leads import SEGMENTS

ACT_2019 = "Act of 9 May 2019"

# segment -> (mandatory, legal_basis). Engineers are decided by their codes, see classify_one.
FIXED = {
    "architects": ("yes", ACT_2019),
    "interior_architects": ("yes", ACT_2019),
    "land_surveyors": ("yes", ACT_2019),
    "urban_landscape": ("likely", ACT_2019),  # only for real estate works
    "accountants": ("yes", "Act of 17 March 2019, art. 44"),
    "psychologists": ("unknown", None),  # obligation not confirmed by a lawyer
    "management_consultants": ("unlikely", None),
    "it_consultants": ("unlikely", None),
    "real_estate": ("yes", "Act of 11 Feb 2013 (collective BIV policy)"),
    "insurance_intermediaries": ("yes", "Insurance Act of 4 April 2014"),
}

# Engineers (71121) fall under the 2019 Act only for real estate works.
# ponytail: prefix rules from phase 2, calibrate against the phase 5 labelled sample.
CONSTRUCTION = ("41", "42", "43", "7111", "71122")  # building, civil works, architecture, surveying
NOT_CONSTRUCTION = tuple(str(n) for n in range(10, 34)) + ("35", "61", "62", "63")  # industry, energy, telecom, IT

SEGMENT_CODES = {segment: set(codes) for segment, _, codes in SEGMENTS}


def classify_one(segment, codes):
    """codes: list of (nace_code, classification). Returns (mandatory, evidence, legal_basis)."""
    def evidence(match):
        return sorted({f"{code} {cls}" for code, cls in codes if match(code)})

    if segment != "engineers":
        mandatory, legal_basis = FIXED[segment]
        return mandatory, evidence(lambda c: c in SEGMENT_CODES[segment]), legal_basis
    if found := evidence(lambda c: c.startswith(CONSTRUCTION)):
        return "likely", found, ACT_2019
    if found := evidence(lambda c: c.startswith(NOT_CONSTRUCTION)):
        return "unlikely", found, None
    return "unknown", [], None


def classify(con):
    """Add the classification columns to `leads` (run right after build_leads)."""
    _llm_table(con)
    codes = {}
    for ent, code, cls in con.execute("""
        SELECT DISTINCT e.ent, a.NaceCode, a.Classification
        FROM leads l
        JOIN entity e ON e.ent = l.enterprise_number
        JOIN activity a ON a.EntityNumber = e.entity
        WHERE a.NaceVersion = '2025'
    """).fetchall():
        codes.setdefault(ent, []).append((code, cls))

    llm = {ent: (m, ev) for ent, m, ev in con.execute(
        "SELECT enterprise_number, mandatory, evidence FROM llm_classification").fetchall()}
    rows = []
    for ent, segment in con.execute("SELECT enterprise_number, segment FROM leads").fetchall():
        mandatory, evidence, legal_basis = classify_one(segment, codes.get(ent, []))
        if mandatory == "unknown" and ent in llm:
            mandatory, evidence = llm[ent][0], [f"llm: {e}" for e in llm[ent][1]]
            legal_basis = ACT_2019 if mandatory == "likely" else None
        rows.append((ent, mandatory, evidence, legal_basis))
    con.execute("CREATE OR REPLACE TEMP TABLE c (ent VARCHAR, mandatory VARCHAR, evidence VARCHAR[], legal_basis VARCHAR)")
    con.executemany("INSERT INTO c VALUES (?, ?, ?, ?)", rows)
    con.execute("""
        CREATE OR REPLACE TABLE leads AS
        SELECT l.* REPLACE (
                   CASE WHEN l.segment = 'engineers' AND c.mandatory = 'unlikely'
                        THEN 'commercial_need' ELSE l.sales_angle END AS sales_angle),
               c.mandatory, c.evidence, c.legal_basis,
               c.mandatory IN ('likely', 'unknown') AS needs_review
        FROM leads l JOIN c ON c.ent = l.enterprise_number
    """)


def _llm_table(con):
    con.execute("""CREATE TABLE IF NOT EXISTS llm_classification
        (enterprise_number VARCHAR PRIMARY KEY, mandatory VARCHAR, evidence VARCHAR[], classified_at TIMESTAMP)""")


def export_unknown(con, path):
    """Write engineers the rules left unknown, and the LLM has not seen yet, to JSONL."""
    _llm_table(con)
    rows = con.execute("""
        SELECT l.enterprise_number,
               CASE WHEN l.legal_form_type = 'company' THEN l.name END AS name,  -- never a sole trader's name
               list_sort(list(DISTINCT {'code': a.NaceCode, 'classification': a.Classification,
                                        'description': c.Description})) AS codes
        FROM leads l
        JOIN entity e ON e.ent = l.enterprise_number
        JOIN activity a ON a.EntityNumber = e.entity AND a.NaceVersion = '2025'
        LEFT JOIN code c ON c.Code = a.NaceCode AND c.Category ILIKE 'Nace2025' AND c.Language = 'NL'
        WHERE l.segment = 'engineers' AND l.mandatory = 'unknown'
          AND l.enterprise_number NOT IN (SELECT enterprise_number FROM llm_classification)
        GROUP BY ALL ORDER BY 1
    """).fetchall()
    with open(path, "w", encoding="utf-8") as f:
        f.writelines(json.dumps({"enterprise_number": ent, "name": name, "codes": codes}, ensure_ascii=False) + "\n"
                     for ent, name, codes in rows)
    return len(rows)


def import_llm(con, path):
    """Store Claude's answers. Every line is checked; one bad line imports nothing."""
    _llm_table(con)
    engineers = {r[0] for r in con.execute("SELECT enterprise_number FROM leads WHERE segment = 'engineers'").fetchall()}
    rows, errors = [], []
    with open(path, encoding="utf-8") as f:
        lines = f.readlines()
    for n, line in enumerate(lines, 1):
        if not line.lstrip().startswith("{"):  # tolerate blank lines and code fences
            continue
        try:
            r = json.loads(line)
            ent, mandatory, evidence = r["enterprise_number"], r["mandatory"], r.get("evidence") or []
            if ent not in engineers:
                raise ValueError(f"{ent} is not an engineer lead")
            if mandatory not in ("likely", "unlikely", "unknown"):
                raise ValueError(f"bad mandatory {mandatory!r}")
            if not isinstance(evidence, list) or not all(isinstance(e, str) for e in evidence):
                raise ValueError("evidence must be a list of strings")
        except (ValueError, KeyError, TypeError) as e:
            errors.append(f"line {n}: {e}")
            continue
        rows.append((ent, mandatory if evidence else "unknown", evidence))
    if errors:
        raise ValueError("Nothing imported:\n" + "\n".join(errors))
    con.executemany("INSERT OR REPLACE INTO llm_classification VALUES (?, ?, ?, now())", rows)
    return len(rows)
