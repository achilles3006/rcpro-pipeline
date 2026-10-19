"""Select active businesses by start date and main activity (NACE-BEL 2025).

Output: one row per business with segment, legal form type, postcode, contact
presence flags, `dm_allowed_from_kbo` and `sales_angle`
(legal_obligation, legal_unconfirmed, commercial_need, no_outreach; see docs/segments.md). Sole traders carry no name.
"""
