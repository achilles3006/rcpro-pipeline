#!/usr/bin/env bash
# Creates labels and backlog issues from docs/open-questions.md.
# Usage (gh must be authenticated):
#   gh repo create <org>/rcpro-pipeline --private --source=. --remote=origin --push
#   ./scripts/create_issues.sh
set -euo pipefail

for l in "legal:b60205" "compliance:d93f0b" "product:0e8a16" "data:1d76db" "validation:5319e7" "P0:b60205" "P1:fbca04" "P2:c2e0c6"; do
  gh label create "${l%%:*}" --color "${l##*:}" 2>/dev/null || true
done

i() { gh issue create --title "$1" --label "$2" --body "$3"; }

i "KBO direct marketing ban: confirm scope" "legal,P0" "Sole traders and named company e-mail addresses. Owner: lawyer. See docs/open-questions.md item 1."
i "Order of Architects register: legal clearance for first contact" "legal,P0" "LIA, art. 14 notice, terms of use, EU database right. Item 2."
i "Consent rules for e-mail and WhatsApp direct marketing" "legal,P0" "Not covered in the Notion open questions. Verify with lawyer. Item 3."
i "FSMA registration: Omata or Induver" "compliance,P0" "Needed for the e-mail footer. Item 4."
i "Accountant referrals: insurance distribution?" "legal,P0" "Item 5."
i "Unit economics for the pilot" "product,P1" "Premium, commission, conversion, cost per policy at about 55 usable companies a month. Item 6."
i "Already insured at registration: size the real addressable share" "product,P1" "Order, employer and group policies. Item 7."
i "Confirm indexed 2026 minimum cover amounts" "product,P1" "Underwriter. Item 8."
i "Decide pilot scope (companies only vs register)" "product,P1" "Depends on legal answers 1 and 2. Item 9."
i "Engineers: now or later" "product,P1" "58% unknown classification. Item 10."
i "Define minimum sample per outreach test" "validation,P1" "Item 11."
i "Request KBO SFTP access" "data,P2" "kbo-bce-webservice@economie.fgov.be. Item 12."
i "Network access to vind.architect.be" "data,P2" "Item 13."
i "Website discovery: test on 100 companies, then decide" "data,P2" "Brave Search API key needed. Item 14."
i "Run LLM classification on 100 unknown engineers" "data,P2" "Anthropic API key needed. Item 15."
i "Phase 5 validation design" "validation,P2" "Item 16."
i "Write Notion pages for phase 3 and phase 5" "compliance,P2" "Item 17."
