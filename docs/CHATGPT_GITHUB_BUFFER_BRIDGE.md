# ChatGPT-Abo → GitHub → Buffer: geprüfter Umbau

Stand 09.10.2026. **Noch nicht produktiv – nur Entwicklungsbranch.** Dieser Text beschreibt den geplanten, zunächst bewusst kontrollierten Workflow.

## Rückkehrpunkt (vor allen Umbauten)

- Repository: `derJosef/social-assets`
- Sicherungsbranch: `checkpoint/2026-10-09-pre-chatgpt-bridge`
- Exakter Commit: `392725cf481c0be930173a8dc5e5cc71c6ee5346`
- Entwicklungsbranch: `feature/chatgpt-bridge-safe-intake-20261009`
- Das produktive `main` bleibt bis zu einem gesonderten Merge unverändert.
- Ein Rücksprung auf diesen Commit stellt **nur GitHub-Dateien und GitHub-Workflows** wieder her. Bereits angelegte, terminierte oder veröffentlichte Buffer-Beiträge bleiben bestehen und müssen gegebenenfalls separat behandelt werden.
- Empfohlener Rückweg nach einem späteren Merge: Merge-Commit/PR **revertieren** und CI prüfen, nicht unkontrolliert `git reset --hard` auf `main` durchführen. Alternativ den unveränderten Sicherungsbranch als Vergleich und Basis einer geprüften Wiederherstellungs-PR verwenden.

## Praktischer Ablauf ohne zusätzliche Modell-API

1. **ChatGPT in einem normalen Chat** recherchiert das Thema, überprüft Quellen, erarbeitet Plattformtexte, sechs Denkhüte und Bildkonzept. Der GitHub-Connector wurde beim normalen Chat durch den Probe-Commit `70485bc` auf `bridge-probe/003` schreibend bestätigt. Für Hintergrundaufgaben ist diese Fähigkeit **noch nicht nachgewiesen**.
2. ChatGPT erstellt auf **einem neuen Arbeitsbranch** (nicht `main`) genau eine neue Datei `orchestration/briefs/YYYY-MM-DD-eindeutiger-slug.json` im bestehenden Schema (`format_version:1`, `brand:ai-agent-builder`, `execution_mode:drafts`, `topic`, `sources`, `posting_sources`, `prepared_content`). Keine Kundendaten/Secrets – das Repository ist öffentlich.
3. ChatGPT eröffnet einen Pull Request nach `main`. Die neue, **nicht privilegierte** Action `chatgpt-handoff-pr.yml` lädt den vertrauenswürdigen Code von `main` und übernimmt **nur die eine JSON-Datei** aus dem PR. Der Offline-Check `validate_chatgpt_handoff.py` prüft Marke, Eindeutigkeit, vollständige Texte, sechs Denkhüte und Bildschema. **Kein Buffer-Schlüssel, kein Versand, kein Merge.**
4. Der Pull Request wird fachlich überprüft. **Der Merge bleibt zunächst eine bewusste Entscheidung.** Das ist eine Kontrollstufe für die Übergangsphase, keine abschließende Lösung für einen vollständig unbeaufsichtigten Wochenlauf.
5. Sobald eine geprüfte `orchestration/briefs/*.json` auf `main` erscheint, startet der **bereits nachgewiesene** `social-campaign-orchestrator.yml`. Er lädt Quellen, erzeugt die Grafik, montiert und verifiziert das unveränderte Original-Logo, baut neun Artefakte, prüft das Quality Gate und erstellt LinkedIn-/Facebook-/Instagram-Drafts mit `saveToDraft:true`. Die Post-IDs und `dueAt=null` werden geprüft und protokolliert.
6. Vorschläge für Veröffentlichungstermine sind **keine Veröffentlichung**. Für eine tatsächliche Terminierung ist weiterhin eine **separate Zustimmung von Josef** nötig.

**Grenze:** Die Offline-Prüfung des PR stellt Struktur und technische Konsistenz sicher, **keine unabhängige inhaltliche Wahrheit**. Die bestehende automatische Erstellung von `checks: true` im Orchestrator wurde von Claude zu Recht kritisiert; vor einem vollständig unbeaufsichtigten Betrieb ist dafür ein eigenständiges, nachweisbares QA-Verfahren erforderlich. Die derzeit verwendeten Zeitfenster sind außerdem feste Vorschläge und keine nach Plattform gemessenen optimalen Postingzeiten.

## Schutz vor versehentlicher Veröffentlichung: vorgeschlagene Gate-Änderung

Der bisherige `buffer-auto-schedule.yml`-Workflow reagiert auf Datei-Pushes nach `ready-to-schedule/`. Das ist für eine automatische Agentenpipeline zu riskant. Der Entwicklungsbranch ersetzt dies durch:

