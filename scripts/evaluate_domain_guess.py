"""Evaluate domain guessing: the current rcpro.websites.candidates against v2 (docs/domain-guess-v2.md).

Usage:
    python scripts/evaluate_domain_guess.py offline [--holdout]   # recall on KBO's own domains, no network
    python scripts/evaluate_domain_guess.py live [--holdout]      # v2's extra domains on leads where the current method found nothing

Every company is in a fixed half by enterprise number (`split`). Develop on dev; run --holdout once, for a
method that is fixed, so there are always leads left that no version has been tuned on.
Offline ground truth: companies started since 2023 whose KBO website or (non-free) e-mail domain is their own,
i.e. used by at most two companies (more is an accountant or a group).
"""
import hashlib
import re
import sys
import unicodedata
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse

import duckdb

from rcpro import websites as w

LEGAL = (r"\b(bv|bvba|srl|sprl|nv|sa|comm\s?v|commv|scomm|vof|snc|cv|cvba|scrl|sc|vzw|asbl|ivzw|sarl|sas|sasu|gmbh|ltd|"
         r"llc|oy|ab|spa|srls|eurl|inc|ug|ag|sl|lda)\b")
GENERIC = {"group", "groep", "groupe", "belgium", "belgie", "belgique", "belgian", "europe", "european", "international",
           "holding", "management", "consulting", "consultancy", "services", "service", "company", "solutions", "bureau",
           "studio", "atelier", "and", "en", "et", "de", "het", "la", "le", "les", "the", "van", "du", "des"}
FREE = w.FREEMAIL | {"outlook.fr", "hotmail.fr", "live.fr", "yahoo.be", "protonmail.com", "proton.me", "pandora.be",
                     "gmx.de", "gmx.net", "web.de", "orange.fr", "free.fr", "icloud.be", "googlemail.com", "hotmail.nl",
                     "outlook.nl", "aol.com", "mail.com", "laposte.net", "wanadoo.fr", "voo.be", "edpnet.be", "msn.be"}
MAILBOX = {"info", "contact", "admin", "office", "mail", "hello", "hallo", "bonjour", "secretariaat", "boekhouding",
           "administratie"}
# pattern.tld kept by greedy gain per extra domain on the first random half (seed 7) of the ground truth
V2 = {"base:joined.be", "base:joined.com", "base:hyphen.be", "base:hyphen.com", "core:joined.be", "core:joined.com",
      "first.be", "first.com", "first2.be", "first2.com", "drop_first.be", "base:joined.eu", "first.eu",
      "base:joined.net", "amp:joined.be", "amp:joined.com"}


def split(enterprise_number):
    return "holdout" if int(hashlib.md5(enterprise_number.encode()).hexdigest(), 16) % 2 else "dev"


def _words(name, amp="en"):
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower().replace("&", f" {amp} ")
    return re.findall(r"[a-z0-9]+", re.sub(LEGAL, " ", re.sub(r"[’'`]", "", s)))


def _slugs(name):
    """(pattern, slug) pairs for one name."""
    ws = _words(name)
    if not ws:
        return
    yield "base:joined", "".join(ws)
    yield "base:hyphen", "-".join(ws)
    if "&" in name:
        yield "amp:joined", "".join(_words(name, "and"))  # vetandgo.be for VET&GO
    if (core := [x for x in ws if x not in GENERIC]) and core != ws:
        yield "core:joined", "".join(core)  # it1.com for IT1 EUROPE
    if len(ws) > 1 and len(ws[0]) >= 4:
        yield "first", ws[0]
    if len(ws) > 2:
        yield "first2", "".join(ws[:2])
        yield "drop_first", "".join(ws[1:])


def mailbox_names(emails):
    """Local parts of free-mail addresses as extra names: studiopli.architecture@gmail.com -> 'studiopli architecture'."""
    out = []
    for e in emails:
        if "@" in e and e.split("@")[-1].strip().lower().rstrip(".") in FREE:
            local = re.sub(r"\d+", "", e.split("@")[0].lower())
            if local not in MAILBOX and len(local.replace(".", "")) >= 4:
                out.append(re.sub(r"[._-]", " ", local))
    return out


