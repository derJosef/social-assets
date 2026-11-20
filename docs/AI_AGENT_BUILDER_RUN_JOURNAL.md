# AI Agent Builder: dauerhaftes Produktionsjournal und Wiederaufnahme

Stand: 20.11.2026. Gilt nur für die **bestehende** Montag-/Donnerstag-Automation
`6ad9da13ed2481919326ec8e2a42d6d5`. Sie wird nicht dupliziert.

## Anlass und harte Grenze

Beim unbeaufsichtigten Lauf `c5238a22-0408-832c-89c2-8d1a2b08bf3d`
(20.11.2026) entstanden laut nachfolgendem Codex-Review **weder Brief-Commit
noch PR noch Actions-Run**; der letzte interne Werkzeugaufruf war nicht mehr
nachvollziehbar. Es wurden **0/3 neue Buffer-Drafts** bestätigt. Daraus lässt
sich **nicht** ableiten, ob ein Bild lokal fertig war oder welcher konkrete
Werkzeugaufruf scheiterte. Keine nachträglich erfundenen Phasen-Logs.

GitHub-Action-Reports beginnen erst *nach* dem GitHub-Transfer. Ein
ChatGPT-Lauf kann jedoch schon davor abbrechen. Deshalb gibt es zwei getrennte
Belege: (1) die vor der Recherche eröffnete GitHub-Issue als append-only
**Laufjournal** und (2) das bestehende dauerhafte Receipt auf dem
`automation-receipts`-Branch mit zusätzlichen GitHub-Action-Step-Outcomes.
Ein ChatGPT-Prozessabbruch mitten in einem Toolaufruf ist nicht vollständig
protokollierbar; der **zuletzt erfolgreich zurückgelesene** Eintrag ist dann
der maßgebliche Wiederaufnahmepunkt. Ein ausstehendes `STARTED` ist kein `PASS`.

## Issue-Protokoll (vor dem ersten produktiven Werkzeug)

1. **Aktuelle Verbindung prüfen:** ausschließlich GitHub-Konto
   `derJosef-agents`, aktuelle `link_id` aus den verfügbaren Verbindungen
   ermitteln und explizit übergeben. PersonalOS nur lesen. Existierendes
   Run-Issue für diese UUID und Bestandskampagnen zuerst suchen. Kein Doppelissue.
2. **Ein einziges Issue** in `derJosef/social-assets` öffnen, Titel
   `AIAGENT_RUN_LOG: <run_uuid>`; als Body ein JSON-Objekt gemäß
   `production_run_journal.new_header(...)` ablegen. Die UUID stammt aus dem
   realen Automations-Run, sonst einmalig per UUIDv4 erzeugen. Keine
   Zugangsdaten, Raw-Toolresponses oder personenbezogene Daten.
3. **Sofort zurücklesen.** Erst nach erfolgreicher Anlage und Readback das
   Kommentar-Event `start`/`PASS` schreiben und zurücklesen. Kann GitHub das
   Journal nicht bestätigen, lautet das Ergebnis `BLOCKED` und es beginnt
   **keine** unbeaufsichtigte neue Produktion.
4. Für **jede** Phase `STARTED` und nach überprüftem Erfolg `PASS` als eigenen
   Kommentar speichern und danach zurücklesen. Phasen in Reihenfolge:
   `start → inventory → research → copy → image → transfer → github → actions → buffer → readback → finish`.
   `start` erhält den initialen `PASS`-Kommentar; für spätere Phasen zuerst
   `STARTED`. `inventory` umfasst den neuesten sicheren Live-Buffer-Audit,
   Themen-/Wochen- und Duplikatprüfung. `transfer` umfasst SHA und
   unverändertes Original. `github` erfasst Branch, Commit, PR, Merge und
   Brief-Datei *erst nach* tatsächlichem Readback. `actions` erfasst die echte
   Run-ID und den endgültigen Job-Status. `buffer` ist **erst** nach eindeutiger
   Anlage ein PASS. `readback` muss für jede Plattform Post-ID, Channel-ID,
   `draft`, `dueAt` und aktuellen Live-Abruf belegen.
5. Jeder Toolfehler führt zu einem `ERROR`- oder `BLOCKED`-Kommentar mit
   `error: {tool,kind,summary}` und **ohne** Token, Header, unbearbeiteten
   Server-Response oder vollständigen Traceback. Referenzen auf echte Logs
   kommen in `evidence`, nicht als erfundene URLs. Liegt der Fehler gerade im
   GitHub-Connector, kann das Event nicht sicher geschrieben werden: im Chat
   melden und nicht aus dem Gedächtnis als gespeichert ausgeben.

Beispiel für einen Event-Kommentar (vollständiger JSON-Kommentar, ohne
Markdown-Codeblock):

```json
{
  "schema_version": 1,
  "run_id": "c5238a22-0408-832c-89c2-8d1a2b08bf3d",
  "phase": "image",
  "state": "ERROR",
  "recorded_at": "2026-11-20T13:24:00Z",
  "error": {
    "tool": "image_generation",
    "kind": "timeout",
    "summary": "Kein bestätigter Bildexport; kein SHA-Nachweis"
  }
}
```

Das obige JSON ist **nur ein Schema-Beispiel** und ausdrücklich kein Beleg
für einen tatsächlich geschehenen Fehler im Lauf vom 20.11.

