# Open questions and research backlog

Ordered by what blocks what. P0 blocks any outreach. P1 blocks a trustworthy pilot. P2 improves it.

## P0: gates (nothing is sent before these are closed)

1. **KBO direct marketing ban.** Confirm scope: sole traders, and named e-mail addresses of companies. Owner: lawyer.
2. **Order of Architects register.** May contact data be used for a first contact (legitimate interest assessment, art. 14 notice)? Also check terms of use and the EU database right, since robots.txt allowing crawling is not legal clearance. Owner: lawyer.
3. **Consent for electronic direct marketing.** Phase 4 is e-mail first. The Notion open questions cover Do Not Call Me and GDPR but not the consent rule for e-mail and WhatsApp to companies and sole traders. Assumption to verify, not a finding. Owner: lawyer.
4. **FSMA registration.** Does Omata act under its own registration or under Induver? The e-mail footer still has a placeholder. Owner: compliance.
5. **Accountant referrals.** Do paid referrals count as insurance distribution? Owner: lawyer.

## P1: pilot design

6. **Unit economics (missing in the research).** Typical starter premium, commission, expected conversion, cost per policy. With about 55 usable companies a month, check whether the pilot can ever pay back. Owner: Achilles with the underwriter or broker.
7. **Already insured at registration.** Does the Order or a client contract force architects to hold a policy before or at registration, and what share of starters buys through employer, Order or group policy (for example VMx)? If most are insured on day one, the addressable share is far smaller than 170 a month. Owner: Order contact, underwriter.
8. **Indexed 2026 minimum amounts** under the 2019 Act. Owner: underwriter.
9. **Pilot scope.** Architect companies only (about 55 a month) or wait for the register answer to include sole traders. Decide with the legal answer on items 1 and 2.
10. **Engineers.** Join the pilot now or after architects. Classification leaves 58% unknown, so qualification must happen in the first conversation.
11. **Statistical power.** Phase 4 plans to change one element at a time per segment and language. At about 55 contacts a month and a low reply rate, versions cannot be compared. Define the minimum sample per test and accept fewer variants.

## P2: data and tooling

12. **KBO SFTP access** from FPS Economy.
13. **Network access** to vind.architect.be, to test linking KBO companies to the register.
14. **Website discovery.** Built and measured on 100 companies (about 4% yield, `docs/contact-sources-measurement.md`, `docs/domain-guess-v2.md`). Open: precision check by a labeller.
15. **LLM classification.** Runs via `claude -p` (no API key). Open: check its answers on 100 unknown engineers.
16. **Validation (phase 5).** Blind-labelled sample of 200 against an underwriter, over-represent engineers, precision target 85% or more, control group, KPIs from contact rate to cost per policy.
17. **Commercial segments.** Measure volume, company versus sole trader share and contact data for management and IT consultants, and test the claim that clients require proof of cover. Wording of the sales story for non-mandatory segments needs lawyer approval (no implied obligation).
18. **Missing Notion pages.** Phase 3 (compliance) and Phase 5 (validation) have no page yet, although Phase 4 is already written.
