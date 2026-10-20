# Domain guessing v2: design and evaluation (20 October 2026)

Question: can a better way of guessing domains from the company data find more own websites than `rcpro.websites.candidates`?

Short answer: it guesses better offline (45% to 51% of known domains), but on real leads it found nothing extra (0 of 157). For starters, the limit is that most of them have no site, not that the guesses are poor.

## Ground truth without labelling

KBO already holds the answer for part of the companies: 17,711 companies started since 2023 have their own domain in KBO (a website, or an e-mail domain that is not free mail and that at most two companies use; more than two is an accountant or a group). For these companies, the question is whether a method that sees only the names produces that domain. No network is needed, so variants can be compared in seconds.

## Split: dev and holdout

Every company falls in a fixed half by `md5(enterprise_number) % 2`. Everything below is measured on **dev**. **Holdout** is kept for one final measurement of a method that is fixed, so that there are always leads that no version has been tuned on. 43 holdout leads were crawled once before the split was introduced (0 hits; no details looked at).

## What was tried

| Idea | Effect on recall | Extra domains per company | Verdict |
|---|---|---|---|
| Patterns chosen by gain per domain (core name without generic words, first two words, without first word, `&` as "and") plus .eu and .net | 45% to 51% | +5 | In v2 |
| Local part of free-mail addresses as an extra name (`studiopli.architecture@gmail.com`) | companies with free mail: 53% to 61% | +5 for those companies | In v2 |
| Name plus a profession word (architect, studio, consulting, boekhouding, ...) | +0.9 points | +80 | Dropped |
| Last name alone, initial plus last name | +0.3 points | +1 | Dropped |

About half of the domains cannot be derived from the name at all (`brasseriebeaulieu.com` for BRASSERIE DU GOLF, `artwoodbelgium.com` for MFJ GROUP). No guessing reaches those.

## Offline result (dev, `python scripts/evaluate_domain_guess.py offline`)

| Group | n | current | v2 |
|---|---|---|---|
| All companies with their own domain | 8,821 | 45.3% (5.2 domains) | 51.1% (10.2 domains) |
| Of which with a free-mail address | 1,024 | 50.2% (5.6) | 60.8% (15.1) |

## Live result (dev, `python scripts/evaluate_domain_guess.py live`)

On the 157 dev leads where the current method found nothing, the domains that v2 adds (3.7 per company) were crawled and checked with the same rule (own enterprise number, or name plus municipality): **0 new sites**.

This is what you would expect. The current method finds a site for 4% of companies (13 of 312). If v2 raises recall by about a sixth, that is less than 1 extra site per 100 companies, so 0 of 157 is within reach of chance, and the gain is too small to see.

## Conclusion

- Hit rate = share that has a site × share of those we guess × share that passes verification. Guessing only moves the middle factor, and that factor is already about 50% of what is guessable.
- v2 is cheap (5 extra DNS lookups per company) and can be put into `rcpro.websites`, but it will not visibly change the contact rate.
- For more contact data, other routes count: retry companies after a few months (untested: do starters get a site later?), and the Claude web search on a larger dev sample.
