"""Command line: python -m rcpro <run|full|update|leads|websites|staatsblad|view|codes|export-...|import-...> ...

Everything in one go (load, leads, websites, Staatsblad, the Claude steps, then the page):
    python -m rcpro run data/KboOpenData_0518_*_Update.zip [--since 2025-10-01] [--limit 100] [--no-claude]

Single steps:
    python -m rcpro full data/KboOpenData_0517_2026_10_19_Full.zip
    python -m rcpro update data/KboOpenData_0518_*_Update.zip
    python -m rcpro leads --since 2025-10-01 [--csv data/leads.csv]
    python -m rcpro websites [--limit 200]        # search company websites, newest first, each once
    python -m rcpro staatsblad [--limit 20]       # founding deeds from the Staatsblad, newest first, each once (1 request / 5 s)
    python -m rcpro view                          # leads as a filterable table in the browser
    python -m rcpro codes

Claude steps one by one (`run` does these with `claude -p`; see README):
    python -m rcpro export-unknown data/unknown.jsonl
    python -m rcpro import-llm data/llm.jsonl     # then run `leads` again
    python -m rcpro export-deeds data/deeds.jsonl
    python -m rcpro import-deeds data/deeds_llm.jsonl   # then run `leads` again
    python -m rcpro export-search data/search.jsonl     # companies without e-mail or website
    python -m rcpro import-search data/search_llm.jsonl # checked against the site, then run `leads` again

The database is data/kbo.duckdb, or the path in RCPRO_DB.
"""

import argparse
import os
import subprocess
from datetime import date, timedelta

import duckdb

from rcpro import classify, kbo, leads, llm, staatsblad, view, websites


def refresh(con, since, csv=None):
    """(Re)build `leads` with every enrichment stored so far."""
    print(f"{leads.build_leads(con, since)} leads")
    classify.classify(con)
    websites.apply(con)
    staatsblad.apply(con)
    if csv:
        path = csv.replace("'", "''")
        con.execute(f"COPY leads TO '{path}' (HEADER)")


def claude_steps(con, since, limit):
    """Deeds, unknown engineers and web search through `claude -p`, each exported, answered and imported."""
    steps = [
        ("deeds", lambda p: staatsblad.export_deeds(con, p), "extract_deeds.md", (), staatsblad.import_deeds),
        ("unknown engineers", lambda p: classify.export_unknown(con, p), "classify_engineers.md", (), classify.import_llm),
        ("web search", lambda p: websites.export_search(con, p, limit), "find_contacts.md", ("WebSearch", "WebFetch"),
         websites.import_search),
    ]
    for name, export, prompt, tools, load in steps:
        path, answers = f"data/{name.replace(' ', '_')}.jsonl", f"data/{name.replace(' ', '_')}_llm.jsonl"
        if not export(path):
            continue
        try:
            print(f"Claude, {name}: {llm.run(prompt, path, answers, tools)} sent; {load(con, answers)}")
        except (subprocess.SubprocessError, OSError, ValueError) as e:
            print(f"Claude, {name}: skipped ({str(e).strip()[:300]})")  # e.g. not logged in: run `claude`, then /login
        refresh(con, since)  # the next export needs this step's answers in `leads`


def run(con, paths, since, limit, use_claude=True):
    full = [p for p in paths if "_full" in p.lower()]
    if full:
        print(f"Loaded full extract {kbo.load_full(con, full[-1])}")
    if updates := [p for p in paths if p not in full]:
        kbo.apply_updates(con, updates)
    print(f"KBO extract: {kbo.last_applied(con)}")
    refresh(con, since)
    print("Websites:", websites.search(con, limit))
    print("Staatsblad (1 request / 5 s):", staatsblad.fetch(con, limit))
    refresh(con, since)
    if use_claude:
        claude_steps(con, since, limit)
    refresh(con, since, "data/leads.csv")
    for row in leads.summary(con):
        print(*row, sep="\t")
    print(f"{view.write_html(con, 'data/leads.html')} leads written to data/leads.html")
    view.open_html("data/leads.html")


