# Kampagnenvorschau: Inhalte und Terminvorschläge – Phase 1 (offline)

**Status: technischer Review-Entwurf, keine Produktivaktivierung.**

Die bestehende Orchestrierung trägt die konkreten Termine bereits unter
`campaign-manifests/<kampagne>.json` in `posting_times` ein, einschließlich
`Europe/Berlin` und UTC. Das ist **keine** Veröffentlichungsgenehmigung.

Zur gemeinsamen Sichtung von Josef und dem Agenten kann daraus eine vollständige
Markdown-Vorschau erzeugt werden:

```bash
python3 -B scripts/campaign_schedule_preview.py \
  --manifest campaign-manifests/2026-10-10-kundenmail-kein-befehl-005.json
```

Das erzeugt auf **stdout** eine reine Leseansicht mit:

- konkretem Termin für LinkedIn, Facebook und Instagram in Berliner Ortszeit und UTC;
- allen drei ungekürzten Beiträgen und Link zum Kampagnenbild;
- SHA-256 der manifestierten Bildbytes, des Manifests und aller drei Draft-Dateien;
- deutlicher Warnung: weder Brief-Freigabe noch Buffer-Status noch Publikationsfreigabe.

**Fail-closed Offline-Prüfung:** Alle Dateien gehören zur gleichen Kampagne,
alle Kanäle sind vorhanden, das Bild stimmt bytegenau, die Sommer-/Winterzeit
ist korrekt umgerechnet, Termine liegen in der Zukunft, und es gibt keine
zeitnahen Kollisionen desselben Kanals (90 Minuten) mit bestehenden Manifests
oder `ready-to-schedule/`-Anfragen. Wenn bereits eine Terminierungsanfrage
für denselben Draft existiert, stoppt die Vorschau und verlangt eine manuelle
Buffer-Statusprüfung. GitHub-Artefakte sind **kein** Beweis für den aktuellen
Buffer-Status oder Josefs Identität.

## Nächster Schritt nach Josefs Korrektur am 11.10.2026

Josef muss **keine Veröffentlichungstermine selbst aussuchen oder eingeben**.
Die Agenten recherchieren und hinterlegen konkrete Vorschläge. Der Plan soll
mit dem ungeplanten Buffer-Draft vorliegen und von Josef als Einheit geprüft
werden können. Die eigentliche Aufnahme in Buffers Veröffentlichungswarteschlange
bedarf **einer separaten ausdrücklichen Freigabe** des gesamten konkreten
Zeitplans; anschließend kann Buffer automatisiert zum gebilligten Zeitpunkt
veröffentlichen.

Buffer unterstützt in der Oberfläche einen Draft mit einem **vorbelegten
Datum**, ohne ihn zur Veröffentlichung einzuplanen:
https://support.buffer.com/en-us/articles/saving-and-scheduling-draft-posts-CBLXg1yFXp

Das GraphQL-Schema enthält `saveToDraft`, `mode` und `dueAt`:
https://developers.buffer.com/types/CreatePostInput.html

**Wichtig:** Ob die Kombination `saveToDraft: true` + `mode: customScheduled`
+ `dueAt` über *unsere* API-Verbindung genau diesen sicheren Zustand erzeugt,
ist **nicht** durch einen Live-Test belegt. Keinerlei Mutationscode wird in
diesem Review-Entwurf geändert. Die tatsächliche Implementierung benötigt erst
einen gesondert genehmigten Test, bei dem der Status nachweislich `draft` bleibt.

## Zeitdaten und Qualitätsgrenze

Die aktuellen bestehenden `social_orchestrator.py`-Vorschläge verwenden
deterministische Wochentag-/Uhrzeitwerte und einen konservativen Abstand zu
anderen Kampagnen. Sie sind nicht automatisch die individuell **besten** Zeiten.
Die Nutzungsdaten von Buffer bieten für Oktober 2026 folgende Startwerte:

- LinkedIn: Mittwoch 16:00; Studie zu 4,8 Millionen Beiträgen:
  https://buffer.com/resources/best-time-to-post-on-linkedin/
- Instagram: Mittwoch 18:00 bzw. Donnerstag 09:00; 9,6 Millionen Beiträge:
  https://buffer.com/resources/when-is-the-best-time-to-post-on-instagram/
- Facebook: Donnerstag 09:00 bzw. Mittwoch 08:00; 14 Millionen Beiträge:
  https://buffer.com/resources/best-time-to-post-on-facebook/

Die spätere Qualitätsverbesserung muss eigenes Publikum, Beitragsart,
Kampagnenanlass, belegte Quellen und freie Zeitfenster berücksichtigen.
Die Vorschau zeigt vorhandene Daten unverändert und **ändert die Terminwahl
nicht stillschweigend**. Nicht geprüfte neue Algorithmen dürfen nicht ohne
weitere Tests in produktive GitHub Actions wandern.

**Keine Änderung:** `buffer_draft.py`, `buffer_schedule.py`, alle produktiven
GitHub-Workflows, Secrets, `main`-Branch-Protection, vorhandene Freigabe- und
Receipt-Dateien, andere Marken und PersonalOS.
