# AI Agent Builder: autonome Entwürfe, Terminplanung und Veröffentlichungsgate

**Genehmigung**: Josef, im Chat am 09.10.2026: Dauerberechtigung für automatische Themenauswahl, Erstellung, Qualitätsprüfung und Transfer nach Buffer als Entwurf; automatische Terminplanung ebenfalls erlaubt; tatsächliche Veröffentlichung nur mit ausdrücklicher Genehmigung.

**Technische Auslegung**: Eine echte Buffer-Terminierung setzt laut unserem funktionsgeprüften `scripts/buffer_schedule.py` per `editPost` den Status auf `scheduled` und `saveToDraft: false`; der Beitrag wird später von Buffer ohne weitere Freigabe veröffentlicht. Daher ist die selbstständige Auswahl des Veröffentlichungszeitpunkts erlaubt, die **Aktivierung dieses Termins in Buffer** aber nicht. Sie erfolgt erst nach Josefs expliziter Veröffentlichungsfreigabe. Kein Trick mit einer automatisch kurz vor dem Termin laufenden Freigabefunktion. Diese Grenze darf auch durch andere Agenten und Workflows nicht umgangen werden.

## Neu: Autonome Erzeugung von Buffer-Entwürfen (AI Agent Builder)

Bei einer neuen Kampagne:
1. Aktuelles Thema mit direkt verifizierten öffentlichen Quellen recherchieren, eigene bereits geplante/veröffentlichte Themen prüfen und Dubletten ausschließen.
2. Drei unterschiedliche, den Markenvorgaben entsprechende Texte schreiben und Quellen/CTA/Sprachstil prüfen.
3. Neue logo-freie PNG-Basis unter `media/source-images/` speichern. Original-Logo (`media/brand/logo-pauderer-original.png`) nur über `scripts/logo_composite.py` mit Original-SHA und `--heading-corner` diagonal gegenüber der Überschrift einarbeiten. Mit `verify` inklusive `--heading-box` kontrollieren; finale PNG unter `media/images/` ablegen.
4. Plattformspezifische Veröffentlichungszeiten auf datierter Studiengrundlage (mindestens zwei Quellen, gegebenenfalls eigene vergleichbare Daten) ermitteln, Europe/Berlin einschließlich Sommer-/Winterzeit exakt nach UTC umrechnen.
5. Ein neues **öffentliches** Manifest `campaign-manifests/YYYY-MM-DD-slug.json` im Format unten ablegen. Jede Quality-Flag darf nur auf `true` stehen, wenn der Test tatsächlich durchgeführt und bestanden wurde. Flags allein sind kein objektiver Beweis für journalistische Richtigkeit – Quellen müssen im Redaktionsprozess geprüft werden.
6. In **einem einzigen Commit** die drei neuen JSON-Dateien `ready-for-buffer/auto-YYYY-MM-DD-slug-{linkedin,facebook,instagram}.json` in exakt Format-2 (`format_version`, `target`, `text`, `media`) anlegen. Kein zusätzlicher Josef-Approval-Schritt mehr erforderlich. **Niemals** mit einer neuen automatisch generierten Datei in `ready-to-schedule/` arbeiten.
7. GitHub Actions `buffer-auto-drafts.yml` ruft VOR irgendeinem Buffer-Aufruf `scripts/autonomous_campaign_gate.py` auf. Das Skript verlangt alle drei Zielkanäle, eindeutige Zuordnung, datierte Quellen, echte SHA des Bildes und eine vollständige erneute deterministische Prüfung des Logo-Compositings. Bei irgendeinem Fail werden alle drei neuen autonomen Drafts blockiert. Danach kontrollieren: 3 Empfangsbelege und im Buffer-API-Status `draft`, `dueAt=null`.
8. In `campaign-manifests/` gespeicherte `posting_times` sind lediglich **Terminvorschläge**, keine Buffer-Publikationsaufträge. Selbst eine neue `ready-to-schedule/`-Datei **(nur Format v2 mit Post-ID und Entwurfs-Hash)** aktiviert keine Veröffentlichung. Erst ein ausdrücklich gestartetes `workflow_dispatch` auf `main`, ein geschütztes `buffer-publish`-Environment und eine von GitHub über die Approvals-API bestätigte **unabhängige menschliche Freigabe** dürfen einen bereits vorhandenen Buffer-Entwurf terminieren. Das geschieht niemals allein aufgrund einer Dateiflag oder eines Commits.

**Achtung GitHub Actions**: Ein Commit eines Workflows mit dem standardmäßigen `GITHUB_TOKEN` löst normalerweise keinen zweiten `push`-Workflow aus. Die drei Auto-Draft-Dateien müssen deshalb durch den verbundenen GitHub-Connector/Agent-Token oder einen ausdrücklich gestarteten Transferworkflow auf `main` angelegt werden; nicht still annehmen, dass ein Workflow-Kettenpush läuft.

## Manifest-Beispiel (Schema v1, Platzhalter niemals unverändert live senden)