def v2(names, emails=()):
    out = {}
    for n in list(names) + mailbox_names(emails):
        for p, s in _slugs(n):
            for tld in ("be", "com", "eu", "net"):
                if f"{p}.{tld}" in V2 and len(s.replace("-", "")) >= 3:
                    out.setdefault(f"{s}.{tld}", f"{p}.{tld}")
    return out


def _registrable(host):
    parts = host.lower().strip(".").removeprefix("www.").split(".")
    return ".".join(parts[-3:] if len(parts) > 2 and parts[-2] in ("co", "com", "org") else parts[-2:])


def ground_truth(con):
    rows = con.execute("""
        WITH ents AS (SELECT EnterpriseNumber e FROM enterprise
                      WHERE TypeOfEnterprise = '2' AND strptime(StartDate, '%d-%m-%Y') >= DATE '2023-01-01')
        SELECT x.ent, list(DISTINCT d.Denomination) FILTER (d.Denomination IS NOT NULL),
               list(DISTINCT k.ContactType || '|' || k.Value) FILTER (k.ContactType IN ('WEB', 'EMAIL'))
        FROM ents JOIN entity x ON x.ent = ents.e
        LEFT JOIN denomination d ON d.EntityNumber = x.entity
        LEFT JOIN contact k ON k.EntityNumber = x.entity
        GROUP BY 1""").fetchall()
    out = []
    for en, names, contacts in rows:
        doms, emails = set(), []
        for c in contacts or []:
            kind, v = c.split("|", 1)
            if kind == "WEB" and (h := urlparse(v if "://" in v else "http://" + v).hostname) and "." in h:
                doms.add(_registrable(h))
            elif kind == "EMAIL" and "@" in v:
                emails.append(v)
                if (d := v.split("@")[-1].strip().lower().rstrip(".")) not in FREE and "." in d:
                    doms.add(_registrable(d))
        if doms and names:
            out.append((en, names, emails, doms))
    used = Counter(d for *_, doms in out for d in doms)
    return [(en, n, e, {d for d in doms if used[d] <= 2}) for en, n, e, doms in out if any(used[d] <= 2 for d in doms)]


def offline(con, half):
    truth = [t for t in ground_truth(con) if split(t[0]) == half]
    free = [t for t in truth if mailbox_names(t[2])]
    for label, rs in (("all", truth), ("has a free-mail address", free)):
        for method, gen in (("current", lambda n, e: w.candidates(n, None, None)), ("v2", v2)):
            found = [set(gen(n, e)) for _, n, e, _ in rs]
            recall = sum(bool(f & doms) for f, (*_, doms) in zip(found, rs)) / len(rs)
            print(f"{label:24s} n={len(rs):6d}  {method:8s} recall {recall:.3f}  domains/company {sum(map(len, found)) / len(rs):.1f}")


def live(con, half):
    """Only domains v2 adds; companies where the current method found nothing (website_matches level none)."""
    cos = [c for c in w._companies(con, "l.enterprise_number IN (SELECT enterprise_number FROM website_matches WHERE level = 'none')")
           if split(c["enterprise_number"]) == half]

    def one(c):
        old = set(w.candidates(c["names"], c["website"], c["email"]))
        new = {d: p for d, p in v2(c["names"], (c["email"] or "").split("; ")).items() if d not in old}
        for d, p in new.items():
            if pages := w.crawl(d):
                level, *_ = w.match(pages, c["enterprise_number"], c["names"], c["municipality"])
                if level != "none":
                    return c["enterprise_number"], d, p, level
        return None

    with ThreadPoolExecutor(16) as ex:
        hits = [h for h in ex.map(one, cos) if h]
    print(f"{len(cos)} companies, {len(hits)} new sites")
    for h in hits:
        print(*h, sep="\t")


if __name__ == "__main__":
    con = duckdb.connect("data/kbo.duckdb", read_only=True)
    {"offline": offline, "live": live}[sys.argv[1]](con, "holdout" if "--holdout" in sys.argv else "dev")