Ein erfolgreiches `readback`/`PASS` braucht zusätzlich das Feld `receipts`
mit genau drei unterschiedlichen `{target, post_id, channel_id, status, due_at}`
(je LinkedIn, Facebook, Instagram; `status = draft`). Das Journal prüft nur
die Form und Konsistenz dieses Eintrags; die **tatsächlichen Buffer-API-Abrufe**
und die GitHub-Receipts bleiben die beweiskräftigen Originalquellen.

## Sichere Wiederaufnahme

- Nach Unterbrechung die ursprüngliche Run-Issue und **alle** Kommentare
  erneut laden, nach GitHub-chronologischer Reihenfolge unverändert prüfen;
  keinen neuen Run derselben Kampagne erfinden.
- Das vollständige JSON-Snapshot `{ "header": <Issue-Body-JSON>,
  "events": [<Kommentar-JSON>, ...] }` ohne Secrets mit
  `python3 scripts/production_run_journal.py snapshot.json` lokal validieren.
  Ohne verfügbare Laufzeit dieselben Zustandsregeln manuell anwenden und die
  Prüfung als manuell kenntlich machen.
- `NEXT`: ausschließlich die nächste unvollständige Phase bearbeiten;
  erreichte Phasen nicht erneut ausführen. `INSPECT`: vorhandene Texte,
  Bilder, Hashes und Fehler prüfen, *bevor* derselbe Phasenschritt fortgesetzt
  wird. Ein korrigierender `PASS` nach Fehler benötigt `resolved_by` mit
  nachlesbarer Referenz. `DONE`: keine neue Produktion oder Duplikate.
- `RECONCILE`: möglicher externer Seiteneffekt bei GitHub, Actions oder Buffer.
  **Keine Wiederholung** der Mutation. Zuerst Branch/Commit/PR/Actions/Receipts
  und den aktuellen, autorisierten Buffer-Live-Readback abgleichen.
  Bei unklarem oder teilweise angelegtem Buffer-Status `BLOCKED`, Josef
  informieren, erst nach eindeutigem Ergebnis und ggf. neuer Freigabe weiter.
- Ein technischer `PASS` aus einem älteren Receipt überschreibt niemals
  einen neueren Live-Befund `scheduled`/`sent` ohne Josefs Freigabebeleg.
- Keine Änderungen an den drei bereits bekannten Telekom–Mistral-Posts,
  kein Re-Send bei unbekanntem Zustand, kein Statuswechsel auf `scheduled`,
  keine Queue, kein `shareNow`, keine Veröffentlichung ohne konkrete Freigabe.

## Actions-Seite und Fehlerbelege

`social-campaign-orchestrator.yml` gibt seinen Schritten feste IDs. Das
`always()`-Receipt ruft `scripts/action_phase_ledger.py` auf und speichert
für alle erreichten/nicht erreichten Schritte `PASS/FAIL/NOT_RUN` und bei
`FAIL` den verantwortlichen Toolnamen sowie einen Link zum zugehörigen
GitHub-Run. **Rohe Tool-Ausgaben werden nicht in öffentliche JSON-Reports
kopiert** (Secrets!). Das vorhandene Orchestrator-Report erfasst zusätzlich
gefilterte Python-Ausnahmen und QA-Gates. Bei Buffer-Send `success`/`failure`
ohne erfolgreiches Readback wird `RECONCILE_BUFFER` statt Erfolg ausgewiesen.
Der gespeicherte Receipt hat `receipt_state=WRITE_PENDING`; erst ein
abgeschlossener GitHub-Run plus Zurücklesen des konkreten Receipt belegen
dessen endgültige Speicherung. Falls die GitHub-Receipt-API ausfällt,
gibt es nur das Actions-Artefakt mit 30 Tagen Vorhaltefrist; **kein
dauerhafter Erfolgsbeleg**, bis autorisiert nachgesichert.

## Kontrolldurchlauf und Freigaben

Die bestehenden Montag-/Donnerstagstermine und maximal zwei Themen je
Redaktionswoche bleiben unverändert. Eine manuelle `Run now`-Ausführung
außerhalb dieser Tage ist gemäß bestehenden Automationsregeln **read-only**;
sie erstellt keine Kampagne und keine Drafts. Ein neuer kontrollierter
Produktionslauf benötigt eine ausdrücklich begrenzte Testfreigabe bzw.
einen regulären Montag-/Donnerstaglauf. Für technische Regressionen sind
`python3 -m unittest discover -s tests -v`, ein offline Smoke-Test und ein
echter GitHub-Actions-Receipt-Lesecheck erforderlich. 3/3 ist ausschließlich
bei drei live nachgelesenen, unterschiedlichen Buffer-Drafts erfolgreich.

## Sechs-Hüte-Entscheidung (Betrieb)

- **Weiß:** Der Ausfall lag vor GitHub; die Ursache des letzten Toolaufrufs ist unbekannt.
- **Rot:** Stille Abbrüche und vermeintliche Erfolgsberichte zerstören Vertrauen.
- **Schwarz:** Ein unklarer Buffer-Status kann bei Retry Dopplungen erzeugen;
  öffentliches Error-Logging kann Secrets verraten.
- **Gelb:** Ein früh angelegtes, zurückgelesenes Journal zeigt wenigstens den
  letzten belegten Schritt; Action-Receipts bleiben rückverfolgbar.
- **Grün:** Die dedizierte Run-Issue vermeidet Änderungen an bestehenden
  produktiven Briefs oder an der Buffer-Sendelogik.
- **Blau:** Zuerst isoliert testen und unabhängig prüfen; danach genau einen
  kontrollierten, deduplizierten E2E-Draftlauf, niemals Publish.
