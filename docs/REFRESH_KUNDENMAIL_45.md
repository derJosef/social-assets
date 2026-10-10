# Ersatzlauf für die bestehenden Buffer-Entwürfe – nur neue Bilder

**Status:** Vorbereitung auf separatem PR-Branch; noch kein Ersatzlauf, keine Buffer-Mutation und keine Freigabe zur Veröffentlichung.

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
  "source": "media/source-images/2026-10-10-kundenmail-sicherheitsfreigabe-v2.png",
  "source_sha256": "<SHA256 des wirklich geprüften Rohmotivs>",
  "heading": "EINE KUNDENMAIL IST KEIN BEFEHL",
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
  --base media/source-images/2026-10-10-kundenmail-sicherheitsfreigabe-v2-with-heading.png \
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

## Alternative: Motiv ohne Bildtext, Original-Logo bleibt

**Josefs ausdrückliche Präzisierung am 10.10.2026:** Solche hochwertigen B2B-Bildmotive dürfen **ohne weitere Beschriftung**, aber **mit dem unveränderten originalen Pauderer-Logo** gestaltet werden. Der Plattform-Postingtext bleibt separat vollständig und unverändert. Das ist eine **zusätzliche** AI-Agent-Builder-Gestaltungsoption; erklärende Karussell-Inhaltsfolien dürfen weiter Text haben.

**Technischer Entwurf auf PR #3, noch nicht in Produktion freigegeben:**

- `scripts/social_portfolio_scene.py` kennt `layout: "logo_only"` mit `heading: null`. Dabei wird weder Headline noch Titel-Veil noch Dummy-Textbox gerendert. Das Rohmotiv muss ohnehin dem Thema entsprechen, genau 4:5 vorliegen und die dokumentierte Bildsichtprüfung auf Fremdmarken, generierte Pseudo-Schrift, technische Fehler, ungewollte Personen/Roboter bestehen.
- Das Original-Logo wird ausschließlich durch den bestehenden unveränderten `logo_composite.py compose` unten rechts platziert. `scripts/logo_only_gate.py` bildet einen **eigenen strengen Prüfungspfad** für den bewusst nicht vorhandenen Bildtext, ohne den kanonischen Kompositor umzuschreiben. Er verlangt das echte Original-Logo samt Prüfsumme, die korrekten 1080×1350, den weißen Außenrahmen, die Ecke unten rechts, echte PNG-Platzierungsmetadaten, Randabstände, unveränderte Pixel außerhalb der Logofläche und alle neun anwendbaren Prüfpunkte im kanonischen Validator. Die zehnte (unpassende) Überschriften-Prüfung wird **ausschließlich bei dem ausdrücklich deklarierten Profil** als „nicht anwendbar“ geführt. Sie wird **nicht** stillschweigend als erfolgreich ausgegeben. Veränderte/fehlende kanonische Prüfpunkte, unbekannte Skips und gefälschte Bildpixel führen zum Abbruch.
- Bestehende `headline`-Variante bleibt getrennt. Für sie müssen `heading` und Inter weiterhin vorhanden sein. Das neue Review-Schema verlangt ausdrücklich `layout` mit einem der beiden Werte. Beispiel für die textfreie Variante:

```json
{
  "format_version": 1,
  "brand": "ai-agent-builder",
  "layout": "logo_only",
  "source": "media/source-images/<wirklich-geprueftes-motiv>.png",
  "source_sha256": "<SHA256 des freigegebenen Originals>",
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
  "review_evidence": "<schriftliche und tatsächlich vorgenommene Bildsichtprüfung>"
}
```

**Noch offene Geltung und Freigabe:** `derJosef/personalos/skills/josefs-marke/references/social-media/DESIGN.md` und die übergeordnete, kanonische Logo-Prüfung müssen durch den autorisierten PersonalOS-Agenten die von Josef beschlossene Logo-only-Option anerkennen oder das vorgeschlagene QA-Profil ausdrücklich fachlich prüfen. Zum letzten geprüften GitHub-Stand `e73814f` war das **nicht synchronisiert**. Der bisherige Pixelprüfpfad im PR ist ein **Testentwurf**, kein Ersatz für eine verbindliche Markenfreigabe. Keine Zusammenführung oder Buffer-Übertragung vor Abgleich.

**Nicht als erledigt ausgeben:** Bisher ist kein für das konkrete Kundenmail-Thema final freigegebenes 4:5-Motiv binär ins Asset-Repository übertragen, kein Endbild mit dieser echten Quelle erstellt, keine neuen Buffer-Drafts geschaffen und kein alter Draft gelöscht. Der sichere Cutover ist weiterhin die vorstehende Austauschreihenfolge. Manche im Chat erzeugten Motivversionen enthalten unerwünschte App-Symbole oder Pseudo-Schrift und sind ungeeignet; die frühere Datenfluss-/CAD-Stilprobe ist allein wegen der Stilfreigabe noch keine fachliche Bildfreigabe für die Kundenmail-Kampagne.