```json
{
  "format_version": 1,
  "brand": "ai-agent-builder",
  "campaign_id": "2026-11-01-beispiel-thema",
  "checked_at": "2026-11-01",
  "sources": [
    {"url": "https://beispiel-quelle-1.de/original", "published_at": "2026-10-10", "checked_at": "2026-11-01"},
    {"url": "https://beispiel-quelle-2.org/leitlinie", "published_at": "2026-10-15", "checked_at": "2026-11-01"}
  ],
  "checks": {
    "novelty": true,
    "claims_with_sources": true,
    "language_and_cta": true,
    "six_hats": true,
    "privacy_and_rights": true,
    "brand_image": true,
    "posting_time_research": true
  },
  "image": {
    "final": "media/images/2026-11-01-beispiel-thema.png",
    "base": "media/source-images/2026-11-01-beispiel-thema.png",
    "sha256": "<durch sha256sum erzeugte 64 Hex-Zeichen>",
    "heading_corner": "top-left",
    "heading_box": [60, 90, 850, 320]
  },
  "posts": {
    "linkedin": "ready-for-buffer/auto-2026-11-01-beispiel-thema-linkedin.json",
    "facebook": "ready-for-buffer/auto-2026-11-01-beispiel-thema-facebook.json",
    "instagram": "ready-for-buffer/auto-2026-11-01-beispiel-thema-instagram.json"
  },
  "posting_times": {
    "linkedin": {"local": "2026-11-04T16:00:00+01:00", "utc": "2026-11-04T15:00:00Z"},
    "facebook": {"local": "2026-11-05T19:00:00+01:00", "utc": "2026-11-05T18:00:00Z"},
    "instagram": {"local": "2026-11-06T18:00:00+01:00", "utc": "2026-11-06T17:00:00Z"}
  }
}
```

## Vollautomatische Produktion neuer Markenbilder

Neben dem manuellen ImageGen→Compositing-Weg existiert jetzt der getestete GitHub-Actions-Workflow [Social Visual – automatisch aus Kampagnenauftrag](../.github/workflows/social-visual-auto-from-spec.yml). Dadurch muss bei einer neuen Kampagne kein individuelles Bildskript programmiert werden.

1. Der Agent erzeugt genau eine neue, quellen- und themenbezogene Datei `artwork-requests/YYYY-MM-DD-slug.json` (schema 1, Marke AI Agent Builder) mit `badge`, `headline`, `subtitle`, exakt drei `cards` mit `title`/`description` und `closing`.
2. Der Push durch einen GitHub-App-/Benutzer-Token startet den Workflow. Er erzeugt **ohne KI-Neuzeichnung des Logos** ein logo-freies PNG unter `media/source-images/` und setzt das SHA-geprüfte Original-PNG mittels Pillow zusammen. Er prüft die finale Grafik gegen Original und Hintergrundpixel.
3. **Nur nach bestandenem Test** werden Basisbild, finale Markenbilddatei und ein Bild-Receipt unter `artwork-receipts/YYYY-MM-DD-slug.json` committet (inklusive SHA-256, Überschriften-Box, Bildpfaden). Der Agent liest diese Belege vor der nächsten Phase zurück.
4. Der Agent führt die eigenständige redaktionelle Prüfung aus, erstellt `campaign-manifests/YYYY-MM-DD-slug.json` und legt die drei neuen Auto-Drafts in `ready-for-buffer/` an; der vorhandene Draft-Workflow verifiziert **vor jedem** Buffer-Aufruf erneut Logo, Basisbild, Quellen und Zeitumrechnung.
5. Fehlt eine Fähigkeit im Hintergrundlauf, bleibt der Beitrag außerhalb von `ready-for-buffer`; kein Fehler darf durch eine bloße Behauptung `checks: true` übersprungen werden. Die Bild-Erstellung und die Freigabe der tatsächlichen Publikation bleiben getrennte Vorgänge.

**Nachgewiesener Bildtest:** [GitHub-Lauf #37899111557](https://github.com/derJosef/social-assets/actions/runs/37899111557) `success`; drei Dateien (Basis, Final, Receipt) auf GitHub. [Finale Testgrafik](../media/images/2026-10-09-automatisierung-probelauf-branded.png). Das ist ein **reiner Techniktest** und hat keinen weiteren Buffer-Beitrag erstellt.

**Nachgewiesener Live-Pilot** (bestehende, ebenfalls verifizierte Grafik): [GitHub-Lauf #37898575725](https://github.com/derJosef/social-assets/actions/runs/37898575725), QA-Gate PASS, drei neue Buffer-Entwürfe. [Statusprüfung #37898698353](https://github.com/derJosef/social-assets/actions/runs/37898698353): alle drei `status=draft`, `dueAt=None`.

## Sicherheitsgrenzen und Tests

- **Autonome Entwürfe** nur für Marke `ai-agent-builder`; nicht für Picture Fix oder Sticken-Lasern.
- **Auto-Quality-Gate** in `scripts/autonomous_campaign_gate.py`: fail-closed, verarbeitet genau eine dreikanalige Kampagne pro Push; kein Buffer-API-Zugriff im Gate. Ungeprüfte Texte, fehlende Bilder, fehlerhafte Zeitrechnungen oder verlorene Logos blockieren den gesamten automatischen Transfer.
- **Legacy-/manuell freigegebene Buffer-Entwürfe** bleiben wie bisher möglich; sie folgen ihren bisherigen Freigaben.
- **Bestehende geplante Posts** bleiben unverändert.
- **Keine Weitergabe von Geheimnissen/privaten Kundenfällen** an das öffentliche GitHub-Repository.
- `scripts/buffer_schedule.py` und `buffer-auto-schedule.yml` verlangen den gesonderten manuellen Dispatch sowie echte GitHub-Genehmigung. Der alte Push-Trigger und ein statisches Freigabe-Secret sind im PR #2 entfernt. **Noch nicht produktiv, bis PR #2 nach zusätzlicher Sicherheitseinstellung freigegeben wurde.**
- Offline: `python3 -B -m unittest discover -s tests -v` und Bildtests in `scripts/test_logo_composite.py`. Das Erstellen einer Demo-Datei im Repo ist **kein** Live-Test des Buffer-Transfers.

Die lokale PersonalOS-Fassung `O:\` bleibt führend; `derJosef/personalos` ist synchronisierter GitHub-Stand. Vor dem nächsten lokalen Sync diese neue Berechtigungsänderung mit dortigen lokalen Änderungen abgleichen.
