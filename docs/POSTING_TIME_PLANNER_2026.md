# Social-Media-Zeitfenster 2026 – geprüfte Vorschläge, kein Scheduling

**Status:** Review-Entwurf. Diese Regel wählt ausschließlich Datum und Uhrzeit
für `campaign-manifests/<kampagne>.json::posting_times` und den lesbaren
Kampagnenplan. Sie ruft Buffer nicht auf und berechtigt weder einen Draft-Transfer
noch einen Wechsel auf `scheduled`.

## Was die bisherige Zeitwahl auf `main` nicht abdeckt

Die bisherige Orchestrierung verwendet unveränderliche Wochentage und verschiebt
eine **komplette neue Kampagne** immer hinter das letzte Datum aller bereits
geplanten Kampagnen, zusätzlich um sieben Tage. Damit können Beiträge trotz
freier geeigneter Zeitfenster wochenlang hinter andere Entwürfe rutschen.
Insbesondere berücksichtigt sie die `ready-to-schedule/`-Anfragen nicht.

## Belegbasis und vorläufige Prioritäten

Die Plattformauswertungen von Buffer sind allgemeine Engagement-Benchmarks,
**keine** Leistungsprognose für Josef Pauderers eigenes B2B-Publikum.

| Plattform | Bevorzugte Start-Slots (Europe/Berlin) | Datenbasis |
| --- | --- | --- |
| LinkedIn | Mittwoch 16 Uhr; danach Freitag 15, Donnerstag 17, Dienstag 16 | [Buffer, Sept. 2026, 4,8 Mio. Beiträge](https://buffer.com/resources/best-time-to-post-on-linkedin/) |
| Facebook | Donnerstag 09 Uhr; danach Mittwoch 08, Dienstag 08, Freitag 08 | [Buffer, 2026, 14 Mio. Beiträge](https://buffer.com/resources/best-time-to-post-on-facebook/) |
| Instagram | Mittwoch 18 Uhr; danach Donnerstag 09, Mittwoch 12, Dienstag 19 | [Buffer, Sept. 2026, 9,6 Mio. Beiträge](https://buffer.com/resources/when-is-the-best-time-to-post-on-instagram/) |

Die sekundären Slots dienen als pragmatische Alternativen aus denselben Studien.
Diese Reihenfolge ist eine **redaktionelle Heuristik** und keine mathematisch
ermittelte Rangfolge einer individuellen Kanalanalyse. Vor dem produktiven
Einsatz soll sie mit eigenen Reichweiten- und Interaktionsdaten abgeglichen
werden, soweit diese verfügbar und zulässig sind. Quellen/Studien können
altern; eine neue Studie erfordert eine bewusste Code-/Testanpassung.

## Auswahlregel

1. Beginne mindestens **fünf Kalendertage** nach Erstellung als Vorlauf für
   die menschliche Brief- und spätere Veröffentlichungsfreigabe.
2. Betrachte höchstens die folgenden **35 Tage**. Falls nichts frei ist,
   stoppe mit Fehlermeldung statt beliebig weit vorzudatieren.
3. Prüfe die Zeitvorschläge jeder Plattform **unabhängig**, statt alle drei
   Kanäle gemeinsam um Wochen zu verzögern.
4. Blockiere pro Kanal Zeitfenster innerhalb von **72 Stunden** um vorhandene
   `campaign-manifests/`-Vorschläge und um `ready-to-schedule/`-Anfragen.
   Die Quellen werden read-only und fail-closed gelesen. Ein GitHub-Dokument
   ist kein Nachweis für den aktuellen Buffer-Status.
5. Suche im freien Kandidatenraum den besten Wert aus
   `8 × Slot-Rang + Kalendertage seit frühestem erlaubtem Tag`.
   Dadurch ist ein besserer Slot einige Tage später oft sinnvoll, aber es
   entsteht keine Wartezeit von vielen Wochen nur wegen eines Top-Slots.
6. Speichere Berliner Ortszeit mit tatsächlichem MEZ/MESZ-Offset und die
   exakte UTC-Zeit im **unveränderten bisherigen Manifest-Schema**.

Diese Zahlen sind überprüfbare Erstvorgaben für eine sichere Vorschau, keine
von Josef bereits gebilligte Marketingstrategie. Das Script ändert keine
bestehenden Manifeste und reserviert keine Termine durch einen GitHub-Commit.

## Beispiele, nur offline

Ausgehend vom 11.10.2026 ohne belegte Buchungen wäre der Vorschlag etwa:

- LinkedIn Mittwoch 21.10.2026 16:00 MESZ
- Facebook Donnerstag 22.10.2026 09:00 MESZ
- Instagram Mittwoch 21.10.2026 18:00 MESZ

Das echte Repository enthält bereits einen anderen LinkedIn-Termin für den
21.10.2026. Dieser wird **nicht** überschrieben; die neue Auswahl findet ein
anderes freies Zeitfenster. In der gestapelten Integrationsvariante mit der
Bot-Schreibtrennung werden ältere Kampagnenmanifeste zuvor ausschließlich
lesend aus `automation/campaign/*` importiert. Die Planung berücksichtigt
dadurch auch bereits vorbereitete, aber nicht auf `main` liegende Termine.

Die Tests sind völlig offline:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest discover -s tests -p 'test_posting_time_planner.py' -v
```

**Diese Zeitplaner-Änderung:** keine Buffer-API-Schreiboperation, keine
Änderung bestehender `ready-to-schedule/`-Anträge, keine automatische
Queue/Veröffentlichung und keine PersonalOS-Schreiboperation.

Ein früherer, ausdrücklich freigegebener Einzel-Abnahmelauf hat bereits
einen datierten Buffer-**Draft** mit unabhängig geprüftem `draft`-Status
bestätigt. Das ist keine Freigabe für erneute Live-Tests oder für einen
Merge dieser Integrationsvariante. Die produktive Aktivierung erfordert
weiterhin persönlich freigegebene Merges und den dokumentierten
Branch-/Ledger-Schutz.
