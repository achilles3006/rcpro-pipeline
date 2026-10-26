"""Staatsblad list parsing on fixed HTML, no network."""

from datetime import date

from rcpro import staatsblad

# Shape of cgi_tsv/list.pl, from TekniSafe (1041.658.155), with a later publication before it.
LIST = """
<A name="SUM0"></a><div class="list-item"><div class="list-item--content">
<p class="list-item--subtitle">1) <font color=blue>TEKNISAFE</font>&nbsp;&nbsp;SRL</p>
<a href="article.pl?btw=1041658155" class="list-item--title">PLACE DE LA QUEUE 11 6010 COUILLET<br>1041.658.155<br>
RUBRIQUE FIN (CESSATION, ANNULATION CESSATION, NULLITE, ETC...)<br>
2026-09-30 / 0400001  &nbsp;<a class="standard" href="/tsv_pdf/2026/09/30/26400001.pdf" target="_blank">BEELD</a></a></div></div>
<A name="SUM1"></a><div class="list-item"><div class="list-item--content">
<a href="article.pl?btw=1041658155" class="list-item--title">1041.658.155<br>
RUBRIQUE CONSTITUTION (NOUVELLE PERSONNE MORALE, OUVERTURE SUCCURSALE, ETC...) <br>
2026-08-27 / 0356300  &nbsp;<a class="standard" href="/tsv_pdf/2026/08/27/26356300.pdf" target="_blank">BEELD</a></a></div></div>
<a href="/img_2024/pdf/GebruiksvoorwaardenNL.pdf">Gebruiksvoorwaarden</a>
"""


def test_founding_pdf_picks_constitution():
    assert staatsblad.founding_pdf(LIST) == (staatsblad.BASE + "/tsv_pdf/2026/08/27/26356300.pdf", date(2026, 8, 27))


def test_founding_pdf_dutch_and_missing():
    nl = LIST.replace("RUBRIQUE CONSTITUTION (NOUVELLE PERSONNE MORALE", "RUBRIEK OPRICHTING (NIEUWE RECHTSPERSOON")
    assert staatsblad.founding_pdf(nl)[1] == date(2026, 8, 27)
    assert staatsblad.founding_pdf(LIST.replace("CONSTITUTION", "STATUTS")) == (None, None)
    assert staatsblad.founding_pdf("<html>Geen resultaten</html>") == (None, None)


def test_contacts_takes_only_the_company_clause():
    text = """3. Site internet et adresse électronique Le site internet de la société est https://www.x-bureau.be/ L’adresse
    électronique de la société est : Info@X-Bureau.be. Toute communication ... 1. De heer Peeters, wonende te Gent,
    e-mailadres voor kennisgevingen: jan.peeters@gmail.com. Volmacht aan Accofid (info@accofid.be). Notaris: www.notaire.be"""
    assert staatsblad.contacts(text) == (["info@x-bureau.be"], ["x-bureau.be"])
    assert staatsblad.contacts(None) == ([], [])
