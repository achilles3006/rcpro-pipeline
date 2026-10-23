# rcpro-pipeline

Finds newly started Belgian businesses that may need professional liability insurance (beroepsaansprakelijkheid, RC pro) and enriches them with contact data, so sales can prepare a first contact. Owner: Omata (Groep Induver).

Input: the public KBO Open Data extract. Output: `data/leads.csv` and a filterable page `data/leads.html`, one row per new business.

> **Before you contact anyone.** Mail only through `python -m rcpro outreach` (compliance gate: legal persons on impersonal addresses, opt-out list, log) and only after the go-live checklist in `docs/outreach-legal.md`. Never contact sole traders or personal addresses, cite the law only for `mandatory = yes`, and never use `founders` for outreach.

## 1. What you need

| What | Why | How |
|---|---|---|
| Python 3.11 or newer | runs the pipeline | `python3 --version` |
| Claude Code CLI, logged in | the three LLM steps (no API key needed) | install from claude.com/claude-code, run `claude` once and type `/login` |
| KBO Open Data account | download the extracts | free registration on the KBO Open Data portal of FPS Economy (kbopub.economie.fgov.be) |
| About 2 GB free disk | the database is about 600 MB | |
| Internet access | websites, Staatsblad (ejustice.just.fgov.be), web search | |

Claude is optional: with `--no-claude` everything else still runs.

## 2. Install (once)

```
git clone <repo-url> rcpro-pipeline
cd rcpro-pipeline
python3 -m venv ~/.venvs/rcpro-pipeline
source ~/.venvs/rcpro-pipeline/bin/activate
pip install -e ".[dev]"
pytest            # should end with "30 passed"
```

Keep the venv outside iCloud-synced folders (Desktop, Documents): iCloud marks files in dot-folders as hidden, and Python 3.13 then skips the editable install. Activate the venv (`source ...`) in every new terminal.

## 3. First run

1. Log in to the KBO Open Data portal and download the latest **full** extract (`KboOpenData_<nr>_<date>_Full.zip`) and any **update** files published after it (`..._Update.zip`). Put them in `data/`. The portal needs a login, so this stays a manual step.
2. Run:

```
python -m rcpro run data/KboOpenData_*_Full.zip data/KboOpenData_*_Update.zip
```

The first run loads the full extract, builds the leads, and enriches the newest 100 companies. It ends by opening `data/leads.html` in the browser.

## 4. Daily routine

Download the new update zip(s) and run:

```
python -m rcpro run data/KboOpenData_<nr>_*_Update.zip
```

- Updates can be given in any order and twice; each is applied once, by extract number. A gap (missing update) gives a warning: download the missing one and run again.
- Without a zip (`python -m rcpro run`) the database is used as it is; useful to work through the enrichment backlog.
- Each network step handles at most `--limit` companies (default 100, newest first) and never the same company twice, so daily runs work through the backlog. The Staatsblad step takes about 10 seconds per company (one request every 5 seconds, on purpose), so 100 companies is about 15 to 20 minutes.
- Once a month or so, load a fresh full extract instead of updates: `python -m rcpro run data/..._Full.zip`.

Options of `run`:

| Option | Default | Meaning |
|---|---|---|
| `--since YYYY-MM-DD` | one year ago | only businesses started on or after this date |
| `--limit N` | 100 | companies per network step |
| `--no-claude` | off | skip the three Claude steps |

The database is `data/kbo.duckdb`; set `RCPRO_DB=/path/to/file.duckdb` to put it elsewhere (for example on private shared storage).

## 5. What `run` does

1. **Load KBO** (`rcpro.kbo`): full extract or updates into DuckDB.
2. **Leads** (`rcpro.leads`): businesses started since `--since` whose main NACE code is in a segment (`SEGMENTS` in `src/rcpro/leads.py`).
3. **Classify** (`rcpro.classify`): rules decide whether insurance is mandatory (yes, likely, unlikely, unknown) with the codes as evidence.
4. **Websites** (`rcpro.websites`): guesses domains from the name, KBO website and e-mail domain, opens the site and keeps it as `verified` (own enterprise number on the site) or `probable` (name plus municipality). Companies only.
5. **Staatsblad** (`rcpro.staatsblad`): fetches the founding deed. Companies only; a company without a deed yet is retried weekly up to 60 days after its start.
6. **Claude steps** (`claude -p --model haiku`, prompts in `prompts/`):
   - deeds: founders, one-line activity summary, construction yes/no with a quote;
   - unknown engineers: mandatory or not, from the company name and codes;
   - web search: website and e-mail for companies that have neither. Claude's answer is never taken as is: the pipeline opens the site itself and applies the same verified/probable check. Nothing found: retried after 30 days.
7. **Output**: `data/leads.csv` and `data/leads.html`.

Each step can also run on its own; see `python -m rcpro --help` and section 9.

## 6. The output

`data/leads.html` has filters per segment and sales angle, a search box, and links to KBO and the websites. `data/leads.csv` has the same rows for Excel. Columns:

| Column | Meaning |
|---|---|
| `enterprise_number`, `start_date` | KBO number and start date |
| `segment`, `sales_angle` | group and sales story: `legal_obligation` (law requires the cover), `legal_unconfirmed` (probably, not confirmed), `commercial_need` (no obligation, other story), `no_outreach` (do not contact) |
| `legal_form_type`, `juridical_form`, `juridical_form_label` | `company` or `sole_trader`, KBO legal form (BV, NV, ...) |
| `name`, `postcode`, `municipality` | from KBO; for a sole trader the owner's name |
| `has_email`, `has_phone`, `has_website`, `email`, `phone`, `website` | contact data from KBO |
| `dm_allowed_from_kbo` | false for every sole trader: **do not contact** |
| `mandatory`, `evidence`, `legal_basis`, `needs_review` | is the cover mandatory, on what evidence, which law, and whether a person should check |
| `site_level`, `site`, `site_email`, `site_phone` | website found by the pipeline and the contact data on it; kept apart from KBO because the legal basis may differ |
| `founders`, `activity_summary` | from the founding deed (companies only) |

Segments and how to approach each one: `docs/segments.md`.

## 7. Rules for using this repo

1. **No personal data in git.** `data/`, `*.duckdb`, `*.csv` and `*.zip` are ignored. Keep the database and extracts on private storage and never commit them.
2. **Sole traders** appear in `leads` with name and KBO contact data (informational list), but keep `dm_allowed_from_kbo = false` and are never searched, exported to an LLM or contacted until the legal question on KBO reuse is answered.
3. Website matches carry a confidence level (`verified`, `probable`) instead of pass/fail. Missing a real prospect costs more than a wrong match, so probable matches are kept.
4. The law is a sales argument only for `sales_angle = legal_obligation`.
5. LLM steps must answer "unknown" without evidence and list the evidence they used; an answer without evidence is stored as unknown.

## 8. Troubleshooting

| Symptom | Fix |
|---|---|
| `Claude, ...: skipped (...)` | `claude` is not installed or not logged in: run `claude`, then `/login`. Or use `--no-claude`. |
| `ModuleNotFoundError: rcpro` | venv not active, or venv inside an iCloud folder (see section 2) |
| Warning about a gap in extract numbers | an update zip is missing: download it and run again |
| `rcpro codes` shows `!! NOT FOUND` | a segment code no longer exists in KBO's `code.csv`: fix `SEGMENTS` in `src/rcpro/leads.py` |
| Database locked | another `rcpro` process (or a DuckDB client) has the file open: close it |
| Very few websites found | expected: most starters have no site yet (about 4% hit rate, see `docs/domain-guess-v2.md`) |

## 9. Single steps and the manual Claude steps

```
python -m rcpro full data/<full>.zip
python -m rcpro update data/<update>.zip ...
python -m rcpro codes                           # check every segment code against code.csv
python -m rcpro leads --since 2025-10-01 --csv data/leads.csv
python -m rcpro websites --limit 200
python -m rcpro staatsblad --limit 200
python -m rcpro view                            # writes and opens data/leads.html
python -m rcpro outreach data/mails.csv --limit 20   # today's mails through the compliance gate, logged
python -m rcpro optout info@example.be          # after a STOP or unsubscribe
```

The Claude steps by hand (what `run` does automatically); after each import, run `leads` again:

```
python -m rcpro export-unknown data/unknown.jsonl
cat data/unknown.jsonl | claude -p --model haiku "$(cat prompts/classify_engineers.md)" > data/llm.jsonl
python -m rcpro import-llm data/llm.jsonl

python -m rcpro export-deeds data/deeds.jsonl
cat data/deeds.jsonl | claude -p --model haiku "$(cat prompts/extract_deeds.md)" > data/deeds_llm.jsonl
python -m rcpro import-deeds data/deeds_llm.jsonl

python -m rcpro export-search data/search.jsonl
cat data/search.jsonl | claude -p --model haiku --allowedTools "WebSearch WebFetch" "$(cat prompts/find_contacts.md)" > data/search_llm.jsonl
python -m rcpro import-search data/search_llm.jsonl
```

Exports hold companies only, never sole traders' names. Answers are stored (`llm_classification`, `deed_extraction`, `web_search`), so each run only sends new companies. One malformed answer line stops the whole import, so nothing half-done is stored.

## 10. Project status

| Phase | Module | State |
|---|---|---|
| 1 | `rcpro.kbo`, `rcpro.leads` | In use, run on real KBO extracts |
| 1 | `rcpro.register` (Order of Architects) | Not started, needs legal sign-off |
| 2 | `rcpro.classify` | Rules plus Claude step for unknown engineers |
| 2 | `rcpro.websites` | In use; precision not yet checked by a labeller (`docs/contact-sources-measurement.md`) |
| 2 | `rcpro.staatsblad` | In use |
| 3 | `rcpro.outreach` (compliance gate) | Built; go-live checklist in `docs/outreach-legal.md` |
| 4 | Playbook, templates | In Notion |
| 5 | Validation with underwriter, KPIs | Not started |

The daily GitHub workflow (`.github/workflows/kbo-daily.yml`) is a placeholder: the KBO download needs a login (or SFTP access, not granted yet) and the database must not live in GitHub. Run the pipeline on a machine with private storage.

## 11. Layout and development

```
src/rcpro/      package: kbo, leads, classify, websites, staatsblad, llm, view, __main__ (CLI)
prompts/        prompts for the Claude steps
tests/          pytest on a synthetic mini extract (no network, no real data)
scripts/        measurements and the GitHub issue script
docs/           research, decisions, open questions, segments, measurements
data/           local only, ignored by git
```

- Add or change a segment: edit `SEGMENTS` in `src/rcpro/leads.py`, run `python -m rcpro codes`, then `pytest`.
- Run `pytest` and `ruff check src tests` before every commit.
- Background: `docs/research-summary.md`, `docs/decisions.md`, `docs/open-questions.md`.
