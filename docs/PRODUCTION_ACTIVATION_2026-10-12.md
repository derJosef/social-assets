# Aktivierung AI Agent Builder Draft-first – 12. Oktober 2026

**Aktueller Stand:** Sicherer Integrations-PR [#14](https://github.com/derJosef/social-assets/pull/14), direkt gegen `main`; noch nicht gemergt. Der ursprüngliche PR-Stack #7 → #11 → #12 → #13 wird **nicht** einzeln gemergt, weil sonst die längst widerrufene Brief-Vorabfreigabe zwischenzeitlich produktiv würde. Die sechs Buffer-Einmaltestdateien auf `main` wurden dabei unverändert bewahrt.

## Belegte Ist-Werte vor Aktivierung

- `main`: HEAD `a5cd8b2f78ea214789517f96259f01cb58e2e68e`, GitHub-Branch-API: `protected=false`. Repository-Rulesets: `[]`.
- `automation-receipts`: am 12.10.2026 mit diesem `main`-HEAD initialisiert, durch den GitHub-Branch-Endpunkt zurückgelesen; `protected=false`; **keine neuen Posts angelegt**.
- Neue Schutzstufe `scripts/production_activation_guard.py`: prüft vor jedem kostenpflichtigen Image-Provider-Aufruf und vor JEDEM Buffer-Draft-Transfer unabhängig die GitHub-Branch-Metadaten auf `protected=true` sowohl für `main` als auch `automation-receipts`, plus exakte `refs/heads/main`- und Commit-SHA-Bindung. Bei 403/404, fehlenden Rechten oder ungeschütztem Branch STOP. Die Sicherheitsabfrage ist vor die Bildvorstufe in den Hauptorchestrator gesetzt.
- Im Integrations-PR neu: `.github/workflows/social-main-offline-required.yml`, **ohne Pfadfilter**, bei jedem Pull Request auf `main` mit Job-Name `social-main-offline-required`. Run enthält ausschließlich synthetische Tests, keinerlei API-/Buffer-Secrets. Nicht mit der gleichnamigen optionalen PR-Testworkflow-Gruppe verwechseln.
- Die bisherigen fünf/sieben alten PRs nicht zusätzlich mergen, auch nicht per Auto-Merge.

## Zwei einmalig nötige Einstellungen in GitHub (Eigentümer)

Der verfügbare GitHub-Connector kann zwar Quellcode und PRs lesen/schreiben, **aber keine Branch-Protection-/Ruleset-Einstellungen durchführen**; der Versuch, den Protection-Endpunkt zu lesen, lieferte `403 Resource not accessible by integration`. Daher diese zwei kurzen GitHub-UI-Schritte vom Repository-Eigentümer selbst:

1. [Repository → Settings → Branches](https://github.com/derJosef/social-assets/settings/branches) → **Add classic branch protection rule**.
   - `Branch name pattern`: exakt **`main`**.
   - **Require a pull request before merging** aktivieren.
   - **Require approvals** zunächst **nicht** aktivieren (ein persönlicher Eigentümer, kein zweiter Reviewer), damit Josef seinen eigenen geprüften PR mergen kann.
   - **Require status checks to pass before merging** aktivieren und den echten Check **`social-main-offline-required`** auswählen, sobald er nach dem PR-#14-Test angezeigt wird. Den Check **nicht** anhand des Workflow-Anzeigenamens verwechseln.
   - **Do not allow bypassing the above settings** aktivieren; `Allow force pushes` und `Allow deletions` ausgeschaltet lassen.
   - **Lock branch** NICHT aktivieren. Speichern.
2. Auf derselben Seite eine zweite **classic branch protection rule** anlegen:
   - `Branch name pattern`: exakt **`automation-receipts`**.
   - **Require a pull request before merging** **nicht** aktivieren; `Require status checks` **nicht** aktivieren; **Lock branch** **nicht** aktivieren. Der GitHub-Actions-Bot muss neue einmalige Pending-/Erfolgsbelege weiterhin regulär an diesen Branch schreiben dürfen.
   - **Allow force pushes** und **Allow deletions** ausgeschaltet lassen; wenn verfügbar **Do not allow bypassing** aktivieren.
   - Speichern. Keine globalen Regeln für `automation/*` pauschal setzen.

Die Regeln gibt es laut offizieller GitHub-Dokumentation auch in öffentlichen Free-Repositories: https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/managing-a-branch-protection-rule

## Danach nur kontrolliert aktivieren

1. Über den GitHub-Connector **beide** öffentlichen Branch-Endpunkte `/repos/derJosef/social-assets/branches/main` und `/repos/derJosef/social-assets/branches/automation-receipts` lesen; beide müssen `protected=true` liefern. Ungeklärte Antworten => BLOCKED, niemals den Schutz als vorhanden annehmen.
2. Auf **dem exakten HEAD von PR #14** alle sechs Offline-Actions `completed/success` bestätigen, insbesondere den neuen erforderlichen Check `social-main-offline-required`. Solange der PR-Diff sich ändert, prüfe neuen Commit erneut.
3. Danach PR #14 als **einzige** atomare Integration zu `main` übernehmen, aber nur mit Jos​efs eindeutiger aktueller Erlaubnis zur Integration. Unter keinen Umständen #7/#11/#12/#13 vorab nacheinander mergen. Endgültige GitHub-Merge-Response und tatsächlichen `main`-HEAD lesen.
4. Verifizieren, dass die neue Workflowdatei und `production_activation_guard.py` wirklich auf `main` liegen, die vorherigen testweise erzeugten Buffer-Drafts unverändert bleiben und der LEDGER weiterhin geschützt und beschreibbar ist.
5. `SOCIAL_OPENAI_API_KEY` muss für `gpt-image-1.5` und `gpt-4.1-mini` nutzbar sein; keine Tokens im Chat/Repo offenlegen. Kein blind wiederholter Einmal-Probe-Post. Bei Abnahme der **nächsten** echten neuen Kampagne alle drei neuen Buffer-Drafts per unabhängigem Readback `status=draft`, korrekter Channel-ID und `dueAt` prüfen, ebenso das Original-Logo, Bild/Claims und Quellen.
6. Nur nach erfolgreich gesicherten Receipts und getrenntem Buffer-Readback als drei fertige Drafts in ChatGPT darstellen. Keine Queue/Publication, keine ungeprüften Deep-Links.
7. Die spätere persönliche Freigabefunktion muss direkt in Buffer vorgenommene Text-/Bild-/Zeitänderungen **erhalten** und verlangt separate Endabnahme; der alte `buffer_schedule.py` ist hierfür NICHT freigegeben.

## Kein Schein-PASS

Die Initialisierung des Ledger-Branches ist nicht dasselbe wie dessen Schutz. Vier oder sechs grüne GitHub-Offline-Checks sind kein Bildmodell-Livetest und kein Buffer-Transfer. Eine eingerichtete Automation ist kein Nachweis für funktionierende neue Drafts. In jeder Teilblockade konkrete Gründe, Logs und vorhandene sichere Vorarbeiten berichten.
