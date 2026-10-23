"""Website discovery for leads.

Each candidate gets a confidence level instead of pass/fail:
- verified: the page shows the lead's enterprise number (Code of Economic Law art. III.74)
- probable: name match plus municipality, and no other enterprise number on the site
Decision of 19 October 2026: a wrong match is cheaper than a missed prospect.
Weak matches (name only) are dropped: on 100 companies they were almost all generic
domains of someone else (docs/contact-sources-measurement.md).

Only companies are searched (never sole traders, KBO direct marketing ban). Candidate
domains: the KBO website, the domain of the KBO e-mail address, and every company
name as joined, hyphen-ated and first word (wodecka.com for Wodecka Architecture), .be and .com. Results are kept in `website_matches`, so a
company is searched once; `apply` copies verified and probable matches into `leads`.
Stdlib only: DNS via getaddrinfo, pages via urllib, robots.txt respected.

Web search step for companies still without e-mail or website: export_search writes them
to JSONL, Claude searches the web with prompts/find_contacts.md (via rcpro.llm), and
import_search checks every answer itself with the same match as above (own enterprise
number, or name plus municipality) on the site and on the page Claude cites. Only answers
that pass go into `website_matches` (source web_search); Claude's word alone is never used.
"""

import http.client
import json
import re
import socket
import ssl
import unicodedata
import urllib.request
import urllib.robotparser
from concurrent.futures import ThreadPoolExecutor, as_completed
from html import unescape
from urllib.parse import urljoin, urlparse

from rcpro.llm import enterprise_number

UA = "Mozilla/5.0 (compatible; omata-research/0.1; +mailto:achilles@omata.be)"
LEGAL = r"\b(bv|bvba|srl|sprl|nv|sa|comm\s?v|scomm|vof|snc|cv|scrl|sc|vzw|asbl|ivzw)\b"
FREEMAIL = {"gmail.com", "hotmail.com", "outlook.com", "outlook.be", "hotmail.be", "live.be", "live.com", "yahoo.com",
            "yahoo.fr", "skynet.be", "telenet.be", "proximus.be", "icloud.com", "me.com", "msn.com", "gmx.com", "scarlet.be"}
PARKED = re.compile(r"domain (is )?(for sale|parked)|this domain|coming soon|under construction|binnenkort|bientôt|"
                    r"default web site page|index of /|website in opbouw|site en construction", re.IGNORECASE)
PAGE_HINT = re.compile(r"contact|privacy|legal|mention|impressum|disclaimer|over|about|propos|cookie|voorwaarden|conditions", re.IGNORECASE)
EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)*\.[a-z]{2,}", re.IGNORECASE)
KBO = re.compile(r"(?<!\d)(?:BE)?\s?([01]\d{3})[.\s]?(\d{3})[.\s]?(\d{3})(?!\d)", re.IGNORECASE)
PHONE = re.compile(r"(?<![\d+])(?:\+32|0032|0)\s?(?:\(0\)\s?)?[1-9](?:[\s./-]?\d){7,8}(?!\d)")
# ssl: we only read public pages; many small sites have broken certificates.
SSL = ssl._create_unverified_context()
NET_ERRORS = (OSError, ValueError, http.client.HTTPException)  # URLError, timeouts and SSL errors are OSError


def valid_kbo(digits):
    """Check digits: last two = 97 - (first eight mod 97). Filters out phone numbers that look like enterprise numbers."""
    return 97 - int(digits[:8]) % 97 == int(digits[8:])


def kbo_numbers(text):
    return {h for m in KBO.finditer(text) if valid_kbo(h := "".join(m.groups()))}


def phones(text):
    """Belgian numbers as +32..., 8 digits after +32 for landlines, 9 for mobiles (4xx)."""
    out = set()
    for m in PHONE.finditer(text):
        digits = re.sub(r"\D", "", m.group())
        if len(digits) == 10 and valid_kbo(digits):
            continue  # an enterprise number, not a phone (ponytail: drops 1 in 97 real 10-digit numbers)
        nsn = re.sub(r"^(0032|32)", "", digits) if m.group().startswith(("+", "00")) else digits
        nsn = nsn.removeprefix("0")
        if len(nsn) == (9 if nsn.startswith("4") else 8):
            out.add("+32" + nsn)
    return out


