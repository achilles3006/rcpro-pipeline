# Research summary (as of 19 October 2026)

Source: Notion, "responsabilité civile professionnelle scraping research". Keep Notion as the working copy until this repo has code.

## Phase 0: regulation and market size

1. The mandatory market among starters is essentially the Act of 9 May 2019 (intellectual service providers in construction).
2. About 4,800 new businesses a year (about 400 a month, Oct 2025 to Sep 2026). Architects and interior architects about 2,000 a year, 170 a month.
3. Minimum cover per claim: EUR 1.5m bodily injury, EUR 500k material and immaterial, EUR 10k entrusted objects, annual aggregate EUR 5m. Indexed, an underwriter must confirm 2026 amounts.
4. Volume is elsewhere (management and IT consultants, about 1,900 a month) but that is a non-mandatory pitch.

## Phase 1: sources and intake

1. KBO intake works (full load 14 seconds, safe daily updates).
2. Blocker: KBO Open Data may not be used for direct marketing, including all data of sole traders. 1,300 of 1,989 architect starters (65%) fall out. Usable: companies, about 55 a month.
3. Contact data in KBO is thin: 9 to 24% e-mail, websites 0 to 3%.
4. Order of Architects public search is the best register, but not yet legally cleared and not reachable from the workspace.

## Phase 2: identification and classification (updated 23 October 2026)

Idea: decide per lead whether the legal obligation applies, with the cheapest evidence first, and only spend effort on leads that can be contacted. Figures are indicative; `python -m rcpro leads` prints the current ones.

1. **Segment by main activity code.** Each lead gets a segment and a sales angle from its main NACE-BEL 2025 code (`SEGMENTS` in `src/rcpro/leads.py`, `docs/segments.md`). The gap check of 23 Oct added healthcare, other FSMA-list professions and more commercial segments; outreach stays limited to the pilot.
2. **Rules on codes settle most segments.** Architects, interior architects and land surveyors are settled by code (about 2,000 leads). So are the other segments, with a fixed answer per segment (`FIXED` in `rcpro.classify`).
3. **Engineers need evidence beyond the code.** The 2019 Act only applies to real estate works. The order of evidence, strongest first:
   - main and secondary codes (construction or not);
   - the purpose clause of the founding deed in the Staatsblad, read by Claude (construction yes/no with a quote);
   - Claude on name and codes, for what is still unknown.
   No evidence means "unknown". An engineer outside construction moves to `commercial_need` instead of being dropped. Since the deeds and the LLM step, unknown fell from about 58% to about a third; it keeps changing while deeds are fetched.
4. **Qualification finishes in the first conversation** (decision 5). Leads that stay unknown are asked the construction question, not discarded.
5. **Only companies go through the network and LLM steps.** Sole traders stay in the list for sizing but are never searched, exported to Claude or contacted (KBO direct marketing ban).
6. **Contact data: matches with a confidence level.** Domains are guessed from the name, the KBO website and the e-mail domain. A site is kept as verified (own enterprise number on the site) or probable (name plus municipality); weak name-only matches are dropped. A Claude web search fills in for companies with nothing, but its answer goes through the same check. Yield is low (a few percent of companies) because most starters have no site yet, not because the guessing is poor (`docs/domain-guess-v2.md`).
7. **"Already insured" cannot be estimated from open data.** It comes from the underwriter or the Order (open question 7).

## Phase 4: conversation

1. Open with a checkable fact (registration date, activity) and one obligation most starters do not know (art. 14: insurer, enterprise number and policy number on every quote and contract).
2. Sequence: e-mail day 1, follow-up day 6, WhatsApp only after reply or click.
3. Eight needs-analysis questions before any quote. Existing cover ends the sales track.
