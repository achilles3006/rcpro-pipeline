"""Classify leads: is professional liability insurance mandatory (yes, likely, unlikely, unknown)?

Rules on activity codes (main and secondary, NACE-BEL 2025, enterprise plus
establishments). Adds to `leads`: mandatory, evidence (codes used), legal_basis,
needs_review, and corrects sales_angle for engineers outside construction.

LLM step (not built yet): only for unknown leads. It must answer "unknown"
without evidence and list the evidence used. Never send sole traders' names.
"""

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
    codes = {}
    for ent, code, cls in con.execute("""
        SELECT DISTINCT e.ent, a.NaceCode, a.Classification
        FROM leads l
        JOIN entity e ON e.ent = l.enterprise_number
        JOIN activity a ON a.EntityNumber = e.entity
        WHERE a.NaceVersion = '2025'
    """).fetchall():
        codes.setdefault(ent, []).append((code, cls))

    rows = [(ent, *classify_one(segment, codes.get(ent, [])))
            for ent, segment in con.execute("SELECT enterprise_number, segment FROM leads").fetchall()]
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
