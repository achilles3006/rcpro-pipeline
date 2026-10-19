"""Measure contact sources outside KBO on a random sample of 100 companies.

Usage: python scripts/measure_contact_sources.py <kbo.duckdb> <out_dir>
Needs dnspython, phonenumbers, httpx and the `whois` CLI. Writes candidates.csv (one row per domain tried), results.csv (one row per company).
"""
import csv
import json
import random
import re
import subprocess
import sys
import time
import unicodedata
import urllib.robotparser
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from html import unescape
from pathlib import Path
from urllib.parse import urljoin, urlparse

import dns.resolver
import duckdb
import httpx
import phonenumbers

DB, OUT = sys.argv[1], Path(sys.argv[2])
OUT.mkdir(exist_ok=True)
UA = "Mozilla/5.0 (compatible; omata-research/0.1; +mailto:achilles@omata.be)"
LEGAL = r"\b(bv|bvba|srl|sprl|nv|sa|comm\s?v|scomm|vof|snc|cv|scrl|sc|vzw|asbl|ivzw|bureau|studio|atelier|office)\b"
PARKED = re.compile(r"domain (is )?(for sale|parked)|this domain|coming soon|under construction|binnenkort|bientôt|"
                    r"default web site page|index of /|website in opbouw|site en construction|parked free", re.I)
PAGE_HINT = re.compile(r"contact|privacy|legal|mention|impressum|disclaimer|over|about|propos|cookie|voorwaarden|conditions", re.I)
EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)*\.[a-z]{2,}", re.I)
KBO = re.compile(r"(?<!\d)(?:BE)?\s?([01]\d{3})[.\s]?(\d{3})[.\s]?(\d{3})(?!\d)", re.I)


def sample(con):
    rows = con.execute("""
        SELECT enterprise_number, start_date, segment, name, postcode, municipality, email, phone, website
        FROM leads WHERE legal_form_type = 'company' AND sales_angle = 'legal_obligation'
          AND mandatory IN ('yes', 'likely') ORDER BY enterprise_number
    """).fetchall()
    cols = ["enterprise_number", "start_date", "segment", "name", "postcode", "municipality", "kbo_email", "kbo_phone", "kbo_website"]
    picked = random.Random(42).sample(rows, 100)
    return [dict(zip(cols, r)) for r in picked], len(rows)


def names(con, ent):
    return [r[0] for r in con.execute("""
        SELECT DISTINCT d.Denomination FROM denomination d
        WHERE d.EntityNumber = ? OR d.EntityNumber IN (SELECT EstablishmentNumber FROM establishment WHERE EnterpriseNumber = ?)
    """, [ent, ent]).fetchall()]


def slug_variants(name):
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"&", " en ", s)
    s = re.sub(LEGAL, " ", s)
    words = re.findall(r"[a-z0-9]+", s)
    if not words:
        return set()
    out = {"".join(words), "-".join(words)}
    if len(words) > 1 and len(words[0]) >= 4:
        out.add(words[0])  # ponytail: first word alone is noisy; only verified matches count
    return {v for v in out if len(v) >= 3}


def candidates(company, all_names):
    found = {}
    if company["kbo_website"]:
        for w in company["kbo_website"].split("; "):
            host = urlparse(w if "://" in w else "http://" + w).hostname
            if host:
                found[host.removeprefix("www.")] = "kbo_web"
    if company["kbo_email"]:
        for e in company["kbo_email"].split("; "):
            dom = e.split("@")[-1].lower().strip()
            if dom and dom not in FREEMAIL:
                found.setdefault(dom, "kbo_email_domain")
    for n in all_names:
        for v in slug_variants(n):
            for tld in ("be", "com"):
                found.setdefault(f"{v}.{tld}", "name_guess")
    return found


FREEMAIL = {"gmail.com", "hotmail.com", "outlook.com", "outlook.be", "hotmail.be", "live.be", "live.com", "yahoo.com",
            "yahoo.fr", "skynet.be", "telenet.be", "proximus.be", "icloud.com", "me.com", "msn.com", "gmx.com", "scarlet.be"}


def dns_check(domain):
    r = dns.resolver.Resolver()
    r.lifetime = 5
    out = {}
    for rr in ("A", "MX"):
        try:
            out[rr] = [str(x) for x in r.resolve(domain, rr)]
        except Exception:
            out[rr] = []
    return out


