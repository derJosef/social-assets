# Buffer-Entwürfe direkt aus social-assets

**Stand: 2026-10-08.** Diese Integration verwendet ausschließlich GitHub Actions + offizielle Buffer-GraphQL-API, **kein n8n**. Der erste Pilot unterstützt genau einen **LinkedIn-Textentwurf** pro manuellem Lauf. Bilder, Karussells und weitere Kanäle werden bewusst erst nach erfolgreichem Ersttest ergänzt.

## Grenzen und Sicherheit

- GitHub Actions läuft **nur manuell** (`workflow_dispatch`). Kein Zeitplan, kein automatischer Push-Trigger.
- Voreinstellung `send_to_buffer = false`: prüft nur das JSON, übermittelt **nichts**.
- Ein Live-Lauf erzeugt nur einen Buffer-**Entwurf**: Der Code erzwingt `saveToDraft: true`. Keine Veröffentlichungs-, Queue- oder Terminierungsoperation im Code. `mode: addToQueue` ist eine von der Buffer-API verlangte Eingabe; wegen `saveToDraft: true` erfolgt **keine** Queue-Aufnahme.
- Die Kanal-ID wird vor dem Senden gegen die Buffer-API auf LinkedIn geprüft.
- Nach dem manuellen Sendeauftrag wird **vor** dem Buffer-Aufruf ein GitHub-Beleg unter `delivery-receipts/` reserviert. Ein zweiter Lauf mit demselben Dateinamen bricht ab, statt nochmals zu senden. Nach Erfolg enthält der Beleg die Buffer-Post-ID und den Status `draft_created`.
- Wenn nach der Reservierung ein API-/Netzwerkfehler auftritt, kann ein Beleg auf `pending_manual_reconciliation_on_failure` stehen bleiben. **Nicht einfach erneut starten**: Zuerst in Buffer nachsehen. Dies schützt vor unbemerkten doppelten Entwürfen, bedeutet aber manuellen Klärungsbedarf.
- Die Beleg-Dateien sind Teil dieses **öffentlichen** GitHub-Repositories. Sie enthalten keine Buffer-API-Schlüssel, jedoch Status, Dateipfad und gegebenenfalls eine Buffer-Post-ID.
- **Wichtig:** Das Repository `derJosef/social-assets` ist öffentlich. Keine vertraulichen, personenbezogenen oder vorab geheimzuhaltenden Beiträge oder Assets hier speichern. Gegebenenfalls später eine private, entsprechend geregelte Ablage einsetzen.

## Einmalige Einrichtung (durch den Repository-Eigentümer)

1. In Buffer unter https://publish.buffer.com/settings/api den **bereits vorhandenen persönlichen API-Schlüssel** wiederverwenden (z. B. den Schlüssel mit der Bezeichnung `GitHub`). **Keinen zweiten Schlüssel erstellen und keinen laufenden Schlüssel löschen.** Ein vorhandener API-Schlüssel kann für mehrere passende API-Abfragen verwendet werden. Der Explorer ist nicht erforderlich.
2. Falls noch nicht geschehen, den vorhandenen Buffer-Schlüssel in GitHub hinterlegen:
   `derJosef/social-assets → Settings → Secrets and variables → Actions → New repository secret`
   **Name:** `BUFFER_API_KEY` – **Wert:** vorhandener persönlicher Buffer-API-Schlüssel. Niemals in Repository-Dateien oder Chat-Nachrichten kopieren. GitHub-Secrets geben ihren Wert später nicht erneut preis: Falls der Schlüssel dort bereits eingerichtet ist, brauchst du ihn nicht noch einmal zu kopieren.
3. **Keine manuelle LinkedIn-Kanal-ID nötig:** Das Skript fragt mit demselben Buffer-Schlüssel erst die Organisation(en), dann die Kanäle ab und wählt automatisch den eindeutigen LinkedIn-Kanal. Wenn mehrere LinkedIn-Kanäle vorhanden sind, stoppt es ohne Versand. In diesem Sonderfall kann `BUFFER_CHANNEL_ID` optional als weiteres GitHub-Secret hinterlegt werden.
4. Auf GitHub unter `Settings → Actions → General` GitHub Actions freischalten und prüfen, dass die Workflow-Berechtigungen ein Repository-`GITHUB_TOKEN` mit `contents: write` für die Empfangsbelege erlauben. Der Workflow fordert die Berechtigung ausdrücklich an.
5. Der manuelle Workflow heißt `Buffer – LinkedIn-Entwurf`: `.github/workflows/buffer-draft.yml`.

