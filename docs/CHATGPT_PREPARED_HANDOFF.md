# AI Agent Builder: ChatGPT erstellt Texte – GitHub erstellt Buffer-Entwürfe

**Betriebsentscheidung, 10.10.2026:** Für den nächsten Ausbauschritt wird keine zusätzliche kostenpflichtige Modell-API eingerichtet. ChatGPT bereitet die drei Texte redaktionell im Gespräch vor; GitHub übernimmt die technische Verarbeitung. Dieser Ablauf ist **teilautomatisch**, nicht autonom in Bezug auf Texterstellung oder Rohmotiv-Auswahl.

## Was Josef in ChatGPT sagt

> Bereite einen neuen Social-Media-Beitrag zum Thema **[Thema]** für AI Agent Builder vor. Verwende Variante A, LinkedIn/Facebook/Instagram und lege noch nichts in Buffer an.

ChatGPT schlägt aus Quellen belegte eigenständige Texte vor, prüft die Aussagen und den Markenstil, dokumentiert die sechs Denk-Hüte (Fakten, Gefühl, Risiken, Nutzen, Alternativen, Struktur) und offene Restrisiken. Es wird ein zum Thema passendes, tatsächlich betrachtetes **4:5-Bild ohne weitere Bildbeschriftung, mit Original-Pauderer-Logo** benötigt. Der Bildinput und ein wahrheitsgemäßer Sichtprüfbericht sind Pflicht.

**Wichtig:** Nicht einfach ein früher geprüftes Bild für ein neues Thema als `matches_topic:true` ausweisen. Im Review muss die konkrete Passung zur neuen Kampagne belegt sein. Keine frei erfundenen Logos, Marken, technischen Details oder Schrift.

## Übergabe in GitHub

Eine Kampagne hat eine eindeutige ID: `YYYY-MM-DD-kurzer-slug`.

Zuerst Rohbild und Prüfnachweis:
- `media/source-images/<datei>.png`: Originalrohmotiv, mindestens 1080×1350, Verhältnis 4:5, technisch und fachlich angesehen.
- `visual-reviews/<kampagnen-id>.json`: `layout: "logo_only"`, `heading: null`, die sieben tatsächlich kontrollierten Eigenschaften, der **echte SHA-256-Fingerabdruck des Rohbilds** und ein konkreter Review-Nachweis.

Dann genau eine **neue** Datei `orchestration/briefs/<kampagnen-id>.json` mit:
- `format_version:1`, `brand:"ai-agent-builder"`, `campaign_id` und `execution_mode:"drafts"`.
- `topic`: präzises Thema (30–550 Zeichen).
- `sources`: zwei bis sechs journalistisch / fachlich verifizierte Belegquellen auf mindestens zwei unterschiedlichen HTTPS-Domains, jeweils `url` und `published_at`. Veröffentlichungsdaten müssen tatsächlich belegt sein; nicht aus dem aktuellen Datum ableiten.
- `posting_sources`: mindestens zwei aufrufbare Zeitstudien von unterschiedlichen Domains.
- `image_review:"visual-reviews/<kampagnen-id>.json"`.
- `prepared_content`: Objekt mit genau `posts`, `visual:null`, `six_hats`, `risks`. `posts` enthält **exakt** `linkedin`, `facebook`, `instagram`, jeweils 250–3000 Zeichen (Instagram maximal 2200). `six_hats` hat `white`, `red`, `black`, `yellow`, `green`, `blue` mit je einer begründeten Aussage. Die Risiken werden nicht verschwiegen.

Ein solcher Brief darf **nie** leer, als synthetisches Test- oder Pseudo-Redaktionsprotokoll in die produktive Kampagne gegeben werden.

## Sicherheitsgrenzen und Freigabepunkte

1. **ChatGPT-Entwurfsphase:** Die Texte und das Motiv werden zunächst hier vorbereitet und geprüft. Ohne ausdrücklichen Auftrag, die neuen Entwürfe anzulegen, wird **kein** produktiver `drafts`-Brief auf `main` committed.
2. **Eingangskontrolle:** `python3 scripts/prepared_brief_preflight.py --brief orchestration/briefs/<kampagnen-id>.json` kontrolliert lokal ohne Netzwerk die Datenstruktur, die Texte, die sechs Hüte, Bild-SHA, Bildreview und Kampagnen-ID. Sie ist **kein** eigenständiger fachlicher Faktencheck. Sie scheitert bei fehlendem `prepared_content`, fehlendem Bild oder bereits angelegter Kampagne.
3. **Nutzerentscheidung:** Erst wenn Josef sagt **„als Buffer-Entwürfe anlegen“**, wird die eindeutige Briefdatei auf `main` bereitgestellt. Dadurch startet der bestehende produktive GitHub-Workflow automatisch. **Nicht** vorab eine produktive Briefdatei nur „zur Vorbereitung“ nach `main` schreiben, da dies die Entwurfsanlage auslöst.
4. **GitHub-Ablauf:** Die vorbereiteten Texte passieren erneut die formale Prüfung, echte externe Quellen werden live abgerufen, das Original-Logo wird pixelgenau verifiziert und es entstehen Basisbild, Endbild, Prüfbericht, Manifest, Plan und genau drei kanalbezogene Buffer-JSON-Dateien. Bei jedem Validierungsfehler erfolgt **sicherer Stopp**. Zuverlässig automatisierte inhaltliche Faktenprüfung aller Claims ist in diesem Modus **nicht** belegt: Quellen und konkrete Behauptungen bereits redaktionell gegenprüfen.
5. **Buffer:** Es werden ausschließlich **Entwürfe** angelegt, ohne Veröffentlichungstermin. GitHub prüft anschließend `status:draft` und `dueAt:null` sowie die Anzahl und Kanäle. Für Veröffentlichung oder Terminierung ist eine separate ausdrückliche Freigabe durch Josef nötig.
6. **Einmaligkeit:** Kampagnen-ID, `artwork-receipts`, `campaign-manifests` und `delivery-receipts` verhindern eine unbemerkte Wiederholung. Eine abgebrochene Teilübertragung wird nicht blind mit einem neuen Kampagnen-Namen erneut gesendet; zuerst die tatsächlichen Buffer-/GitHub-IDs prüfen.

## Was diese Einrichtung NICHT leistet

- Kein neuer Textmodell-Anbieter. GitHub Models ist seit 30.07.2026 eingestellt und gesperrt. Kein OpenAI-API-Schlüssel oder neues kostenpflichtiges Abo wurde eingerichtet.
- Keine automatische Erzeugung und unabhängige fachliche Sichtprüfung von fotorealistischen neuen Rohmotiven.
- Keine bereits jetzt angelegte neue Buffer-Kampagne, kein Scheduling, kein Publishing.
- Nicht mit Claudes PersonalOS-Schreibrechten verwechseln: dieses Dokument dokumentiert den Arbeitsweg in `social-assets`; verbindliche Markenregeln bleiben im PersonalOS.

**Technischer Nachweis vor Einführung:** [Isolierter E2E-Probelauf 38086687450](https://github.com/derJosef/social-assets/actions/runs/38086687450) mit echten Quellen, vorbereiteten Texten und 4:5-Original-Logo war erfolgreich. Die ergänzte Eingangskontrolle besitzt eigene Tests und wird auch in der vollständigen Offline-Suite mitgeprüft.