def main():
    p = argparse.ArgumentParser(prog="rcpro")
    sub = p.add_subparsers(dest="cmd", required=True)
    rp = sub.add_parser("run")
    rp.add_argument("paths", nargs="*", help="KBO full (*_Full.zip) and/or update zips; none: use the database as it is")
    rp.add_argument("--since", default=str(date.today() - timedelta(days=365)), help="YYYY-MM-DD, default one year ago")
    rp.add_argument("--limit", type=int, default=100, help="per network step: companies searched, deeds, web searches")
    rp.add_argument("--no-claude", action="store_true", help="skip the claude -p steps")
    sub.add_parser("full").add_argument("path")
    sub.add_parser("update").add_argument("paths", nargs="+")
    lp = sub.add_parser("leads")
    lp.add_argument("--since", required=True, help="YYYY-MM-DD")
    lp.add_argument("--csv", help="also write the leads table to this CSV")
    sub.add_parser("websites").add_argument("--limit", type=int, help="search at most this many companies, newest first")
    sub.add_parser("staatsblad").add_argument("--limit", type=int, help="fetch at most this many companies, newest first")
    sub.add_parser("view").add_argument("--html", default="data/leads.html")
    sub.add_parser("codes")
    sub.add_parser("export-unknown").add_argument("path")
    sub.add_parser("import-llm").add_argument("path")
    sub.add_parser("export-deeds").add_argument("path")
    sub.add_parser("import-deeds").add_argument("path")
    sub.add_parser("export-search").add_argument("path")
    sub.add_parser("import-search").add_argument("path")
    args = p.parse_args()

    con = duckdb.connect(os.environ.get("RCPRO_DB", "data/kbo.duckdb"))
    if args.cmd == "run":
        run(con, args.paths, args.since, args.limit, not args.no_claude)
    elif args.cmd == "full":
        print(f"Loaded full extract {kbo.load_full(con, args.path)}")
    elif args.cmd == "update":
        kbo.apply_updates(con, args.paths)
        print(f"Last applied extract: {kbo.last_applied(con)}")
    elif args.cmd == "leads":
        refresh(con, args.since, args.csv)
        for row in leads.summary(con):
            print(*row, sep="\t")
    elif args.cmd == "websites":
        for level, n in sorted(websites.search(con, args.limit).items()):
            print(level, n, sep="\t")
        websites.apply(con)
    elif args.cmd == "staatsblad":
        for status, n in sorted(staatsblad.fetch(con, args.limit).items()):
            print(status, n, sep="\t")
    elif args.cmd == "view":
        print(f"{view.write_html(con, args.html)} leads written to {args.html}")
        view.open_html(args.html)
    elif args.cmd == "codes":
        for segment, code, description in leads.codes(con):
            print(segment, code, description or "!! NOT FOUND in code.csv", sep="\t")
    elif args.cmd == "export-unknown":
        print(f"{classify.export_unknown(con, args.path)} unknown engineers written to {args.path}")
    elif args.cmd == "import-llm":
        print(f"{classify.import_llm(con, args.path)} answers stored; run `leads` again to apply them")
    elif args.cmd == "export-deeds":
        print(f"{staatsblad.export_deeds(con, args.path)} deeds written to {args.path}")
    elif args.cmd == "import-deeds":
        print(f"{staatsblad.import_deeds(con, args.path)} answers stored; run `leads` again to apply them")
    elif args.cmd == "export-search":
        print(f"{websites.export_search(con, args.path)} companies without e-mail or website written to {args.path}")
    elif args.cmd == "import-search":
        print(f"Checked answers: {websites.import_search(con, args.path)}; run `leads` again to apply them")


if __name__ == "__main__":
    main()
