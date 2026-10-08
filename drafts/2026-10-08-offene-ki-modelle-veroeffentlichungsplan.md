# Veröffentlichungsplan: Offene KI-Modelle, klare Kontrolle

Stand: 08.10.2026, 18:24 Europe/Berlin. **Alle drei Beiträge sind nach ausdrücklicher Freigabe durch Josef in Buffer fest terminiert** (Status `scheduled` unmittelbar über die Buffer-API bestätigt). Die tatsächliche Veröffentlichung erfolgt automatisch durch Buffer zum angegebenen Termin.

| Kanal | Zieltermin (Europe/Berlin) | Zieltermin (UTC) | Begründung |
| --- | --- | --- | --- |
| LinkedIn | Fr., 09.10.2026, 15:00 MESZ | 2026-10-09T13:00:00Z | Zeitnahe B2B-Einordnung; Buffer 2026: Freitag 15 Uhr besonders stark |
| Facebook | Mi., 14.10.2026, 09:00 MESZ | 2026-10-14T07:00:00Z | Buffer 2026: Mittwoch guter Tag, morgendliche Interaktion |
| Instagram | Mi., 14.10.2026, 18:00 MESZ | 2026-10-14T16:00:00Z | Buffer 2026: Mittwoch 18 Uhr unter den besten Slots |

Die drei Beiträge verwenden das Bild `media/images/2026-10-08-offene-ki-modelle-klare-kontrolle-linkedin.webp`, aber kanalangepasste Texte.

## Ablauf und Freigabe
- Dateien in `drafts/` lösen keinen Buffer-Transfer aus.
- Erst nach Zustimmung neu nach `ready-for-buffer/` hinzugefügte JSON-Dateien lösen **nur Buffer-Entwürfe** aus.
- Die Terminierung erfolgte nach **separater ausdrücklicher Veröffentlichungsfreigabe** über `ready-to-schedule/` und den GitHub-Workflow `.github/workflows/buffer-auto-schedule.yml` anhand der bereits vorhandenen Buffer-Post-IDs. Keine manuellen Datums-/Uhrzeiteingaben in Buffer nötig.
- Der neue Workflow bearbeitet nur vorhandene Entwürfe; `ready-for-buffer/` erzeugt weiterhin ausschließlich Entwürfe.
- Vor Veröffentlichung verbleiben die drei Beiträge in der Buffer-Warteschlange. Buffer kann bei Plattform-/Kontofehlern scheitern; dies ist keine Garantie, dass die Plattform die Beiträge tatsächlich publiziert.
- Vor zukünftigen Beiträgen sind die Postingzeiten erneut zu recherchieren und mit eigenen Kanalstatistiken abzugleichen.

## Verifizierte Buffer-Terminierungen (08.10.2026)

| Kanal | Buffer-Post-ID | Nachweis GitHub Actions |
| --- | --- | --- |
| LinkedIn | `6ac7b25edaf7bb7cba274102` | [Lauf #37808077681](https://github.com/derJosef/social-assets/actions/runs/37808077681) |
| Facebook | `6ac7b255daf7bb7cba273f54` | [Lauf #37808388065](https://github.com/derJosef/social-assets/actions/runs/37808388065) |
| Instagram | `6ac7b25ab99c473c41ba1503` | [Lauf #37808451845](https://github.com/derJosef/social-assets/actions/runs/37808451845) |

Die [abschließende lesende Statusprüfung](https://github.com/derJosef/social-assets/actions/runs/37808524833) bestätigt die drei exakten UTC-Termine und `scheduled` für alle Post-IDs. Frühere abgewiesene Versuche sind mit `pending`-Belegen auditierbar; sie erzeugten keine Terminierung und wurden vor neuen Versuchen per Buffer-Statusabfrage abgeglichen.

## Recherchierte Quellen
- LinkedIn: https://buffer.com/resources/best-time-to-post-on-linkedin/ (09.09.2026, 4,8 Mio. Beiträge)
- Facebook: https://buffer.com/resources/best-time-to-post-on-facebook/ (26.02.2026, 14 Mio. Beiträge)
- Instagram: https://buffer.com/resources/when-is-the-best-time-to-post-on-instagram/ (23.09.2026, 9,6 Mio. Beiträge)
- Abgleich: https://sproutsocial.com/insights/best-times-to-post-on-social-media/ (2026)

Die Studien sind plattformweite Orientierungswerte. Eigene Reichweiten- und Interaktionsdaten haben nach ausreichend Beobachtungen Vorrang.
