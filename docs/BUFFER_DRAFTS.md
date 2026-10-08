# Buffer-Entwürfe direkt aus social-assets

**Stand: 2026-10-08.** GitHub Actions + offizielle Buffer-GraphQL-API, **kein n8n**. Manuelle und automatische LinkedIn-Entwürfe wurden erfolgreich an Buffer übertragen: Text, Bild und PDF-Dokument. Seit dem 08.10.2026 sind zudem Facebook-Textentwürfe und Instagram-Bildentwürfe mit API- und GitHub-Belegen erfolgreich getestet. Der Freigabeordner `ready-for-buffer/` startet nur für neu hinzugefügte JSON-Dateien automatisch. Video und weitere, nicht genannte Kanäle bleiben deaktiviert.

## Facebook und Instagram – Erweiterung vom 08.10.2026

Die Eingabedatei entscheidet mit `target` ausdrücklich, zu welcher Plattform ein Beitrag übertragen wird. **Jede Datei erzeugt ausschließlich einen Entwurf für genau einen Kanal.** Es gibt kein automatisches Mehrfachposting.

- LinkedIn: Text, Bilder, PDF-Dokumente (wie bisher).
- Facebook-Seite: Textentwürfe (Format 1) oder Bildentwürfe (Format 2).
- Instagram: ausschließlich Bildentwürfe (Format 2). Text ohne Bild, PDFs, Reels und Storys sind in diesem Workflow gesperrt. Maximal 10 Bilder und 2.200 Zeichen je Caption. Instagram-Bilder müssen ein geeignetes Seitenverhältnis haben (4:5 bis 1,91:1).
- Die eigentliche Übertragung ist weiterhin ausschließlich ein Buffer-Entwurf mit `saveToDraft: true`. Kein Terminieren, kein Queueing, kein Veröffentlichen.
- Buffer-Kanäle werden nach ihrem `service`-Wert unterschieden. Sollte mehr als ein Facebook- oder Instagram-Kanal verbunden sein, stoppt der Transfer, bevor Buffer einen Entwurf erstellt. Dann kann die richtige ID ausdrücklich über das GitHub Actions Secret `BUFFER_FACEBOOK_CHANNEL_ID` bzw. `BUFFER_INSTAGRAM_CHANNEL_ID` ausgewählt werden. `BUFFER_CHANNEL_ID` bleibt die bisherige LinkedIn-Option.
- Neue Vorlagen: [Facebook-Text](../drafts/vorlage-facebook-text.json) und [Instagram-Bild](../drafts/vorlage-instagram-bild.json). Keine dieser Vorlagen wird automatisch versendet, solange sie unter `drafts/` liegt.
- `ready-for-buffer/` bleibt das **einzige** automatische Freigabeverzeichnis. Ein neuer Dateiname wird durch einen separaten Empfangsbeleg gegen wiederholten Versand geschützt.
- Medien liegen öffentlich unter `media/`. Keine nicht freigegebenen Firmen- oder Personenbilder hochladen.

Offizielle Quellen: https://developers.buffer.com/guides/data-model.html · https://developers.buffer.com/examples/create-draft-post.html · https://support.buffer.com/en-us/articles/using-instagram-with-buffer-YSjg2dXFV8

