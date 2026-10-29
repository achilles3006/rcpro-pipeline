"""Founding deeds from the annexes of the Belgisch Staatsblad (docs/enrichment-options.md, section 1).

fetch: for companies in `leads` (never sole traders, never no_outreach) not fetched before,
engineers the codes left unknown first, then newest first, read the publication list on ejustice, take the PDF under RUBRIEK
OPRICHTING / RUBRIQUE CONSTITUTION and keep its text (pdftotext) in `deeds`. A company
without a founding deed gets a row too; it is retried weekly until 60 days after its start date.
Rate limit: 1 request per 5 seconds; HTTP 429 came after about 50 requests at 1/s.

LLM step, run by hand in Claude Code (no API key), like classify: export_deeds writes deed
text to JSONL, Claude answers with prompts/extract_deeds.md, import_deeds stores the answers
in `deed_extraction`. classify uses construction_related as evidence for engineers the rules
left unknown; apply adds founders and activity_summary to `leads`.
Founder names are personal data (docs/open-questions.md, question 2): stored, not for outreach yet.

contacts: the company's own e-mail address and website, which the articles may state (art. 2:31 WVV / CSA).
Only values right after such a clause count, so the notary's, the accountant's and the partners' addresses
("e-mailadres voor kennisgevingen") stay out. No LLM: a regex on the stored text.
"""

import json
import re
import subprocess
import time
import urllib.error
import urllib.request
from datetime import date
from html import unescape

from rcpro.llm import enterprise_number
from rcpro.websites import EMAIL

BASE = "https://www.ejustice.just.fgov.be"
LIST = BASE + "/cgi_tsv/list.pl?language=nl&btw={}&page=1&la_search=f&view_numac="
UA = "Mozilla/5.0 (compatible; omata-research/0.1; +mailto:achilles@omata.be)"
FOUNDING = re.compile(r"OPRICHTING|CONSTITUTION|GR\S{1,2}NDUNG", re.IGNORECASE)
DELAY = 5.0
_last = 0.0
# "L'adresse électronique de la société est : x@y.be", "E-mailadres: info@x.be", "Le site internet de la société est www.x.be"
CLAUSE = re.compile(r"(?i)(adresse\s+(?:électronique|e-?mail|mail)|courriel|e-?mail(?:adres)?|site\s+internet|website)"
                    r"([^@]{0,60}?)(" + EMAIL.pattern + r"|(?:https?://)?www\.[\w-]+(?:\.[\w-]+)*\.[a-z]{2,}|https?://[\w.-]+\.[a-z]{2,})")
NOT_COMPANY = re.compile(r"(?i)kennisgeving|notification|geboren|née?\b|wonende|domicili")
THIRD_PARTY = re.compile(r"(?i)notai?r|naban|fednot|izimi|belgium\.be|fgov\.be|staatsblad|moniteur")


def contacts(text):
    """(emails, websites) the deed gives as the company's own, each a sorted list."""
    emails, sites = set(), set()
    for m in CLAUSE.finditer(text or ""):
        value = m.group(3).lower().rstrip(".")
        if NOT_COMPANY.search(m.group(2)) or THIRD_PARTY.search(value):
            continue
        if "@" in value:
            emails.add(value)
        else:
            sites.add(re.sub(r"^https?://", "", value).removeprefix("www.").split("/")[0])
    return sorted(emails), sorted(sites)


def founding_pdf(html):
    """(pdf_url, published) of the founding publication in a list page, or (None, None)."""
    for item in re.split(r'class="list-item"', html)[1:]:
        text = unescape(re.sub(r"<[^>]+>", " ", item))
        pdf = re.search(r'href="(/tsv_pdf/[^"]+\.pdf)"', item)
        if pdf and FOUNDING.search(text):
            day = re.search(r"(\d{4}-\d{2}-\d{2}) /", text)
            return BASE + pdf.group(1), date.fromisoformat(day.group(1)) if day else None
    return None, None


