# Postingzeiten-Recherche – AI Agent Builder – 20.11.2026

Status: datierter redaktioneller Quellenabgleich für Entwurfsplanung, **keine Veröffentlichungsfreigabe**.

## Quellenbasis (Abruf 20.11.2026)

| Kanal | Buffer | Sprout Social | Befund / Abweichung |
|---|---|---|---|
| LinkedIn | [Buffer 2026, 4,8 Mio. Posts](https://buffer.com/resources/best-time-to-post-on-linkedin/) (Herbst 2026): Mittwoch 16 Uhr, Freitag 15–16 Uhr; werktags 15–20 Uhr | [Sprout Social, März 2026](https://sproutsocial.com/insights/best-times-to-post-on-linkedin/): Dienstag 11–17 Uhr; Basis 307.000 Profile/knapp 2 Mrd. Interaktionen plattformübergreifend | Wochentag und Tageszeit weichen ab. Beibehaltung Mittwoch 16 Uhr als Pilot-Hypothese aufgrund Buffer/B2B-Fokus, keine Aussage über Josef-spezifische Reichweite |
| Facebook | [Buffer 2026, 14 Mio. Posts](https://buffer.com/resources/best-time-to-post-on-facebook/) (2026): Donnerstag 9 Uhr; Mittwoch 8 Uhr ebenfalls stark | [Sprout Social, März 2026](https://sproutsocial.com/insights/best-times-to-post-on-facebook/): Dienstag/Mittwoch 12–20 Uhr, Donnerstag 12–14 Uhr | Deutliche Stundenabweichung. Der bisherige Donnerstag-9-Uhr-Pilot bleibt vorerst auf Grundlage der größeren plattformspezifischen Buffer-Stichprobe; später eigene Daten bevorzugen |
| Instagram | [Buffer 23.09.2026, 9,6 Mio. Posts](https://buffer.com/resources/when-is-the-best-time-to-post-on-instagram/): Mittwoch 12/18 Uhr, Donnerstag 9 Uhr; mittwochs insgesamt stark | [Sprout Social, März 2026](https://sproutsocial.com/insights/best-times-to-post-on-instagram/): starker Schwerpunkt auf Werktagen (Zeiten variieren je Branche/Tag) | Mittwoch 18 Uhr bleibt ein datengestützter Startwert, nicht als verbindlich optimale Uhrzeit für das Konto behauptet |

Sprout-Erhebung: ca. 30.000 Kunden, nahezu 2 Milliarden Interaktionen auf ca. 307.000 Profilen, Zeitraum 27.11.2025–27.02.2026 (laut Studienmethodik). Buffer untersuchte je Kanal andere Datenbestände (siehe Links).

## Grenzen

- Keine hinreichend großen und vergleichbaren **eigenen** Account-Statistiken wurden in diesem Auftrag ausgelesen. Die Vorschläge sind Bevölkerungs-/Plattformhypothesen.
- Die Datei `scripts/posting_time_planner.py` verwendet weiterhin die bisherige Priorisierung der Slot-Kandidaten; es wurde nur das tatsächliche Prüfdatum auf 20.11.2026 fortgeschrieben. Grund: Quellen rechtfertigen keinen unbemerkten Wechsel der bisher benutzten Pilotzeiten.
- `MIN_REVIEW_DAYS=5`, `MIN_CHANNEL_GAP=3` und konfliktfreie Reservierungsprüfung bleiben unverändert. Kalenderzeiten sind Europe/Berlin (MEZ/MESZ) und werden explizit nach UTC konvertiert.
- News vom 19.11.2026 können bei einem Prüfpuffer von fünf Tagen an Aktualität verlieren. Eine **frühere tatsächliche Veröffentlichung** erfordert die gesonderte Freigabe Josefs und darf nicht automatisch aus `dueAt` erfolgen.
- Neue Recherche spätestens 20.12.2026; früher bei wesentlich veränderten Plattformregeln oder ausreichenden eigenen Daten.

Erfasst für den einmaligen News-Auftrag `2026-11-20-telekom-mistral-europa`. Keine Änderungen an bestehenden Buffer-Posts.
