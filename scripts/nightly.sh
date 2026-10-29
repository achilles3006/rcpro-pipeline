#!/bin/zsh
# Nightly: founding deeds of mailable companies, Claude extraction, leads.csv, Notion.
# Started by launchd (scripts/be.omata.rcpro.nightly.plist); output goes to data/nightly.log.
set -e
cd "${0:A:h}/.."
source ~/.config/rcpro.env  # NOTION_*, SSL_CERT_FILE; never in git
source ~/.venvs/rcpro-pipeline/bin/activate
export PATH="$HOME/.local/bin:$PATH"  # claude
echo "== $(date '+%F %T')"
python -m rcpro mx
python -m rcpro staatsblad --mailable --limit 200
python -m rcpro export-deeds data/deeds.jsonl
if [[ -s data/deeds.jsonl ]]; then
  python -c "from rcpro import llm; llm.run('extract_deeds.md', 'data/deeds.jsonl', 'data/deeds_llm.jsonl')"  # in batches of 10
  python -m rcpro import-deeds data/deeds_llm.jsonl
fi
python -m rcpro leads --csv data/leads.csv | tail -1
python -m rcpro notion
echo "== done $(date '+%F %T')"