def _get(url, tries=4):
    """GET with 1 request per DELAY seconds; on 429 wait 1, 2, 4 minutes, then give up."""
    global _last
    for attempt in range(tries):
        time.sleep(max(0, _last + DELAY - time.monotonic()))
        _last = time.monotonic()
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=30) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code != 429 or attempt == tries - 1:
                raise
            time.sleep(60 * 2 ** attempt)


def pdf_text(data):
    return subprocess.run(["pdftotext", "-q", "-", "-"], input=data, capture_output=True, check=True).stdout.decode("utf-8", "ignore")


def fetch_one(enterprise_number):
    """(pdf_url, published, text) for one company; text is None for a scan without a text layer."""
    raw = _get(LIST.format(enterprise_number.replace(".", "")))
    url, published = founding_pdf(raw.decode("latin-1"))  # only ASCII markers are parsed
    if not url:
        return None, None, None
    return url, published, pdf_text(_get(url)).strip() or None


def tables(con):
    con.execute("""CREATE TABLE IF NOT EXISTS deeds (enterprise_number VARCHAR PRIMARY KEY, pdf_url VARCHAR,
        published DATE, text VARCHAR, fetched_at TIMESTAMP)""")
    con.execute("""CREATE TABLE IF NOT EXISTS deed_extraction (enterprise_number VARCHAR PRIMARY KEY,
        founders STRUCT(name VARCHAR, role VARCHAR)[], activity_summary VARCHAR, construction_related VARCHAR,
        evidence VARCHAR, extracted_at TIMESTAMP)""")


def fetch(con, limit=None, mailable=False):
    """Fetch deeds for companies not fetched before, newest first; with `mailable`, only companies with an
    outreach_email. Returns {found|no_deed|no_text|error: count}."""
    tables(con)
    rows = con.execute(f"""
        SELECT enterprise_number FROM leads
        WHERE legal_form_type = 'company' AND sales_angle <> 'no_outreach'
          {"AND outreach_email IS NOT NULL" if mailable else ""}
          -- a deed is published days to weeks after the start: retry "no deed" weekly for 60 days
          -- (ponytail: fixed windows, measure the real publication lag when there is more data)
          AND enterprise_number NOT IN (SELECT d.enterprise_number FROM deeds d JOIN leads l USING (enterprise_number)
                                        WHERE d.pdf_url IS NOT NULL OR d.fetched_at > l.start_date + INTERVAL 60 DAY
                                           OR d.fetched_at > now() - INTERVAL 7 DAY)
        -- mailable companies first (their deed is read before contact), then engineers without code evidence:
        -- the purpose clause is the best evidence for them
        ORDER BY outreach_email IS NOT NULL DESC, segment = 'engineers' AND (mandatory = 'unknown' OR evidence[1] LIKE 'llm:%') DESC,
                 start_date DESC, enterprise_number
        {"LIMIT " + str(int(limit)) if limit else ""}
    """).fetchall()
    counts = {}
    for (ent,) in rows:
        try:
            url, published, text = fetch_one(ent)
        except (OSError, ValueError, subprocess.CalledProcessError) as e:
            print(f"{ent}: {e}")  # not stored, retried next run
            counts["error"] = counts.get("error", 0) + 1
            continue
        con.execute("INSERT OR REPLACE INTO deeds VALUES (?, ?, ?, ?, now())", [ent, url, published, text])
        status = "found" if text else "no_text" if url else "no_deed"
        counts[status] = counts.get(status, 0) + 1
    return counts


def export_deeds(con, path, max_chars=20000):
    """Write deeds with text that Claude has not read yet to JSONL. Companies only."""
    tables(con)
    rows = con.execute("""
        SELECT d.enterprise_number, l.name, l.segment, d.text
        FROM deeds d JOIN leads l USING (enterprise_number)
        WHERE l.legal_form_type = 'company' AND d.text IS NOT NULL
          AND d.enterprise_number NOT IN (SELECT enterprise_number FROM deed_extraction)
        ORDER BY 1
    """).fetchall()
    with open(path, "w", encoding="utf-8") as f:
        # ponytail: purpose clause and founders sit in the first pages; raise max_chars if answers miss them
        f.writelines(json.dumps({"enterprise_number": ent, "name": name, "segment": seg, "text": text[:max_chars]},
                                ensure_ascii=False) + "\n" for ent, name, seg, text in rows)
    return len(rows)


