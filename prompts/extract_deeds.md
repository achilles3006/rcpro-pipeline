You read founding deeds of newly started Belgian companies, published in the annexes
of the Belgisch Staatsblad / Moniteur belge (Dutch, French or German).

Input below: one JSON object per line with `enterprise_number`, `name`, `segment`
(the KBO activity group) and `text` (the deed, extracted from the PDF).

For each deed, extract:
1. `founders`: every founder (oprichter, comparant, constituant, Gründer) and every
   first director or manager (bestuurder, zaakvoerder, administrateur, gérant), as
   {"name": "...", "role": "..."}. Role in English: founder, director, founder and director,
   permanent representative. Not the notary. A company that founds or directs, by its
   name. Leave out addresses and dates of birth.
2. `activity_summary`: one line in English, at most 20 words, on what the company does,
   from the purpose clause (voorwerp, objet). Null if there is no purpose clause.
3. `construction_related`: does the purpose clause cover intellectual services for real
   estate works (buildings, civil works, stability, HVAC or electrical design for
   buildings, EPB, site safety coordination, architecture, surveying)?
   - `yes`: the clause names such services.
   - `no`: the clause names engineering or design work outside real estate (industry,
     machines, vehicles, software, products, processes) and no real estate works.
   - `unknown`: anything else, including a long generic clause that lists everything.
4. `evidence`: a short quote from the deed, in its own language, that supports
   `construction_related`. Null for unknown.

Rules: use only the deed text; do not guess from general knowledge about a company.
No evidence means unknown.

Output: only JSON lines, one per input line, nothing else:
{"enterprise_number": "...", "founders": [{"name": "...", "role": "..."}], "activity_summary": "...", "construction_related": "yes|no|unknown", "evidence": "..."}