- **Nur `workflow_dispatch`** mit einem expliziten Pfad zu einer vorhandenen Terminierungsanfrage. Datei-Push allein darf nicht mehr terminieren.
- Separater **Plan-Job ohne Buffer-Token** und mit GitHub-Actions-Zusammenfassung: Kanal, Entwurfsdatei, Post-ID, genaues UTC-Datum und Datei-Prüfsummen.
- Separater **Publish-Job** mit GitHub-Environment `buffer-publish`; die Ausführung wartet auf den dort konfigurierten Pflicht-Prüfer.
- Nur **Publisher-Code aus dem unveränderlichen SHA** der Repository-Variable `BUFFER_PUBLISHER_SHA` darf mit dem Publishing-Key laufen. JSON-Anfrage und vorhandener Buffer-Entwurf werden getrennt als Daten von `main` gelesen, erneut hashgeprüft und gegen den bestätigten Delivery-Receipt validiert.
- Anfragen benötigen **Format 2** mit `post_id` und `draft_sha256`. Freigaben mit altem Format 1 werden abgewiesen.
- **Mindestens 24 Stunden Vorlauf** statt zwei Minuten.
- Das Skript blockiert Publish-Aufrufe ohne `workflow_dispatch` und ohne **echte, aktuelle GitHub-Approval-Bestätigung** eines Prüfers, der weder `github.actor` noch `github.triggering_actor` ist. Der API-Endpunkt `GET /repos/{owner}/{repo}/actions/runs/{run_id}/approvals` wird im Publisher-Code erneut geprüft. Die vorherige statische Konstante `BUFFER_PUBLISH_GATE` entfällt.
- Die Plan-Zusammenfassung enthält nach Prüfung Plattform, Post-ID, Termin, **HTML-escaped Textvorschau und Bild-URL**. Ausgabeparameter aus GitHub-Daten dürfen keine Zeilenumbrüche enthalten.

**Wichtig: Der Gate-Branch ist noch nicht freigegeben oder auf `main` aktiviert.** Er verhindert nicht, dass ein Schreiber auf einem weiterhin ungeschützten `main` über andere, weniger sichere Workflows Zugriff auf den **bisherigen gemeinsamen** `BUFFER_API_KEY` erhält. Das kann nur durch Secret-Trennung, Pfad-/Branchschutz beziehungsweise eingeschränkte App-Rechte nachhaltig gesichert werden.

### Erforderliche manuelle GitHub-Einstellungen VOR einem Merge

1. GitHub App unter *Settings → Applications* prüfen: welche Berechtigungen kann sie zur Verwaltung von Actions, Deployments und Workflows ausüben? Die Agenten dürfen das spätere Genehmigungsgate nicht umgehen können.
2. Für `buffer-publish` ein GitHub-Environment mit **Required reviewers** einrichten: ein **zweites, nur einem Menschen gehörendes und nicht mit ChatGPT verbundenes GitHub-Konto**, `Prevent self-review` **AN**, nur `main` als Deployment-Branch. Eine automatisierbare Selbstgenehmigung unter `derJosef` erfüllt das Ziel nicht.
3. Nach Review der Publisher-Skripte die Repository-Variable `BUFFER_PUBLISHER_SHA` auf den **exakt genehmigten Commit-SHA** auf `main` setzen. Die zusätzliche Variable `BUFFER_APPROVER_LOGINS` enthält ausschließlich die unabhängigen zugelassenen Reviewer-Logins.
4. Environment-Secret **nur** `BUFFER_PUBLISH_API_KEY` setzen und die Kanal-IDs prüfen. `BUFFER_PUBLISH_GATE` wird **nicht** mehr eingerichtet (statische Konstante entfernt). Keine Secrets in Commits, Logs oder Chat-Nachrichten.
5. Prüfen, ob Buffer getrennte Token-Berechtigungen für Drafts/Publish zulässt. Falls nicht, Zugriff auf den bestehenden gemeinsamen `BUFFER_API_KEY` in anderen Workflows als verbleibendes P0-Risiko behandeln. Kein produktives Merge, bevor das bewusst entschieden ist.

Diese Einstellungen können von der normalen GitHub-Dateiverbindung **nicht** nachweislich konfiguriert werden. Dafür ist die GitHub-Oberfläche oder ein ausdrücklich autorisierter Administrationszugang nötig.

## Tests

- `.github/workflows/social-bridge-tests.yml`: sicherer Branch-CI-Test, nur `contents:read`, ohne Buffer-Secrets.
- `tests/test_buffer_schedule.py`: Format 2, 24-stellige Hex-Post-ID, Hash-Bindung, 24 Stunden Vorlauf, falscher Eventtyp, API-Freigabe verweigert, Replay-Verhinderung und Output-Injektionsregression.
- `tests/test_chatgpt_handoff.py`: vollständige Vorlagen, fehlende Plattform, unerlaubte Marke, doppelte Kampagne, Pfadmanipulation.
- `tests/test_publish_approval.py`: echte unabhängige Genehmigung; Status `pending/rejected`, falsche Identität, Selbstgenehmigung, falsches Environment, GitHub-Netzwerkfehler.
- **Kein Live-Buffer-Test auf diesem Entwicklungsbranch**, keinerlei Terminierung oder Veröffentlichung.

## Ungeklärte Punkte

- **ChatGPT Scheduled → GitHub:** normale Chat-Nachrichten können Branches und Dateien schreiben; Hintergrundaufgaben sind weiterhin nicht zuverlässig. Dafür separat eine neue geplante Probe ausschließlich auf `bridge-probe/*` durchführen, mit Ausführungsantwort und Berechtigungsmeldungen.
- QA-Aussagen/Postingzeitstudien müssen fachlich nachprüfbar dokumentiert werden, bevor ein vollständig selbstständiger Wochenlauf aktiv wird.
- Die GitHub-Environment-Genehmigung samt Rechteprüfung muss vor Live-Schaltung tatsächlich getestet werden.

## Freigabe-/Rollback-Regel

**Zunächst nur PR zur Durchsicht.** Kein Merge, keine Eingabe in `ready-for-buffer/` oder `ready-to-schedule/`, keine Buffer-Aktion. Ein endgültiger Merge braucht Josefs ausdrückliche Zustimmung nach grünem CI und GitHub-Environment-Vortest. Falls irgendetwas scheitert: Entwicklungsbranch/PR schließen, Sicherungsbranch erhalten, `main` nicht verändern.