def emails(html, text):
    found = set(re.findall(r'mailto:([^"\'?>\s]+)', html)) | set(EMAIL.findall(text))
    found |= {v for k, v in re.findall(r'"(email)"\s*:\s*"([^"]+)"', html)}
    found = {e.replace("mailto:", "").replace("\\", "").split("%")[0].strip().lower() for e in found}
    return {e for e in found if "@" in e and not re.search(r"\.(png|jpe?g|gif|svg|webp)$|example\.|sentry|wixpress|@2x", e)}


def _words(name):
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower().replace("&", " en ")
    return re.findall(r"[a-z0-9]+", re.sub(LEGAL, " ", s))


def slugs(name):
    words = _words(name)
    return {v for v in ("".join(words), "-".join(words)) if len(v) >= 3}


def candidates(names, kbo_website, kbo_email):
    found = {}
    for w in filter(None, (kbo_website or "").split("; ")):
        if host := urlparse(w if "://" in w else "http://" + w).hostname:
            found[host.removeprefix("www.").rstrip(".")] = "kbo_web"  # KBO has values like "www.x.com."
    for e in (kbo_email or "").split("; "):
        dom = e.split("@")[-1].strip().lower().rstrip(".")
        if "@" in e and dom not in FREEMAIL:
            found.setdefault(dom, "kbo_email_domain")
    for n in names:
        words = _words(n)
        # first word alone: mostly someone else's domain, but the match gate rejects those
        for v in slugs(n) | ({words[0]} if len(words) > 1 and len(words[0]) >= 4 else set()):
            for tld in ("be", "com"):
                found.setdefault(f"{v}.{tld}", "name_guess")
    return found


