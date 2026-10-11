# Einmaliger Abnahmetest: Datum an Buffer-Entwurf, ohne Queue

**Status:** isolierter, nicht produktiv angebundener Draft-PR. Kein Test wurde
ausgeführt und kein Entwurf angelegt. Der PR ist **keine** Freigabe zum Merge,
keine allgemeine Draft-Übertragungsberechtigung und keine Terminfreigabe.

## Warum ein eigener, begrenzter Test?

Buffer beschreibt offiziell den Unterschied zwischen einem Draft **mit
vorausgewähltem Datum** und einem tatsächlich eingeplanten Post. Der Draft
erscheint im Kalender, wird aber erst nach gesonderter Entscheidung für die
Queue zur Veröffentlichung freigegeben:

- [Buffer: Saving and scheduling draft posts](https://support.buffer.com/en-us/articles/saving-and-scheduling-draft-posts-CBLXg1yFXp)
- [Buffer API: CreatePostInput](https://developers.buffer.com/types/CreatePostInput.html)

Die API dokumentiert `saveToDraft: true`, `mode: customScheduled` und `dueAt`,
aber das **Zusammenspiel dieser Parameter in Josefs Konto ist nicht live
validiert**. Das kann weder ein Offline-Test noch dieser PR beweisen.

## Fest eingebaute Schranken

1. **Nur manueller Start** per `workflow_dispatch` des Repository-Eigentümers
   `derJosef` auf `main`, erst nach späterer ausdrücklicher Merge-Freigabe.
2. **Erneute Bedienhandlung:** Der Eigentümer muss
   `DATIERTER_DRAFT_EINMALTEST_OHNE_QUEUE` als Bestätigung eingeben. Nach
   Installation **niemals** allein aufgrund dieses PR oder einer Brief-Freigabe
   ausführen.
3. **Einmaligkeit:** Ein fester Empfangsbeleg unter
   `delivery-receipts/2026-10-11-prescheduled-draft-probe.json` wird zuerst
   auf `main` reserviert; er sperrt spätere Wiederholungen auch bei Fehlern.
   GitHub-Actions-Retries (`run_attempt > 1`) sind zusätzlich ausgeschlossen.
   Der Live-Test verwendet die bestehende `buffer-drafts-single-flight`-Gruppe,
   um sich nicht mit der normalen Entwurfsübertragung zu überschneiden.
4. **Nur LinkedIn, nur Testtext, keine Bilder:** Keine bestehenden Entwürfe
   werden verändert. Der Text ist deutlich als interner, nicht zu
   veröffentlichender Techniktest gekennzeichnet.
5. **120 Tage Zukunft:** Das Datum wird automatisch in UTC berechnet, nicht
   von Josef eingetippt. Damit verbleibt Zeit für manuelle Gegenmaßnahmen,
   selbst wenn die API wider Erwarten etwas terminieren sollte.
6. **Nur eine Buffer-Mutation:** `createPost(... saveToDraft: true,
   mode: customScheduled, dueAt: ...)`, keine `editPost`, kein `deletePost`,
   kein `shareNow` oder Queue-Befehl.
7. **Sofortige Doppelprüfung:** Zuerst die Create-Antwort und dann ein
   **unabhängiger lesender** `post(id)`-Aufruf. Erwartet sind identische
   Post-ID/Kanal-ID, `status=draft` und exakt der gewählte UTC-Zeitpunkt.
   Erst dann wird der Beleg als `verified_prescheduled_draft_not_queued` markiert.
8. **Fail-closed:** Bei jeder Mehrdeutigkeit bleibt der Beleg gesperrt.
   Die Post-ID wird, soweit bekannt, für menschliche Nachkontrolle dokumentiert.
   **Keine automatische Wiederholung und keine automatische Korrektur**, denn
   Letztere wäre eine weitere nicht freigegebene Buffer-Mutation.

Das Github-Secret `BUFFER_API_KEY` wird ausschließlich zur späteren manuellen
Laufzeit aus der vorhandenen Actions-Konfiguration bezogen. Es wird nicht
gelesen, kopiert oder in Logs ausgegeben. GitHub-Rechte für den manuellen
Workflow sind auf `contents: write` zum festen Beleg begrenzt. Die separate
PR-Test-Aktion hat nur `contents: read` und erhält **keine Secrets**.

## Wie man später prüft

Bis zur ausdrücklichen Entscheidung über den Merge bleiben beide neuen
Workflows unverbunden. Erst ein späterer **separater** manueller Start des
Test-Workflows kann Buffer ändern. Ein grüner GitHub-CI-Test ist **kein**
Nachweis, dass Buffer diese Kombination unterstützt.

Nach einem genehmigten Einmallauf ist der Beleg mit Post-ID und Status
zu lesen, zusätzlich in der Buffer-Oberfläche nachzusehen, ob der Beitrag
unter **Drafts mit Datum** und **nicht** in der Queue erscheint. Falls der
Status unerwartet ist, muss Josef sofort benachrichtigt werden. Korrektur oder
Entfernung erfolgt nicht automatisch, sondern nach gesonderter Entscheidung.

Erst nach diesem erfolgreichen Nachweis darf über eine Änderung der
eigentlichen Kampagnen-Workflows entschieden werden. Variante A bleibt:
Brief-Freigabe erlaubt höchstens nicht terminierte automatische Buffer-Drafts;
Veröffentlichung/Queue bleibt ein eigenständiger Freigabeschritt.

## Offline-Prüfung

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest discover -s tests -p 'test_buffer_prescheduled_draft_probe.py' -v
```
