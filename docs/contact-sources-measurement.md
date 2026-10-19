# Contact sources outside KBO: measurement on 100 companies (19 October 2026)

Question: how many extra e-mail addresses, phone numbers and websites can we find outside KBO, and how sure are we of each one? This report covers the measurement only. Nothing has been built into `rcpro.websites` yet.

## Sample

- Population: 1,886 companies (not sole traders) in `leads` with `sales_angle = legal_obligation` and `mandatory` yes or likely, KBO extract 517.
- Sample: 100 drawn at random (seed 42). Breakdown: 33 architects, 22 accountants, 21 engineers, 16 urban and landscape, 7 interior architects, 1 land surveyor.
- Sole traders and the Order of Architects register are out of scope until the lawyer answers open questions 1 to 3.

## Method

For each company (`scripts/measure_contact_sources.py`):

1. Candidate domains come from:
   - the KBO WEB value;
   - the domain of the KBO e-mail address (free mail providers excluded);
   - every KBO denomination (official, abbreviation, commercial name, on the enterprise and on its establishments). Each name is normalised and its legal form stripped, then tried as `joined`, `hy-phen` and `firstword`, with `.be` and `.com`.
2. DNS: A and MX records (dnspython).
3. For each domain with an A record: fetch the homepage, plus up to six pages it links to whose links say contact, privacy, legal, mentions, impressum or about. robots.txt is respected.
4. The page is checked for an enterprise number, using the regex plus the mod-97 check digits. Without the check digit, Belgian 04xx mobile numbers matched as enterprise numbers in the first run.
5. Each match is classified as:
   - **verified**: the company's own enterprise number is on the site (Code of Economic Law art. III.74);
   - **other_company**: a different, valid enterprise number is on the site;
   - **probable**: a name match plus the postcode or municipality;
   - **weak**: a name match only;
   - **parked**: a parked page, or fewer than 40 words.
6. E-mail addresses come from `mailto:`, the page text and JSON-LD. Phone numbers come from `tel:`, the page text and JSON-LD, normalised to E.164 with `phonenumbers`. Each e-mail domain gets an MX check (no SMTP probing).
7. The domain's registration date comes from whois.dns.be (.be) or RDAP (.com).

Not measured:
- crt.sh, which returned HTTP 502 all day;
- the search API (Brave or Google), because there is no API key in the environment.

## Results

### Coverage per source (n = 100)

| | E-mail | Phone | Website |
|---|---|---|---|
| KBO | 17 | 10 | 2 |
| Site (verified + probable) only, not in KBO | +8 | +9 | +10 |
| **KBO or site** | **25** | **19** | **10** (both KBO websites turned out parked or unmatched) |

All 9 companies with a site e-mail pass the MX check. 2 of those addresses are Gmail addresses that the site itself publishes.

### Best match per company

| Level | Companies | Use |
|---|---|---|
| verified | 5 | Yes, the company's own number is on the site |
| probable | 5 | Yes, per decision 4 (1 also confirmed by the KBO e-mail domain) |
| other_company | 4 | No, see below |
| weak | 26 | No. Almost all are generic single-word .com domains (`maison.com`, `design.com`, `agence.com`) registered years before the start date |
| parked | 31 | No. Domain exists, but no usable page |
| no_http, no_dns, no_match, no candidates | 29 | Nothing found |

Per segment, verified or probable: urban and landscape 4 of 16, architects 4 of 33, engineers 2 of 21, accountants 0 of 22, interior architects 0 of 7.

### Precision of the name-guess route

- 427 name-guess domains were tried, and 6 of them hit the company's own enterprise number.
- **weak** is useless as a level. The 26 weak matches came from the noisy first-word guess. Drop that guess, or treat weak as "no match".
- **other_company** (8 domains) catches two different things:
  1. A different business with the same name, for example `marinus.be` for "Marinus architecten", whose real domain according to the KBO e-mail is `marinus-architect.be`.
  2. A predecessor or sister company of the same person, for example "WARD ROMBAUT" landing on `rdbplus.be` with `ward@rdbplus.be`.

  Only a human can tell these apart.
- The precision of probable is not yet measured independently, see below.

### Finding that changes the question: the sites are older than the companies

All 10 usable sites have a domain that was registered **before** the KBO start date:

