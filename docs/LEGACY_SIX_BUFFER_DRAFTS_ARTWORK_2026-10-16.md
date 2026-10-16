# Zwei neue 4:5-Grafiken für sechs bestehende Buffer-Drafts – 16.10.2026

**Status:** Nur Bildvorbereitung im separaten, manuellen GitHub-Workflow. **Kein** bestehender Buffer-Draft wird angelegt, editiert, terminiert oder veröffentlicht. Die drei ähnlichen alten „Kundenmail ist kein Befehl“-Beiträge bleiben unberührt.

## Prüfausgangslage

Lesender [Buffer-Audit #38889175483](https://github.com/derJosef/social-assets/actions/runs/38889175483) fand neun ältere `draft`-Beiträge ohne `dueAt`, gruppiert in drei Dreierpakete. Der vollständige originale, 24 Stunden aufbewahrte GitHub-Artifact-JSON-Audit wurde gezielt eingelesen. **Alle neun hatten `asset_count=1` und `asset_types=["image"]`**. Bei den vom Nutzer als ohne sichtbares Bild beschriebenen sechs Beiträgen zeigt die `asset_urls`-Liste die zwei bereits im Repository vorhandenen älteren **1080×1080-Grafiken** an. Diese sind keine aktuellen 4:5-3D-Rohbilder, sondern alte textlastige quadratische Layouts. Ein per Buffer referenziertes Asset bedeutet nicht zwingend, dass Buffer die Grafik sichtbar und fehlerfrei darstellt.

Die sechs zu reparierenden IDs stehen **unverändert** fest:

| Thema | LinkedIn | Facebook | Instagram |
|---|---|---|---|
| Wer liest bei deinem KI-Chat mit? | `6ac8d5a926e224ee545ee6b5` | `6ac8d5ab26e224ee545ee761` | `6ac8d5ae26e224ee545ee809` |
| Ein Agent. Drei Tests | `6ac8961e7d9f9f33012bc9cd` | `6ac89617f07e682de6a98b36` | `6ac8961b7d9f9f33012bc803` |

**Alle sechs** aktuellen Buffer-Post-IDs beibehalten. Der Auditor gibt vorhandene `status=draft`, `dueAt=null` aus. Texte in Buffer haben Vorrang vor alten GitHub-Kopien. Neue `createPost`-Aufrufe sind ausdrücklich kein Reparaturweg.

## Zwei neue, echte ChatGPT-Bildquellen (ohne Adobe-Firefly)

Beide Bildmotive im Chat mit nativer ImageGen-Funktion erzeugt; keine realistischen Menschen, keine Roboter, keine Zahlen/Buchstaben, Fremdlogos oder fremde Bilder als Input. Die vom Modell gelieferten PNG-Abmessungen wurden **proportional mit Pillow LANCZOS** auf 1080×1350 skaliert; bei Bedarf wurden dünne dunkelmarineblaue Seitenränder ergänzt. **Kein Crop, keine geometrische Verzerrung.** Die Bilder wurden mit ChatGPT visuell geprüft, aber keine unabhängige Host-Kontextisolation attestiert.

| Themenpaket | Originalausgabe | Geprüfter finaler **Roh**-SHA256 | Adobe-Kurzlink |
|---|---|---|---|
| Wer liest mit | 1092×1440 | `74a7debcc3d5598fa328fc9a5c0376c9cd2797ed2d722ed7a9c4e6ec5c3abfd7` | `https://at.adobe.com/xJC6aVh2hPgh9EnZ` |
| Ein Agent. Drei Tests | 1122×1402 | `95f82aa8b82c749a89d73e5f1ba34bb4a2521c31f9043bf80dffaee328406c7a` | `https://at.adobe.com/wuislato0VUYlaeT` |

Adobe Creative Cloud hat die **beiden normierten 1080×1350 PNGs** am 16.10. als `wer_liest_mit_raw_1080x1350.png` und `ein_agent_drei_tests_raw_1080x1350.png` übernommen. Die Adobe-Suche lieferte die Asset-IDs `urn:aaid:sc:EU:ebaa449f-8851-47a9-89f1-311ff59d5373` und `urn:aaid:sc:EU:e1c54cc5-41f1-4848-81f6-10e6668bfe7b`. Die erste **Byte-Rückprüfung** aus Adobe erfolgt erst im GitHub-Workflow und muss jeweils gegen den angegebenen Roh-SHA bestehen.

## Der neue alleinstehende Bildvorbereitungsweg

- `scripts/legacy_six_draft_image_prepare.py` liest ausschließlich die zwei exakt festgelegten Adobe-Kurzlinks über den vorhandenen sicheren Importer. Original-/Rohbild-SHA und echte PNG-Größe müssen passen, sonst Stopp.
- Für jedes Thema werden die einmaligen neuen Dateien `media/source-images/*-source.png`, `*-base.png`, `media/images/*-branded.png`, `visual-reviews/*.json` und `artwork-receipts/*.json` vorbereitet.
- Bestehender `social_portfolio_scene.build` montiert **deterministisch das originale Pauderer-Logo** und führt vollständige 4:5-/Pixel-/Disclosure- und Original-Logo-QA aus. Keine generierte Logo-Version; keine Personen- oder Veröffentlichungslizenz behaupten.
- [Manueller Workflow](../.github/workflows/legacy-six-draft-images-only.yml) nur `workflow_dispatch` auf dem geschützten `main`, von `derJosef` und nur bei `GITHUB_RUN_ATTEMPT=1` plus Bestätigung `ZWEI_LEGACY_BILDER_NUR_GITHUB`.
- Sämtliche Output-Assets werden erst nach beiden vollständigen Qualitätsprüfungen in **einen neuen separaten Branch** `automation/legacy-artwork-repair-20261016` geschrieben. Exakt zehn **neue** Dateien, keine Änderung am geschützten `main`. Besteht der Output-Branch bereits, keine zweite Ausführung. Der Commit-SHA dieses Bildbranches erlaubt später manipulationsfest gepinnte Bildlinks.
- **Null Buffer-Schreibaufrufe**, null `editPost`, null `createPost`, null Queue, null Publikation, null Änderung vorhandener Termine. Kein neues Firefly-/Adobe-Bildmodell und keine API-Generierungskosten. Es ist ein **vorbereitender** Schritt; ein Merge aktiviert keine Buffer-Aktion.

## Zweite Stufe – vorerst NICHT freigegeben/implementiert

Die tatsächliche **in-place**-Aktualisierung der sechs ursprünglichen Buffer-Drafts folgt als **eigener gesicherter Edit-Auftrag**, nachdem die beiden fertigen Marken-PNGs aus dem Bildbranch visuell geprüft wurden. Der Bearbeiter muss unmittelbar vor jedem `editPost` per Buffer-`post`-Readback sicherstellen:

- Post-ID und Kanal stimmen exakt; `status=draft`, `dueAt=null` (keine übergangene vorhandene Terminierung).
- Tatsächlichen aktuellen Buffer-Text **unverändert** belassen; frühere GitHub-Textkopien nicht darüberkopieren.
- Vollständige für die jeweilige Plattform erforderliche Metadaten lesen und erhalten; GraphQL-`editPost`-Validator kann sonst Inhalte zurückweisen. Nur Medienarray durch die **eine** geprüfte, SHA-gepinnte Original-Logo-Datei ersetzen; `saveToDraft:true`, **weder Mode noch dueAt neu setzen**.
- Vor jedem Post einmaligen `pending_manual_reconciliation_on_failure`-Beleg schreiben, dann **maximal eine** Mutation, keinen automatischen Retry. Nach Erfolg neu lesen und verifizieren: alte ID, unveränderter Text, `draft`, `dueAt=null`, genau erwartetes `image`-Asset. Andere Kanäle bei Fehler stoppen.
- Buffer zeigt das Bild in der UI tatsächlich richtig an – bei Abweichung klären, nicht blind nachtragen.

Die offizielle [Buffer EditPostInput-Dokumentation](https://developers.buffer.com/types/EditPostInput.html) bestätigt die optionale `assets`-Array-Änderung und `saveToDraft`-Verhalten, warnt aber vor dem Verlust plattformspezifisch zwingender Metadaten bei Editieren. Ein `editPost` ist **nicht** freigegeben, bevor die neue separate Stufe vorbereitet, getestet und anschließend gezielt beauftragt wird.

## Parallel: Frequenz 2 Themen pro Woche (noch Empfehlung, keine Automatismusänderung)

Buffer empfiehlt nach Auswertung von über 2 Millionen LinkedIn-Posts von 94.000 Konten **2–5 Beiträge je Woche**. Daher vierwöchiger Pilot mit **2 verschiedenen Themen/Woche**, pro Thema passgenauer LinkedIn-, Facebook- und Instagram-Text, also **6 Kanalbeiträge/Woche**, redaktionell unterschiedlich. Keine ungeprüfte Anpassung der aktuellen GitHub-Postingfrequenz, keine Aufhebung der 3-Tage-Kanalabstände und vorhandenen `ready-to-schedule`-Reservierungen. Vor Wechsel zunächst bestehende alte Themen qualitätsprüfen, Terminüberlappungen auflösen und die **Steigerung als separate redaktionelle Entscheidung** dokumentieren. Quelle: https://buffer.com/resources/how-often-to-post-on-linkedin/.
