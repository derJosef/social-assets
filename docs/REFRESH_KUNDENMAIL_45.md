# Ersatzlauf für die bestehenden Buffer-Entwürfe – nur neue Bilder

**Aktueller Status (10.10.2026):** **Einmaliger Buffer-Bildaustausch erfolgreich abgeschlossen:** drei neue Drafts mit unveränderten Texten erstellt, drei alte Drafts nach Live-Preflight exakt gelöscht, Audit bestätigt, drei neue Drafts nach Löschung erneut geprüft (`draft`, `dueAt:null`). Der PR enthält weiterhin nur die noch nicht gemergte Bildpipeline. Keine Terminierung oder Veröffentlichung. Die folgenden früheren Arbeitsschritte dokumentieren die damalige Vorbereitung.

## Unveränderliche redaktionelle Grundlage

Kampagne: \`2026-10-10-kundenmail-kein-befehl-005\`.

Bestehende drei plattformspezifische Texte sind **wortwörtlich zu übernehmen**, einschließlich Quellen und Hashtags. Die maßgeblichen unveränderten Dateien auf \`main\` sind:

- \`ready-for-buffer/auto-2026-10-10-kundenmail-kein-befehl-005-linkedin.json\` (GitHub Blob \`eeadd4bd149253ac81ed4d277c8dca76bc09408d\`); historischer Buffer-Post \`6ac9e964c4de2d2b121be215\`
- \`ready-for-buffer/auto-2026-10-10-kundenmail-kein-befehl-005-facebook.json\` (Blob \`2797c317402fb9cebb86d3c3e2f749dac8c13442\`); historischer Buffer-Post \`6ac9e967b07d37ac9764aac6\`
- \`ready-for-buffer/auto-2026-10-10-kundenmail-kein-befehl-005-instagram.json\` (Blob \`986ed4f06afe202cbc885b6984df24e39cdd876f\`); historischer Buffer-Post \`6ac9e96ac4de2d2b121be2e2\`

**Niemals** die früheren Dateien oder ihre Delivery-Receipts überschreiben. Ersatz benötigt neue Kampagnen-ID und neue Dateien. Bei einem späteren Austausch nur \`media\` und bei Bedarf den korrekten \`alt_text\` ändern; \`text\` exakt auf Identität prüfen. Nicht versehentlich beim erneuten Orchestrator-Start die Texte redaktionell umformulieren.

## Bildpipeline – abgesicherte erste Stufe

Das neue Hilfsskript \`scripts/social_portfolio_scene.py\` nimmt ein vorab vollständig geprüftes und im Repository vorhandenes **4:5-Rohmotiv** (mindestens 1080×1350) mit SHA256-Nachweis entgegen. Es erzeugt eine neue 1080×1350-Komposition mit separat in Inter gesetzter Überschrift oben links, ergänzt das **unveränderte Original-Pauderer-Logo** über das bestehende \`scripts/logo_composite.py\` unten rechts und führt \`verify\` aus. Es löscht, überschreibt und veröffentlicht nichts.

**Wichtig:** Die automatischen Checks können nur Pixelmaße, SHA, Eingabeschema und geometrische Logo-Integrität zuverlässig prüfen. Die visuelle Prüfung auf erfundene Logos/Schrift, Personen/Roboter, technische Falschdetails und Themenpassung ist weiterhin **manuell**; die \`visual_review\`-Wahrheitswerte einer Prüfdatei sind eine dokumentierte Behauptung, kein unabhängiger menschlicher Identitätsnachweis. Daher erst nach tatsächlich abgeschlossener fachlicher Sichtung in eine neue \`visual-reviews/*.json\` aufnehmen. Eine reine **Stilfreigabe** ist nicht gleichbedeutend mit einer Freigabe des Rohmotivs für die konkrete Kampagne.

Weder das hier ursprünglich in ChatGPT akzeptierte Rohmotiv \`holografischer_datenfluss_zur_cad_konstruktion.png\` noch die beiden neueren generierten Laptop-Arbeitsplatzbilder sind bislang in \`derJosef/social-assets\` als geprüfte Rohbilder verfügbar. Die zuletzt erzeugten Laptop-Bilder enthalten unerwünschte fremde App-/Markensymbole, automatische Beschriftungen, eines sogar einen Roboter; **nicht verwenden**. Das bereits bestätigte Rohmotiv ist nur eine *visuelle Stilreferenz* und zeigt eine CAD-Baugruppe, nicht exakt das Kundenmail-Sicherheitsproblem.

**Beispiel einer späteren manuell ausgefüllten Prüfdatei** (nicht aus diesem Muster automatisch ausführen):

\`\`\`json
{
  "format_version": 1,
  "brand": "ai-agent-builder",
  "layout": "logo_only",
  "source": "media/source-images/2026-10-10-kundenmail-sicherheitsfreigabe-v2.png",
  "source_sha256": "<SHA256 des wirklich geprüften Rohmotivs>",
  "heading": null,
  "visual_review": {
    "no_people": true,
    "no_robot": true,
    "no_foreign_logo": true,
    "no_generated_text": true,
    "plausible_details": true,
    "matches_topic": true,
    "heading_and_logo_space": true
  },
  "review_evidence": "<tatsächlicher dokumentierter Review, niemals erfunden>"
}
\`\`\`

Erst **danach** ausführbar (im Asset-Repo):

\`\`\`bash
python3 scripts/social_portfolio_scene.py \
  --spec visual-reviews/2026-10-10-kundenmail-sicherheitsfreigabe-v2.json \
  --base media/source-images/2026-10-10-kundenmail-sicherheitsfreigabe-v2-logo-only-base.png \
  --final media/images/2026-10-10-kundenmail-sicherheitsfreigabe-v2-branded.png \
  --font /tmp/Inter.ttf \
  --logo media/brand/logo-pauderer-original.png
\`\`\`

## Sichere Austauschreihenfolge

1. Rohmotiv **zum Thema Kundenmail / externe Anweisungen / Freigabe** erzeugen oder auswählen und auf Fremdzeichen, Personen, Roboter und sachliche Darstellung prüfen. Motiv source/version getrennt auf GitHub verfügbar machen; keine externen oder kostenpflichtigen Dienste ohne entsprechende Erlaubnis einsetzen.
2. Markenbild erstellen, das Original-Logo im exakten 4:5-Export prüfen; quellgeprüften Alternativtext formulieren.
3. Drei neue, ausschließlich als \`draft\` und \`dueAt=null\` übertragene Buffer-Ersatzentwürfe mit **unveränderten Texten** erstellen. Alle drei über die Buffer-API zurückprüfen. Keine gleichen Dateinamen wie alte Dateien oder Receipts verwenden.
4. Vor Löschung die drei alten Post-IDs **live** auf \`status=draft\`, \`dueAt=null\`, Kanal und ursprünglichen Text prüfen. Nur nach genauem Identitätsabgleich und vorhandenen Ersatzentwürfen die drei alten Beiträge mittels neuem eng eingegrenztem \`deletePost\`-Einmalworkflow entfernen. Nach jeder Löschung Buffer-Antwort und Audit-Commit kontrollieren. Das historische Sechser-Tests-Skript ist hierfür **nicht** verwendbar.
5. Alte und neue IDs sowie Text-Hash, Medien-URL und Audit in einem neuen datierten Report dokumentieren. Buffer-Link zum Review bereitstellen. **Keine automatische Terminierung oder Veröffentlichung.**

**Referenz für gezielte Löschaktion:** [historischer Actions-Lauf 37792336656](https://github.com/derJosef/social-assets/actions/runs/37792336656); Audit \`cleanup-audit/2026-10-08-buffer-test-drafts.json\` (sechs vorher bestätigte Tests). Sicherheitslücke M4 ist ungeklärt und wird durch diesen Bild-Refresh nicht bearbeitet.

## Motiv ohne Bildtext, Original-Logo bleibt – jetzt PersonalOS-konform

**Josefs Entscheidung, 10.10.2026:** hochwertige AI-Agent-Builder-Einzelbildposts dürfen ohne zusätzliche Beschriftung, **aber mit dem unveränderten Pauderer-Original-Logo** als 4:5-Bild gestaltet werden. Der ausführliche Plattformbeitrag bleibt getrennt. Für Karussell-Inhaltsseiten ist die Ausnahme nicht pauschal gültig.

**Kanonische Quelle:** `derJosef/personalos` Commit `1c7b02d2ede03003da61fb70ae3ab71996b63a86`, `skills/josefs-marke/references/social-media/DESIGN.md`, `skills/josefs-marke/scripts/logo_composite.py` und `skills/josefs-marke/scripts/test_logo_composite.py`. Deren zwei Python-Dateien wurden **bytegleich** nach `social-assets/scripts/` kopiert. Diese Kopie ist nur zur technischen Nutzung im Asset-Repository; bei neuen PersonalOS-Versionen kontrolliert synchronisieren.

`scripts/social_portfolio_scene.py` kennt `layout: "logo_only"` mit `heading: null` und erzeugt exakt **1080 × 1350** ohne Headline, Titel-Veil oder Dummy-Textbox. Es ruft dann die kanonische Routine auf:

```bash
python scripts/logo_composite.py compose basis.png fertig.png \
  --original media/brand/logo-pauderer-original.png \
  --logo-corner bottom-right --frame on --margin-ratio 0.05 --stroke-ratio 0.03