## Verbindungstest (nur lesend, keine Buffer-Entwürfe)

In `derJosef/social-assets → Actions → Buffer – LinkedIn-Entwurf → Run workflow`:

- Branch: `main`
- `draft_file`: `drafts/beispiel-linkedin.json` unverändert lassen.
- `check_connection`: **anhaken**.
- `send_to_buffer`: **nicht anhaken**.
- Starten. Das Log sollte `Verbindungstest erfolgreich: LinkedIn-Kanal eindeutig gefunden.` anzeigen.
- Bei fehlendem `BUFFER_API_KEY` oder ungültigem Schlüssel kommt eine Fehlermeldung; es wird nichts an Buffer gesendet.
- Der Test liest nur Organisations-/Kanalinformationen über die Buffer-API. Die ermittelte Kanal-ID wird **nicht** in den öffentlichen GitHub-Actions-Logs ausgegeben.

## Trockenlauf (keine Buffer-Übertragung)

In `derJosef/social-assets → Actions → Buffer – LinkedIn-Entwurf → Run workflow`:

- Branch: `main`.
- `draft_file`: `drafts/beispiel-linkedin.json`.
- `send_to_buffer`: **nicht anhaken**.
- `check_connection`: **nicht anhaken**.
- Starten und im Actions-Protokoll auf `DRY-RUN OK` prüfen. Dabei wird **kein** Buffer-Schlüssel benötigt.

Alternativ lokal aus dem Repository-Root:

```bash
python3 scripts/buffer_draft.py --draft drafts/beispiel-linkedin.json --dry-run
```

## Erster echter Entwurf (keine Veröffentlichung)

1. In `drafts/` eine neue JSON-Datei anlegen. `drafts/beispiel-linkedin.json` enthält nur einen nicht zur Veröffentlichung bestimmten Testtext:
   ```json
   {
     "format_version": 1,
     "target": "linkedin",
     "text": "Dein LinkedIn-Beitragstext hier."
   }
   ```
2. Die neue Datei auf `main` committen. Erst nach Prüfung des Inhalts im GitHub-Workflow die Datei auswählen.
3. Workflow manuell starten, **nur diesmal** `send_to_buffer` aktivieren und `check_connection` deaktiviert lassen. Eine LinkedIn-ID brauchst du bei genau einem verbundenen LinkedIn-Kanal nicht selbst einzutragen.
4. Die Ausführung bestätigt bei Erfolg die Buffer-Post-ID. Im entsprechenden LinkedIn-Kanal in Buffer unter **Entwürfe** nachsehen.
5. Keine Veröffentlichung oder Planung durch den GitHub-Workflow. Eine spätere manuelle Planung in Buffer ist eine eigenständige Entscheidung.

**Achtung:** Nie einen bestehenden Dateinamen für einen zweiten Beitrag wiederverwenden. Für jeden neuen Entwurf eine **neue** Datei anlegen. Das ist beabsichtigt: die Empfangsbelege blockieren Wiederholungen für bereits versendete oder unklar gebliebene Dateinamen.

## Quelle und API-Vertrag

- Buffer offizielles Draft-Beispiel: https://developers.buffer.com/examples/create-draft-post.html
- Buffer GraphQL-Schnittstelle und Autorisierung: https://developers.buffer.com/guides/getting-started.html
- Buffer-Kanal-IDs: https://developers.buffer.com/examples/get-channels.html
- Buffer-Organisationen: https://developers.buffer.com/guides/data-model.html
- API-Authentifizierung: https://developers.buffer.com/guides/authentication.html
- GitHub Actions manueller Start: https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax#onworkflow_dispatch

## Abgrenzung zu PersonalOS / agent-workspace

- **PersonalOS:** führender Kontext, Skills, verbindliche Regeln; durch ChatGPT nicht schreibbar.
- **agent-workspace:** Recherche und Entwürfe während der Zusammenarbeit mehrerer Agenten.
- **social-assets:** explizit für den Buffer-Übertragungsweg freigegebene, unkritische Beiträge und später öffentliche Medien-URLs. Keine automatische Übernahme aus agent-workspace; die Übertragung wird bewusst vorbereitet und manuell gestartet.

## Ausbau nach dem Pilot

Bildposts/Karussells benötigen über Buffer öffentlich abrufbare, dauerhaft verfügbare direkte Bild-URLs; Buffer bietet keinen nativen Upload-Endpunkt über diese API. Vor Erweiterung die Plattformanforderungen und die Rechte an Assets prüfen.

Offizielle Buffer-Anleitung: https://developers.buffer.com/guides/hosting-media.html