def import_deeds(con, path):
    """Store Claude's answers. Every line is checked; one bad line imports nothing."""
    tables(con)
    known = {r[0] for r in con.execute("SELECT enterprise_number FROM deeds WHERE text IS NOT NULL").fetchall()}
    rows, errors = [], []
    with open(path, encoding="utf-8") as f:
        lines = f.readlines()
    for n, line in enumerate(lines, 1):
        if not line.lstrip().startswith("{"):  # tolerate blank lines and code fences
            continue
        try:
            r = json.loads(line)
            ent, related = enterprise_number(r["enterprise_number"]), r["construction_related"]
            founders, summary, evidence = r.get("founders") or [], r.get("activity_summary"), r.get("evidence")
            if ent not in known:
                raise ValueError(f"{ent} has no deed text")
            if related not in ("yes", "no", "unknown"):
                raise ValueError(f"bad construction_related {related!r}")
            if not isinstance(founders, list) or not all(
                    isinstance(p, dict) and isinstance(p.get("name"), str) and isinstance(p.get("role"), (str, type(None)))
                    for p in founders):
                raise ValueError("founders must be a list of {name, role}")
            if not all(isinstance(v, (str, type(None))) for v in (summary, evidence)):
                raise ValueError("activity_summary and evidence must be strings")
        except (ValueError, KeyError, TypeError) as e:
            errors.append(f"line {n}: {e}")
            continue
        founders = [{"name": p["name"], "role": p.get("role")} for p in founders]
        rows.append((ent, founders, summary, related if evidence else "unknown", evidence or None))
    if errors:
        raise ValueError("Nothing imported:\n" + "\n".join(errors))
    con.executemany("INSERT OR REPLACE INTO deed_extraction VALUES (?, ?, ?, ?, ?, now())", rows)
    return len(rows)


def apply(con):
    """Add founders ("Name (role); ..."), activity_summary, deed_email, deed_website and deed_url (the founding
    deed PDF) to `leads`, for companies only."""
    tables(con)
    con.execute("CREATE OR REPLACE TEMP TABLE deed_contacts (enterprise_number VARCHAR, email VARCHAR, website VARCHAR)")
    found = [(ent, *contacts(text)) for ent, text in con.execute("SELECT enterprise_number, text FROM deeds WHERE text IS NOT NULL").fetchall()]
    if rows := [(ent, "; ".join(e) or None, "; ".join(s) or None) for ent, e, s in found if e or s]:
        con.executemany("INSERT INTO deed_contacts VALUES (?, ?, ?)", rows)
    cols = ", ".join(f"l.{c[0]}" for c in con.execute("DESCRIBE leads").fetchall()
                     if c[0] not in ("founders", "activity_summary", "deed_email", "deed_website", "deed_url"))
    con.execute(f"""
        CREATE OR REPLACE TABLE leads AS
        SELECT {cols},
               CASE WHEN l.legal_form_type = 'company' THEN nullif(array_to_string(list_transform(x.founders,
                   p -> p.name || coalesce(' (' || p.role || ')', '')), '; '), '') END AS founders,
               CASE WHEN l.legal_form_type = 'company' THEN x.activity_summary END AS activity_summary,
               CASE WHEN l.legal_form_type = 'company' THEN dc.email END AS deed_email,
               CASE WHEN l.legal_form_type = 'company' THEN dc.website END AS deed_website,
               CASE WHEN l.legal_form_type = 'company' THEN d.pdf_url END AS deed_url
        FROM leads l LEFT JOIN deed_extraction x ON x.enterprise_number = l.enterprise_number
        LEFT JOIN deed_contacts dc ON dc.enterprise_number = l.enterprise_number
        LEFT JOIN deeds d ON d.enterprise_number = l.enterprise_number
    """)
