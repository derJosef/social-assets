# Postingzeiten 2026: zwei unabhängige Studien je Kanal

**Stand: 12. Oktober 2026.** Gilt für den Entwurfszeitplan der
AI-Agent-Builder-Wochenkampagne. Das Modul `scripts/posting_time_planner.py`
berechnet Uhrzeit und Datum in Europe/Berlin und UTC. Es ruft keine Buffer-API
auf und berechtigt keinesfalls zur Veröffentlichung.

## Tatsächliche Quellen und Messbasis

| Kanal | Buffer-Studie (herausgegeben / Datensatz) | Sprout-Social-Studie (herausgegeben / Datensatz) |
| --- | --- | --- |
| LinkedIn | [Buffer, 09.09.2026](https://buffer.com/resources/best-time-to-post-on-linkedin/): 4,8 Mio. Beiträge; lokale Engagement-Zeiten | [Sprout, 31.03.2026](https://sproutsocial.com/insights/best-times-to-post-on-linkedin/): Teil der ca. 2 Mrd. Interaktionen / 307.000 Profile, Messzeitraum 27.11.2025–27.02.2026 |
| Facebook | [Buffer, 26.02.2026](https://buffer.com/resources/best-time-to-post-on-facebook/): 14 Mio. Beiträge | [Sprout, 31.03.2026](https://sproutsocial.com/insights/best-times-to-post-on-facebook/): gleiche unabhängige Sprout-Stichprobe; zusätzlich branchenspezifisch Software & Tech |
| Instagram | [Buffer, 23.09.2026](https://buffer.com/resources/when-is-the-best-time-to-post-on-instagram/): 9,6 Mio. Beiträge, 200.000+ Accounts, Messzeitraum 01/2024–12/2025 | [Sprout, 31.03.2026](https://sproutsocial.com/insights/best-times-to-post-on-instagram/): Teil der ca. 2 Mrd. Interaktionen / 307.000 Profile, Messzeitraum 27.11.2025–27.02.2026 |

**Unabhängigkeit:** Buffer wertet über Buffer gesendete Beiträge aus,
Sprout Social die Profile/Interaktionen seiner eigenen Kunden. Diese
Populationen, Messgrößen und Erhebungszeiträume sind nicht identisch;
die Prozent- oder Engagementwerte dürfen nicht unmittelbar gleichgesetzt
werden. Beide Anbieter formulieren ihre Zeitfenster in **lokaler Zeit**.

**Aktualitätsprüfung:** Originalseiten am 12.10.2026 direkt geöffnet und
inhaltlich geprüft. Die Recherche ist spätestens nach 30 Tagen neu
abzugleichen (**11.11.2026**). Das Programm stoppt bei älteren Daten
absichtlich fail-closed, statt still veraltete Spitzenzeiten als
aktuell auszugeben. Kein automatischer erneuter Abruf oder Änderung von
Dateien wird durch einen Testlauf vorgetäuscht.

## Fachlicher Abgleich statt Scheingenauigkeit

**LinkedIn:** Buffer beobachtet stärkere spätere Slots, vor allem
Mittwoch 16 Uhr, Donnerstag 17 Uhr und Dienstag 16 Uhr. Sprout findet
Dienstag bis Donnerstag überwiegend 11–17 Uhr. Die Schnittmenge unterstützt
Mittwoch 16, Donnerstag 17, Dienstag 16 und Mittwoch 15 Uhr. Buffer bewertet
Freitag 15 Uhr gut, Sprout hält Freitag vornehmlich 11 und 13–14 Uhr für
stark; der strittige Freitagsslot wurde deshalb nicht übernommen.

**Facebook:** Die Gesamtmarktstudien widersprechen sich:
Buffer bevorzugt insbesondere Donnerstag 9 Uhr und Werktagsmorgende
(6–11 Uhr), Sprout insgesamt Dienstag/Mittwoch 12–20 Uhr. Für die hier
angenommene **B2B-/Software-&-Tech-Zielgruppe** zeigt Sprouts
branchenspezifische Aufschlüsselung jedoch Dienstag 7–11 Uhr, Mittwoch
8–11 Uhr sowie Donnerstag/Freitag 7–10 Uhr. Als bewusst
**branchenspezifische Pilot-Hypothese** bleiben Donnerstag 9,
Mittwoch 8, Dienstag 8, Freitag 8 Uhr. Es gibt keine statistische
Sicherheit, dass Josefs Facebook-Follower diesen Mustern entsprechen.

**Instagram:** Buffer bevorzugt Donnerstag 9, Mittwoch 12 und 18 Uhr;
Sprout zeigt höhere Gesamt-Engagementfenster Mittwoch 12–21 Uhr,
Dienstag 13–19 Uhr, Donnerstag 12–14 Uhr. Die robuste Schnittmenge
lautet Mittwoch 18 und 12 Uhr sowie Dienstag 19 Uhr.
Der widersprüchliche Donnerstagmorgen wird nicht als Standard verwendet.

Damit sind die priorisierten **Test-Slots** (Montag=0 im Programm):

| LinkedIn | Facebook | Instagram |
| --- | --- | --- |
| Mi 16, Do 17, Di 16, Mi 15 | Do 09, Mi 08, Di 08, Fr 08 | Mi 18, Mi 12, Di 19 |

Die Reihenfolge ist eine **redaktionelle Heuristik**. Sie ist kein
experimentell ermitteltes Optimum für Josef. Eigene valide Kanalstatistik,
sofern künftig lesbar und ausreichend groß, hat Vorrang vor diesen
übergreifenden Studien.

## Algorithmus und sichere Grenzen

1. Mindestens fünf Kalendertage Vorlauf zwischen Recherche und dem ersten
   vorgeschlagenen Publikationsdatum.
2. Maximal 35 Tage Suchhorizont, ohne automatische Verlängerung.
3. Pro Plattform/Channel werden gespeicherte Manifestzeiten und
   `ready-to-schedule/`-Anfragen separat und nur lesend als Reservierungen
   berücksichtigt. Der Abstand beträgt mindestens 72 Stunden.
4. Der Zielwert priorisiert den Slot-Rang (Gewicht 8) und berücksichtigt
   Wartezeit in Tagen. Ein besserer Slot gewinnt innerhalb dieses
   nachvollziehbaren Rankings.
5. Ausgabe immer in Europe/Berlin inklusive tatsächlich zutreffendem
   MEZ-/MESZ-Offset und als korrespondierende UTC-ISO-Zeit.
6. Wenn die Quellenrecherche veraltet, die Reservierung ungültig oder
   kein Fenster frei ist, stoppt die Planung – **niemals erfinden**.
7. Die ausgewählten Zeiten werden in Buffer zunächst nur als
   `status=draft` und als `dueAt` gespeichert. Erst Josefs
   nachgelagerte Freigabe darf eine bestehende Post-ID aktivieren.

## Bereits getestete technische Grenzen

- Das Modul schreibt selbst keine Dateien und ruft weder Buffer noch
  GitHub-API auf. Alle Determinismus- und DST-Tests sind offline.
- Historische Kampagnen aus separaten Output-Branches werden durch
  `scripts/campaign_reservations.py` read-only importiert, nicht
  auf `main` zurückgeschrieben.
- Ein früherer von Josef ausgelöster
  [Buffer-Einmaltest](https://github.com/derJosef/social-assets/actions/runs/38179032859)
  bewies die API-Kombination `saveToDraft:true` +
  `mode:customScheduled` + `dueAt` mit `status=draft`.
  Das ist **kein** neuer Live-Test und keine Freigabe der Integration.
- Quellzeitpunkte ohne echte Buffer-Kanalstatistik und die bildseitige
  Vollautomation bleiben separate Produktionsrisiken.

Offline testen:
```bash
python3 -B -m unittest discover -s tests -p 'test_posting_time_planner.py' -v
```
