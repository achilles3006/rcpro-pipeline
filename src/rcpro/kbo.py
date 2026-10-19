"""Load the KBO Open Data full extract and apply daily updates into DuckDB.

Contract (from phase 1): updates are applied in order and never twice, via an
extract log; gaps raise a warning; an update deletes the listed keys, then inserts.
"""
