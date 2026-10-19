"""Command line: python -m rcpro <full|update|leads|websites|staatsblad|view|codes|export-unknown|import-llm|export-deeds|import-deeds> ...

    python -m rcpro full data/KboOpenData_0517_2026_10_19_Full.zip
    python -m rcpro update data/KboOpenData_0518_*_Update.zip
    python -m rcpro leads --since 2025-10-01 [--csv data/leads.csv]
    python -m rcpro websites [--limit 200]        # search company websites, newest first, each once
    python -m rcpro staatsblad [--limit 20]       # founding deeds from the Staatsblad, newest first, each once (1 request / 5 s)
    python -m rcpro view                          # leads as a filterable table in the browser
    python -m rcpro codes

Weekly LLM step for unknown engineers, by hand in Claude Code (see README):
    python -m rcpro export-unknown data/unknown.jsonl
    python -m rcpro import-llm data/llm.jsonl     # then run `leads` again
    python -m rcpro export-deeds data/deeds.jsonl
    python -m rcpro import-deeds data/deeds_llm.jsonl   # then run `leads` again

The database is data/kbo.duckdb, or the path in RCPRO_DB.
"""

import argparse
import os

import duckdb

from rcpro import classify, kbo, leads, staatsblad, view, websites


def main():
    p = argparse.ArgumentParser(prog="rcpro")
    sub = p.add_subparsers(dest="cmd", required=True)
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
    args = p.parse_args()

    con = duckdb.connect(os.environ.get("RCPRO_DB", "data/kbo.duckdb"))
    if args.cmd == "full":
        print(f"Loaded full extract {kbo.load_full(con, args.path)}")
    elif args.cmd == "update":
        kbo.apply_updates(con, args.paths)
        print(f"Last applied extract: {kbo.last_applied(con)}")
    elif args.cmd == "leads":
        print(f"{leads.build_leads(con, args.since)} leads")
        classify.classify(con)
        websites.apply(con)
        staatsblad.apply(con)
        for row in leads.summary(con):
            print(*row, sep="\t")
        if args.csv:
            path = args.csv.replace("'", "''")
            con.execute(f"COPY leads TO '{path}' (HEADER)")
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


if __name__ == "__main__":
    main()
