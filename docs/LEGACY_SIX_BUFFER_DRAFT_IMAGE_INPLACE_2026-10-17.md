# Sichere Aktualisierung der sechs bestehenden Buffer-Draft-Bilder – 17.10.2026

**Ergebnis der Vorstufe:** Der von ChatGPT über GitHub-Owner-Kommentar selbst gestartete [Bildlauf #39004850866](https://github.com/derJosef/social-assets/actions/runs/39004850866) ist `success`. Auf dem isolierten Branch `automation/legacy-artwork-repair-20261016` liegt der geprüfte unveränderliche Commit `ac03f948b5ed24dd49c3363dfdef7c82de01810b` mit genau zwei 1080×1350 Original-Logo-Bildern.

### Exakte Bildquellen (nur Version im unveränderlichen Commit)

- **Wer liest bei deinem KI-Chat mit?**: `media/images/2026-10-16-legacy-wer-liest-mit-4x5-branded.png`; Datei-SHA-256 `27229315d6fd2135b1c0cdc4be20eb94023e25818c7c7fe34c93fe9b715ada55`. Ausschließlich die bestehenden Buffer-Post-IDs LinkedIn `6ac8d5a926e224ee545ee6b5`, Facebook `6ac8d5ab26e224ee545ee761`, Instagram `6ac8d5ae26e224ee545ee809`.
- **Ein Agent. Drei Tests**: `media/images/2026-10-16-legacy-ein-agent-drei-tests-4x5-branded.png`; Datei-SHA-256 `adf8f0dff10489bc482d1f11aed8c55a8f3a37c1395c57b376d39517a2ddc73a`. Ausschließlich bestehende LinkedIn `6ac8961e7d9f9f33012bc9cd`, Facebook `6ac89617f07e682de6a98b36`, Instagram `6ac8961b7d9f9f33012bc803`.

### Rechtlicher/API-Vertrag und Änderungsgrenzen

Offizielles [Buffer EditPostInput](https://developers.buffer.com/types/EditPostInput.html): `assets` ersetzt vorhandene Medien, `saveToDraft:true` belässt den Post als Draft; Auslassen von `mode`, `dueAt` und `schedulingType` erhält alle Terminierungsattribute. Wichtig: Die Buffer-API validiert beim Editieren den **ganzen** Post. Deshalb wird der **aktuell** gespeicherte Text und die lesbaren aktuellen Metadaten/Tags für jede der sechs IDs direkt aus Buffer übernommen, niemals ein veralteter GitHub-Text.

Der separate Datei-SHA-Vergleich und die PNG-1080×1350-Prüfung erfolgen **vor** jeder Buffer-API-Mutation. Vor dem Schreiben müssen **alle sechs** Posts dem ursprünglich vereinbarten Kanal entsprechen und `status=draft` und `dueAt=null` haben. Andere Einzelposts oder manuell geänderte Status werden geschlossen blockiert. Die Metadaten werden für eine eindeutige Einzelfeed-Post-Version (keine Geolocation, keine Linkattachment-Payload) originalgetreu übernommen; unbekannte Metadaten blockieren statt überschrieben zu werden. `shareNow` wird nie erlaubt.

Jeder neue Lauf wird **einmalig gesperrt**: Ein dauerhaft gespeicherter Gesamtbeleg auf `automation-receipts` wird **vor** der ersten Mutation angelegt. Vor **jedem** individuellen `editPost` reserviert ein weiterer unveränderlicher Beleg die einzelne Post-ID. Ein Fehlresultat oder unklarer API-Zustand bleibt gesperrt, keine Auto-Retries, kein Rollback per geratenen Daten. Nach einem bestätigten Update erfolgt die **eigene neue Buffer-GET-Rückfrage**, die Originaltext, Post-ID, Kanal, Status `draft`, `dueAt=null`, Bildquelle, MIME `image/png`, Tags und Scheduling-Attribute prüfen muss. Nur dann bekommt die einzelne ID einen positiven Beleg. Teiländerungen müssen ggf. manuell rekonstruiert werden; nicht erneut blind ausführen.

### Eigenständig freizugebender aktiver GitHub-Lauf

`.github/workflows/legacy-six-buffer-inplace-image-update.yml` hat **nur** `issue_comment.created` mit eigentümergeprüftem Event unter **Issue #19**, `github.actor=derJosef`, `refs/heads/main`, `run_attempt=1`, Nachricht genau `LEGACY_SIX_DRAFTS_REPLACE_IMAGE_ONLY_ONCE_20261017`. Der Python-Prozess überprüft diesen Event-Inhalt selbst nochmals, sogar wenn die YAML-Gates defekt wären. Kein Push-, PR- oder Zeittrigger. Im Moment ist dieser Workflow ausschließlich Teil eines **Draft-PRs**, der **nicht** automatisch zur Buffer-Mutation berechtigt.

**Vor Live-Start:** Erst Josef um expliziten Merge und **eigene Edit-Freigabe für exakt sechs bestehende Buffer-Draft-Post-IDs** bitten. Erst nach beiden Freigaben `main` und CI erneut unabhängig lesen und genau **einen** Owner-Kommentar senden. Der Output ist **keine Veröffentlichung** und keine Terminierung. Es ist weiterhin nur ein Redaktions-Draft-Repair. Die drei separaten „Kundenmail ist kein Befehl“-Drafts, die drei bereits `scheduled` neuen Kampagnenposts und alle anderen Buffer-Posts bleiben unangetastet.

### Einschränkung

Die Offline-Suite kann die vollständige aktuelle Buffer-API nicht simulieren. Trotz formal dokumentiertem API-Vertrag können Live-Validierung und Konto-spezifische Metadaten einen einzelnen Edit ablehnen. In diesem Fall **keine Wiederholung**, sondern manuelle Abklärung der zugehörigen GitHub-Receipts und der Live-Posts. Ein erfolgreicher Bildtest auf GitHub allein reicht nicht als Nachweis eines in Buffer sichtbaren Bildes; bei 6/6 technisch positiven Buffer-GET-Prüfungen soll Josef abschließend die UI-Vorschau kontrollieren.
