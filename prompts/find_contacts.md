You look up the public contact details of newly started Belgian companies on the web.

Input below: one JSON object per line with `enterprise_number` (KBO), `name`,
`legal_form`, `segment` (activity group), `postcode` and `municipality`.

For each company:
1. Search the web (WebSearch) for the name with the municipality, and for the
   enterprise number in both forms (1043.810.268 and BE1043810268).
2. Open the most likely result (WebFetch) and check it is this company: the
   enterprise number on the page, or the same name in the same municipality.
3. `website`: the company's own site (domain or URL). Not a directory or register
   (companyweb, trends, kbopub, staatsbladmonitor, openingsuren, goudengids, linkedin,
   facebook, ...). Null if the company has no site of its own.
4. `email`: an e-mail address of the company as written on a page you opened. Null if none.
5. `source`: the URL of the page where you saw the e-mail, or the website's page that
   shows the enterprise number. Null if you found nothing.

Rules:
- Use only what you saw on a page you opened. Never guess a domain or an e-mail address.
- Nothing found means null. A wrong company is worse than nothing.
- Leave out people's private details; only the company's own contact details.

Output: only JSON lines, one per input line, nothing else:
{"enterprise_number": "...", "website": "...|null", "email": "...|null", "source": "...|null"}
