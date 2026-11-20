#!/bin/zsh
# Nightly: new KBO updates, websites, founding deeds, Claude extraction, leads.csv, Notion.
# Started by launchd (scripts/be.omata.rcpro.nightly.plist); output goes to data/nightly.log.
set -e
cd "${0:A:h}/.."
source ~/.config/rcpro.env  # NOTION_*, KBO_USER/KBO_PASSWORD, SSL_CERT_FILE; never in git
source ~/.venvs/rcpro-pipeline/bin/activate
export PATH="$HOME/.local/bin:/opt/homebrew/bin:$PATH"  # claude, pdftotext
echo "== $(date '+%F %T')"
python -m rcpro kbo-download
python -m rcpro websites --limit 500  # no Claude; site e-mails then go through mx
python -m rcpro mx
python -m rcpro staatsblad --limit 1000  # all companies, mailable first: the deed often holds the company's e-mail (~3 h)
python -m rcpro leads > /dev/null  # deed e-mails into outreach_email before choosing what Claude reads
python -m rcpro export-deeds data/deeds.jsonl --mailable  # Claude reads only deeds that matter for contact
if [[ -s data/deeds.jsonl ]]; then
  # a failing Claude (e.g. login expired) must not stop leads.csv and Notion; the deeds wait for the next night
  if python -c "from rcpro import llm; llm.run('extract_deeds.md', 'data/deeds.jsonl', 'data/deeds_llm.jsonl')"; then  # in batches of 10
    python -m rcpro import-deeds data/deeds_llm.jsonl
  else
    echo "!! deed extraction failed (claude -p); continuing without it"
  fi
fi
python -m rcpro leads --csv data/leads.csv | tail -1
python -m rcpro notion --since "$(date -v-14d +%F)"  # last two weeks only, until `notion --full` has cleaned up the duplicates
echo "== done $(date '+%F %T')"
