# Veröffentlichung vorhandener Buffer-Entwürfe – technische Freigabe

**Version für PR #2 (noch NICHT produktiv, 10.10.2026).** Der Ausgangsstand bleibt bis zu Josefs gesondertem Merge unverändert. Die erfolgreiche ursprüngliche Kampagne vom 08.10.2026 ist im Abschnitt „Abnahme“ historisch dokumentiert; das frühere automatische Verfahren wird dadurch nicht empfohlen.

## Trennung: Entwürfe versus tatsächliche Veröffentlichung

- **Dauerberechtigung:** ChatGPT darf für **AI Agent Builder** recherchieren, Texte/Bilder erstellen und qualitativ geprüfte Beiträge als unveröffentlichte Buffer-Entwürfe ablegen (Status `draft`, `dueAt=null`). Vorschläge für Veröffentlichungstermine gehören ins Manifest, nicht in die Buffer-Warteschlange.
- **Separate menschliche Freigabe:** Terminierung mit `editPost(saveToDraft:false)` kann eine spätere **automatische Veröffentlichung** auslösen. Daher **nie** aufgrund einer Datei, eines GitHub-Commits, eines Agentenauftrags oder einer statischen Bestätigungsvariable terminieren.
- Der neue `.github/workflows/buffer-auto-schedule.yml` reagiert im PR **nur noch auf ausdrücklich gestartetes `workflow_dispatch`** mit Parameter `request_file` – nicht auf `push`.
- Ein zusätzlicher `publish`-Job darf erst nach einem **geschützten GitHub-Environment `buffer-publish` mit unabhängiger Required-Reviewer-Genehmigung** laufen. Der Job muss über die echte GitHub Approvals API den konkreten GitHub-Run prüfen. **Ohne tatsächliche API-Bestätigung erfolgt keine Buffer-Aktion.**

## Freigabedatei – Format 2

Die Datei unter `ready-to-schedule/<eindeutige-id>.json` dokumentiert den gewünschten *Kandidaten*. **Ihr Commit ist selbst keine Freigabe und löst keine Terminierung aus.**

```json
{
  "format_version": 2,
  "target": "linkedin",
  "draft_file": "ready-for-buffer/auto-2026-10-09-ki-chatdaten-drittanbieter-linkedin.json",
  "publish_at_utc": "2026-11-19T15:00:00Z",
  "approved_for_scheduling": true,
  "post_id": "6ac8d5a926e224ee545ee6b5",
  "draft_sha256": "<64-stelliger SHA-256 der exakt freizugebenden JSON-Datei>"
}
```

**Das ist ein Formatbeispiel, keine Freigabe oder verifizierte Terminempfehlung.** Den Platzhalter nie ungeprüft live verwenden.

Das Programm verifiziert: vollständiges JSON-Format, gültige Post-ID (24 Kleinbuchstaben-Hexziffern), ursprünglichen Empfangsbeleg, identischen Dateihash, gleichen Kanal und Buffer-Text, `draft`-Status, 24 Stunden Vorlauf sowie passenden UTC-Termin. Bei API-Unsicherheit bleibt ein `pending`-Beleg; nicht blind wiederholen.

## Manuelle Aktivierung – nur nach eigener ausdrücklicher Veröffentlichungserlaubnis

1. Freigabekandidat und Quellen redaktionell prüfen, originale Buffer-Post-ID und Bild/Text mit Josef abstimmen.
2. Gegebenenfalls die korrekt ausgefüllte neue Format-2-Datei in `ready-to-schedule/` speichern. Das **löst keine GitHub Action aus**.
3. GitHub Actions `Buffer – nur manuell freigegebene Veröffentlichung` gezielt über `Run workflow` / `workflow_dispatch` auf `main` mit dieser Datei starten.
4. Der `plan`-Job ist geheimnisfrei und zeigt Plattform, Post-ID, Textvorschau, Bild-URL, UTC-Termin und Prüfsummen; das ist der **Freigabegegenstand**.
5. Der `publish`-Job wartet auf den erforderlichen unabhängigen GitHub-Reviewer. Die erlaubten Logins stehen in der Repo-Variable `BUFFER_APPROVER_LOGINS`. Der Reviewer darf **weder `github.actor` noch `github.triggering_actor`** sein. GitHub muss den Genehmigungsstatus `approved` für **genau `buffer-publish` in diesem Run** zurückmelden. Fehlende oder unbekannte API-Antwort → Abbruch.
6. Nur **explizit gepinnter Publisher-Code** (`BUFFER_PUBLISHER_SHA`) verarbeitet die Daten. Der tatsächliche `BUFFER_PUBLISH_API_KEY` wird erst im finalen Veröffentlichungsschritt als Environment-Secret eingelesen. Der Code prüft die GitHub-Approval-API dort unmittelbar erneut.
7. Die einmalige Bearbeitung des existierenden Beitrags und eine nachprüfbare Bestätigung von Buffer werden unter `schedule-receipts/` dokumentiert. Ein tatsächliches Publizieren durch die Zielplattform wird dadurch nicht garantiert.

