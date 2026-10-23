# Segments and sales angle

Rule: the legal obligation is used as a sales argument only for segments marked `legal_obligation`. For every other segment, messages and call scripts must not state or imply that the law requires the insurance. Reason: claiming an obligation that does not exist is a misleading commercial practice and an insurance distribution risk. Lawyer to confirm wording.

Every lead carries a `sales_angle` value. Message templates are selected on it.

| sales_angle | Segments | Sales story | Notes |
|---|---|---|---|
| legal_obligation | Architects, interior architects, land surveyors (settled by code); engineers and design offices, landscape and urban architects (classification needed); EPB/EPC assessors, asbestos experts, safety coordinators (no usable list yet) | Act of 9 May 2019: mandatory cover, minimum amounts, insurer and policy number on every quote and contract | Pilot segment. About 400 starters a month, about 170 architects. |
| legal_obligation, partner | Certified accountants and tax advisers (ITAA, Act of 17 March 2019, art. 44) | Same style of story, but they are also a referral channel | About 53 a month. Decide per lead: prospect or partner. Referral fees need legal validation. |
| legal_unconfirmed | Psychologists and therapists (about 200 a month); healthcare: dentists, GPs and specialists, physiotherapists, nurses and other paramedics (see gap check); professions on the FSMA list not yet verified (alternative medicine, veterinarians, patent attorneys, insolvency practitioners, recruitment agencies in Flanders, financial planners); technical testing (may hold EPB/EPC and asbestos experts) | Professional risk and client protection. No statement about an obligation until the lawyer confirms | Treat as commercial until confirmed. |
| commercial_need | Management consultants, IT consultants and software developers, marketing/PR/design agencies, legal advisers (non-lawyers), real estate appraisers, other advisory and service professions | Advice errors and client claims; clients and contracts often ask for proof of cover (hypothesis, to test) | About 1,900 starters a month, four times the mandatory segment. NACE-BEL 2025 codes to confirm (70200 is management consulting). |
| no_outreach | Real estate agents and property managers (collective BIV policy), lawyers, notaries, bailiffs and company auditors (collective policies via bar or chamber, to confirm), insurance and credit intermediaries (competitors) | n/a | Already covered or competitors. Revisit only as a review offer at renewal. |

## Gap check (23 Oct 2026)

All NACE-BEL 2025 main codes in liberal, advisory, health, IT and construction sections, starters 1 Oct 2025 to 19 Oct 2026 (12.6 months), KBO snapshot of 19 Oct. "Companies" = not a sole trader, so contactable by e-mail within the legal-person exception. "KBO contact" = company with e-mail or website in KBO (the website finder adds more).

| Segment (codes) | Starters a month | Companies a month | Companies with KBO contact | Sole traders |
|---|---|---|---|---|
| Physiotherapists (86951) | 302 | 128 | 20 | 58% |
| Medical specialists (86220) | 155 | 112 | 11 | 28% |
| Nurses and midwives (86940) | 298 | 110 | 17 | 63% |
| GPs (86210) | 120 | 81 | 8 | 33% |
| Dentists (86230) | 79 | 46 | 4 | 42% |
| Speech, podiatry, dietetics, occupational therapy, osteopathy (86996, 86994, 86995, 86952, 86963) | 247 | 53 | 8 | 60-90% |
| Veterinarians (75000) | 56 | 20 | 3 | 63% |
| Software design, other IT (62100, 62900) | 679 | 318 | 47 | about 50% |
| PR, advertising, graphic design (73300, 73110, 74120) | 861 | 287 | 43 | 48-82% |
| Lawyers (69101) | 223 | 90 | 8 | 60% |
| Financial support incl. planners (66199) | 59 | 44 | 5 | 25% |
| Technical testing (71209) | 56 | 30 | 6 | 46% |
| Real estate appraisers (68322) | 73 | 30 | 6 | 59% |
| Legal advisers, non-lawyers (69109) | 57 | 27 | 3 | 52% |
| Recruitment (78100) | 40 | 22 | 3 | 45% |

Findings:

1. Healthcare is the largest missing block: about 530 companies a month, more than all construction professions together. None of it was in the pipeline. Dentists alone are small (46 companies a month) but they are run as companies more often than paramedics.
2. Obligation for healthcare practitioners: not found. The Quality Act of 22 April 2019 sets practice requirements; searches found no insurance duty in it. Do not cite a law for these segments until the lawyer confirms. Insurers (KBC, DVV, AXA) already sell dedicated (para)medical policies, and professional associations often bundle group policies, the same risk as VMx for architects.
3. Financial planners: the Act of 25 April 2014 requires professional liability cover for FSMA-licensed independent planners (FSMA licence checklist). 66199 is broader, so match against the FSMA list before using the obligation.
4. Lawyers, notaries, bailiffs and auditors: collective policies are assumed, so no_outreach. Confirm per profession.
5. Considered and left out: contractors (41, 42, 43; their 2018 obligation is ten-year liability, out of scope per decision 1), beauty and wellness (96), coaching and training (85), artists (90), translators and interpreters (74301, 74302; about 9 companies a month), interior design without the architect title (74130), patent agents (74910, under 5 a month). Revisit translators and interior designers if commercial_need works.

Codes are in `SEGMENTS` (`src/rcpro/leads.py`). Outreach stays limited to the pilot (`PILOT` in `src/rcpro/outreach.py`).

## To measure before building templates for commercial_need

1. Companies versus sole traders per segment. The KBO direct marketing ban on sole traders applies here as well.
2. E-mail and website presence per segment, as done for the pilot.
3. Whether clients actually require proof of cover (interview two or three consultants or a broker).

## Main reason to buy per group

Confidence: high = legal text, medium = known market pattern not yet verified, low = hypothesis. Same table as Phase 4 in Notion; Notion holds the templates per segment.

| Group | sales_angle | Main reason | Confidence |
|---|---|---|---|
| Architects, interior architects, land surveyors | legal_obligation | Act of 9 May 2019; insurer and policy number on every quote and contract (art. 14); fine EUR 26 to 10,000 | High |
| Engineers, design offices, landscape architects | legal_obligation if building work, else commercial_need | Same Act, only for real estate works; qualifying question first | High for the Act, low for scope |
| EPB/EPC, asbestos, safety coordinators | legal_obligation | Same Act | Medium |
| Accountants, tax advisers (ITAA) | legal_obligation, partner | Act of 17 March 2019, art. 44; possibly partnership instead of policy | High |
| Psychologists, therapists | legal_unconfirmed | Personal liability for client harm; complaints and disciplinary procedures | Low |
| Other FSMA-list professions | legal_unconfirmed | Unknown per profession | Low |
| IT consultants | commercial_need | Clients and staffing agencies ask for an attest; one error can exceed a year of fees | Medium |
| Management consultants | commercial_need | Client claims for financial loss from advice; larger clients and tenders ask for proof | Medium |
| Other advisory professions | commercial_need | Client claims for loss from the service; some clients ask for an attest | Low |

For every group, but never presented as an obligation: a sole trader answers with private assets, and a professional stays personally liable for own faults inside a company. Strongest timing signal: the first assignment as an independent.

## Workflow rule

Non-mandatory leads are prospects and follow the same sequence (e-mail day 1, follow-up day 6, WhatsApp after reply or click). An engineer who answers "no" to the construction question moves to commercial_need instead of being dropped. Only an explicit "not interested" or unsubscribe ends contact.
