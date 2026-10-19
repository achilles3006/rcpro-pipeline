# rcpro-pipeline

Pipeline to find newly started Belgian businesses that must carry professional liability insurance (beroepsaansprakelijkheid, RC pro), and to prepare a compliant first contact. Owner: Omata (Groep Induver).

Status: research phase 0 to 2 done, phase 3 (compliance) and 5 (validation) not started. Nothing in this repo may be used for outreach until the legal blockers in `docs/open-questions.md` are closed.

## Scope

1. Target: every newly started business that could plausibly buy professional liability insurance, grouped by `sales_angle` (see `docs/segments.md`).
2. Pilot: construction professionals under the Act of 9 May 2019, architects first. This is the only group where the legal obligation is used as the sales story.
3. Out of scope: ten-year liability (Act of 31 May 2017) and general third-party liability.
4. Pilot size: architects and interior architects, about 170 starters a month, of which about 55 companies a month are usable from KBO data.

## Pipeline

| Phase | Module | Purpose | State |
|---|---|---|---|
| 1 | `rcpro.kbo`, `rcpro.leads` | Load KBO full extract and daily updates into DuckDB, build leads per segment with a legal flag | Built, tested on synthetic data; real extract not run yet |
| 1 | `rcpro.register` | Detect new registrations in the Order of Architects register | Not started, needs legal sign-off |
| 2 | `rcpro.classify` | Rules plus LLM step: is the activity mandatory (yes, likely, unlikely, unknown) | Rules built (run by `leads`); LLM step weekly by hand in Claude Code |
| 2 | `rcpro.websites` | Website discovery for companies: verified (own enterprise number on the site) or probable (name plus municipality) | Built; measured on 100 companies (`docs/contact-sources-measurement.md`), precision not yet checked by a labeller |
| 2 | `rcpro.staatsblad` | Founding deed from the Staatsblad annexes: founders, activity summary, construction yes/no as evidence for unknown engineers | Built; fetch daily, LLM step weekly by hand in Claude Code |
| 3 | n/a | Compliance gate | Not started |
| 4 | n/a | Playbook, templates, needs analysis | Written in Notion |
| 5 | n/a | Validation against underwriter, control group, KPIs | Not started |

## Rules for this repo

1. No personal data in git. The DuckDB file and extracts live in private storage. `data/` is ignored.
2. Sole traders get no name in any table until the legal question on KBO reuse is answered.
3. Website and register matches carry a confidence level (verified, probable) instead of a pass/fail. Missing a real prospect costs more than a wrong match, so probable matches are used. Weak (name only) matches were dropped after the measurement: almost all were someone else's domain.
4. The law is cited as a sales argument only for `sales_angle = legal_obligation`. Other segments get a different story.
5. LLM steps must answer "unknown" without evidence and list the evidence used.

## Layout

```
docs/           research summary, open questions, decisions
src/rcpro/      package (kbo, leads, classify, websites built; register still a stub)
tests/          pytest on a synthetic mini extract
scripts/        helper scripts (issue creation)
.github/        workflows
data/           local only, ignored
```

## Setup

```
python3 -m venv ~/.venvs/rcpro-pipeline && source ~/.venvs/rcpro-pipeline/bin/activate
pip install -e ".[dev]"
```

Keep the venv outside iCloud-synced folders (Desktop, Documents): iCloud marks files in dot-folders hidden, and Python 3.13 then skips the editable install.

## Usage

Download a full extract (and optional daily updates) from the KBO Open Data portal into `data/`, then:

```
python -m rcpro full data/<full>.zip
python -m rcpro update data/<update>.zip ...   # any order; applied by extract number, never twice
python -m rcpro codes                           # check every segment code against code.csv
python -m rcpro leads --since 2025-10-01 --csv data/leads.csv
python -m rcpro websites --limit 200            # search company websites (newest first, each company once)
python -m rcpro staatsblad --limit 200          # founding deeds (companies only, newest first, each once, 1 request / 5 s)
python -m rcpro view                            # opens data/leads.html: filters per segment, search, links
pytest
```

The `leads` table (and `data/leads.csv`) is the pipeline's output: one row per new business with segment, `sales_angle`, `mandatory` plus evidence, postcode, contact flags and `dm_allowed_from_kbo`. Companies also carry name, municipality, e-mail, phone and website from KBO, and after `websites` the site found (`site`, `site_level`) with the e-mail and phone published on it (`site_email`, `site_phone`), kept apart from the KBO values because the legal basis may differ. After the deed step, companies also carry `founders` and `activity_summary` from their founding deed. Sole traders carry flags only, no name or contact values, until the KBO question in `docs/open-questions.md` is answered.

Segment codes and their priority live in `SEGMENTS` in `src/rcpro/leads.py`.

### Weekly: LLM step for unknown engineers (Claude Code, no API key)

```
python -m rcpro export-unknown data/unknown.jsonl
cat data/unknown.jsonl | claude -p --model haiku "$(cat prompts/classify_engineers.md)" > data/llm.jsonl
python -m rcpro import-llm data/llm.jsonl
python -m rcpro leads --since 2025-10-01 --csv data/leads.csv
```

The export holds codes and company names only, never sole traders' names. Answers are kept in `llm_classification`, so each week only new unknown engineers are exported. An answer without evidence is stored as unknown, and one bad line stops the whole import.

### Weekly: LLM step for founding deeds (Claude Code, no API key)

```
python -m rcpro export-deeds data/deeds.jsonl
cat data/deeds.jsonl | claude -p --model haiku "$(cat prompts/extract_deeds.md)" > data/deeds_llm.jsonl
python -m rcpro import-deeds data/deeds_llm.jsonl
python -m rcpro leads --since 2025-10-01 --csv data/leads.csv
```

`staatsblad` keeps the deed text in `deeds` (a row also when there is no founding deed; that company is retried only until 60 days after its start date, because deeds are published days to weeks after the start). Claude extracts the founders (name, role), a one-line activity summary and `construction_related` (yes, no, unknown) with a quote as evidence; answers are kept in `deed_extraction`. For engineers the rules left unknown, a yes or no with evidence sets `mandatory` to likely or unlikely (evidence `deed: ...`), before the name-based LLM answer. Founder names are personal data (open question 2): stored, never used for outreach until that is answered. Sole traders are never fetched, exported or shown.
