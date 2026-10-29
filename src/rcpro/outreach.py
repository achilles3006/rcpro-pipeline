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
import random
import re
import socket
import struct
import tomllib
from concurrent.futures import ThreadPoolExecutor
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


def mx_answer(resp):
    """True if a DNS response holds an MX record, False if the domain has none (or does not exist)."""
    if resp[3] & 0x0F == 3:  # NXDOMAIN
        return False
    pos, answers = 12, struct.unpack(">H", resp[6:8])[0]
    while resp[pos]:  # skip the question name
        pos += resp[pos] + 1
    pos += 5
    for _ in range(answers):
        while resp[pos] and resp[pos] < 0xC0:
            pos += resp[pos] + 1
        pos += 2 if resp[pos] else 1
        rtype, length = struct.unpack(">H", resp[pos:pos + 2])[0], struct.unpack(">H", resp[pos + 8:pos + 10])[0]
        if rtype == 15 and resp[pos + 12] != 0:  # MX, not a null MX ("." = accepts no mail, RFC 7505)
            return True
        pos += 10 + length
    return False


def has_mx(domain, resolver="1.1.1.1"):
    """Does the domain accept mail (an MX record)? None when DNS gives no answer, so it is checked again next run.
    Stdlib only: one UDP query to a public resolver. Says nothing about the mailbox itself (catch-all servers)."""
    qid = random.randrange(65536)
    query = struct.pack(">HHHHHH", qid, 0x0100, 1, 0, 0, 0) + b"".join(
        bytes([len(p)]) + p for p in domain.encode("idna").split(b".")) + b"\0" + struct.pack(">HH", 15, 1)
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.settimeout(3)
        for _ in range(2):
            try:
                s.sendto(query, (resolver, 53))
                resp = s.recv(4096)
            except OSError:
                continue
            if resp[:2] == query[:2] and resp[3] & 0x0F in (0, 3):  # ponytail: truncated (TC) answers read as-is
                return mx_answer(resp)
    return None


def _domains(value):
    return {e.split("@")[1].strip().lower() for e in (value or "").split(";") if "@" in e}


def _mx_table(con):
    con.execute("CREATE TABLE IF NOT EXISTS mx_check (domain VARCHAR PRIMARY KEY, has_mx BOOLEAN, checked DATE)")


def check_mx(con, workers=20):
    """Look up every e-mail domain in `leads` that has no stored answer yet. Returns {True: n, False: n, None: n}.
    ponytail: a domain is checked once; add a re-check age when parked domains start getting mail."""
    _mx_table(con)
    known = {r[0] for r in con.execute("SELECT domain FROM mx_check WHERE has_mx IS NOT NULL").fetchall()}
    todo = sorted({d for row in con.execute("SELECT email, site_email, deed_email FROM leads").fetchall()
                   for v in row for d in _domains(v)} - known)
    with ThreadPoolExecutor(workers) as ex:
        results = list(zip(todo, ex.map(has_mx, todo)))
    con.executemany("INSERT OR REPLACE INTO mx_check VALUES (?, ?, current_date)", results)
    counts = {}
    for _, ok in results:
        counts[ok] = counts.get(ok, 0) + 1
    return counts


def pick(addresses, suppressed=frozenset(), no_mx=frozenset()):
    """The first impersonal address (KBO, then website, then deed) as (email, source), or None."""
    found = [(e.strip().lower(), src) for src, value in zip(("kbo", "website", "deed"), addresses) for e in (value or "").split(";")]
    return next(((e, src) for e, src in found if e and impersonal(e) and e not in suppressed
                 and e.split("@")[1] not in no_mx), None)


def apply(con):
    """Add email_mx_ok (an address whose domain takes mail; null = not checked), outreach_email (the address
    the gate would use: legal person, impersonal, domain not without MX, not opted out) and personal_email
    (named addresses of those same companies: informational, never mailed) to `leads`."""
    _tables(con)
    _mx_table(con)
    mx = dict(con.execute("SELECT domain, has_mx FROM mx_check WHERE has_mx IS NOT NULL").fetchall())
    no_mx = {d for d, ok in mx.items() if not ok}
    suppressed = {r[0] for r in con.execute("SELECT email FROM suppression").fetchall()}
    blocked = {r[0] for r in con.execute("SELECT enterprise_number FROM suppression WHERE enterprise_number IS NOT NULL").fetchall()}
    rows = []
    for ent, ok_form, *addresses in con.execute(f"""
            SELECT enterprise_number, legal_form_type = 'company' AND sales_angle <> 'no_outreach'
                   AND juridical_form IN ({", ".join("?" * len(LEGAL_PERSON_FORMS))}), email, site_email, deed_email
            FROM leads""", sorted(LEGAL_PERSON_FORMS)).fetchall():
        checked = [mx[d] for v in addresses for d in _domains(v) if d in mx]
        hit = ok_form and ent not in blocked and pick(addresses, suppressed, no_mx)
        personal = sorted({e.strip().lower() for v in addresses for e in (v or "").split(";") if "@" in e and not impersonal(e)})
        rows.append((ent, any(checked) if checked else None, hit[0] if hit else None,
                     "; ".join(personal) if ok_form and personal else None))
    con.execute("""CREATE OR REPLACE TEMP TABLE mail_check (enterprise_number VARCHAR, email_mx_ok BOOLEAN,
                   outreach_email VARCHAR, personal_email VARCHAR)""")
    if rows:
        con.executemany("INSERT INTO mail_check VALUES (?, ?, ?, ?)", rows)
    added = ("email_mx_ok", "outreach_email", "personal_email")
    cols = ", ".join(f"l.{c[0]}" for c in con.execute("DESCRIBE leads").fetchall() if c[0] not in added)
    con.execute(f"""CREATE OR REPLACE TABLE leads AS SELECT {cols}, m.email_mx_ok, m.outreach_email, m.personal_email
                    FROM leads l LEFT JOIN mail_check m USING (enterprise_number)""")


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
    _mx_table(con)
    no_mx = {r[0] for r in con.execute("SELECT domain FROM mx_check WHERE NOT has_mx").fetchall()}
    out = []
    for ent, name, segment, mandatory, basis, postcode, _, *addresses in rows:
        if hit := pick(addresses, suppressed, no_mx):
            out.append({"enterprise_number": ent, "name": name, "segment": segment, "email": hit[0], "source": hit[1],
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
