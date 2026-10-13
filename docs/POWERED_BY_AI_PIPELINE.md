# AI Agent Builder – Powered by AI als echte geprüfte Ebene

Stand: 11.10.2026. **PR-Entwicklungsversion; nicht mit einer Freigabe zur Produktion oder Veröffentlichung gleichsetzen.** Maßgeblich: `derJosef/personalos/skills/josefs-marke/SKILL.md`, `references/social-media/DESIGN.md` und die neueste Decision `2026-10-11-powered-by-ai-nur-bei-fotorealistischen-menschen.md`.

## Auslöser und harte Grenzen

Der exakte Schriftzug `Powered by AI` ist nur bei **fotorealistischen KI-generierten Menschen mit erkennbarem Gesicht** (auch Profil) und bei **realen fotografierten Menschen, deren Darstellung generativ KI-verändert wurde** (z. B. andere Kleidung) vorgeschrieben. Holografische, stilisierte oder gezeichnete Menschengestalten und unbearbeitete echte Fotos lösen diese markeninterne Regel **nicht** aus. Die bestehenden Rechte-/Personenfreigaben sind **zusätzlich** einzuholen; robotische Darstellungen bleiben nach PersonalOS gesperrt. Zusätzliche rechtliche oder plattformseitige KI-Offenlegung bleibt eine separate Prüfung.

- Logo-/Textfreies 4:5-Rohmotiv, mindestens 1080×1350 px, echtes manuelles Review, tatsächliche SHA.
- **Neu für jeden Personenfall:** Nur mit expliziter dokumentierter **Einzelfreigabe durch Josef**, einer positiv geprüften visuellen Review und wahrheitsgemäß ausgefüllter Klassifizierung.
- Position für den Hinweis durch Josef am 11.10. bestätigt: **unten links, Inter Medium 42 px, Textbeginn x=54 px, Außenrand unten=54 px**, helle Schrift `#F5F7FA` auf Navy `#07111F`. Mindestens **4,5:1**; ohne Overlap zum Original-Pauderer-Logo unten rechts. Die Textgröße und Randabstände gelten für **1080×1350-Posts** und nicht automatisch für Portfolios oder die Website.
- Rein deterministische Ebene in `scripts/ai_disclosure.py` **vor** `scripts/logo_composite.py compose`. Im endgültigen Bild ist kein vom Modell erzeugtes Logo und keine KI-erzeugte Schrift zulässig.
- `scripts/ai_disclosure.py` prüft die Textregion bitgenau gegen die bekannte Renderroutine, Farbe, Position und Größe, später eine zweite unabhängige Prüfung durch `scripts/autonomous_campaign_gate.py`; der unveränderte kanonische Logo-Compositor prüft Logo/SHA/Restpixel getrennt.
- Jede fälschlich abgegebene menschliche Freigabebestätigung kann ein **formaler Automat nicht unabhängig beweisen**. Daher dokumentiertes menschliches Review einschließlich Originalbild und Personeneinzelfreigabe beibehalten.

## Manuelle Review-Spezifikation

Für bereits freigegebene **personenfreie** Altmotive bleibt das siebenfeldige v1-Review-Schema kompatibel. Neue Personenmotive erhalten genau drei weitere boolesche Felder in `visual_review` und eine separate dokumentierte Freigabe-Notiz. Beispiel **nur als Platzhalter mit synthetischen Daten; keine echte Freigabe**:

```json
{
  "format_version": 1,
  "brand": "ai-agent-builder",
  "source": "media/source-images/YYYY-MM-DD-wirklich-geprueft.png",
  "source_sha256": "64_tatsaechlich_berechnete_hex_zeichen",
  "layout": "logo_only",
  "heading": null,
  "visual_review": {
    "no_people": false,
    "no_robot": true,
    "no_foreign_logo": true,
    "no_generated_text": true,
    "plausible_details": true,
    "matches_topic": true,
    "heading_and_logo_space": true,
    "photorealistic_ai_face": true,
    "ai_altered_real_person": false,
    "person_use_approved": true
  },
  "person_approval_evidence": "Link zur tatsächlichen, kampagnenbezogenen Freigabe durch Josef mit Datum",
  "review_evidence": "Tatsächliche Sichtprüfung des genauen unveränderten Bildes mit Person, Herkunft und Thema"
}
```

Das Beispiel ist **nicht lauffähig**, da der tatsächliche SHA-Wert, die reale Dateiberechtigung und die persönliche Freigabe absichtlich fehlen. Für ein reales neues Bild keine `true`-Werte oder Freigabeerklärungen erfinden.

**Fall „echtes Foto mit generativ geänderter Person“:** `photorealistic_ai_face: false`, `ai_altered_real_person: true`, `no_people: false`, `person_use_approved: true`; Hinweistext identisch.

**Fall „nur stilisierte digitale Figur“:** beide Auslöser `false` und für die Darstellung dennoch alle nach POS erforderlichen Personen-/Rechtefreigaben; **keine** Kennzeichnung automatisch. Im Zweifel das Bild nicht produktiv verwenden.

## Qualität und Wiederholbarkeit

Beim Bildaufbau wird nur bei einem der zwei KI-Auslöser das Caption-Overlay erzeugt. Die generierte Basis mit Schrift wird **vor** und nach dem Logo-Compositing geprüft. Die unabhängige Kampagnen-QA verlangt bei Kennzeichnung einen expliziten Bild-Receipt und reproduziert die Textpixel vor Anlage der Buffer-Drafts. Überlagerung durch die Logo-Box führt zu `BLOCK`.

Alle in PR #6 enthaltenen positiven Menschen-Tests nutzen **synthetische Testbilder mit nur fiktiver Freigabe**. Das ist eine technische Probe, **keine** tatsächlich freigegebene Personenveröffentlichung. Ohne passenden realen Bildreview darf ein produktiver `drafts`-Brief nicht auf `main` kommen. Es werden niemals Upload-/Freigabe-/Posting-Rechte automatisch aus einem Foto oder einer Testklasse hergeleitet.

## Regressionen

Im isolierten PR-Check läuft `tests/test_ai_disclosure.py` mit positiven und negativen Fällen (fehlender Hinweis, manipulierte Glyphen, andere Position, falsche Größe, fehlende Schrift, Logo-Kollision), `tests/test_social_portfolio_scene.py` mit falschen/fehlenden Personeneinzelfreigaben und synthetischem E2E, plus die bestehenden Logo-, Orchestrator- und Draft-Gate-Tests. Das PR-Check-Workflow-Recht bleibt `contents: read`; keine Buffer-Secrets und keine automatische Veröffentlichung.
