# Eerste mail: wat mag, en hoe de pipeline het afdwingt

Stand 23 oktober 2026. Dit is een werkdocument, geen juridisch advies. De punten onder "Restrisico" moeten nog naar de advocaat (open question 1 en 3).

## De regels

| Regel | Bron | Gevolg voor ons |
|---|---|---|
| Reclame per e-mail vraagt voorafgaande toestemming | art. XII.13 WER | Zonder toestemming mag het alleen binnen de uitzondering hieronder |
| Uitzondering: rechtspersonen, op onpersoonlijke adressen (info@, contact@) | KB 4 april 2003, art. 1 | Alleen BV, NV, CommV, VOF, CV, VZW, stichting. Geen eenmanszaak (natuurlijke persoon), geen maatschap zonder rechtspersoonlijkheid. Geen jan@ of voornaam.naam@ |
| Derden mogen persoonsgegevens uit de KBO niet voor direct marketing gebruiken | KB 18 juli 2008, art. 2 §1 lid 2 (herhaald in GBA-beslissing 72/2025) | Gegevens van eenmanszaken en persoonlijke adressen uit de KBO: nooit. Oprichters uit het Staatsblad: nooit |
| Algemene adressen zoals info@ zijn geen persoonsgegevens, jan@bedrijf.be wel | GBA-lijn, o.a. samengevat door Cultuurloket | Met alleen onpersoonlijke adressen valt de AVG grotendeels weg. We geven toch een korte melding (bron, doel, bezwaar) |
| Reclame moet herkenbaar zijn, de afzender identificeerbaar, met een eenvoudige manier om af te melden | art. XII.12 en XII.13 WER, KB 4 april 2003 | Het onderwerp zegt meteen dat het een verzekeringsvoorstel is (XII.12: herkenbaar "gezien de globale indruk", anders het woord "reclame"). Volledige afzender in de footer. In elke mail een afmeldmogelijkheid (XII.13 §2: ook bij handmatig verstuurde mails) |
| Een verzekeringstussenpersoon moet ingeschreven zijn bij de FSMA; reclame moet correct, duidelijk en niet misleidend zijn | Wet 4 april 2014, art. 259 | FSMA-nummer in elke mail. De wet alleen noemen waar de verplichting vaststaat (`mandatory = yes`) |

## Wat de code doet

`python -m rcpro outreach data/mails.csv` (in `src/rcpro/outreach.py`) neemt een lead alleen mee als alles klopt:

1. vennootschap met rechtspersoonlijkheid (KBO-rechtsvorm 610, 612, 011, 014, 706, 017, 125, 026);
2. een onpersoonlijk adres uit de KBO of van de eigen website (lijst `IMPERSONAL`, bv. info, contact, hello, office);
3. `sales_angle` is niet `no_outreach`, segment zit in de pilot (architecten, interieurarchitecten) tenzij `--segment` iets anders zegt;
4. adres en bedrijf staan niet op de suppressielijst, en het bedrijf is nog nooit gemaild.

Elke geëxporteerde mail komt in `outreach_log` (bedrijf, adres, bron, sjabloon, datum). De teksten staan in `templates/`: NL of FR volgens postcode (Brussel en Wallonië in het Frans), en de wettelijke versie alleen als de verplichting vaststaat. De export weigert te draaien zolang `templates/sender.toml` nog TODO's bevat.

Op 23 oktober haalden 16 pilotbedrijven alle regels (13 architecten, 3 interieurarchitecten). Over alle segmenten zijn het er 386.

## Vandaag live: checklist

Doe deze stappen in deze volgorde. Elk punt dat niet af is, blokkeert de eerste mail.

1. **FSMA-nummer.** Zoek het op in het FSMA-register en beslis of je onder de inschrijving van Omata of van Induver mailt. Zonder inschrijving mag je geen verzekeringen aanbieden.
2. **`templates/sender.toml` invullen**: naam, adres, nummers en privacylink staan er al (van omata.be). Vul nog de ondertekenaar, het mailadres en het telefoonnummer in. Laat compliance bevestigen dat Ōmata mailt onder de FSMA-inschrijving van Group Induver NV.
3. **Privacyverklaring online.** Ze moet bevatten: welke gegevens je gebruikt (algemeen adres en bedrijfsnaam), de bron (KBO, website), het doel, de grond (gerechtvaardigd belang), het recht op bezwaar, hoe lang je de gegevens bewaart, en een contactpersoon.
4. **Verwerkingsregister.** Voeg één regel toe voor "prospectie per e-mail", met een korte belangenafweging. Dit is een half uur werk.
5. **Afmelden.** Kijk elke werkdag de mailbox na. Wie STOP antwoordt of afmeldt: `python -m rcpro optout <adres>`, en zeker nooit opnieuw mailen.
6. **Versturen.** Draai `python -m rcpro outreach data/mails.csv --limit 20` en verstuur de mails één voor één vanuit een gewone mailbox (geen BCC, geen bulk). Zet eerst SPF, DKIM en DMARC op het domein. Dat is geen wettelijke eis, maar zonder belandt de mail in spam.
7. **Opvolging.** Stuur hoogstens één herinnering na ongeveer 6 dagen, de mail belooft dat. Een "nee" betekent definitief stoppen: zet het adres op de optout-lijst.
8. **Niet doen.** Geen eenmanszaken, geen persoonlijke adressen (ook niet van de website), geen oprichtersnamen, geen koude WhatsApp, en geen wettelijke verplichting noemen bij segmenten waar die niet vaststaat.

## Restrisico (voor de advocaat)

- Bij een BV met één persoon kan zelfs info@ als persoonsgegeven gelden. Dan geldt de AVG wel, en daarom staan de melding en de bezwaarmogelijkheid al in de mail.
- Valt een algemeen KBO-adres van een vennootschap onder het KBO-verbod uit 2008? Wij gaan ervan uit van niet, omdat het verbod alleen over persoonsgegevens gaat.
- De lijst `IMPERSONAL` en de keuze voor rechtsvormen 030 (buitenlandse entiteit) en 721 (zonder rechtspersoonlijkheid): die vallen nu buiten de export.
- Mogen de wettekst-zinnen in `nl_legal.txt` en `fr_legal.txt` zo blijven staan?

## Bronnen

- [GBA, beslissing ten gronde 72/2025](https://dataprotectionauthority.be/publications/beslissing-ten-gronde-nr.-72-2025.pdf): citeert KB 18 juli 2008, art. 2 §1 lid 2
- [GBA, aanbeveling 01/2020 over direct marketing](https://www.gegevensbeschermingsautoriteit.be/publications/aanbeveling-nr.-01-2020.pdf)
- [Cultuurloket, Mails en direct marketing](https://www.cultuurloket.be/kennisbank/administratieve-verplichtingen-van-je-organisatie/mails-en-direct-marketing): algemene en persoonlijke adressen
- [Juridisch Forum](https://juridischforum.be/viewtopic.php?p=387339): tekst van art. 1 KB 4 april 2003 (rechtspersoon + onpersoonlijk adres). Dit is een secundaire bron: controleer de tekst in het Staatsblad
- [FSMA, minnelijke schikking 2018](https://www.fsma.be/sites/default/files/legacy/content/NL/Sancties/2018-10-02_minnelijkeschikking.pdf): inschrijvingsplicht, art. 259 Wet 4 april 2014