def text_of(html):
    return unescape(re.sub(r"(?s)<[^>]+>", " ", re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", html)))


def match(pages, enterprise_number, names, municipality):
    """pages: {url: html}. Returns (level, emails, phones) with level verified, probable or none."""
    html = "\n".join(pages.values())
    text = text_of(html)
    found = kbo_numbers(text)
    own = enterprise_number.replace(".", "").zfill(10)
    flat = re.sub(r"[^a-z0-9]", "", unicodedata.normalize("NFKD", text.lower()).encode("ascii", "ignore").decode())
    name_hit = any(v in flat for n in names for v in slugs(n) if "-" not in v and len(v) >= 4)
    # municipality at a word start ("Gent" in "Gentbrugge", not in "agent"); postcodes are not used:
    # they match years ("since 2018") and sites often show the main postcode (7500 for Kain 7540)
    place_hit = bool(municipality and re.search(rf"\b{re.escape(municipality)}", text, re.IGNORECASE))
    if own in found:
        level = "verified"
    elif found or len(text.split()) < 40 or PARKED.search(text):
        level = "none"  # someone else's site, or nothing on it
    elif name_hit and place_hit:
        level = "probable"
    else:
        level = "none"
    return level, emails(html, text), phones(text) | {p for t in re.findall(r'tel:([^"\'>]+)', html) for p in phones(t)}


def _get(url, html_only=True):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=12, context=SSL) as r:
        if html_only and "html" not in r.headers.get("Content-Type", ""):
            return None, None
        charset = r.headers.get_content_charset() or "utf-8"
        return r.url, r.read(2_000_000).decode(charset, "ignore")


def crawl(domain):
    """Homepage plus up to six contact or legal pages it links to. None if there is no site."""
    try:
        socket.getaddrinfo(domain, 443)
    except OSError:
        return None
    for base in (f"https://{domain}/", f"https://www.{domain}/", f"http://{domain}/"):
        try:
            url, html = _get(base)
            if html is not None:
                break
        except NET_ERRORS:
            continue
    else:
        return None
    host = urlparse(url).hostname
    robots = urllib.robotparser.RobotFileParser()
    try:
        robots.parse(_get(urljoin(url, "/robots.txt"), html_only=False)[1].splitlines())
    except NET_ERRORS:
        robots.parse([])
    pages = {url: html}
    links = [urljoin(url, link) for link in re.findall(r'href=["\']([^"\'#]+)', html) if PAGE_HINT.search(link)]
    for link in [u for u in dict.fromkeys(links) if urlparse(u).hostname == host][:6]:
        if robots.can_fetch(UA, link):
            try:
                if (page := _get(link)[1]) is not None:
                    pages[link] = page
            except NET_ERRORS:
                pass
    return pages


def search_one(company):
    """company: dict with enterprise_number, names, municipality, email, website (KBO)."""
    best = ("none", None, None, set(), set())
    for domain, source in candidates(company["names"], company["website"], company["email"]).items():
        if not (pages := crawl(domain)):
            continue
        level, found_emails, found_phones = match(pages, company["enterprise_number"], company["names"], company["municipality"])
        if level == "verified":
            return level, domain, source, found_emails, found_phones
        if level == "probable" and best[0] == "none":
            best = (level, domain, source, found_emails, found_phones)
    return best


def _table(con):
    con.execute("""CREATE TABLE IF NOT EXISTS website_matches (enterprise_number VARCHAR PRIMARY KEY, level VARCHAR,
        domain VARCHAR, source VARCHAR, emails VARCHAR, phones VARCHAR, checked_at TIMESTAMP)""")


def search(con, limit=None, workers=12):
    """Search companies in `leads` not searched before, newest first. Returns {level: count}."""
    _table(con)
    rows = _companies(con, "l.enterprise_number NOT IN (SELECT enterprise_number FROM website_matches)", limit)
    counts = {}
    with ThreadPoolExecutor(workers) as ex:
        futures = {ex.submit(search_one, c): c["enterprise_number"] for c in rows}
        for f in as_completed(futures):
            level, domain, source, found_emails, found_phones = f.result()
            con.execute("INSERT OR REPLACE INTO website_matches VALUES (?, ?, ?, ?, ?, ?, now())",
                        [futures[f], level, domain, source, "; ".join(sorted(found_emails)) or None,
                         "; ".join(sorted(found_phones)) or None])
            counts[level] = counts.get(level, 0) + 1
    return counts


def apply(con):
    """Add site_level, site, site_email and site_phone to `leads` (verified and probable only)."""
    _table(con)
    site_cols = ("site_level", "site", "site_email", "site_phone")
    cols = ", ".join(f"l.{c[0]}" for c in con.execute("DESCRIBE leads").fetchall() if c[0] not in site_cols)
    con.execute(f"""
        CREATE OR REPLACE TABLE leads AS
        SELECT {cols}, w.level AS site_level, w.domain AS site, w.emails AS site_email, w.phones AS site_phone
        FROM leads l
        LEFT JOIN website_matches w ON w.enterprise_number = l.enterprise_number AND w.level IN ('verified', 'probable')
    """)


def _companies(con, where, limit=None):
    """Companies (never sole traders, never no_outreach) as dicts for search_one and check_answer."""
    rows = con.execute(f"""
        SELECT l.enterprise_number, l.municipality, l.email, l.website,
               list(DISTINCT d.Denomination) FILTER (d.Denomination IS NOT NULL) AS names
        FROM leads l
        LEFT JOIN entity e ON e.ent = l.enterprise_number
        LEFT JOIN denomination d ON d.EntityNumber = e.entity
        WHERE l.legal_form_type = 'company' AND l.sales_angle <> 'no_outreach' AND {where}
        GROUP BY ALL ORDER BY any_value(l.start_date) DESC, 1
        {"LIMIT " + str(int(limit)) if limit else ""}
    """).fetchall()
    return [dict(zip(("enterprise_number", "municipality", "email", "website", "names"), r)) for r in rows]


def _search_table(con):
    con.execute("""CREATE TABLE IF NOT EXISTS web_search (enterprise_number VARCHAR PRIMARY KEY, website VARCHAR,
        email VARCHAR, source VARCHAR, level VARCHAR, checked_at TIMESTAMP)""")


def export_search(con, path, limit=None):
    """Write companies with no e-mail and no website (KBO or found), not searched on the web in the last 30 days, to JSONL."""
    _table(con)
    _search_table(con)
    rows = con.execute(f"""
        SELECT enterprise_number, name, juridical_form_label, segment, postcode, municipality FROM leads
        WHERE legal_form_type = 'company' AND sales_angle <> 'no_outreach'
          AND email IS NULL AND website IS NULL AND site IS NULL
          -- nothing found: search again after 30 days, new companies often get a site later
          AND enterprise_number NOT IN (SELECT enterprise_number FROM web_search WHERE checked_at > now() - INTERVAL 30 DAY)
        ORDER BY start_date DESC, enterprise_number
        {"LIMIT " + str(int(limit)) if limit else ""}
    """).fetchall()
    keys = ("enterprise_number", "name", "legal_form", "segment", "postcode", "municipality")
    with open(path, "w", encoding="utf-8") as f:
        f.writelines(json.dumps(dict(zip(keys, r)), ensure_ascii=False) + "\n" for r in rows)
    return len(rows)


def check_answer(company, website, email, source):
    """Check Claude's answer ourselves. Returns (level, domain, emails, phones); level verified, probable or none."""
    ent, names, place = company["enterprise_number"], company["names"], company["municipality"]
    domain = urlparse(website if "://" in website else "http://" + website).hostname if website else None
    domain = domain.removeprefix("www.").rstrip(".") if domain else None
    site = (crawl(domain) or {}) if domain else {}
    cited = {}
    if source and source not in site:
        try:
            if (html := _get(source)[1]) is not None:  # ponytail: one page, robots.txt not checked
                cited[source] = html
        except NET_ERRORS:
            pass
    rank = {"none": 0, "probable": 1, "verified": 2}
    level, found_emails, found_phones = "none", set(), set()
    for pages in (site, cited):
        if pages:
            lvl, e, p = match(pages, ent, names, place)
            level = max(level, lvl, key=rank.get)
            found_emails |= {x for x in e if pages is site and domain and x.endswith("@" + domain)}
            found_phones |= p if pages is site else set()
            if email and email.strip().lower() in e:
                found_emails.add(email.strip().lower())
    return level, domain if site else None, found_emails, found_phones


def import_search(con, path, workers=12):
    """Store and check Claude's answers. Every line is checked; one bad line imports nothing. Returns {level: count}."""
    _table(con)
    _search_table(con)
    answers, errors = {}, []
    with open(path, encoding="utf-8") as f:
        lines = f.readlines()
    for n, line in enumerate(lines, 1):
        if not line.lstrip().startswith("{"):  # tolerate blank lines, prose and code fences
            continue
        try:
            r = json.loads(line)
            ent = enterprise_number(r["enterprise_number"])
            values = [r.get(k) for k in ("website", "email", "source")]
            if not all(isinstance(v, (str, type(None))) for v in values):
                raise ValueError("website, email and source must be strings or null")
        except (ValueError, KeyError, TypeError) as e:
            errors.append(f"line {n}: {e}")
            continue
        answers[ent] = [v.strip() or None if v else None for v in values]
    companies = {c["enterprise_number"]: c for c in _companies(con, "true")}
    errors += [f"{ent} is not a company lead" for ent in answers if ent not in companies]
    if errors:
        raise ValueError("Nothing imported:\n" + "\n".join(errors))
    counts = {}
    with ThreadPoolExecutor(workers) as ex:
        futures = {ex.submit(check_answer, companies[ent], *a): ent for ent, a in answers.items()}
        for f in as_completed(futures):
            ent = futures[f]
            level, domain, found_emails, found_phones = f.result()
            level = level if domain or found_emails else "none"  # a page about the company is not a contact
            con.execute("INSERT OR REPLACE INTO web_search VALUES (?, ?, ?, ?, ?, now())", [ent, *answers[ent], level])
            if level != "none":
                con.execute("INSERT OR REPLACE INTO website_matches VALUES (?, ?, ?, 'web_search', ?, ?, now())",
                            [ent, level, domain, "; ".join(sorted(found_emails)) or None,
                             "; ".join(sorted(found_phones)) or None])
            counts[level] = counts.get(level, 0) + 1
    return counts
