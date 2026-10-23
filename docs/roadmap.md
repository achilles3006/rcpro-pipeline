# Vervolgplan rcpro-pipeline (23 oktober 2026)

## Waar het project nu staat

De pipeline is gebouwd, maar heeft nog maar weinig gedraaid:

| Onderdeel | Stand in `kbo.duckdb` |
|---|---|
| KBO-extract | Alleen de volledige extract 517 (20 okt). Er zijn nog geen updates geladen. |
| Leads | 28.869, waarvan 5.073 `legal_obligation`. 12.707 zijn eenmanszaken, die je niet mag contacteren. |
| Websites | 312 bedrijven geprobeerd, 13 gevonden (9 verified, 4 probable) |
| Staatsblad | 20 aktes opgehaald, 11 geëxtraheerd |
| LLM-classificatie van ingenieurs | 0: de stap heeft nooit echt gedraaid |
| Claude web search | 20 bedrijven |
| Blind labelen van contacten | Het bestand met 100 rijen staat klaar, maar niemand heeft het ingevuld |

Conclusie: de techniek is klaar. Twee dingen houden het tegen: de juridische vragen, en het feit dat de pipeline nog niet op schaal is gedraaid en gemeten.

Nummers als "punt 15" verwijzen naar `docs/open-questions.md`.

## Spoor A: juridische gates (P0, blokkeert alle outreach)

Dit is het kritieke pad. Zonder antwoord hierop gaat er geen enkele mail de deur uit.

1. Bundel de vijf P0-vragen in één brief aan de advocaat:
   - het verbod op direct marketing met KBO-gegevens;
   - het register van de Orde van Architecten;
   - toestemming voor e-mail en WhatsApp;
   - het hergebruik van oprichtersnamen uit het Staatsblad;
   - doorverwijzingen door accountants.
2. Vraag compliance welke FSMA-registratie je gebruikt: die van Omata of die van Induver. Dan kan de placeholder in de footer weg.
3. Laat de advocaat ook de verkoopformulering voor de niet-verplichte segmenten goedkeuren (punt 17).

## Spoor B: loont de pilot? (P1, beslis vóór je verder bouwt)

1. Maak met de underwriter of broker de unit economics op: premie, commissie, verwachte conversie en kost per polis. Met ongeveer 55 architectenbedrijven per maand is dit de go/no-go-vraag.
2. Ga na welk deel van de starters al verzekerd is via de Orde, een werkgever of een groepspolis. Als dat het grootste deel is, krimpt de markt sterk.
3. Hou het pilotontwerp eenvoudig: alleen architectenbedrijven, en per test maar één variant tegelijk. Statistische power is bij dit volume een echt probleem.

Beslis daarna de twee openstaande punten uit `docs/decisions.md`: wel of geen eenmanszaken, en ingenieurs nu of later.

## Spoor C: de pipeline echt laten draaien (kan meteen, geen blokkade)

1. Laad de KBO-updates sinds extract 517 en draai daarna dagelijks `python -m rcpro run`, zodat de backlog wegloopt. Met 100 bedrijven per dag duurt de Staatsblad-stap ongeveer 15 tot 20 minuten.
2. Draai de LLM-stap voor ingenieurs voor het eerst echt. Controleer daarna 100 antwoorden met de hand (punt 15).
3. Automatiseer lokaal met launchd of een cron op de Mac. De GitHub-workflow kan weg, want de database mag niet in GitHub. Vraag ondertussen SFTP-toegang aan bij FOD Economie (punt 12), zodat ook de download zonder handwerk kan.

## Spoor D: meten wat het oplevert (P1/P2)

1. Laat de 100 contactrijen blind labelen (`data/contact_labels_blind.csv`). Daarmee ken je de precisie van de verified- en probable-matches, die nu nog niet gemeten is.
2. Validatie met de underwriter (punt 16): een blind gelabelde steekproef van 200, met extra ingenieurs, en een doel van minstens 85% precisie.
3. Leg de KPI's vast, van contactratio tot kost per polis, en zet de ontbrekende Notion-pagina's voor fase 3 en 5 op.

## Spoor E: meer contactgegevens (alleen waar het iets oplevert)

Het knelpunt is dat starters vaak nog geen website hebben, niet dat het raden slecht gaat (`docs/domain-guess-v2.md`). Verder sleutelen aan het raden van domeinen heeft dus weinig zin.

| Optie | Waarde | Voorwaarde |
|---|---|---|
| Bedrijven na 3 tot 6 maanden opnieuw proberen (krijgen starters later een site?) | Ongetest, goedkoop te meten op de 312 bedrijven die al geprobeerd zijn | Geen |
| Claude web search op een grotere dev-steekproef (bv. 200) | Nu alleen op 20 getest | Alleen dev-leads, de holdout blijft onaangeroerd |
| Oprichter koppelen aan zijn vorige zaak in de KBO | Goed signaal om te kwalificeren | Juridisch akkoord (spoor A) |
| Register van de Orde van Architecten | Grootste winst bij architecten | Juridisch akkoord en netwerktoegang tot vind.architect.be |
| Domeinraden v2 inbouwen | Minder dan 1 extra site per 100 | Lage prioriteit |

## Spoor F: compliance-gate in code (fase 3, vóór de eerste mail)

Zodra spoor A antwoorden heeft:

- een suppressielijst en opt-out die de export controleert;
- een harde blokkade op `dm_allowed_from_kbo = false` en `no_outreach`;
- een log van wie wanneer en via welke bron gecontacteerd werd;
- de art. 14-melding in het eerste bericht.

Bouw dit niet vroeger: de vorm hangt af van wat de advocaat zegt.

## Voorgestelde volgorde

| Wanneer | Wat |
|---|---|
| Deze week | Brief naar de advocaat (A), afspraak met de underwriter (B), updates laden en de dagelijkse run starten (C1, C2) |
| Week 2–3 | Contacten labelen en LLM-antwoorden controleren (D1, C2), retry en web search meten (E), lokale automatisering (C3) |
| Na de juridische antwoorden | Compliance-gate (F), scope van de pilot vastleggen, eventueel het architectenregister |
| Pilot | Architectenbedrijven, één variant per keer, en na 2 à 3 maanden evalueren tegen de KPI's |

Laat vallen: verder tunen van het domeinraden en de GitHub-workflow.
