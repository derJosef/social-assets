# Aktivierung AI Agent Builder Draft-first – 12. Oktober 2026

**Aktueller Stand:** Sicherer Integrations-PR [#14](https://github.com/derJosef/social-assets/pull/14), direkt gegen `main`; noch nicht gemergt. Der ursprüngliche PR-Stack #7 → #11 → #12 → #13 wird **nicht** einzeln gemergt, weil sonst die längst widerrufene Brief-Vorabfreigabe zwischenzeitlich produktiv würde. Die sechs Buffer-Einmaltestdateien auf `main` wurden dabei unverändert bewahrt.

## Belegte Ist-Werte vor Aktivierung

- `main`: HEAD `a5cd8b2f78ea214789517f96259f01cb58e2e68e`, GitHub-Branch-API: `protected=false`. Repository-Rulesets: `[]`.
- `automation-receipts`: am 12.10.2026 mit diesem `main`-HEAD initialisiert, durch den GitHub-Branch-Endpunkt zurückgelesen; `protected=false`; **keine neuen Posts angelegt**.
- Neue Schutzstufe `scripts/production_activation_guard.py`: prüft vor jedem kostenpflichtigen Image-Provider-Aufruf und vor JEDEM Buffer-Draft-Transfer unabhängig die GitHub-Branch-Metadaten auf `protected=true` sowohl für `main` als auch `automation-receipts`, plus exakte `refs/heads/main`- und Commit-SHA-Bindung. Bei 403/404, fehlenden Rechten oder ungeschütztem Branch STOP. Die Sicherheitsabfrage ist vor die Bildvorstufe in den Hauptorchestrator gesetzt.
- Im Integrations-PR neu: `.github/workflows/social-main-offline-required.yml`, **ohne Pfadfilter**, bei jedem Pull Request auf `main` mit Job-Name `social-main-offline-required`. Run enthält ausschließlich synthetische Tests, keinerlei API-/Buffer-Secrets. Nicht mit der gleichnamigen optionalen PR-Testworkflow-Gruppe verwechseln.
- Die bisherigen fünf/sieben alten PRs nicht zusätzlich mergen, auch nicht per Auto-Merge.

## Automatischer Kampagneneingang OHNE Vorabfreigabe und OHNE Bot-Push nach main

**Verbindlicher Betrieb:** Die montägliche ChatGPT-Automation verfasst den
vollständigen, geprüften öffentlichen Kampagnenbrief und legt mit der
verbundenen GitHub-App **genau ein neues Issue** an:

- **Titel exakt:** `AIAGENT_BRIEF:YYYY-MM-DD-slug`
- **Body:** ausschließlich ein gültiges UTF-8-JSON-Objekt nach dem
  bestehenden vollständigen `orchestration/briefs/YYYY-MM-DD-slug.json`-
  Schema (`format_version: 1`, Marke `ai-agent-builder`,
  `execution_mode: drafts`, mindestens zwei unabhängige Inhaltsquellen und sechs Postingzeit-Quellen,
  `image_review: visual-reviews/<slug>.json`, alle drei `prepared_content.posts` (je Kanal 250 bis 3.000 Zeichen,
  Instagram maximal 2.200), `prepared_content.visual=null`,
  sechs vollständige Hüte und `prepared_content.risks`).
  **Kein Markdown-Codeblock** und keine persönlichen oder geheimen Daten.
- Das GitHub-`issues: opened`-Ereignis startet GitHub Actions mit dem
  **vertrauenswürdigen Workflow-Code auf dem geschützten Default-Branch
  main**. Triggerbedingung: Benutzername **`derJosef`**, GitHub-
  Autorbeziehung **`OWNER`**, passender Titel. Andere öffentliche
  Issues sind ausgeschlossen.
- `scripts/issue_brief_intake.py` prüft GitHub-Server-Ereignisdaten,
  Größe, Marken-ID, Drei-Kanal-Texte und exakt zulässige Felder;
  schreibt den Brief **nur lokal im Runner** und niemals nach
  `main`. Vor Bildanbieter/Buffer prüft `production_activation_guard.py`
  den effektiven Schutz beider Branches. Der vorhandene Preflight
  prüft danach echte Quell-/Visual-/Kanal-/Marken-/Zeitbelege.
- Der vom Issue übertragene Original-Brief wird zusammen mit Manifest,
  drei Postdateien und Plan im **isolierten eindeutigen
  `automation/campaign/<slug>`-Branch** archiviert. Bot schreibt
  nicht auf geschütztes `main`; bei identischem Kampagnen-Branch,
  fehlendem Ledger oder unvollständiger QA STOP/kein Retry.
- Die bereits dokumentierten Pfade über neue Brief-Dateien auf
  `main` bleiben nur als manuell freigegebene Alternative bestehen.
  **Keine manuelle PR-Freigabe pro Wochenkampagne nötig.**

**Tatsächlicher Berechtigungsnachweis vom 12.10.2026:** Einmaliges
ungefährliches GitHub-[Issue #15](https://github.com/derJosef/social-assets/issues/15)
über den GitHub-Connector erstellt, GitHub-REST-Issue-Liste unabhängig
gelesen: `user.login=derJosef`,
`author_association=OWNER`; danach Issue #15 geschlossen und erneut
`state=closed` geprüft. Das Test-Issue hat absichtlich **keinen**
`AIAGENT_BRIEF:`-Titel und löst keinen Buffer-Prozess aus. Das
bestätigt die Identität des GitHub-Issue-Eingangs, aber noch nicht
den echten GitHub-Actions-Issue-Workflow auf `main`, solange der PR
ungemergt bleibt.

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
