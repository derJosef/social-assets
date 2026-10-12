# Automatische Bildquelle für die AI-Agent-Builder-Wochenkampagne

**Stand: 12.10.2026 – ausschließlich PR #13, kein produktiver Lauf.**  
Diese Implementierung überbrückt die bisher fehlende Rohbild-Vorstufe. Sie
ändert die Freigabereihenfolge nicht: **Drei vollständige datierte Buffer-Drafts
zuerst, Josefs persönliche Freigabe erst danach.**

## Technischer Ablauf

1. Die ChatGPT-Wochenkampagne bereitet einen neuen eindeutigen Brief unter
   `orchestration/briefs/YYYY-MM-DD-slug.json` vor. Das Pflichtfeld
   `image_review` verweist auf
   `visual-reviews/YYYY-MM-DD-slug.json`. Existiert die
   Prüfung bereits, verwendet der Workflow die vorhandene Quelle und
   prüft sie mit dem bisherigen vollständigen Gate erneut.
2. Fehlt der Bildreview, erstellt
   `scripts/automatic_image_source.py --brief <BRIEF>` genau
   **eine** Rohbildvariante aus dem konkreten Thema. Das Modell
   `gpt-image-1.5` erzeugt ein 1024×1536-PNG. Der Prompt verbietet
   menschliche Körper/Gesichter, Roboter, Hände, Texte, Logos und
   fremde Marken und verlangt eine plausible hochwertige B2B-Szene
   in Navy/Petrol mit Platz für das später technisch montierte Logo.
   Das Original-Logo wird niemals an das Bildmodell übergeben.
3. Das Originalbild wird ohne Motivbeschnitt mit proportionalem
   Hauptmotiv und unscharf abgeleitetem Seitenhintergrund auf ein
   echtes 1080×1350-PNG gesetzt. Dieses Rohmotiv enthält weiterhin
   **kein** Logo, keinen Schriftzug und keine KI-Personen.
4. Zwei separate Bildprüfanfragen an `gpt-4.1-mini`
   kontrollieren jeweils sieben Kriterien: keine Menschen, keine Roboter,
   keine Fremdlogos, keine Schrift, technische Plausibilität,
   Themenpassung und freie Logo-Ecke. Jede Verneinung, Unklarheit,
   fehlende Angabe oder widersprüchliche Prüfantwort stoppt die
   Dateierstellung. Das ist **maschinenbasiertes Screening**, keine
   unabhängige menschliche Sichtprüfung und keine Garantie gegen
   semantische Fehler.
5. Erst danach werden die Rohbild-PNG-Datei und die Prüfspezifikation
   mit genauen SHA-256-Fingerabdrücken neu angelegt. Review-Evidence
   vermerkt ausdrücklich `machine_draft_only` und
   `NOT a human`. Alte personenbezogene Bildspezifikationen behalten
   ihre strengere Einzelfreigabe, es wird keine eigene Personenfreigabe
   erfunden. KI-generierte Gesichter werden im **automatischen**
   Workflow grundsätzlich abgewiesen; der spezielle `Powered by AI`-
   Compositor bleibt für gesondert freigegebene Personenfälle erhalten.
6. `prepared_brief_preflight.py` prüft danach Brief, Quelle und
   das neue deklarierte Review; `social_portfolio_scene.py`
   setzt ausschließlich das unveränderte Original-Logo mit dem
   kanonischen `logo_composite.py` auf das finale Bild. Alle
   vorhandenen Pixel-/Hash- und Drei-Kanal-Kampagnentests laufen
   weiter. Bei maschinellen Rohbildern weist der Image-Receipt
   `human_visual_review=pending_in_buffer` aus.
7. Eine neue automatisch erzeugte Rohbild-PNG-Datei **und ihre
   Prüfspezifikation** werden mit der geprüften Basisgrafik, Endgrafik
   und dem Artwork-Receipt im ersten Commit des isolierten
   `automation/campaign/<kampagne>`-Branches gesichert.
   Der zweite Commit enthält Manifest/Termine, Plan und drei Drafts
   mit auf den Bild-Commit-SHA gepinnten Media-URLs. `main` bleibt
   unverändert. Bestehende Review-Dateien und Rohbilder dürfen
   nicht überschrieben werden.
8. Erst nach unveränderter vollständiger Qualitätsprüfung und
   Existenz des geschützten Receipt-Ledgers darf der vorhandene
   Entwurfssender drei `createPost(saveToDraft:true,
   mode:customScheduled,dueAt)`-Operationen ausführen. Jeder
   Draft erhält seinen Einmal-Receipt und unabhängigen Readback.
   **Keine Queue oder Veröffentlichung**, auch nicht bei
   durchlaufender Bildgenerierung.

## Sicherheit, Kosten und Betriebsgrenzen

- **Externer Provider erforderlich:** GitHub Secret
  `SOCIAL_OPENAI_API_KEY` muss für Image API und
  Vision-API berechtigt sein. Ein funktionierendes Textmodell
  beweist **nicht**, dass das Konto für kostenpflichtige
  Bildgeneration berechtigt ist. Es wird kein Key in GitHub-Dateien
  oder Logs geschrieben.
- Die Bild-API erzeugt einen kostenpflichtigen Bildaufruf und
  anschließend zwei Modellprüfaufrufe. Automatische Wiederholung
  fehlgeschlagener Buffer-Aktionen bleibt untersagt; bereits
  existierende Kampagnen-Branches werden **vor** Generierung
  auf Duplikate geprüft.
- Der neue visuelle Prüfpfad ist **nur für unveröffentlichte
  Entwürfe** konzipiert. Vor der späteren Freigabe zur
  Veröffentlichung muss Josef den tatsächlichen Buffer-Draft
  ansehen, inklusive Motiv, möglicher technischer Fehler,
  Kennzeichnung, Logo und Text. Maschinen können Fehlklassifikationen
  nicht ausschließen.
- Die zwei Audits stammen vom selben Modellanbieter. Sie sind zwei
  getrennte Prüfungen, **keine** Anbieter-unabhängige Begutachtung.
  Die Behauptung, Josef habe den Rohbild-Review bereits durchgeführt,
  wäre falsch und ist durch das neue Review-Schema verboten.
- Es gibt **keine** automatische Begründung, andere Marken oder
  sensible Kundendaten in diese Pipeline einzuspeisen. Öffentliche
  Bilder und Beiträge dürfen keine vertraulichen Informationen
  enthalten.
- **Keine Live-Abnahme erfolgt:** Die CI-Tests verwenden
  synthetische PNGs und vollständig gemockte Provider, ohne
  Secrets, Buffer oder GitHub-API-Schreiboperationen.
  Ein späterer tatsächlicher Wochenlauf erfordert die separate
  Integration und die vorhandenen Sicherheitsvoraussetzungen.
- Eigene manuelle 4:5-Motive und echte Review-Belege werden weiterhin
  unterstützt. Nie automatische Überschreibung oder Umdeutung
  dieser bereits existierenden Belege.

## Offline-Abnahme

```bash
python3 -B -m unittest discover -s tests -p 'test_automatic_image_source.py' -v
python3 -B -m unittest discover -s tests -q
```

Die Tests decken Provider-Ausfälle, fehlenden Key, unvollständige/
inkonsistente Bildgutachten, Dimensionsfehler, No-Overwrite, gefälschte
manuelle Abnahme und die **vollständige synthetische Kette**
Rohmotiv → 4:5 → SHA → Original-Logo-Composite → Logo-Verifikation ab.
Sie belegen keine Live-Bild-API-Abnahme und keine produktive
Buffer-Draft-Kampagne.
