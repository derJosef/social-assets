# HISTORISCH – Brief-Vorabfreigaben nicht mehr im Draft-Workflow

**Status seit 12.10.2026: ABGELÖST.** Josef hat die individuelle
Freigabe **vor** der Erzeugung von Buffer-Drafts ausdrücklich aufgehoben.
Für AI Agent Builder sollen zuerst drei qualitativ geprüfte, mit konkretem
Datum und Uhrzeit gespeicherte Buffer-**Entwürfe** entstehen. Erst danach
entscheidet Josef anhand der Inhalte und Links im ChatGPT-Wochenbericht
oder nach eigenen Änderungen direkt in Buffer über eine spätere
Freigabe zur Veröffentlichung.

Die unten dokumentierte alte `brief_approval_gate.py`-Architektur ist
**nur historisches Wissen und Gegenstand synthetischer Regressionstests**.
Sie darf nicht automatisch wieder in den Produktionsworkflow aufgenommen
werden. Ein Freigabe-JSON unter `orchestration/approvals/` löst künftig
keine neue Draft-Kampagne aus. Die vor Veröffentlichung notwendige
persönliche Freigabe ist ein **separater späterer Vorgang** und muss die
aktuelle live gelesene Buffer-Fassung inklusive manueller Änderungen
erhalten. Dessen verlustfreie technische Umsetzung ist weiterhin offen.

Siehe `docs/APPROVED_DATED_BUFFER_DRAFTS.md` und
`docs/BRANCH_PROTECTION_MIGRATION.md`.

---

# Kampagnen-Brief-Freigaben – Entwurf, noch nicht produktiv

**Status: gestapelter Implementierungsentwurf, noch nicht auf `main`.**
Die Weiterentwicklung `approved-dated-drafts` verbindet die Freigabeprüfung
im Entwurfszweig mit allen drei Draft-Einstiegen, aktiviert aber **keinen**
Workflow auf `main`. Ein bestandenes `--lint-only` ist nie eine Erlaubnis
zum Senden.

## Entscheidung von Josef, 11.10.2026

Nach **ausdrücklicher Freigabe eines einzelnen Kampagnen-Briefs** dürfen daraus
automatisch Buffer-Drafts entstehen. Am 11./12.10.2026 präzisierte Josef:
**Die recherchierten Termine sollen bereits im Draft stehen**, ohne
Veröffentlichungswarteschlange oder Veröffentlichung. Das wurde mit dem
einmaligen Live-Lauf #38179032859 als `draft` samt `dueAt` nachgewiesen.
Ein Entwurf mit Datum ist keine aktivierte Veröffentlichung.

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
  "purpose": "dated_buffer_draft_not_queued",
  "state": "approved"
}
```

**Abgrenzung:** Eine `execution_mode: drafts`-Eigenschaft im Brief ist keine
menschliche Freigabe. Ebenso wenig genügen grüne CI-Checks, ein Merge des
Briefs oder ein `workflow_dispatch`.
Der alte Freigabezweck `unscheduled_buffer_draft_only` darf **nicht** still
für einen datierten Entwurf umgedeutet werden. Er ist nur für den historischen,
ungeplanten Pfad bekannt; der neue Sender verlangt exakt
`dated_buffer_draft_not_queued`.

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
- **Alle drei** Draft-Einstiege sind in diesem Integrationszweig über denselben
  Sender abgesichert: Orchestrator, automatischer Ready-for-Buffer-Push und
  manueller `buffer-draft.yml`-Dispatch. Der Orchestrator prüft den Brief
  zusätzlich vor dem ersten externen Aufruf. Bestehende nicht-`auto-`
  Dateien unter `ready-for-buffer/` werden fail-closed gesperrt; `drafts/`
  bleiben ausdrücklich manuell und undatiert.
- Für den GitHub-PR-Nachweis erhalten die neuen Jobs nur zusätzliche
  **Pull-requests-Leserechte**. Das erlaubt keinen PR-Merge.
- Der neue Approval-PR-Merge muss einen kontrollierten Kampagnenlauf anstoßen,
  ohne dass ein bloßer Brief-Push schon senden darf.
- Der separate bestehende `buffer-auto-schedule.yml` reagiert bereits auf
  **individuell freigegebene** Dateien unter `ready-to-schedule/` und plant
  damit Termine. Dieser **nicht veränderte** Workflow ist gesondert mit
  Josefs Wunsch „keine automatische Terminierung“ abzugleichen.
- Die Gate-Bibliothek enthält **keine Buffer-Mutation**; der getrennte Sender
  benutzt nur `createPost(saveToDraft:true, mode:customScheduled, dueAt)`.
  Die Integrations- und Fehlertests sind bislang **offline**; der Live-Nachweis
  stammt allein aus dem genehmigten Einmaltest, nicht aus einem Kampagnenlauf.

**Keines der hier beschriebenen Genehmigungs- oder Ablaufbeispiele ist aktiv
oder genehmigt. Kein Merge/Buffer-Draft/Scheduling/Publishing ohne separate
Josef-Freigabe.**
