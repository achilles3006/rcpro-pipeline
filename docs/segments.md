# Segments and sales angle

Rule: the legal obligation is used as a sales argument only for segments marked `legal_obligation`. For every other segment, messages and call scripts must not state or imply that the law requires the insurance. Reason: claiming an obligation that does not exist is a misleading commercial practice and an insurance distribution risk. Lawyer to confirm wording.

Every lead carries a `sales_angle` value. Message templates are selected on it.

| sales_angle | Segments | Sales story | Notes |
|---|---|---|---|
| legal_obligation | Architects, interior architects, land surveyors (settled by code); engineers and design offices, landscape and urban architects (classification needed); EPB/EPC assessors, asbestos experts, safety coordinators (no usable list yet) | Act of 9 May 2019: mandatory cover, minimum amounts, insurer and policy number on every quote and contract | Pilot segment. About 400 starters a month, about 170 architects. |
| legal_obligation, partner | Certified accountants and tax advisers (ITAA, Act of 17 March 2019, art. 44) | Same style of story, but they are also a referral channel | About 53 a month. Decide per lead: prospect or partner. Referral fees need legal validation. |
| legal_unconfirmed | Psychologists and therapists (about 200 a month); professions on the FSMA list not yet verified (alternative medicine, veterinarians, patent attorneys, insolvency practitioners, recruitment agencies in Flanders) | Professional risk and client protection. No statement about an obligation until the lawyer confirms | Treat as commercial until confirmed. |
| commercial_need | Management consultants, IT consultants, other advisory and service professions | Advice errors and client claims; clients and contracts often ask for proof of cover (hypothesis, to test) | About 1,900 starters a month, four times the mandatory segment. NACE-BEL 2025 codes to confirm (70200 is management consulting). |
| no_outreach | Real estate agents and property managers (collective BIV policy), company auditors and notaries (collective policies), insurance and credit intermediaries (competitors) | n/a | Already covered or competitors. Revisit only as a review offer at renewal. |

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
