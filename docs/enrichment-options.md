# Enrichment beyond websites: options tested (19 October 2026)

Goal: find more websites, learn who the founders are, and learn what the new company will actually do. Each option was tried on the 100-company sample from `docs/contact-sources-measurement.md`, or on part of it. Ranked by value.

## 1. Staatsblad founding deed (recommended)

Every new company publishes its founding deed in the annexes of the Belgisch Staatsblad. The list per enterprise number is at `ejustice.just.fgov.be/cgi_tsv/list.pl?btw=<number>`, and the PDF is linked from it.

Tested on the first 25 of the sample:

| Found | Companies |
|---|---|
| Publication exists | 24 of 25 |
| PDF has a text layer (no OCR needed) | 23 of 25 |
| Founder or director named, crude regex | 16 of 25 |
| Purpose clause (voorwerp, objet) | 23 of 25 |
| Company e-mail or website in the statutes | 1 of 25 |

What the deed adds:
- **Who**: founders, shareholders, first directors, notary.
- **What**: the purpose clause in the company's own words, for example "diensten die behoren tot de uitoefening van het beroep van architect". For engineers, whose activity codes leave 58% unknown, this is the missing evidence.
- **Where**: the full registered office address.

Constraints:
- **Reuse**: the terms of use (section III) say the information is free of rights and may be reused for commercial purposes. Founder names and home addresses are still personal data under GDPR, so this needs a legitimate interest assessment and an art. 14 notice. This is open question 2 again, for a different source.
- **Rate limit**: HTTP 429 after about 50 requests at 1 per second. Use 1 request per 5 seconds. With about 400 starters a month, that is a few minutes a day.
- **Extraction**: a regex finds founders in 16 of 25 deeds, and misses French forms and deeds with several parties. Use the same weekly LLM step as `classify`: export deed text, Claude extracts founders, a one-line activity summary and construction yes/no with a quote as evidence, then import. That also feeds the engineers classification.

## 2. Founder to existing business, inside KBO (recommended as a qualification signal, legal check first)

The other enterprise numbers printed on sites in the measurement turned out to be the founder's own earlier business:

| New company | Number on its site | In KBO |
|---|---|---|
| Tuinen Uyttendaele | 0824.285.115 | sole trader "Uyttendaele, Peter", active since 2010 |
| TekniSafe | 0544.304.711 | sole trader "Hernandez Vazquez, Nicolas", since August 2025 |
| CAZAL GROUP | 0777.354.337 | sole trader "Cazal, Loïc", since 2021 |
| ATALEX GROUP | 0826.352.995 | company ATALEX (accountants), since 2010 |

KBO Open Data does contain sole traders' names. A founder name from the deed (option 1) can therefore be matched to an active or stopped sole trader with the same name, activity and postcode, without any website.

That answers an important question: is this a real starter, or an existing practice moving into a company, which probably already holds a policy (open question 7)? All 10 sites found in the measurement had a domain registered before the start date, which points the same way.

Legal constraint: this processes sole traders' KBO data for a commercial purpose. Use it only to qualify or deprioritise a lead, never to contact the sole trader. Confirm under open question 1 before building.

## 3. Bug fix in `rcpro.websites` (done)

KBO stores some websites and e-mail domains with a trailing dot (`www.lotharmorioux.com.`). DNS lookups on those failed, so a site KBO itself listed was never fetched. Fixed and covered by a test. In the case found, the site is genuinely "under construction", but the e-mail address is real.

## 4. Search API with founder name (worth a paid test)

Query `"<company name>" <municipality>`, then `"<founder>" architect|ingenieur|comptable`. That finds Instagram, LinkedIn, Facebook pages and personal sites, which architects and designers use more than websites.

- Needs a Brave Search or Google Programmable Search key. There is none in the environment. The earlier Notion test found 0 of 10, but that was by company name only.
- LinkedIn and Instagram results are links to read by hand, not pages to scrape: their terms forbid scraping.
- Test on the same 100 companies once there is a key. The cost is about EUR 0.50 for 100 companies on Brave's paid tier.

## 5. Professional registers (needs legal sign-off)

- **Order of Architects** (vind.architect.be): best source for architects, already blocked by open question 2.
- **ITAA** (accountants and tax advisers): accountants scored 0 of 22 websites, so a register would help most here. The site renders the search with JavaScript and could not be read automatically. Check by hand whether it shows contact data, and under which terms.
- **Landmeters-experten** (FOD Economie) and the **Psychologencommissie**: public registers, not tested.

All registers raise the same questions as the Order: terms of use, database right, art. 14 notice.

## Not worth it

- **Founder-name domains** (`surname.be`, `firstname-surname.be`): 168 domains tried for 16 companies. At most 1 plausible personal site (krisdekeyzer.be). The rest belonged to namesakes: a print shop, a kitchen maker, a painter, a web agency.
- **Certificate Transparency**: crt.sh returned 502 all day, and Cert Spotter only searches exact domains, so there is no keyword search for new domains.
- **MX-only domains**: 7 found, none added a contact.
- **KBO Public Search** (kbopub): shows the directors, but the Staatsblad deed holds the same and more, under clearer reuse terms. Skip unless the deed is missing.

## Suggested order

1. Staatsblad fetcher plus the LLM extraction step: founders, activity summary, construction yes/no. This also reduces the engineers' unknown share.
2. Ask the lawyer about option 2 and the registers, alongside open questions 1 and 2.
3. A paid search API test on 100 companies, using founder names from step 1.

## First real run (19 October 2026)

`python -m rcpro websites` on the 301 newest companies, started 1 to 16 October 2026. This ran with the code from before the trailing-dot fix.

| Group | Companies | Site found (verified + probable) | Extra e-mail | Extra phone |
|---|---|---|---|---|
| legal_obligation | 49 | 3 | 3 | 1 |
| legal_unconfirmed | 6 | 0 | 0 | 0 |
| commercial_need | 246 | 9 | 7 | 4 |
| **Total** | **301** | **12 (4%)** | **10** | **5** |

That is 4%, against 10% in the sample, which spans a full year. Companies two weeks old mostly have no site yet.

`websites` searches each company only once. A second pass on `none` results after about 60 days would catch sites that go live later, and it costs only one query on `checked_at`.
