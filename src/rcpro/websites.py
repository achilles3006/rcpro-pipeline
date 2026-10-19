"""Website discovery for leads.

Each candidate gets a confidence level instead of pass/fail:
- verified: the page shows the lead's enterprise number (Code of Economic Law art. III.74)
- probable: name match plus municipality or postcode, and a matching activity
- weak: name match only (manual review, not used for outreach)
Decision of 19 October 2026: a wrong match is cheaper than a missed prospect.
"""
