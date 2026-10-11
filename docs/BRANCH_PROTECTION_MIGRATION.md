# Vorbereitung: geschütztes `main`, funktionsfähige Automatisierung

**Status: eigenständiger Draft-PR auf PR #11, kein Live-Rollout.** Keine
Kampagne ist dadurch genehmigt, kein Buffer-Entwurf wird durch diesen PR
angelegt, keine Terminierung/Publikation freigegeben.

## Was wohin geschrieben wird

| Datentyp | Quelle / Ziel nach Aktivierung | Schreibende Instanz | Vertrauensgrenze |
|---|---|---|---|
| Brief, Quellenbild-Review, Freigabe-JSON, Code | geschütztes `main` | Josef per PR-Merge | `orchestration/approvals/*`: alleiniger PR mit SHA-Bindung und Josefs echtem Merge |
| Automatisch erzeugte Kampagnenbilder, Manifests und drei Posts | einzigartiger `automation/campaign/<kampagne>`-Branch | Orchestrator `GITHUB_TOKEN` | vor Buffer: vollständige QA und SHA-256-Bildprüfung |
| Bild-URL für alle drei Buffer-Drafts | `raw.githubusercontent.com/.../<40-stelliger Bild-Commit-SHA>/media/images/...` | Orchestrator pinnt den unveränderlichen Git-Commit | Bild wird zusätzlich **öffentlich heruntergeladen und gehasht**, bevor der Sender eine Einmalreservierung schreibt |
| Versand- und Terminierungsbelege, Orchestrator-Reports | `automation-receipts` | Actions-Token | alter `main`-Receipt hat Vorrang; `pending` blockiert jede Wiederholung |
| Einzelne manuell ausgelöste Visual-Produktion | `automation/visual/run-<runid>` | Visual-Workflow | Aufnahme auf `main` weiterhin nur nach einem gesonderten PR |

Der Orchestrator läuft weiterhin **auf `main`**: Nur der tatsächlich geschützte
Brief samt Freigabe wird dort geladen. Vor externer Recherche und vor jedem
schreibenden Aufruf muss `brief_approval_gate.py` die persönliche Merge-Provenienz
prüfen. Die generierten acht Dateien werden in **zwei lokalen Git-Commits**
geschrieben (3 Bild-/Bildbelegdateien, dann 5 Manifest-/Textdateien). Erst
nach dem zweiten lokalen Qualitätscheck wird der einmalige Output-Branch
gepusht. **Keine Direktpushes auf `main`.** Ein GitHub-Actions-Push mit dem
`GITHUB_TOKEN` startet absichtlich keine erneute automatische Push-Action;
die drei Sender laufen wie bisher im ursprünglichen Job.

## Dauerhafter Einmal-Beleg

`buffer_draft.fetch_receipt` prüft zuerst den historischen Pfad **auf `main`**.
Ein alter `pending`- oder Erfolgsbeleg verhindert dieselbe Buffer-Aktion
weiterhin. Nur falls dort kein Beleg existiert, wird die Existenz des separaten
Ledger-Branches nachgewiesen, danach der dortige Pfad geprüft. Ein 404 beim
Branch-Nachweis **stoppt** den Versand; es gibt kein automatisches Erstellen
oder Wiederholen. Neue Reservierungen und Bestätigungen gehen ausschließlich
auf `automation-receipts`. Die aus `main` geladene manuelle Terminierungsstrecke
liest ältere Receipts direkt und neue via separat gefetchtem Ledger-Ref;
ohne Beleg verweigert sie die Terminierung.

## Reihenfolge der Aktivierung – NICHT durch diesen PR ausgeführt

1. Gestapelte PRs **#7 → #11 → diesen PR** sowie das separate Timing-PR #9
   auf den finalen Zustand prüfen. Ihre Merge-Freigabe ist eine eigene,
   ausdrückliche Entscheidung Josefs.
2. Einmal den öffentlichen Branch `automation-receipts` erstellen und lesend
   nachprüfen; die bisherigen GitHub-Belege auf `main` **nicht löschen**.
   Den Branch gegen **Force-Push und Löschung** sichern, aber normale
   neue, nicht-überschreibende Contents-API-Commits durch Actions zulassen.
   Ohne Branch kein Live-Senden.
3. Erst wenn alle Bot-Direktpushes von `main` entfernt und die betroffenen
   Workflows erfolgreich *offline* getestet sind: GitHub `Settings → Branches`
   oder Rulesets für `main`: **Pull Request erforderlich**, erzwungene
   Statusprüfungen (nur zuvor beobachtete Check-Namen), keine Force-Pushes,
   keine Löschung, **Administrator-Bypass nicht zulassen**. Bei nur einem
   Repository-Eigentümer keinen unlösbaren fremden Review erzwingen. Für die
   Brief-Genehmigung zählt der vom Eigentümer tatsächlich selbst gemergte
   **Ein-Datei-PR**, nicht ein frei editierbares `approved_by`-Feld.
4. Nach Aktivierung `branches/main.protected == true` prüfen, danach nur
   read-only/offline die drei Pfade (Orchestrator, automatische `auto-*`-Posts,
   manueller Draft-Dispatch), bestehende und neue Receipt-Lookups,
   den Visual-Branch, die Berichtsablage und die manuelle Terminierung
   prüfen. Kein erneuter Live-Buffer-Probeversand: Die datierte Draft-Funktion
   ist durch GitHub-Lauf #38179032859 bereits bestätigt.

## Wichtige Grenzen

- `automation-receipts` ist ein operationelles Audit-Ledger, **keine
  menschliche Freigabequelle**. Deshalb hängt das Approval-Gate weiterhin
  ausschließlich an geschütztem `main` und GitHub-Merge-Metadaten.
- Der dynamische Output-Branch ist nicht durch die Branch-Protection
  derselben Vertrauensklasse wie `main`. Deshalb wird nicht die Branch-URL,
  sondern der Bild-Commit-SHA im Post gespeichert und vor dem Buffer-Aufruf
  der Remote-Bildhash mit dem lokalen, visuell geprüften SHA-256 verglichen.
- Bilder unter commit-gepinnten URLs müssen weiterhin öffentlich abrufbar
  bleiben. Ein fehlender/abweichender Remote-Download stoppt den Sender
  **vor** dessen Reservierungsbeleg und vor Buffer.
- Die alten `ready-to-schedule`-Anfragen behalten ihre **eigenständige,
  explizite Terminierungsfreigabe**. Datierte Drafts (`state=
  verified_prescheduled_draft_not_queued`) sind dafür nicht geeignet.
  **Keine automatische Queue, keine automatische Veröffentlichung.**
- Aktionen sind erst nach finaler Freigabe der jeweiligen Kampagne zulässig.
  Alle lokalen und PR-CI-Tests sind synthetisch, ohne Buffer-Mutation.

## Synthetische Abnahme

```bash
python3 -B -m unittest discover -s tests -q
```

Enthalten: alte Belege vor neuen, nicht vorhandener Ledger-Branch als
Blocker, Receipt-Schreibziel, Git-Commit-Herkunft und Bildhash,
unveränderliche Bild-URLs, atomare Post-Pin-Prüfung und statische Kontrolle
der Workflow-`main`-Schreibgrenze.