python scripts/logo_composite.py verify fertig.png basis.png \
  --original media/brand/logo-pauderer-original.png
```

Der separate Versuch `scripts/logo_only_gate.py` wurde **ersatzlos gelöscht**, ebenso dessen Tests. Keine zweite unabhängige Auslegung der Original-Logo-Prüfung. Der kanonische Prüfer kontrolliert die Platzierung und Pixelschutzregeln im Logo-only-Modus vollständig. Er kennzeichnet jedoch die **Text- und Fremdlogo-Freiheit des Rohmotivs ausdrücklich als `MANUAL`**. Ein bestandener technischer Test ist daher **keine** unabhängige visuelle Qualitätsabnahme. `visual_review` muss nach echter, dokumentierter Sichtprüfung wahrheitsgemäß eingetragen werden.

Beispiel einer **noch nicht ausgefüllten** Prüfdatei unter `visual-reviews/`:

```json
{
  "format_version": 1,
  "brand": "ai-agent-builder",
  "layout": "logo_only",
  "source": "media/source-images/<thematisch-und-visuell-geprueftes-motiv>.png",
  "source_sha256": "<SHA256 des unveraenderten Rohmotivs>",
  "heading": null,
  "visual_review": {
    "no_people": true,
    "no_robot": true,
    "no_foreign_logo": true,
    "no_generated_text": true,
    "plausible_details": true,
    "matches_topic": true,
    "heading_and_logo_space": true
  },
  "review_evidence": "<konkrete schriftliche Sichtpruefung>"
}
```

Die anderen `headline`-Layouts benutzen weiterhin `--heading-corner` und die sichtbare Inter-Headline mit `--heading-box`. Beides zugleich ist bei der neuen kanonischen Routine verboten.

**Tests und Grenze:** [Draft-PR #3](https://github.com/derJosef/social-assets/pull/3) führt die vollständige übernommene PersonalOS-Testsuite und die zusätzlichen Scene-E2E-Tests in einem isolierten GitHub-Workflow **ohne Buffer-Zugangsdaten** aus. Kein Merge, keine Veröffentlichung und kein Buffer-Austausch vor bestandener QA sowie dem konkreten, thematisch geprüften Rohmotiv.

**Nicht als erledigt ausgeben:** Bisher ist kein für das konkrete Kundenmail-Thema final freigegebenes 4:5-Motiv binär ins Asset-Repository übertragen, kein Endbild mit dieser echten Quelle erstellt, keine neuen Buffer-Drafts geschaffen und kein alter Draft gelöscht. Der sichere Cutover ist weiterhin die vorstehende Austauschreihenfolge. Manche im Chat erzeugten Motivversionen enthalten unerwünschte App-Symbole oder Pseudo-Schrift und sind ungeeignet; die frühere Datenfluss-/CAD-Stilprobe ist allein wegen der Stilfreigabe noch keine fachliche Bildfreigabe für die Kundenmail-Kampagne.


## Abschlussnachweis – 10.10.2026

**Ergebnis des einmaligen Vorgangs: DONE.** Alle drei ursprünglichen Plattformtexte (einschließlich Quellen, CTA und Hashtags) wurden wortwörtlich übernommen. Bild-URL und Alternativtext wurden aktualisiert, keine anderen Post-Eigenschaften. Ein einziges öffentliches 1080 × 1350 Original-Logo-Bild wird für die drei Kanäle verwendet.

- **Bild:** [2026-10-10-kundenmail-pruefpunkt-portfolio-v2-logo-only.png](../media/images/2026-10-10-kundenmail-pruefpunkt-portfolio-v2-logo-only.png), SHA256 `9103a36e4239a433244acaddab7d3f1af6308e5dac5e4238656ed60b70a95230`. Rohmotiv-Übernahme SHA256 `626966b2022754ff953219d298fb2af226d4c6223920d118a9e96871ce208555`; [Art-Receipt](../artwork-receipts/2026-10-10-kundenmail-pruefpunkt-portfolio-v2.json). Rohmotiv kam für den einmaligen GitHub-Import über eine temporäre Adobe-Dateiverbindung. GitHub-Image-Import [Run 38082634118](https://github.com/derJosef/social-assets/actions/runs/38082634118), Logo-Render [Run 38082774496](https://github.com/derJosef/social-assets/actions/runs/38082774496), beide erfolgreich. Die Quelle ist visuell geprüft; eine illustrative Prozessdarstellung, kein echter Security-Beweis.
- **Übernahme ins stabile `main`:** [Commit e00340b](https://github.com/derJosef/social-assets/commit/e00340b40407becdcbdd35c3d984e778ea9cfb4c), exakt fünf Assets/QA-Dateien, bytegleiche Prüfsummen.
- **Textidentität und Erreichbarkeit:** [Offline-Prüfung 38083143991](https://github.com/derJosef/social-assets/actions/runs/38083143991): 3× exakte Originaltexte, öffentliches Bild `HTTP 200 / image/png`, kanonisches Original-Logo-Verify, Buffer-Draft-Dry-Run PASS.
- **Buffer-Neuanlage:** [Run 38083224273](https://github.com/derJosef/social-assets/actions/runs/38083224273), `success`, Commmit `d61e749ce193fbf2814f84f6d4fedc8618e4e425`. Drei neue Buffer-Draft-IDs und je `draft_created`-Empfangsbeleg.
- **Vorabstatus & Originaltext-Abgleich live:** [Statusdiagnose 38083381954](https://github.com/derJosef/social-assets/actions/runs/38083381954): sechs Posts vor Löschung `draft`, `dueAt=None`, gleiche Kanal-ID je Paar. [Read-only-Abgleich 38083458598](https://github.com/derJosef/social-assets/actions/runs/38083458598): alle sechs Posttexte **exakt gleich** mit den GitHub-Ausgangstexten, gleiche Buffer-Kanäle, keine Termine.
- **Gezielte Löschung nur der drei ALTEN IDs:** [Run 38083623721](https://github.com/derJosef/social-assets/actions/runs/38083623721), `success`, drei `DELETE_CONFIRMED`, Audit unter [cleanup-audit/2026-10-10-kundenmail-v2-image-replacement.json](../cleanup-audit/2026-10-10-kundenmail-v2-image-replacement.json): `three_superseded_drafts_deleted`, `confirmed_deleted: 3`. Vor jeder Löschung nochmals live alter und neuer Post geprüft. Die alten Dateien im GitHub-Repository bleiben als historische Quellen, **nur** die alten Buffer-Posts wurden gelöscht.
- **Abschlussstatus der drei NEUEN IDs:** [Live-Diagnose 38083691687](https://github.com/derJosef/social-assets/actions/runs/38083691687): alle drei weiterhin `draft`, `dueAt=None`. **Keine Veröffentlichung.**

| Kanal | Gelöschter Alt-Post | Neuer, unterm. Buffer-Draft |
| --- | --- | --- |
| LinkedIn | `6ac9e964c4de2d2b121be215` | `6aca9d9fd9cab260a7d7b34c` |
| Facebook | `6ac9e967b07d37ac9764aac6` | `6aca9d99bba9419ccb148eba` |
| Instagram | `6ac9e96ac4de2d2b121be2e2` | `6aca9d9cf91f772d45a67ff7` |

**Aufgeräumt:** Einmalige Media-Import-/Render- und Alt-Entwurfs-Löschworkflow-Dateien und deren einmaliges Script wurden nach Abschluss aus den aktiven Repository-Branches entfernt; im Git-Verlauf bleiben sie vollständig nachvollziehbar. Dauerhafte Original-Assets, Empfangsbelege, Prüffiles, Audit und generische PersonalOS-konforme 4:5-Szeneroutine im offenen Draft-PR bleiben erhalten.

**Offen getrennt vom Kampagnenabschluss:** Draft-[PR #3](https://github.com/derJosef/social-assets/pull/3) mit der generischen, kanonischen Logo-only-Bildpipeline ist **noch nicht gemergt**. Ein erfolgreicher einmaliger Buffer-Austausch ist keine Freigabe für allgemeine produktive Workflow-Umbauten oder die Veröffentlichung dieser Drafts.