**Abnahme vom 08.10.2026:** 34 Offline-Regressionstests bestanden. Beide zusätzlichen Kanäle sind durch bestätigte Live-Übertragungen abgenommen:
- Facebook: [GitHub-Lauf #37785740152](https://github.com/derJosef/social-assets/actions/runs/37785740152), [Empfangsbeleg](../delivery-receipts/d4a745d637fb922f3cd89153.json), Buffer-Post-ID `6ac79c7cd1ababbf88b1c607`.
- Instagram: [GitHub-Lauf #37785797813](https://github.com/derJosef/social-assets/actions/runs/37785797813), [Empfangsbeleg](../delivery-receipts/2b85199bff09bcfce284c209.json), Buffer-Post-ID `6ac79c9782db5af660c65919`.

**Fehlerbehebung:** In der ersten Version fehlte die laut Buffer API verpflichtende Social-Media-Metadatenangabe (`facebook.type=post` beziehungsweise `instagram.type=post` und `instagram.shouldShareToFeed=true`). Beide ersten Anfragen wurden von Buffer mit MutationError zurückgewiesen; ihre ursprünglichen `pending_manual_reconciliation_on_failure`-Belege bleiben als unveränderte Prüfspur erhalten. Die erfolgreiche, korrigierte Version verwendet neue, eindeutige Dateinamen und erzeugt niemals von sich aus eine Veröffentlichung oder Terminierung.

---

## Grenzen und Sicherheit

- Zwei GitHub Actions: ein manueller `workflow_dispatch`-Test und ein automatischer Push-Workflow ausschließlich für neu hinzugefügte Dateien unter `ready-for-buffer/`. Kein Zeitplan.
- Voreinstellung `send_to_buffer = false`: prüft nur das JSON, übermittelt **nichts**.
- Ein Live-Lauf erzeugt nur einen Buffer-**Entwurf**: Der Code erzwingt `saveToDraft: true`. Keine Veröffentlichungs-, Queue- oder Terminierungsoperation im Code. `mode: addToQueue` ist eine von der Buffer-API verlangte Eingabe; wegen `saveToDraft: true` erfolgt **keine** Queue-Aufnahme.
- Die Kanal-ID wird vor jedem Senden gegenüber dem in `target` ausdrücklich genannten Buffer-Dienst geprüft.
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
- **social-assets:** explizit für den Buffer-Übertragungsweg freigegebene, unkritische Beiträge und später öffentliche Medien-URLs. Keine automatische Übernahme aus agent-workspace; die Übertragung wird bewusst vorbereitet und durch neue, freigegebene JSON-Dateien unter `ready-for-buffer/` gestartet.

## Automatische Übertragung neuer freigegebener LinkedIn-Entwürfe

Der Workflow [buffer-auto-drafts.yml](../.github/workflows/buffer-auto-drafts.yml) überwacht ausschließlich **neu hinzugefügte** JSON-Dateien unmittelbar unter `ready-for-buffer/` auf Branch `main`.

Ablauf:
1. Beitrag unter `drafts/` vorbereiten und inhaltlich prüfen. **Das Anlegen oder Bearbeiten dieser Datei löst keinen Buffer-Transfer aus.**
2. **Erst nach ausdrücklicher Freigabe durch Josef** eine neue JSON-Datei unter `ready-for-buffer/<eindeutiger-dateiname>.json` erstellen oder dorthin übertragen und nach `main` committen/pushen. Git behandelt Umbenennungen bei der Freigabe absichtlich als neu hinzugefügte Datei.
3. Der GitHub-Push startet den automatischen Workflow. Nur auf diesem Push **hinzugefügte** JSON-Dateien werden übertragen; Bearbeitungen vorhandener Dateien lösen keinen zweiten Versand aus. Pro Dateiname erzeugt das Skript einen dauerhaften Reservierungs-/Ergebnisbeleg und blockiert Wiederholungen.
4. Buffer erhält ausschließlich einen **Entwurf**, niemals eine Queue-Aufnahme oder Veröffentlichung. Kontrolle und Veröffentlichung bleiben manuell in Buffer.

Technische Schutzmaßnahmen:
- `push`-Trigger ist auf `ready-for-buffer/*.json` begrenzt. Ein Commit in `drafts/`, `scripts/`, `docs/` oder `delivery-receipts/` löst keinen automatischen Entwurfstransfer aus.
- Bei kombinierten Commits werden nur **neu hinzugefügte Dateien** im Freigabeordner verarbeitet. Der Workflow behandelt Dateiänderungen und Löschungen nicht als erneute Freigaben.
- Falls ein GitHub-Workflow selbst mit dem regulären `GITHUB_TOKEN` Dateien committet, startet dies in der Regel **keinen weiteren Push-Workflow**. Das ist GitHub-Sicherheitsverhalten; direkte Commits durch einen Agenten mit separatem GitHub-App-/Benutzertoken können ihn hingegen auslösen. Deshalb müssen Agenten die Freigabegrenze einhalten. Quelle: https://docs.github.com/en/actions/concepts/security/github_token
- Ein `pending`-Beleg nach Netzwerk-/API-Fehler muss manuell geklärt werden, um doppelte Entwürfe zu vermeiden.
- Der automatische Live-Push-Test ist bestanden (Text, Bild und PDF). Kein Test im Freigabeordner anlegen, sofern nicht wirklich ein zusätzlicher Buffer-Entwurf erzeugt werden soll.

### Bestehenden Testentwurf nicht erneut übertragen

Der Beispieltext `drafts/beispiel-linkedin.json` wurde bereits manuell als Entwurf übertragen, mit bestätigt gespeicherter Buffer-Post-ID. Verschiebe ihn **nicht** nach `ready-for-buffer/`, wenn du nicht ausdrücklich einen zusätzlichen Testentwurf erzeugen möchtest: Der neue Dateipfad hätte absichtlich einen anderen Empfangsbeleg.

### Medienformate: Bilder und PDF-Karussells freigeschaltet

Für Medienentwürfe gilt `format_version: 2`; das ursprüngliche Textformat `format_version: 1` funktioniert unverändert weiter.

- **Bilder:** Im Feld `media` steht `{"type":"images","images":[{"url":"...","alt_text":"..."}]}`. Zulässig sind 1 bis 20 Bilder (PNG, JPG/JPEG, WebP) mit aussagekräftigem Alternativtext. Vorlage: [LinkedIn-Bild](../drafts/vorlage-linkedin-bild.json).
- **LinkedIn-PDF-Karussell:** Im Feld `media` steht `{"type":"document","url":"...pdf","thumbnail_url":"...png","title":"Dokumenttitel"}`. Genau ein PDF je Beitrag; zusätzlich sind ein Vorschau-Bild und ein Titel erforderlich. Vorlage: [LinkedIn-PDF](../drafts/vorlage-linkedin-karussell.json). Buffer dokumentiert bis zu 100 MB und 300 PDF-Seiten.
- **Hosting:** Medien unter `media/images/` oder `media/documents/` müssen öffentlich und über `https://raw.githubusercontent.com/derJosef/social-assets/main/media/...` erreichbar sein. Die API akzeptiert keine Dateiuploads, sondern nur Medien-URLs. Die Dateien müssen bis zur späteren manuellen Veröffentlichung bestehen bleiben.
- **Live-Prüfung:** Das Skript kontrolliert vor dem Versand den HTTPS-Medienpfad und die direkte öffentliche Erreichbarkeit per HEAD-Anfrage. Fehler verhindern den Buffer-Aufruf. Wiederholungen werden durch die bestehenden GitHub-Belege blockiert.
- **Keine automatische Veröffentlichung:** Die einzige Buffer-Mutation setzt weiter `saveToDraft: true`. Bilder und PDFs gehören nur zum bestehenden LinkedIn-Kanal, kein Video und keine zusätzlichen Kanäle.
- **Wichtig:** Das gesamte Repository ist öffentlich. Vor dem Upload Datenschutz, Urheberrechte, Bildrechte und etwaige Personenbezüge prüfen.

Offizielle Dokumentation:
- https://developers.buffer.com/examples/create-image-post.html
- https://developers.buffer.com/guides/hosting-media.html
- https://support.buffer.com/articles/using-linkedin-with-buffer-K7tRkGD3mH

**Nachgewiesene Live-Medientests am 08.10.2026:**
- Bild-Entwurf: [GitHub-Lauf #37766082237](https://github.com/derJosef/social-assets/actions/runs/37766082237), Buffer-Post-ID `6ac77566390a3385c92eda30`.
- PDF-Karussell-Entwurf: [GitHub-Lauf #37766132425](https://github.com/derJosef/social-assets/actions/runs/37766132425), Buffer-Post-ID `6ac77582f9e3728044fb41d9`.
- Die Buffer-API hat jeweils die Entwurfserstellung bestätigt. Ob die Medien vollständig und optisch korrekt im Buffer-Editor erscheinen, ist zusätzlich manuell zu prüfen.

## Lokale Tests / GitHub CI

```bash
python3 -m unittest discover -s tests -v
```

Die Tests sind offline und benötigen keinen Buffer- oder GitHub-Schlüssel.

## Ausbau nach dem Pilot

Für die produktive Nutzung zunächst ein echtes Markenbild und ein PDF-Karussell in Buffer visuell prüfen. Danach kann das Bild-/PDF-Format für freigegebene Inhalte verwendet werden. Die gemischte Bild-und-Video-Funktion aus Buffers Weboberfläche ist noch nicht separat über die API geprüft und bleibt daher außerhalb dieser Integration.

Offizielle Buffer-Anleitung: https://developers.buffer.com/guides/hosting-media.html
