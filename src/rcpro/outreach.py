"""Compliance gate for the first e-mail: who may be mailed, the mail text, opt-outs and a log.

A lead is exported only when every rule below holds (see docs/outreach-legal.md):
- a legal person (company form with legal personality), never a sole trader: art. XII.13 WER and
  KB 4 April 2003 allow advertising e-mail without consent only to legal persons on impersonal addresses;
- the address (from KBO, the own website or the founding deed) is impersonal (info@, contact@, ...), so no personal data is used: this keeps KB 18 July 2008
  art. 2 (no KBO personal data for direct marketing) and the GDPR out of the way;
- sales_angle is not no_outreach, the address is not on the suppression list, the company was never exported.
Every exported row is logged in `outreach_log` (who, which address, from which source, when).
"""

import csv
import re
import tomllib
from datetime import date
from pathlib import Path

TEMPLATES = Path(__file__).resolve().parents[2] / "templates"

# KBO JuridicalForm codes with legal personality: BV, CommV, VOF, NV, CV, VZW, IVZW, private foundation.
# Left out on purpose: 721 (no legal personality), 003 (VAT unit), 030 (foreign entity, unclear), 070.
LEGAL_PERSON_FORMS = {"610", "612", "011", "014", "706", "017", "125", "026"}

# Local parts that name a role, not a person. ponytail: allowlist, so a new generic word is skipped until added here.
IMPERSONAL = {
    "info", "contact", "hello", "hallo", "office", "admin", "administratie", "administration", "mail", "bureau",
    "kantoor", "studio", "atelier", "secretariaat", "secretariat", "onthaal", "accueil", "welkom", "bonjour",
    "team", "sales", "support", "boekhouding", "compta", "comptabilite", "direction", "directie", "projects",
    "projecten", "projets", "architecten", "architectes", "architects", "architect", "architecte",
}

PILOT = ("architects", "interior_architects")  # docs/decisions.md: the pilot starts with these two

LAW = {  # legal_basis (classify.py) -> how the mail names it
    "Act of 9 May 2019": {"nl": "de wet van 9 mei 2019", "fr": "la loi du 9 mai 2019"},
    "Act of 17 March 2019, art. 44": {"nl": "artikel 44 van de wet van 17 maart 2019",
                                      "fr": "l'article 44 de la loi du 17 mars 2019"},
}


def impersonal(email):
    m = re.fullmatch(r"([^@\s]+)@[^@\s]+\.[a-z]{2,}", email.strip().lower())
    return bool(m) and m.group(1) in IMPERSONAL


def language(postcode):
    """French for Brussels and Wallonia, Dutch elsewhere. ponytail: Brussels gets French; add a language column if replies say otherwise."""
    try:
        pc = int(postcode)
    except (TypeError, ValueError):
        return "nl"
    return "fr" if 1000 <= pc <= 1499 or 4000 <= pc <= 7999 else "nl"


def _tables(con):
    con.execute("CREATE TABLE IF NOT EXISTS suppression (email VARCHAR, enterprise_number VARCHAR, reason VARCHAR, added DATE)")
    con.execute("""CREATE TABLE IF NOT EXISTS outreach_log (enterprise_number VARCHAR, email VARCHAR, source VARCHAR,
                   template VARCHAR, exported_on DATE)""")


def optout(con, email, reason="opt-out"):
    """Suppress an address and every company that uses it. Takes effect on the next export."""
    _tables(con)
    email = email.strip().lower()
    ents = [r[0] for r in con.execute("""
        SELECT enterprise_number FROM leads
        WHERE list_contains(list_transform(string_split(lower(coalesce(email, '')), ';'), x -> trim(x)), ?)
           OR list_contains(list_transform(string_split(lower(coalesce(site_email, '') || ';' || coalesce(deed_email, '')), ';'),
                            x -> trim(x)), ?)""", [email, email]).fetchall()]
    for ent in ents or [None]:
        con.execute("INSERT INTO suppression VALUES (?, ?, ?, ?)", [email, ent, reason, date.today()])
    return len(ents)


def sender():
    """templates/sender.toml; refuses to run while any field is empty or still TODO (FSMA number, privacy link, ...)."""
    s = tomllib.loads((TEMPLATES / "sender.toml").read_text(encoding="utf-8"))
    if missing := [k for k, v in s.items() if not str(v).strip() or "TODO" in str(v)]:
        raise SystemExit(f"Fill in templates/sender.toml first: {', '.join(missing)}")
    return s


def candidates(con, segments=PILOT):
    _tables(con)
    rows = con.execute(f"""
        SELECT enterprise_number, name, segment, mandatory, legal_basis, postcode, juridical_form, email, site_email, deed_email
        FROM leads
        WHERE legal_form_type = 'company' AND sales_angle <> 'no_outreach'
          AND juridical_form IN ({", ".join("?" * len(LEGAL_PERSON_FORMS))})
          AND segment IN ({", ".join("?" * len(segments))})
          AND enterprise_number NOT IN (SELECT enterprise_number FROM outreach_log)
          AND enterprise_number NOT IN (SELECT enterprise_number FROM suppression WHERE enterprise_number IS NOT NULL)
        ORDER BY start_date DESC, enterprise_number
    """, [*sorted(LEGAL_PERSON_FORMS), *segments]).fetchall()
    suppressed = {r[0] for r in con.execute("SELECT email FROM suppression").fetchall()}
    out = []
    for ent, name, segment, mandatory, basis, postcode, _, *addresses in rows:
        found = [(e.strip().lower(), src) for src, value in zip(("kbo", "website", "deed"), addresses) for e in (value or "").split(";")]
        found = [(e, src) for e, src in found if e and impersonal(e) and e not in suppressed]
        if found:
            out.append({"enterprise_number": ent, "name": name, "segment": segment, "email": found[0][0], "source": found[0][1],
                            "lang": language(postcode), "legal": mandatory == "yes" and basis in LAW, "legal_basis": basis})
    return out


def render(lead, s):
    """(template name, subject, body) for one lead. The law is cited only when the obligation is settled (mandatory = yes)."""
    name = f"{lead['lang']}_{'legal' if lead['legal'] else 'commercial'}"
    subject, body = (TEMPLATES / f"{name}.txt").read_text(encoding="utf-8").split("\n", 1)
    source = {"nl": {"kbo": "de Kruispuntbank van Ondernemingen", "website": "uw website",
                     "deed": "uw oprichtingsakte in het Belgisch Staatsblad"},
              "fr": {"kbo": "la Banque-Carrefour des Entreprises", "website": "votre site web",
                     "deed": "votre acte de constitution au Moniteur belge"}}[lead["lang"]][lead["source"]]
    values = {**s, "company": lead["name"] or "", "source": source,
              "law": LAW.get(lead["legal_basis"], {}).get(lead["lang"], "")}
    return name, subject.removeprefix("Subject: ").format(**values), body.strip().format(**values)


def export(con, path, limit=50, segments=PILOT):
    """Write today's mails to a CSV for sending one by one, and log them. Returns the number written."""
    s = sender()
    picked = candidates(con, segments)[:limit]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["enterprise_number", "company", "segment", "to", "source", "subject", "body"])
        for lead in picked:
            name, subject, body = render(lead, s)
            w.writerow([lead["enterprise_number"], lead["name"], lead["segment"], lead["email"], lead["source"], subject, body])
            con.execute("INSERT INTO outreach_log VALUES (?, ?, ?, ?, ?)",
                        [lead["enterprise_number"], lead["email"], lead["source"], name, date.today()])
    return len(picked)
