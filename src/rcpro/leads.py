"""Select active businesses by start date and main activity (NACE-BEL 2025).

Output: one row per business with segment, legal form type, postcode, contact
presence flags, `dm_allowed_from_kbo` and `sales_angle`
(legal_obligation, legal_unconfirmed, commercial_need, no_outreach; see docs/segments.md).
Every business gets name, municipality, e-mail, phone and website from KBO; for a
sole trader the name is the owner's ("Surname, First name"). The list is informational:
sole traders keep dm_allowed_from_kbo = false (KBO direct marketing ban).
"""

# (segment, sales_angle, NACE-BEL 2025 main codes). Order is priority: a business
# with main codes in two segments lands in the first one. Codes from Notion phase 0.
SEGMENTS = [
    ("architects", "legal_obligation", ["71111"]),
    ("interior_architects", "legal_obligation", ["71112"]),
    ("urban_landscape", "legal_obligation", ["71113", "71119"]),
    ("engineers", "legal_obligation", ["71121"]),  # needs classification (rcpro.classify)
    ("land_surveyors", "legal_obligation", ["71122"]),
    ("accountants", "legal_obligation", ["69201", "69202"]),  # prospect or partner
    ("psychologists", "legal_unconfirmed", ["86931", "86932"]),
    ("management_consultants", "commercial_need", ["70200"]),
    ("it_consultants", "commercial_need", ["62200", "62100", "62900"]),  # consultancy, software design, other IT services
    # Healthcare and other FSMA-list professions: obligation not confirmed (docs/segments.md, gap check 23 Oct 2026)
    ("dentists", "legal_unconfirmed", ["86230", "86991"]),
    ("doctors", "legal_unconfirmed", ["86210", "86220"]),
    ("paramedics", "legal_unconfirmed", ["86951", "86952", "86940", "86963", "86994", "86995", "86996"]),
    ("veterinarians", "legal_unconfirmed", ["75000"]),
    ("technical_testing", "legal_unconfirmed", ["71209"]),  # may hold EPB/EPC and asbestos experts, needs classification
    ("financial_planners", "legal_unconfirmed", ["66199"]),  # only FSMA-licensed planners are obliged; code is broad
    ("recruitment", "legal_unconfirmed", ["78100"]),
    ("marketing_communication", "commercial_need", ["73110", "73300", "74120"]),
    ("legal_advisers", "commercial_need", ["69109"]),  # legal services by non-lawyers
    ("real_estate_appraisers", "commercial_need", ["68322"]),
    ("real_estate", "no_outreach", ["68310", "68321"]),
    ("insurance_intermediaries", "no_outreach", ["66220"]),
    ("legal_collective", "no_outreach", ["69101", "69102", "69103", "69203"]),  # lawyers, notaries, bailiffs, auditors: collective policies
]


# KBO JuridicalForm code -> usual abbreviation. Other codes show the KBO description.
LEGAL_FORMS = {"610": "BV", "612": "CommV", "011": "VOF", "014": "NV", "706": "CV", "017": "VZW", "125": "IVZW"}


def _segment_rows():
    return [(code, seg, angle, i) for i, (seg, angle, codes) in enumerate(SEGMENTS) for code in codes]


def _segment_table(con):
    con.execute("CREATE OR REPLACE TEMP TABLE segment (code VARCHAR, segment VARCHAR, sales_angle VARCHAR, priority INTEGER)")
    con.executemany("INSERT INTO segment VALUES (?, ?, ?, ?)", _segment_rows())