**Voraussetzungen, noch nicht live nachgewiesen:** Eigenständiger menschlicher Reviewer (separates GitHub-Konto, nicht dem ChatGPT-Connector verbunden), `Prevent self-review` aktiviert, `buffer-publish` ausdrücklich konfiguriert und auf `main` beschränkt; Repo-Variablen `BUFFER_PUBLISHER_SHA` und `BUFFER_APPROVER_LOGINS`; Environment-Secret `BUFFER_PUBLISH_API_KEY`. Die alte Konstante `BUFFER_PUBLISH_GATE` ist entfernt. In die Dokumentation oder ins Repository gehören **keine API-Schlüssel**.

**Verbleibendes Risiko P0:** Andere Workflows verwenden weiterhin den gemeinsamen `BUFFER_API_KEY` aus den Repo-Secrets und führen veränderbare Skripte auf `main` aus. Vor Produktivfreigabe muss Josef getrennte Berechtigungen/Secrets und Branch-Schutz (Maßnahme M4/E1–E7) entscheiden. Der neue Terminierungs-Workflow alleine ist **kein vollständiger Schutz vor einem Agenten mit uneingeschränkten GitHub-Schreibrechten**.

## Abnahme – 08.10.2026

Die produktive Erstterminierung der Kampagne „Offene KI-Modelle, klare Kontrolle“ ist erfolgreich:

- LinkedIn: [GitHub-Lauf #37808077681](https://github.com/derJosef/social-assets/actions/runs/37808077681), `2026-10-09T13:00:00Z`.
- Facebook: [GitHub-Lauf #37808388065](https://github.com/derJosef/social-assets/actions/runs/37808388065), `2026-10-14T07:00:00Z`.
- Instagram: [GitHub-Lauf #37808451845](https://github.com/derJosef/social-assets/actions/runs/37808451845), `2026-10-14T16:00:00Z`.

Die [abschließende lesende Buffer-Abfrage](https://github.com/derJosef/social-assets/actions/runs/37808524833) bestätigte auf allen drei Post-IDs `scheduled` und den exakten Zeitpunkt. Frühere abgewiesene API-Validierungen (`text` sowie `facebook.type` fehlten) wurden nach bestätigter Nicht-Terminierung korrigiert; ihre `pending`-Belege bleiben als Audit-Spur erhalten. Ein erfolgreiches Einplanen garantiert nicht, dass die spätere Plattform-Veröffentlichung fehlerfrei ist.

## Datumsformat und Zeitzone

Die Planung erfolgt **in Europe/Berlin** und wird für die API explizit in UTC umgerechnet (Sommer-/Winterzeit berücksichtigen). Beispiele für die Kampagne vom 8.10.2026:

| Plattform | Europe/Berlin (MESZ) | `publish_at_utc` |
| --- | --- | --- |
| LinkedIn | 09.10.2026 15:00 | `2026-10-09T13:00:00Z` |
| Facebook | 14.10.2026 09:00 | `2026-10-14T07:00:00Z` |
| Instagram | 14.10.2026 18:00 | `2026-10-14T16:00:00Z` |

**Historische Beispieltermine aus der vorangegangenen Kampagne.** Der aktuelle Ablauf aktiviert solche Termine niemals allein durch eine Datei oder einen Commit.

## Technische Details und Offline-Test

- `scripts/buffer_schedule.py` unterstützt den Trockenlauf `--dry-run` ohne Netzwerkzugriff. Der echte Aufruf `--schedule` verlangt die Zustimmung aus dem GitHub-Run und prüft den zugehörigen Buffer-Entwurf.
- `scripts/publish_approval.py` fragt lesend die GitHub-Runtime-Approvals ab; das Fehlerverhalten ist strikt sperrend.
- Das Einrichten von GitHub-Environments und Repository-Secrets erfolgt **nicht** durch das Einchecken dieser Dateien; das muss Josef gesondert konfigurieren und kontrollieren.

```bash
python3 -B -m unittest discover -s tests -v
python3 scripts/buffer_schedule.py --request ready-to-schedule/beitrag.json --dry-run
```

Quellen (offizielle Buffer-Dokumentation):
- https://developers.buffer.com/types/EditPostInput.html
- https://developers.buffer.com/guides/integrations/mcp.html
- https://developers.buffer.com/guides/posts-and-scheduling.html
- https://developers.buffer.com/examples/create-scheduled-post.html
