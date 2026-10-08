# Automatische Terminierung – getrennt von der Entwurfserstellung

## Ziel und Freigabegrenze

Der bestehende Workflow `buffer-auto-drafts.yml` erstellt ausschließlich **Buffer-Entwürfe**.
Der hier ergänzte Workflow `buffer-auto-schedule.yml` kann einen **bereits vorhandenen** Buffer-Entwurf erst **nach einer zweiten, ausdrücklichen Freigabe von Josef** automatisch für einen festen Termin in die Veröffentlichungswarteschlange übernehmen.

**Achtung:** Sobald eine Terminierungsanfrage verarbeitet wurde, plant Buffer die Veröffentlichung **automatisch** zur angegebenen Uhrzeit. Ohne Veröffentlichungserlaubnis darf daher **keine** Datei unter `ready-to-schedule/` angelegt oder committet werden. Einen Entwurf anzulegen oder einen Termin zu recherchieren, ist noch keine solche Erlaubnis.

GitHub-Repository `derJosef/social-assets` bleibt öffentlich: keine vertraulichen Informationen in JSON, Commit-Nachrichten oder Belegen speichern. PersonalOS ist keine Schreibfläche dieser Integration.

## Ablauf für Agenten

1. Text und Medien in `drafts/` vorbereiten, Postingzeiten recherchieren, mit Europe/Berlin und UTC dokumentieren.
2. Nach ausdrücklicher **Entwurfsfreigabe** die drei JSON-Dateien unter `ready-for-buffer/` übertragen. GitHub Actions erstellt Buffer-Entwürfe und bestätigt sie unter `delivery-receipts/`.
3. Josef erhält eine eindeutige Übersicht: Plattform, Beitrag und konkreter Veröffentlichungstermin. Die **Termine und die automatische Veröffentlichung müssen separat freigegeben** werden.
4. Erst dann je Kanal eine neue, eindeutige Datei unter `ready-to-schedule/` committen, zum Beispiel:

   ```json
   {
     "format_version": 1,
     "target": "linkedin",
     "draft_file": "ready-for-buffer/2026-10-08-linkedin-offene-ki-modelle-klare-kontrolle.json",
     "publish_at_utc": "2026-10-09T13:00:00Z",
     "approved_for_scheduling": true
   }
   ```

5. **Nur neue Dateien** lösen automatische Terminierung aus. Eine Textänderung oder erneute Ausführung kann denselben Auftrag nicht wiederholen. Das Skript liest den originalen Buffer-Entwurfsbeleg und editiert genau dessen vorhandene Post-ID; es erzeugt **keinen zweiten Post**.
6. Der Workflow prüft vor dem API-Aufruf Kanal, ursprünglichen Entwurf, unveränderten Text, Status `draft`, mindestens zwei Minuten Vorlauf und die exakte UTC-Zeit. Nach erfolgreicher API-Antwort muss der Termin übereinstimmen. Es entsteht ein Beleg unter `schedule-receipts/`.
7. Bei unklaren API-Fehlern bleibt der Beleg auf `pending_manual_reconciliation_on_failure`. **Nicht automatisch wiederholen**; erst Status in Buffer prüfen. Die Reservierung schützt vor Doppelaktionen.

## Abnahme – 08.10.2026

Die produktive Erstterminierung der Kampagne „Offene KI-Modelle, klare Kontrolle“ ist erfolgreich:

- LinkedIn: [GitHub-Lauf #37808077681](https://github.com/derJosef/social-assets/actions/runs/37808077681), `2026-10-09T13:00:00Z`.
- Facebook: [GitHub-Lauf #37808388065](https://github.com/derJosef/social-assets/actions/runs/37808388065), `2026-10-14T07:00:00Z`.
- Instagram: [GitHub-Lauf #37808451845](https://github.com/derJosef/social-assets/actions/runs/37808451845), `2026-10-14T16:00:00Z`.

Die [abschließende lesende Buffer-Abfrage](https://github.com/derJosef/social-assets/actions/runs/37808524833) bestätigte auf allen drei Post-IDs `scheduled` und den exakten Zeitpunkt. Frühere abgewiesene API-Validierungen (`text` sowie `facebook.type` fehlten) wurden nach bestätigter Nicht-Terminierung korrigiert; ihre `pending`-Belege bleiben als Audit-Spur erhalten. Ein erfolgreiches Einplanen garantiert nicht, dass die spätere Plattform-Veröffentlichung fehlerfrei ist.

## Datumsformat und Zeitzone

Die Planung erfolgt **in Europe/Berlin** und wird für die API explizit in UTC umgerechnet (Sommer-/Winterzeit berücksichtigen). Beispiele für die Kampagne vom 8.10.2026:

| Plattform | Europe/Berlin (MESZ) | `publish_at_utc` |
| --- | --- | --- |
| LinkedIn | 09.10.2026 15:00 | `2026-10-09T13:00:00Z` |
| Facebook | 14.10.2026 09:00 | `2026-10-14T07:00:00Z` |
| Instagram | 14.10.2026 18:00 | `2026-10-14T16:00:00Z` |

**Diese Tabelle ist nur der unverbindliche Kampagnenvorschlag.** Sie aktiviert selbst keine Terminierung. Der Auftrag muss nach aktueller Quellenprüfung weiterhin ausdrücklich freigegeben werden.

## Technische Details

`scripts/buffer_schedule.py` verwendet die vorhandene Buffer-API-Verbindung und das GitHub-Secret `BUFFER_API_KEY`. Es prüft zuerst das existierende Buffer-Post-Objekt und verwendet anschließend `editPost` mit `mode: customScheduled`, `dueAt` in UTC und `saveToDraft: false`. Buffers API verlangt beim Bearbeiten zusätzlich den **identischen Text sowie die ursprünglichen Medien- und Plattformmetadaten**; diese stammen aus der freigegebenen JSON-Datei. Es wird **kein zweiter Post** erstellt. Nach der Entwurfsübertragung keine manuellen Medienänderungen direkt in Buffer durchführen, ohne zuvor die Freigabedatei abzugleichen.

Offline-Test:

```bash
python3 -m unittest discover -s tests -v
```

Optionaler Offline-Trockenlauf **nachdem** eine Freigabedatei erstellt wurde:

```bash
python3 scripts/buffer_schedule.py --request ready-to-schedule/beitrag.json --dry-run
```

Quellen (offizielle Buffer-Dokumentation):
- https://developers.buffer.com/types/EditPostInput.html
- https://developers.buffer.com/guides/integrations/mcp.html
- https://developers.buffer.com/guides/posts-and-scheduling.html
- https://developers.buffer.com/examples/create-scheduled-post.html