def build_leads(con, since):
    """(Re)build the `leads` table for businesses started on or after `since` (YYYY-MM-DD)."""
    _segment_table(con)
    con.execute("CREATE OR REPLACE TEMP TABLE legal_form (code VARCHAR, short VARCHAR)")
    con.executemany("INSERT INTO legal_form VALUES (?, ?)", list(LEGAL_FORMS.items()))
    con.execute("""
        CREATE OR REPLACE VIEW entity AS  -- activities and contacts sit on the enterprise or on its establishments
        SELECT EnterpriseNumber AS entity, EnterpriseNumber AS ent FROM enterprise
        UNION ALL
        SELECT EstablishmentNumber, EnterpriseNumber FROM establishment
    """)
    con.execute("""
        CREATE OR REPLACE TABLE leads AS
        WITH picked AS (
            SELECT e.ent, arg_min(s.segment, s.priority) AS segment, arg_min(s.sales_angle, s.priority) AS sales_angle
            FROM activity a
            JOIN entity e ON a.EntityNumber = e.entity
            JOIN segment s ON starts_with(a.NaceCode, s.code)  -- includes 7-digit subcodes (7111101)
            WHERE a.Classification = 'MAIN' AND a.NaceVersion = '2025'
            GROUP BY e.ent
        ),
        contacts AS (
            SELECT e.ent,
                   bool_or(c.ContactType = 'EMAIL') AS has_email,
                   bool_or(c.ContactType = 'TEL') AS has_phone,
                   bool_or(c.ContactType = 'WEB') AS has_website,
                   string_agg(DISTINCT c.Value, '; ') FILTER (c.ContactType = 'EMAIL') AS email,
                   string_agg(DISTINCT c.Value, '; ') FILTER (c.ContactType = 'TEL') AS phone,
                   string_agg(DISTINCT c.Value, '; ') FILTER (c.ContactType = 'WEB') AS website
            FROM contact c JOIN entity e ON c.EntityNumber = e.entity
            GROUP BY e.ent
        )
        SELECT
            p.ent AS enterprise_number,
            strptime(en.StartDate, '%d-%m-%Y')::DATE AS start_date,
            p.segment,
            p.sales_angle,
            CASE WHEN en.TypeOfEnterprise = '1' THEN 'sole_trader' ELSE 'company' END AS legal_form_type,
            en.JuridicalForm AS juridical_form,
            coalesce(lf.short, (SELECT min(Description) FROM code
                                WHERE Category = 'JuridicalForm' AND Code = en.JuridicalForm AND Language = 'NL'))
                AS juridical_form_label,
            (SELECT min(Denomination) FROM denomination d
             WHERE d.EntityNumber = en.EnterpriseNumber AND d.TypeOfDenomination = '001') AS name,
            -- registered office; sole traders have none in KBO, so fall back to their establishment
            coalesce((SELECT min(Zipcode) FROM address ad
                      WHERE ad.EntityNumber = en.EnterpriseNumber AND ad.TypeOfAddress = 'REGO'),
                     (SELECT min(Zipcode) FROM address ad JOIN establishment es ON ad.EntityNumber = es.EstablishmentNumber
                      WHERE es.EnterpriseNumber = en.EnterpriseNumber)) AS postcode,
            coalesce((SELECT min(MunicipalityNL) FROM address ad
                      WHERE ad.EntityNumber = en.EnterpriseNumber AND ad.TypeOfAddress = 'REGO'),
                     (SELECT min(MunicipalityNL) FROM address ad JOIN establishment es ON ad.EntityNumber = es.EstablishmentNumber
                      WHERE es.EnterpriseNumber = en.EnterpriseNumber)) AS municipality,
            coalesce(c.has_email, false) AS has_email,
            coalesce(c.has_phone, false) AS has_phone,
            coalesce(c.has_website, false) AS has_website,
            c.email,
            c.phone,
            c.website,
            en.TypeOfEnterprise <> '1' AS dm_allowed_from_kbo
        FROM picked p
        JOIN enterprise en ON en.EnterpriseNumber = p.ent
        LEFT JOIN contacts c ON c.ent = p.ent
        LEFT JOIN legal_form lf ON lf.code = en.JuridicalForm
        WHERE en.Status = 'AC' AND strptime(en.StartDate, '%d-%m-%Y')::DATE >= ?::DATE
    """, [since])
    return con.execute("SELECT count(*) FROM leads").fetchone()[0]


def summary(con):
    """Leads per segment, classification and legal form type (after classify), for a quick check against the Notion figures."""
    return con.execute("""
        SELECT segment, sales_angle, mandatory, legal_form_type, count(*) AS n
        FROM leads GROUP BY ALL ORDER BY ALL
    """).fetchall()


def codes(con):
    """Each configured code with its KBO description; a missing description means a wrong code."""
    _segment_table(con)
    return con.execute("""
        SELECT s.segment, s.code, any_value(c.Description) AS description
        FROM segment s
        LEFT JOIN code c ON c.Code = s.code AND c.Category ILIKE 'Nace2025' AND c.Language = 'NL'
        GROUP BY ALL ORDER BY min(s.priority), s.code
    """).fetchall()
