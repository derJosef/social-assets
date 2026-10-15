# Kontrolle des realen Adobe-Hand-offs (15.10.2026)

**Owner:** \`social-assets\`. Originalbild, bestätigte Farben, Kennzeichnung und Logo-Quelle stehen weiterhin in PersonalOS. Dieser Test ist ein Techniknachweis, keine autonome Bildgenerierung und keine Freigabe der Buffer-Publikation.

## Reale Daten des bisherigen freigegebenen Rohbilds

| Stufe | Beleg |
| --- | --- |
| ChatGPT generiertes Roh-PNG vom 14.10. | 1122 × 1402 Pixel, 2.024.527 Bytes, SHA256 \`22df4bff1d1043929272e93f2c1ace3c7d273efa7c3617db8ee417747033982d\` |
| Normierung vor Adobe | Pillow LANCZOS **ohne Zuschneiden**, 1080 × 1350 Pixel, 1.810.753 Bytes, SHA256 \`ddf69cce1a4a781321dad84809e7f4e7896c6ed40f115c12b8548cdf7d2c8d5c\` |
| Gesicherte Adobe-Datei | 15.10.2026 erfolgreich über den **bereits verbundenen Adobe-Dateidienst** als \`social_rawbild_e2e_1080x1350.png\` hochgeladen |
| Adobe-Asset-ID | \`urn:aaid:sc:EU:bd3681fc-9a88-4501-8ff9-ac7ec09b4959\` |
| Von Adobe zurückgegebener Kurzlink | \`https://at.adobe.com/5pnv27RxE28EVU3C\` |
| Adobe-Link in Bildimport-Schema | Form \`https://at.adobe.com/<id>\` entspricht der bestehenden hostgeprüften Import-URL |
| Exakter Byte-Rücklese-Nachweis aus Adobe | **Noch offen:** Ein GitHub-Runner muss die Downloadbytes selbst gegen den **Ausgabe**-SHA prüfen. Adobe-Asset-Metadaten oder ein Kurzlink beweisen für sich keine Byte-Gleichheit. |
| Vollständige Medien-/Buffer-Prüfung | **Noch offen:** GitHub-Orchestrator muss Logo-Compositing, SHA-/Pixel-QA, Entwurfsablage und Buffer-\`draft\`-/\`dueAt\`-Readback eigenständig nachweisen. |
| Generator-Kontextisolation | **Nicht nachgewiesen:** Ein zuvor bereinigter Prompt allein beweist keine abgeschottete ImageGen-Ausführung. |

### Zwei getrennte Stufen – ohne Eingriff in den bewährten Importer

1. **Vor Adobe:** \`scripts/normalize_chatgpt_raw_png.py --source native.png --output normalized.png --report normalize.json\`. Dadurch entstehen unabhängig überprüfbare *Original-* und *Ausgabe-*Prüfsummen. Das ist Bildformattechnik, keine Inhaltsfreigabe.
2. **Nach Adobe-Upload:** \`scripts/prepare_normalized_adobe_handoff.py --normalized normalized.png --receipt normalize.json --visual-review echte-sichtpruefung.json --adobe-url https://at.adobe.com/5pnv27RxE28EVU3C --campaign 2026-10-15-raw-image-handoff-probe --output handoff.json\`.

Die zweite Stufe prüft den Post-Normierungs-SHA und die originale unveränderte Import-Prüfstruktur (\`scripts/chatgpt_image_import.py:inspect_brief\`). Die \`handoff.json\` enthält ausschließlich das importfähige \`chatgpt_image\`-Objekt. Es muss in einen **vollständigen, owner-authored Brief mit echten Quellen, Kanaltexten und sechs Hüten** übernommen werden, nicht in einen automatischen Buffer-Publish-Aufruf. Die Prüfung enthält keine echte Adobe-Download- oder Buffer-Aktion.

### Offene praktische Grenzen

- Die beiden Python-Stufen laufen aktuell **vor dem Adobe-Transfer**, etwa in einem ChatGPT-Datei-Arbeitsbereich. Der GitHub-Runner lädt anschließend schon die normierte Datei von Adobe und prüft den übergebenen Ausgabe-Hash. Das **richtige** Integrationsniveau ist eine sicher geprüfte Dateihandoff-Schnittstelle, kein nachträgliches heimliches Verändern bereits SHA-gepinnter Adobe-Bytes.
- Der Bildimport darf niemals den alten nativen \`source_sha256\` zur Validierung der normierten PNG verwenden.
- Die visuelle Einordnung der blau leuchtenden Figur als eindeutiges Hologramm setzt \`figure_review\` (\`kind: stylized_hologram\`) voraus; sie benötigt weder neue Personeneinzelfreigabe noch \`Powered by AI\`. Menschenrechte-/Plattformprüfung für fotorealistische Menschen bleibt ein getrennter Prüfpfad.
- Änderungen nur als **isolierter Draft-PR**, keine stillschweigende Merge- oder Produktionsaktivierung. Der erfolgreiche Adobe-Upload selbst wurde im Chat in Auftrag gegeben; er erzeugte noch keinen Buffer-Eintrag.
- Zur echten E2E-Abnahme muss ein einmaliger eindeutig identifizierbarer Draft-only-Test durch die bestehende Workflow-/GitHub-Guard-Logik geführt werden. Auch bei offenem Draft sind Entwurfstext, Termin und Bild separat in Buffer nachzulesen; Veröffentlichung nur nach ausdrücklicher Freigabe.

**Rollback:** Bis zur expliziten Merge-/Live-Freigabe bleibt \`main\` mit dem nachweislich vorhandenen unveränderten Adobe-Kurzlink-\`chatgpt_image\`-Importer der Rückfallstand. Die neue Handoff-Stufe erweitert nur die Vorbereitung, nicht die Veröffentlichung.
