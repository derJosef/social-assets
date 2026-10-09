# Social-Media-Bildpipeline: Hintergrund + unverändertes Original-Logo

Stand: 09.10.2026. Technischer Integrationstest **PASS**. Keine Freigabe für einen konkreten Social-Media-Post oder eine Veröffentlichung.

## Architektur

1. **Motiv erstellen**: Für den E2E-Test erzeugt `scripts/social_visual_e2e_20261008.py` ein logo-freies PNG (`drafts/.visual-e2e-base.png`). Für künftige Motive kann eine vorab erstellte, logo-freie PNG verwendet werden.
2. **Original-Logo lesen**: `media/brand/logo-pauderer-original.png` ist eine bytegleiche Kopie aus `derJosef/agent-workspace/work/assets/brand/logo/logo.png`. Erwartet: 1939 × 1324 Pixel und SHA256 `15dc410d1a05b96c13466ddf3052ba9cc783cdd7252b74f4fb5c3f886510dea0`.
3. **Deterministisches Compositing**: `scripts/logo_composite.py` (Kopie der geprüften PersonalOS-Implementierung aus `skills/meine-marke/scripts/logo_composite.py` am 09.10.2026) skaliert das Logo proportional und erstellt auf dunklem Grund den gleichmäßigen weißen Außenrahmen aus der Maske. Die Hauptüberschrift steht hier oben links, das Logo unten rechts.
4. **Prüfen (FAIL-CLOSED)**: `verify` prüft das finale PNG gegen das Basisbild, das Original-Logo und die explizit angegebene Heading-Box: Seitenverhältnis, Pixelgenauigkeit, Rahmen, diagonale Position, Sicherheitsabstände, Überschneidungen und unveränderte Bildpixel außerhalb der Logobox. Exit-Code 1 oder 2 stoppt den Job.
5. **Speichern**: Jeder erfolgreiche Lauf lädt das verifizierte PNG als Action-Artefakt hoch. Bei `mode=existing` committet er zusätzlich **ausschließlich** die neue finale Bilddatei nach `media/images/`. Im automatischen Smoke-Test erfolgt dagegen **kein** neuer GitHub-Medien-Commit. Bestehende Bilder werden niemals überschrieben. Die Pipeline erstellt keine Buffer-Entwürfe und keine Veröffentlichungstermine.

Verbindliche Markenregeln bleiben in `derJosef/personalos/skills/meine-marke` (lokale PersonalOS-Fassung ist führend). Wenn der dortige Compositor geändert wird, muss die hier verwendete Kopie kontrolliert synchronisiert und erneut getestet werden. Private Repositories sind auf Standard-GitHub-Runnern möglicherweise nicht zugreifbar; deshalb liegt die ausführbare Snapshot-Kopie im Asset-Repository. Kein schreibender Zugriff auf PersonalOS oder agent-workspace.

## GitHub Actions

Workflow: [Social Visual – Generate, Composite, Verify](../.github/workflows/social-visual-brand-test.yml)

- **Automatisch** bei Änderungen am Workflow oder den Bild-/Logo-Skripten: Ein **wiederholbarer** Smoke-Test mit dem festen Testmotiv wird ausgeführt. Das überprüfte Ergebnis steht als GitHub-Actions-Artefakt bereit, ohne ein vorhandenes Repository-Bild zu überschreiben und ohne einen neuen Medien-Commit zu erzeugen.
- **Manuell** via **Actions → Social Visual – Generate, Composite, Verify → Run workflow** mit `mode=existing`:
  - `source_image`: ein vorher committedes **logo-freies** PNG unmittelbar unter `drafts/` oder `media/source-images/` (Beispiel `media/source-images/neues-motiv.png`).
  - `output_name`: neuer, noch nicht vorhandener PNG-Dateiname, z. B. `2026-11-03-praxisreihe.png`.
  - `heading_corner`: tatsächliche Ecke der Hauptüberschrift, etwa `top-left`.
  - `heading_box`: tatsächliche Bounding-Box `x0,y0,x1,y1` in Pixeln; ohne diesen Wert keine vollständige Freigabe.

Die Eingaben werden auf sichere Pfade und Syntax geprüft. Der Workflow übergibt keinerlei Bildmaterial an einen Generator, sobald das Original-Logo eingesetzt ist.

## Nachgewiesener Integrationstest

- [GitHub-Lauf 37894607255 – SUCCESS](https://github.com/derJosef/social-assets/actions/runs/37894607255)
- Original-Logo: Prüfsumme und Abmessungen **PASS**
- PersonalOS-Regressionstests: **28 Tests, OK, 3 übersprungen** (die drei benötigen den lokalen Windows-Originalpfad; für den eigentlichen Live-Lauf wird ausdrücklich der gehashte Repository-Asset-Pfad übergeben)
- Finale Live-Prüfung: **alle 10 Prüfpunkte PASS**, einschließlich 0 Pixeländerungen außerhalb der Logoebene
- Ausgabe: [2026-10-09-ein-agent-drei-tests-branded-test.png](../media/images/2026-10-09-ein-agent-drei-tests-branded-test.png), 1080 × 1080 px
- **Keine** neue `ready-for-buffer/`-Datei, kein `ready-to-schedule/`-Auftrag, keine Buffer-Mutation.

## Veröffentlichungsgrenze

Ein technischer PASS besagt nur, dass das **Bild** markenkonform zusammengesetzt wurde. Er ersetzt weder Quellenrecherche noch inhaltliche Qualitätskontrolle, menschliche Themen-/Text-/Bildfreigabe oder die gesonderte Erlaubnis zum Erstellen von Buffer-Entwürfen und zur Veröffentlichung. Bei einem späteren Beitrags-Workflow muss ein geprüftes Bild ausgewählt und **vor** dem explizit freigegebenen Transfer nach `ready-for-buffer/` verwendet werden. Dieser Bildworkflow veröffentlicht nie.

- [Wiederholungstest für den Überschreibschutz](https://github.com/derJosef/social-assets/actions/runs/37894871638): Ausführung nach Umstellung auf temporäre Artefakte ohne neuen Medien-Commit; Status anhand des Workflow-Laufs kontrollieren.