def registered(domain):
    try:
        if domain.endswith(".be"):
            txt = subprocess.run(["whois", "-h", "whois.dns.be", domain], capture_output=True, text=True, timeout=20).stdout
            m = re.search(r"Registered:\s*\w{3} (\w{3} \d{1,2} \d{4})", txt)
            return datetime.strptime(m.group(1), "%b %d %Y").date() if m else None
        r = httpx.get(f"https://rdap.org/domain/{domain}", timeout=15, follow_redirects=True)
        for ev in r.json().get("events", []):
            if ev.get("eventAction") == "registration":
                return datetime.fromisoformat(ev["eventDate"][:10]).date()
    except Exception:
        return None


def text_of(html):
    html = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", html)
    return unescape(re.sub(r"(?s)<[^>]+>", " ", html))


def crawl(domain):
    """Homepage plus up to 6 legal/contact pages. Respects robots.txt."""
    with httpx.Client(headers={"User-Agent": UA}, timeout=12, follow_redirects=True, verify=False) as c:
        home = None
        for base in (f"https://{domain}/", f"https://www.{domain}/", f"http://{domain}/"):
            try:
                home = c.get(base)
                if home.status_code < 400 and "html" in home.headers.get("content-type", ""):
                    break
                home = None
            except Exception:
                continue
        if home is None:
            return None
        root = f"{home.url.scheme}://{home.url.host}/"
        rp = urllib.robotparser.RobotFileParser()
        try:
            rp.parse(c.get(urljoin(root, "/robots.txt")).text.splitlines())
        except Exception:
            rp.parse([])
        pages = {str(home.url): home.text}
        links = re.findall(r'href=["\']([^"\'#]+)', home.text)
        hinted = [urljoin(str(home.url), l) for l in links if PAGE_HINT.search(l)]
        hinted = [u for u in dict.fromkeys(hinted) if urlparse(u).hostname == home.url.host][:6]
        for u in hinted:
            if not rp.can_fetch(UA, u):
                continue
            try:
                r = c.get(u)
                if r.status_code < 400 and "html" in r.headers.get("content-type", ""):
                    pages[u] = r.text
            except Exception:
                pass
        return {"final_host": home.url.host, "pages": pages}


def norm_phone(raw):
    out = set()
    for m in phonenumbers.PhoneNumberMatcher(raw, "BE"):
        out.add(phonenumbers.format_number(m.number, phonenumbers.PhoneNumberFormat.E164))
    return out


def valid_kbo(digits):
    """Enterprise number check digits: last two = 97 - (first eight mod 97). Filters out 04xx mobile numbers."""
    return 97 - int(digits[:8]) % 97 == int(digits[8:])


def analyse(domain, site, company, all_names):
    html = "\n".join(site["pages"].values())
    text = text_of(html)
    ent_digits = company["enterprise_number"].replace(".", "")
    kbo_hits = {h for m in KBO.finditer(text) if valid_kbo(h := "".join(m.groups()))}
    has_own = ent_digits in kbo_hits or ent_digits.lstrip("0") in {h.lstrip("0") for h in kbo_hits}
    other_kbo = sorted(h for h in kbo_hits if h.lstrip("0") != ent_digits.lstrip("0"))
    low = text.lower()
    name_hit = any(v in re.sub(r"[^a-z0-9]", "", unicodedata.normalize("NFKD", low).encode("ascii", "ignore").decode())
                   for n in all_names for v in slug_variants(n) if "-" not in v and len(v) >= 4)
    place_hit = bool(company["postcode"] and company["postcode"] in text) or bool(
        company["municipality"] and company["municipality"].lower() in low)
    emails = {e.lower() for e in re.findall(r'mailto:([^"\'?>\s]+)', html)} | {e.lower() for e in EMAIL.findall(text)}
    emails = {e.split("%")[0].strip() for e in emails}
    emails = {e for e in emails if "@" in e and not re.search(r"\.(png|jpe?g|gif|svg|webp)$|example\.|sentry|wixpress|@2x", e)}
    phones = set()
    for m in re.findall(r'tel:([^"\'>]+)', html):
        phones |= norm_phone(m)
    phones |= norm_phone(text)
    jsonld = re.findall(r'(?is)<script[^>]+ld\+json[^>]*>(.*?)</script>', html)
    for blob in jsonld:
        for k, v in re.findall(r'"(email|telephone)"\s*:\s*"([^"]+)"', blob):
            if k == "telephone":
                phones |= norm_phone(v)
            elif "@" in v:
                emails.add(v.replace("mailto:", "").lower())
    emails = {e.replace("\\", "") for e in emails}
    parked = len(text.split()) < 40 or bool(PARKED.search(text))
    if has_own:
        level = "verified"
    elif other_kbo:
        level = "other_company"  # page names a different enterprise number: almost surely not ours
    elif parked:
        level = "parked"
    elif name_hit and place_hit:
        level = "probable"
    elif name_hit:
        level = "weak"
    else:
        level = "no_match"
    return {"level": level, "pages": len(site["pages"]), "final_host": site["final_host"],
            "other_kbo": " ".join(other_kbo[:3]), "emails": "; ".join(sorted(emails)), "phones": "; ".join(sorted(phones))}


