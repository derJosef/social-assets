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

## Live-E2E vom 15.10.2026: Bild erfolgreich, Buffer fail-closed

Für die neue **eindeutig als TESTENTWURF – NICHT VERÖFFENTLICHEN** gekennzeichnete Kampagne wurde owner-authored [Issue #29](https://github.com/derJosef/social-assets/issues/29) erstellt. Die vorhandene, nicht geänderte Hauptworkflow-Datei startete automatisch [Run #38748011264](https://github.com/derJosef/social-assets/actions/runs/38748011264).

### Erfolgreich und durch GitHub Actions geprüft

- Geschütztes main und Receipt-Ledger, einmalige Kampagnen-ID, redaktionelle Zwei-Quellen-Regel und sechs Postingstudien: **PASS**.
- **Echter Adobe-Download** des normierten Bildes: exaktes PNG 1080×1350, erwarteter Ausgabe-SHA \`ddf69cce1a4a781321dad84809e7f4e7896c6ed40f115c12b8548cdf7d2c8d5c\`; Quell-/Sichtprüfspezifikation einschließlich Hologrammklassifikation: **PASS**.
- Tatsächliches deterministisches Original-Logo-Compositing und Pixel-Verifikation: **PASS**, Original-Logo-SHA \`15dc410d1a05b96c13466ddf3052ba9cc783cdd7252b74f4fb5c3f886510dea0\`, Bildgröße 1080×1350, korrektes Logo unten rechts, keine geänderten Pixel außerhalb der Logobox.
- Finales Marken-PNG SHA \`31da8e5364587b58d011c83f17ae8caab437c9af490995808db742de95feb496\`.
- Unveränderlicher separater GitHub-Bild-Commit \`b535972ce7f788b7150edfede56093f0371c349a\` sowie Kampagnen-Branch \`automation/campaign/2026-10-15-drei-kontrollpunkte-e2e\`: **erfolgreich**. Kein Commit an main durch den Live-Lauf.
- Alle drei vorgesehenen Plattformdateien mit terminlichen Vorschlägen auf dem Kampagnen-Branch: LinkedIn 11.11.2026 16:00 MEZ, Facebook 05.11.2026 09:00 MEZ, Instagram 04.11.2026 18:00 MEZ. **Nur vorgeschlagene, nicht in Buffer bestätigte Draft-Termine**.

### Buffer-Blocker – keine automatische Wiederholung

Beim **ersten** Versuch, den LinkedIn-Entwurf in Buffer anzulegen, antwortete die GraphQL-Mutation mit \`InvalidInputError\`. Damit wurde Run #38748011264 als \`failure\` beendet; unabhängige Buffer-Draft-Verifikation \`skipped\`. In GitHub bleibt ein unveränderter Reservierungs-/Sicherheitsbeleg:
\`automation-receipts/delivery-receipts/f0361bec557d3fb7e6f4d75b.json\` mit \`state: pending_manual_reconciliation_on_failure\`, \`due_at_utc: 2026-11-11T15:00:00Z\`. **Kein zweiter Versuch**, keine Facebook-/Instagram-Mutation. Die konkrete fachliche Ursache von \`InvalidInputError\` ist aus den sicher redigierten Runner-Logs **nicht ersichtlich**; keine Spekulation, dass fehlende Kanal-ID oder Termin die Ursache sei (die LinkedIn-ID wurde bereits aufgelöst).

Ein **bestehender, ausdrücklich nur lesender Buffer-Audit** wurde anschließend durch den dafür vorgesehenen Owner-Kommentar auf [Issue #19](https://github.com/derJosef/social-assets/issues/19) ausgelöst: [Run #38749047157](https://github.com/derJosef/social-assets/actions/runs/38749047157), \`success\`. Der Audit erfasste **26 vorhandene Buffer-Beiträge**, **keinen** mit dem Textpräfix \`TESTENTWURF – NICHT VERÖFFENTLICHEN\` oder diesem E2E-Kampagnenthema. Ein zusätzlicher unverändert vorhandener Recovery-Workflow wurde wegen seiner streng auf einen anderen alten Issue-Kommentar beschränkten Bedingungen korrekt \`skipped\`. **Befund:** kein neuer Testdraft in der aktuellen Buffer-Bestandsaufnahme; der Pending-Beleg bleibt dennoch unangetastet. Keine Queue, kein Publish.

Der ordnungsgemäße Workflow-Abschlussbericht liegt unter
\`automation-receipts/orchestration/reports/2026-10-15-drei-kontrollpunkte-e2e-run-38748011264.json\`
und markiert den Vorgang als **BLOCKED**. **Nicht** \`buffer_drafts_verified\` behaupten oder ein Test-Posting freigeben.

### Offene Entscheidung

1. Buffer \`InvalidInputError\` mit einem dedizierten **lesenden** Diagnoseschritt oder Buffer-Support abklären; erst dann neue eindeutige Kampagne und separate Freigabe. Den reservierten, fehlgeschlagenen E2E-Auftrag niemals mit identischer Post-ID erneut senden.
2. Die neue Offline-Handoff-Stufe in Draft-PR #28 ist 5/5 CI-grün, aber nicht gemergt. Der reale Live-Test verwendete den kompatiblen **bestehenden main-Importer**, indem die PNG bereits **vor** Adobe normiert wurde. Keine Behauptung, PR #28 sei live produktiv aktiviert.
3. Native ImageGen-Kontextisolation weiter nicht nachgewiesen; Buffer-Entwürfe werden ausschließlich nach gültigen, unabhängigen Rücklesebelegen zur Freigabe gezeigt.

**Veröffentlicht: 0. Neue bestätigte Buffer-Entwürfe: 0. Adobe→GitHub→Original-Logo: PASS.**
