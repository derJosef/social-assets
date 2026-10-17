# 17.10.2026: frische Adobe-Links für bestehende Bild-Drafts

## Beleg und Problem

ChatGPT-eigener [Bildworkflow #38926616610](https://github.com/derJosef/social-assets/actions/runs/38926616610) startete tatsächlich über den freigegebenen Issue-Kommentar. Der enge Owner- und Sicherheits-Gate lief erfolgreich; der GitHub-Runner bekam beim Abruf des rund vier Stunden zuvor erzeugten Adobe-Kurzlinks **HTTP 403 Forbidden**, bei einem vorherigen Lauf eine von der freigegebenen Originaldatei abweichende SHA256. Kein finaler Bild-Commit, 0 Buffer-Mutationen. Der aktuelle read-only [Buffer-Bestandsaudit #39002314880](https://github.com/derJosef/social-assets/actions/runs/39002314880) vom 17.10. bestätigt die sechs ursprünglichen Post-IDs unverändert als `draft`, ohne `due_at`; API meldet je ein altes Medienobjekt, sichtbare Buffer-Bilder fehlen laut Josef.

Die zwei originalen, bereits von Josef freigegebenen ChatGPT-PNG-Quellen existieren weiterhin unverändert:
- `wer_liest_mit_raw_1080x1350.png`, 1.839.099 Bytes, SHA256 `74a7debcc3d5598fa328fc9a5c0376c9cd2797ed2d722ed7a9c4e6ec5c3abfd7`.
- `ein_agent_drei_tests_raw_1080x1350.png`, 1.729.109 Bytes, SHA256 `95f82aa8b82c749a89d73e5f1ba34bb4a2521c31f9043bf80dffaee328406c7a`.

Adobe Creative Cloud speichert die Dateien unter `urn:aaid:sc:EU:ebaa449f-8851-47a9-89f1-311ff59d5373` bzw. `urn:aaid:sc:EU:e1c54cc5-41f1-4848-81f6-10e6668bfe7b`; frische temporäre Shortlinks sind über `asset_get_presigned_urls` erhältlich. Der erfolgreiche Adobe-Vorschauzugriff ist **kein Beweis**, dass GitHub die vollen 1080×1350-Original-PNG-Bytes anonym abrufen kann. Darauf darf nur eine exakte Byte- und 4:5-Rückprüfung entscheiden.

## Neuer eng begrenzter Laufzeit-Transfer

1. Ab sofort kann ein authentifizierter **Eigentümer** auf **genau GitHub-Issue #19** den allein für die zwei freigegebenen Rohbilder vorgesehenen Job über den Kommentar mit **exakt drei Zeilen** starten:

```text
LEGACY_IMAGE_FRESH_LINKS_ONCE_20261017
wer_liest_mit=https://at.adobe.com/<FRISCHER_SHORTLINK_1>
ein_agent_drei_tests=https://at.adobe.com/<FRISCHER_SHORTLINK_2>
```

2. GitHub-YAML prüft weiterhin Actor/Issue-Autor/Kommentar-Autor `derJosef`, `refs/heads/main`, `run_attempt==1`, nur `issue_comment.created`, kein PR-Kommentar und exakten Bestätigungspräfix. Python liest den aktuellen GitHub-Ereignisinhalt über `GITHUB_EVENT_PATH`, prüft vollständige **dreizeilige Struktur**, ausschließlich die zwei festen Schlüssel und zwei **verschiedene Adobe-HTTPS-Shortlinks**. Fremde URLs, Extra-Befehle, andere Autoren oder dritte/zusätzliche Zeilen scheitern geschlossen. In Text/Logs keine HTTP-Body-/URL-Inhalte.
3. **Erst unmittelbar vor Kommentar-Trigger** werden die zwei links via Adobe-Connector neu bezogen. Damit wird die veraltete Hardcode-Quelle nicht erneut verwendet. Gelingt der anonyme Vollbild-Transfer dennoch nicht (403 oder andere SHA), bricht der Job geschlossen ab und **niemand darf versuchen, statt des PNG eine verkleinerte JPEG-Vorschau zu akzeptieren**.
4. Unabhängig von den wechselnden URLs bleiben die SHA256-Werte, Pixelmaße `1080×1350`, technische Bild-QA, unverändertes Original-Logo und Anti-Wiederholungs-Guard fest verankert. Bei Erfolg exakt zwei Markenbilder auf dem isolierten, erstmals anzulegenden Branch `automation/legacy-artwork-repair-20261016`, keine Änderung auf `main`.

**Scope:** Immer noch reiner Original-Logo-Bildworkflow; nicht mit dem separaten, noch nicht implementierten **in-place**-Reparaturweg der sechs Buffer-Entwürfe verwechseln. Kein `createPost`, `editPost`, `scheduled` oder `publish` durch den Bildjob. Das Owner-Gate bleibt unabhängig von der Linkgültigkeit. Nicht denselben fehlgeschlagenen GitHub-Job erneut laufen lassen.

**Privacy:** Adobe-Shortlinks im öffentlichen Issue-Kommentar können bis zu ihrem Ablauf auch durch andere gelesen werden. Deshalb nur die ohnehin für Social Media freigegebenen Rohmotive verwenden, niemals geheime Dokumente/Authentifizierungstokens. Das Token selbst wird nie als Geheimnis oder GitHub-Secret behandelt.

**Freigabe:** Dieser PR enthält nur einen verbesserten Transport-Trigger und Tests. Merge benötigt Josefs explizite Freigabe. Erst danach dürfen die URLs frisch bezogen und genau **ein** neuer Owner-Issue-Start ausgelöst werden.