def mx_ok(email):
    try:
        dns.resolver.resolve(email.split("@")[1], "MX", lifetime=5)
        return True
    except Exception:
        return False


def run_company(company, all_names):
    rows = []
    for domain, source in candidates(company, all_names).items():
        d = dns_check(domain)
        row = {"enterprise_number": company["enterprise_number"], "domain": domain, "source": source,
               "has_a": bool(d["A"]), "has_mx": bool(d["MX"]), "level": "no_dns"}
        if d["A"]:
            site = crawl(domain)
            row.update(analyse(domain, site, company, all_names) if site else {"level": "no_http"})
        rows.append(row)
    return rows


def main():
    con = duckdb.connect(DB, read_only=True)
    comps, population = sample(con)
    all_names = {c["enterprise_number"]: names(con, c["enterprise_number"]) for c in comps}
    con.close()
    with ThreadPoolExecutor(12) as ex:
        per = list(ex.map(lambda c: run_company(c, all_names[c["enterprise_number"]]), comps))
    start = {c["enterprise_number"]: c["start_date"] for c in comps}
    for rows in per:
        for r in rows:
            r["registered"] = r["days_after_start"] = ""
            if r["level"] in ("verified", "probable", "other_company") or (r["has_mx"] and r["source"] != "name_guess"):
                reg = registered(r["domain"])
                time.sleep(4)
                if reg:
                    r["registered"], r["days_after_start"] = reg.isoformat(), (reg - start[r["enterprise_number"]]).days
    cand = [r for rows in per for r in rows]
    keys = sorted({k for r in cand for k in r}, key=lambda k: list(cand[0]).index(k) if k in cand[0] else 99)
    with open(OUT / "candidates.csv", "w", newline="") as f:
        w = csv.DictWriter(f, keys)
        w.writeheader()
        w.writerows(cand)
    order = ["verified", "probable", "weak", "other_company", "parked", "no_match", "no_http", "no_dns"]
    results = []
    for c, rows in zip(comps, per):
        best = min(rows, key=lambda r: order.index(r["level"])) if rows else {"level": "no_candidates"}
        usable = best if best["level"] in ("verified", "probable") else {}
        emails = [e for e in usable.get("emails", "").split("; ") if e]
        results.append({**{k: c[k] for k in ("enterprise_number", "start_date", "segment", "name", "postcode", "municipality",
                                            "kbo_email", "kbo_phone", "kbo_website")},
                        "names": " | ".join(all_names[c["enterprise_number"]]),
                        "best_level": best["level"], "best_domain": best.get("domain", ""), "best_source": best.get("source", ""),
                        "domain_registered": best.get("registered", ""), "days_after_start": best.get("days_after_start", ""),
                        "mx_only_domains": "; ".join(r["domain"] for r in rows if r["has_mx"] and not r["has_a"]),
                        "site_emails": "; ".join(emails), "site_emails_mx_ok": all(mx_ok(e) for e in emails) if emails else "",
                        "site_phones": usable.get("phones", "")})
    with open(OUT / "results.csv", "w", newline="") as f:
        w = csv.DictWriter(f, list(results[0]))
        w.writeheader()
        w.writerows(results)
    json.dump({"population": population}, open(OUT / "meta.json", "w"))
    print(f"population {population}, sample {len(comps)}, candidates {len(cand)}")


if __name__ == "__main__":
    import warnings
    warnings.filterwarnings("ignore")
    main()
