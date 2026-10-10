# AI Agent Builder – 4:5-Bildpipeline im Orchestrator

Stand: 2026-10-10. **Kein Modell erhält die Erlaubnis, ungeprüfte Bilder als markenkonform zu bezeichnen.**

## Architektur

1. Ein konkretes 4:5-Rohbild (mindestens 1080 × 1350) wird als `media/source-images/...` auf GitHub gespeichert. Ein Mensch prüft es anhand von `derJosef/personalos/skills/josefs-marke/references/social-media/DESIGN.md`: technisch plausibel, themenrichtig, keine Schrift/Fremdlogos/Roboter/ungewollten Personen, Platz für das Original-Logo. SHA-256 und konkrete Sichtprüfungsnotiz in `visual-reviews/<campaign>.json`.
2. Erst danach kann `orchestration/briefs/<campaign>.json` unter dem Feld `image_review: "visual-reviews/<campaign>.json"` angelegt werden. Die übrigen bestehenden Felder `sources`, `posting_sources`, `topic` etc. bleiben erforderlich. Im optionalen `prepared_content` muss `visual: null` stehen; bei automatischem LLM-Textauftrag fordert der Systemprompt `visual: null`.
3. Der Orchestrator validiert das freigegebene Rohmotiv **vor** Modell- und Netzwerkaufrufen, erstellt plattformspezifische Texte und Forschungsnachweise, rendert mit `social_portfolio_scene.py` die 4:5-Basis und setzt das unveränderte Original-Pauderer-Logo via dem kanonischen PersonalOS-`logo_composite.py` ein.
4. Manifest und `autonomous_campaign_gate.py` verifizieren **erneut** die Bild-SHA, Review-SHA, 4:5-Dimensionen, Original-Logo-Position, Pixelintegrität, Quellen, Postingzeiten und die drei zielgenauen Buffer-JSON-Dateien. Der neue Gate verlangt bei autonomen Kampagnen das erweiterte Format mit `layout`, `review_spec`, `source_sha256`; alte 1:1-Karten-Manifeste werden **nicht** als neue autonome Kampagnen akzeptiert.
5. Erst bei vollständigem Erfolg werden **acht neue** Artefakte atomar nach `main` geschrieben: Basis-PNG, Final-PNG, Bildreceipt, Kampagnenmanifest, Zeit-/QA-Plan und drei Plattformentwürfe. Die freigegebene **Quelle und Review sind bereits vor dem Workflow vorhanden** und gehören nicht zu diesen acht. Der bestehende Buffer-Sender erstellt nur `draft`-Posts und prüft anschließend live `status: draft`, `dueAt: null`.
6. Buffer-Scheduling und Veröffentlichung bleiben getrennt und dürfen nicht vom Orchestrator aktiviert werden. Der Legacy-Autoworkflow für quadratische Drei-Karten-Bilder wird stillgelegt; das Skript bleibt für nachvollziehbare Altfälle erhalten.

## Review-Beispiel

```json
{
  "format_version": 1,
  "brand": "ai-agent-builder",
  "source": "media/source-images/2026-11-01-beispiel-motiv.png",
  "source_sha256": "<tatsaechliche_sha256_des_rohmotivs>",
  "layout": "logo_only",
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
  "review_evidence": "<konkrete_tatsaechlich_durchgefuehrte_Sichtpruefung>"
}
```

Diese Booleschen Felder sind eine **dokumentierte menschliche Feststellung**, kein maschineller Beweis. Fehlt ein Bild oder stimmt seine Prüfsumme nicht, **BLOCK**. Platzhalter dürfen niemals im Live-Betrieb akzeptiert werden.

## Was noch nicht vollautomatisch ist

Der bisherige GitHub-Textmodellzugang kann keine verlässliche fotorealistische B2B-Bildszene als neue Bilddatei liefern und die inhaltliche Sichtprüfung nicht ersetzen. Damit ist die Strecke **ab bereits geprüfter Grafik** automatisiert; die erstmalige Motiverzeugung, Qualitätskontrolle und Ablage neuer Bildquellen ist derzeit weiterhin ein getrennter Arbeitsschritt. Hierfür später einen ausdrücklich konfigurierten, begrenzten Bildgenerierungs-/Review-Weg mit Kosten-, Rechte-, Marken- und Zugriffsprüfung entwickeln. Keine Ersatzkarten und kein schleichender Rückfall auf den alten Generator.

## Nachweis

Der isolierte GitHub-PR-Workflow testet den vollständigen Pfad **ohne Buffer-Schreibzugriff**: Original-Logo-Compositing, 4:5-Szenenrenderer, Orchestrator mit geprüfter synthetischer Quelle, Manifest und drei Entwurfsdateien, Quality-Gate sowie negative Tests (fehlender Review, falsche SHA, 1:1-Motiv, Dummy-Titel, altes Manifest). Beispiel- und Testmotive sind **keine Freigabe für reale Kampagnen**.
