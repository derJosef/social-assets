# Buffer-API-Abgleich und gesondert freizugebender Einmal-Bildtest

Stand: **16. Oktober 2026**. Owner `derJosef/social-assets`. Nicht mit dem PersonalOS verwechseln: Dies ist ein technischer Prüfungsvorschlag. **Keine Buffer-Mutation bei der Erstellung dieses PR.**

## 1. Aktuelle offizielle Buffer-API-Spezifikation geprüft

Verwendete Primärquellen, am 16.10.2026 gelesen:

- [CreatePostInput](https://developers.buffer.com/types/CreatePostInput.html)
- [Buffer API Changelog](https://developers.buffer.com/changelog.html)
- [Create Draft Post](https://developers.buffer.com/examples/create-draft-post.html)
- [Create Scheduled Post](https://developers.buffer.com/examples/create-scheduled-post.html)
- [AssetInput](https://developers.buffer.com/types/AssetInput.html), [ImageAssetInput](https://developers.buffer.com/types/ImageAssetInput.html), [ImageMetadataInput](https://developers.buffer.com/types/ImageMetadataInput.html)
- [LinkedInPostMetadataInput](https://developers.buffer.com/types/LinkedInPostMetadataInput.html)
- [Hosting Media](https://developers.buffer.com/guides/hosting-media.html)
- [Error Handling](https://developers.buffer.com/guides/error-handling.html)

**Felder und Befunde:**

| Codeeingabe in `CREATE_DATED_DRAFT` | API-Vertrag am 16.10. | Bewertung |
| --- | --- | --- |
| `text: $text` | `String`, Entwurf mit Text möglich | Schema PASS |
| `channelId: $channelId` | `ChannelId!` | Schema PASS, historischer Kanal im API-Abgleich gefunden |
| `schedulingType: automatic` | gültiger Enum | PASS |
| `mode: customScheduled` | gültiger Enum `ShareMode` | PASS |
| `dueAt: $dueAt` | `DateTime` | PASS |
| `saveToDraft: true` | erlaubt; ergibt Status `draft` statt Veröffentlichungswarteschlange | PASS |
| `assets: $assets` | Liste `[AssetInput!]!` | PASS, genaue Bildprüfung erfolgt auf Buffer-Seite |
| Bild: `image.url` + `image.metadata.altText` | Felder existent, `url: String!`, `altText: String!` | PASS |
| LinkedIn-`metadata: null` | `PostInputMetaData` ist nullable; LinkedIn-Unterfelder optional | PASS |
| `needsApproval` im Code **weggelassen** | Die Detailseite zeigt `Boolean!`; das Changelog vom **28.07.2026** nennt ausdrücklich **Default `false`**. Beispielmutationen lassen das Feld weg. | **Kein belegter Mangel. Kein blindes Hinzufügen** |
| `aiAssisted` im Code weggelassen | Optionales `Boolean`; ggf. später für Herkunft kennzeichnen, keine belegte Ursache für `InvalidInputError` | Kein Grund für ungeprüften Mutationspatch |

Buffer stellt **separat** ein dokumentiertes Beispiel für das Anlegen eines Entwurfs und ein Beispiel für die Terminierung dar; die Kombination wird in den Beispielen nicht formal bewiesen. Dass sie **praktisch funktioniert**, belegt jedoch unser historischer [Einmaltest #38179032859](https://github.com/derJosef/social-assets/actions/runs/38179032859): LinkedIn `customScheduled` + `dueAt` + `saveToDraft: true`, jedoch **`assets: []`**. Der Lauf bestätigte den Status `draft` mit per Buffer-Readback überprüftem Datum. Damals war die Kanal-ID ebenfalls ohne optionales `BUFFER_CHANNEL_ID`-Secret eindeutig aufgelöst.

Der anschließende [Bild-Livetest #38748011264](https://github.com/derJosef/social-assets/actions/runs/38748011264) scheiterte bei `createPost` mit `InvalidInputError`. Dabei war das dokumentierte Rohbild über GitHub und den eigenen GitHub-Runner vollständig SHA-geprüft. **Das beweist nicht, dass Buffers Server dasselbe Bild erreichen, seine Dimensionen lesen oder verarbeiten konnte.** Die konkrete alte Fehlermeldung ging damals verloren; auch der neu gemergte sichere Diagnosecode kann sie nicht rückwirkend wiederherstellen.

**Fachliches Ergebnis:** Es wurde keine eindeutig falsche CreatePost-Eingabe gefunden. Darum **keine spekulative Änderung an der produktiven Mutation.** Nächster sinnvoller isolierter Vergleich ist ein technisch identischer, datierter LinkedIn-Entwurf **mit genau einem PNG**.

## 2. Vorbereitung des einmaligen Bildtests (nicht ausgeführt)

Neue ID: **`2026-10-16-buffer-image-draft-probe-001`**. Sie unterscheidet sich von `2026-10-15-drei-kontrollpunkte-e2e` und von dem bereits erfolgreich durchgeführten Text-only-Probe.

- **Nur LinkedIn**, nicht die vollständige Drei-Kanal-Kampagne.
- Kein neuer KI-Generator oder Adobe-Upload. Als Medienquelle dient ausschließlich das aus dem echten E2E erzeugte, deterministisch originalgelogte Markenbild: unveränderlicher GitHub-Commit `b535972ce7f788b7150edfede56093f0371c349a`, SHA256 `31da8e5364587b58d011c83f17ae8caab437c9af490995808db742de95feb496`. Die Datei wurde zuvor auf 1080×1350 und Original-Logo-Korrektheit geprüft.
- Dasselbe produktive `CREATE_DATED_DRAFT`-GraphQL-Schema, dasselbe `metadata: null` für LinkedIn, nur ein Bild in `assets` mit Alt-Text. Im Gegensatz zum vorherigen erfolgreichen Text-only-Einmaltest ist damit der **Bildpfad isoliert**.
- Ein eigener, deutlich markierter Text beginnt mit **INTERNER TECHNISCHER TEST – NICHT VERÖFFENTLICHEN.**
- Zukunftstermin ca. **120 Tage ab Ausführung**, bewusst weit genug entfernt, um bei unerwartetem Buffer-Fehlverhalten eine manuelle Prüfung zu ermöglichen. **Status muss in der Erstantwort UND unabhängig nachgelesen `draft` sein.** Kein `scheduled`, Queue oder Publish.
- Vor dem einzigen Create-Versuch: Besitzer-`workflow_dispatch` auf geschütztem `main`, `GITHUB_RUN_ATTEMPT=1`, festes Bestätigungswort, bestehender Receipt-Ledger vorhanden, Einmaltest-Receipt bisher nicht vorhanden, Bild-Git-Commit öffentlich als direkte Datei abrufbar, Quellbytes SHA-verifiziert, GitHub-Schutzregeln bestätigt.
- Neuer eigener Receipt-Pfad: `delivery-receipts/2026-10-16-buffer-image-prescheduled-draft-probe.json`. **Erst `pending_manual_reconciliation_on_failure` sicher auf `automation-receipts` schreiben, dann maximal EINE Buffer-Create-Mutation.** Bei jeder Unklarheit keine Wiederholung.
- Nach bestätigtem Create: identifizierte Post-ID sofort als `created_requires_independent_check` sichern; das separate Buffer-`post`-Readback muss exakte ID/Kanal/Datum/Text, `draft` und tatsächlich ein Bild-Asset mit Bild-`mimeType` bestätigen. Erst dann `verified_prescheduled_image_draft_not_queued`.
- Der historische Pending-Receipt `delivery-receipts/f0361bec557d3fb7e6f4d75b.json` wird **nicht** geändert. Kein Bypass des alten gesperrten Kampagnenauftrags, keine weiteren Kanäle.

### Sicherheitssteuerung

Neue isolierte Dateien `scripts/buffer_image_prescheduled_draft_probe.py` und `tests/test_buffer_image_prescheduled_draft_probe.py`; Trigger ausschließlich `.github/workflows/buffer-one-time-image-draft-probe.yml` per manuellem `workflow_dispatch`. Die bloße Aufnahme in ein Draft-PR, dessen Merge oder ein gewöhnlicher `push`, `pull_request` oder Issue-Event kann **keine Buffer-Mutation auslösen**. Jeder künftige Live-Start benötigt ausdrücklich eine **zweite, separate Entscheidung von Josef** und den exakten Workflow-Bestätigungswert `BILD_DATIERTER_DRAFT_EINMALTEST_NUR_BUFFER`.

**Bei einem Fehler** zeigt der bereits eingeführte sichere Buffer-Diagnosepfad ausschließlich den Typ und eine statische Kategorie wie `media_access`, nicht den rohen Buffer-Text. Eine Kategorie ist ein Diagnosehinweis, **keine unabhängige Ursachenattestierung**.

### Abnahme und Folgen

Nach einem ersten Live-PASS würde **nur** gelten: LinkedIn kann den konkreten Bildbeitrag mit Datum als `draft` anlegen und zurückliefern. **Nicht** bestätigt wären damit Facebook/Instagram, eine laufende automatische Kampagne, der isolierte native ChatGPT-Generator, reale Personenrechte oder Josefs Veröffentlichungsfreigabe. Die neue Testdatei bleibt ausdrücklich ein interner Draft bis Josef ggf. gesondert die Entfernung oder einen anderen Umgang genehmigt.

**Vor dem Merge dieses vorbereitenden PR**: Alle offline CI-Prüfungen, Testbestätigung der Einmaligkeit und getrennte Merge-Freigabe. **Vor dem späteren manuellen Live-Test**: vorhandene Buffer-Posts erneut **lesend** prüfen und ausdrücklich den separaten Teststart freigeben. Kein neuer Workflow wird ohne Freigabe auf `main` geschaltet.
