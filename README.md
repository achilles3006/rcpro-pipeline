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
| 2 | `rcpro.websites` | Website discovery, accepted only with enterprise number match | Built elsewhere, untested |
| 3 | n/a | Compliance gate | Not started |
| 4 | n/a | Playbook, templates, needs analysis | Written in Notion |
| 5 | n/a | Validation against underwriter, control group, KPIs | Not started |

## Rules for this repo

1. No personal data in git. The DuckDB file and extracts live in private storage. `data/` is ignored.
2. Sole traders get no name in any table until the legal question on KBO reuse is answered.
3. Website and register matches carry a confidence level (verified, probable, weak) instead of a pass/fail. Missing a real prospect costs more than a wrong match, so probable matches are used; weak matches go to manual review.
4. The law is cited as a sales argument only for `sales_angle = legal_obligation`. Other segments get a different story.
5. LLM steps must answer "unknown" without evidence and list the evidence used.

## Layout

```
docs/           research summary, open questions, decisions
src/rcpro/      package (kbo, leads, classify rules built; websites, register still stubs)
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
pytest
```

Segment codes and their priority live in `SEGMENTS` in `src/rcpro/leads.py`.

### Weekly: LLM step for unknown engineers (Claude Code, no API key)

```
python -m rcpro export-unknown data/unknown.jsonl
cat data/unknown.jsonl | claude -p --model haiku "$(cat prompts/classify_engineers.md)" > data/llm.jsonl
python -m rcpro import-llm data/llm.jsonl
python -m rcpro leads --since 2025-10-01 --csv data/leads.csv
```

The export holds codes and company names only, never sole traders' names. Answers are kept in `llm_classification`, so each week only new unknown engineers are exported. An answer without evidence is stored as unknown, and one bad line stops the whole import.
