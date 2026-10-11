# Kampagnen-Brief-Freigaben – Entwurf, noch nicht produktiv

**Status: nur Implementierungsentwurf auf einem nicht gemergten Feature-Branch.**
Diese Dokumentation erteilt keine Freigabe für eine konkrete Kampagne.
`scripts/brief_approval_gate.py` ist **noch nicht** mit GitHub Actions oder
`buffer_draft.py --send` verbunden. Ein bestandenes `--lint-only` ist nie
eine Erlaubnis zum Senden.

## Entscheidung von Josef, 11.10.2026

Nach **ausdrücklicher Freigabe eines einzelnen Kampagnen-Briefs** dürfen daraus
automatisch **ungeplante Buffer-Drafts** entstehen. Eine erneute Freigabe je
Draft ist nicht nötig. Terminierung und Veröffentlichung sind davon vollständig
getrennt und brauchen eine eigene Josef-Entscheidung.

## Vorgeschlagener Genehmigungsweg

1. Der Brief unter `orchestration/briefs/` und sein manuell geprüftes
   `visual-reviews/`-Dokument samt Quellbild liegen bereits auf `main`.
2. Für **genau diese Bytes** werden SHA-256-Werte ermittelt.
3. Ein **separater PR, der ausschließlich eine Freigabe-JSON-Datei hinzufügt
   oder ändert**, enthält die genaue Kampagnen- und Zweckbindung. Josef merged
   diesen Freigabe-PR bewusst persönlich; kein Bot und keine Kombination mit
   Änderungen am Brief oder an Workflows.
4. Die spätere produktive Authorisierung muss sowohl die lokalen Hashes als
   auch die GitHub-Metadaten dieses PRs auf dem **geschützten** `main` prüfen.
   `approved_by` im JSON oder ein Git-Commit-Autorname sind keine Beweise.
5. Jede Änderung an Brief, Review oder Bildquelle macht die alte Freigabe
   unwirksam. Zum Widerruf wird die neueste Freigabe auf `state: revoked`
   gesetzt; bereits an Buffer übertragene Drafts sind manuell abzugleichen.

Das vorgeschlagene Schema ist ein JSON-Objekt mit **genau** folgenden Feldern
(Werte sind rein schematisch und **keine echte Freigabe**):

```json
{
  "format_version": 1,
  "campaign_id": "2026-10-11-beispiel",
  "brief_path": "orchestration/briefs/2026-10-11-beispiel.json",
  "brief_sha256": "<64 Hex-Zeichen des unveränderten Briefs>",
  "image_review_path": "visual-reviews/2026-10-11-beispiel.json",
  "image_review_sha256": "<64 Hex-Zeichen des unveränderten Reviews>",
  "source_sha256": "<64 Hex-Zeichen der unveränderten Bildquelle>",
  "targets": ["linkedin", "facebook", "instagram"],
  "purpose": "unscheduled_buffer_draft_only",
  "state": "approved"
}
```

**Abgrenzung:** Eine `execution_mode: drafts`-Eigenschaft im Brief ist keine
menschliche Freigabe. Ebenso wenig genügen grüne CI-Checks, ein Merge des
Briefs oder ein `workflow_dispatch`.

## Aufrufe und Tests (ohne Buffer)

- `python3 -m unittest discover -s tests -p 'test_brief_approval_gate.py' -v`
  führt ausschließlich synthetische Offline-Fixtures aus.
- `python3 scripts/brief_approval_gate.py --draft ready-for-buffer/auto-<KAMPAGNE>-linkedin.json --lint-only`
  prüft bei existierender Freigabe **nur** lokale Belege. Der Erfolg erlaubt
  **keinen** Buffer-Aufruf.
- Die Prüfung **ohne** `--lint-only` verlangt GitHub Actions auf
  `social-assets/main`, einen GitHub-Lesetoken sowie PR-Merge-Provenienz
  einschließlich `merged_by: derJosef`. Sie liest lediglich GitHub-Daten,
  verändert nichts und enthält keinerlei Buffer-Code.

## Aktivierungsblocker (vorher ausdrücklich neu genehmigen)

- `main` ist laut Ist-Aufnahme ungeschützt. `protected: true` ist notwendig,
  aber nicht allein ausreichend: Rulesets und etwaige Bot-Bypässe müssen
  gesondert auf echte menschliche Merge-Entscheidungen geprüft werden.
- Die Orchestrator-Action schreibt generierte Dateien und Berichte derzeit
  unmittelbar nach `main`; der zentrale Buffer-Sender speichert dort
  Einmal-Receipts. Vor strenger Branch-Protection sind diese Schreibwege
  ohne Verlust des Retry-/Doppelsendeschutzes zu migrieren.
- **Alle drei** Draft-Einstiege sind später gesondert zu verdrahten und
  fail-closed zu testen: Orchestrator, automatischer Ready-for-Buffer-Push
  und manueller `buffer-draft.yml`-Dispatch. Bestehende nicht-`auto-`
  Dateien benötigen eine eigene, ausdrücklich bestätigte Übergangsregel.
- Die späteren prüfenden Jobs brauchen für den GitHub-PR-Nachweis zusätzlich
  eng begrenzte **Pull-requests-Leserechte**; die aktuellen
  `permissions: contents: write` reichen dafür nicht ohne Weiteres aus.
- Der neue Approval-PR-Merge muss einen kontrollierten Kampagnenlauf anstoßen,
  ohne dass ein bloßer Brief-Push schon senden darf.
- Der separate bestehende `buffer-auto-schedule.yml` reagiert bereits auf
  **individuell freigegebene** Dateien unter `ready-to-schedule/` und plant
  damit Termine. Dieser **nicht veränderte** Workflow ist gesondert mit
  Josefs Wunsch „keine automatische Terminierung“ abzugleichen.
- Die jetzige Gate-Bibliothek enthält **keine Buffer-Mutation**, ersetzt
  keine redaktionelle Wahrheit und beweist noch keine produktive Integration.

**Keines der hier beschriebenen Genehmigungs- oder Ablaufbeispiele ist aktiv
oder genehmigt. Kein Merge/Buffer-Draft/Scheduling/Publishing ohne separate
Josef-Freigabe.**