| Company | Domain registered | Start date | Gap |
|---|---|---|---|
| Wodecka Architecture | 2021-01-25 | 2026-09-10 | 5.6 years |
| Tuinen Uyttendaele | 2020-10-14 | 2025-12-17 | 5.2 years |
| Architectureren | 2022-04-04 | 2026-06-23 | 4.2 years |
| BEYAERT GROENAANLEG | 2023-01-19 | 2025-12-29 | 2.9 years |
| KW ARCHITECT | 2023-08-31 | 2026-05-21 | 2.7 years |
| Gardenscapes | 2024-04-16 | 2026-09-15 | 2.4 years |
| TekniSafe | 2025-10-01 | 2026-08-25 | 328 days |
| Atelier vert lion | 2025-03-23 | 2025-10-30 | 221 days |
| Wattineo | 2025-06-06 | 2025-10-08 | 124 days |
| BE-Maps | 2025-07-31 | 2025-11-16 | 108 days |

The four within a year look like preparation before incorporation. The six of two years or more look like an existing practice that moved into a company: a former sole trader, or a predecessor company. That explains the other_company hits.

Consequences:
- The website route mostly finds businesses that are **not** real starters. For open question 7 (already insured), these are exactly the leads most likely to hold a policy already.
- For a true starter, the website route finds almost nothing, and DNS or MX on a new domain adds nothing either. The 7 domains that had MX but no site were all generic names or already known from the KBO e-mail.

## Is it worth building?

Net gain on 100 companies is +8 e-mail addresses and +9 phone numbers, about 160 extra e-mails a year across the population of 1,886. The cost is DNS, a few HTTP requests per company, and no API key. Building only the **verified + probable** path in `rcpro.websites` is cheap. Drop **weak** and the first-word guess.

Before outreach depends on it:
1. **Independent check (step 2 below).** Precision of probable and recall of the whole route are unknown until someone other than us labels the sample.
2. **Legal check.** Personal e-mail addresses on a site (`joppe@…`, `matthieu@…`) and Gmail addresses are personal data. They belong under open questions 1 and 3, just like the KBO e-mail addresses.
3. **Domain age as a lead feature.** Domain age is a cheap signal for "existing practice, probably insured already" and can lower the priority of a lead. Check this against the conversations.

## Independent validation (not yet done)

- `data/contact_labels_blind.csv` holds the same 100 companies in random order, with names and municipality only. It does not show our result.
- Someone who has not seen `data/contact_results.csv` fills in `website`, `email`, `phone`, `how_found` and `minutes` by hand. Allow about 3 to 5 minutes per company with a normal search engine.
- Score with:

```sql
-- duckdb, from data/
SELECT r.best_level,
       count(*) AS n,
       count(*) FILTER (l.website <> '') AS has_true_site,
       count(*) FILTER (l.website <> '' AND l.website ILIKE '%' || r.best_domain || '%') AS we_found_it
FROM 'contact_results.csv' r JOIN 'contact_labels_blind.csv' l USING (enterprise_number)
GROUP BY ALL;
```

  The rows for verified and probable give precision. `has_true_site` summed over all levels gives the recall base.
- The second independent signal is the bounce rate and reply rate of the first e-mail wave, measured separately for KBO addresses and site addresses.

## Files

- `scripts/measure_contact_sources.py`: the measurement, reproducible with seed 42.
- `data/contact_results.csv`: one row per company. `data/contact_candidates.csv`: one row per domain tried.
- `data/contact_labels_blind.csv`: sheet for the labeller.

The `data/` folder is not in git.

## Built (19 October 2026)

`rcpro.websites` (`python -m rcpro websites --limit N`) implements the verified and probable path with the standard library only. On the same 100 companies it finds the same 10 sites (5 verified, 5 probable), +8 e-mail addresses and +9 phone numbers, in about 75 seconds.

Two changes from the measurement:
- Probable now needs the municipality at a word start. A postcode no longer counts. In a test version, the postcode rule took "since 2018" on studiorickjoy.com as postcode 2018, and "Gent" matched inside another word. Requiring the postcode as well lost vertlion.com (site shows 7500, KBO has 7540) and gardenscapes.be (no postcode on the site).
- The first-word guess stays. It is the only route to wodecka.com, which is verified. The match gate rejects the generic domains it also turns up.
