# AI Agent Builder: autonome Entwürfe, Terminplanung und Veröffentlichungsgate

**Genehmigung**: Josef, im Chat am 09.10.2026: Dauerberechtigung für automatische Themenauswahl, Erstellung, Qualitätsprüfung und Transfer nach Buffer als Entwurf; automatische Terminplanung ebenfalls erlaubt; tatsächliche Veröffentlichung nur mit ausdrücklicher Genehmigung.

**Technische Auslegung**: Eine echte Buffer-Terminierung setzt per `editPost` den Status auf `scheduled` und `saveToDraft: false`; der Beitrag wird später von Buffer ohne weitere Freigabe veröffentlicht. Diese Aktivierung bleibt gesperrt. Am 12.10.2026 bestätigte der einmalige Live-Test #38179032859 dagegen, dass `createPost(saveToDraft:true, mode:customScheduled, dueAt)` einen **datumsbehafteten Draft mit Status `draft`** erzeugt, ohne Queue. Seit Josefs Entscheidung vom 12.10.2026 werden qualitätsgeprüfte Kampagnen ohne individuelle Brief-Vorabfreigabe als datierte Buffer-Drafts vorbereitet. Erst nach Einsicht der drei fertigen Entwürfe darf Josef die Veröffentlichung freigeben. Die technische Aktivierung bleibt bis zu geprüftem Repo-/Ledger-Schutz auf einem Draft-PR. Kein Umweg zur Veröffentlichung.

## Neu: Autonome Erzeugung von Buffer-Entwürfen (AI Agent Builder)

Bei einer neuen Kampagne:
1. Aktuelles Thema mit direkt verifizierten öffentlichen Quellen recherchieren, eigene bereits geplante/veröffentlichte Themen prüfen und Dubletten ausschließen.
2. Drei unterschiedliche, den Markenvorgaben entsprechende Texte schreiben und Quellen/CTA/Sprachstil prüfen.
3. Neue logo-freie PNG-Basis unter `media/source-images/` speichern. Original-Logo (`media/brand/logo-pauderer-original.png`) nur über `scripts/logo_composite.py` mit Original-SHA und `--heading-corner` diagonal gegenüber der Überschrift einarbeiten. Mit `verify` inklusive `--heading-box` kontrollieren; finale PNG unter `media/images/` ablegen.
4. Plattformspezifische Veröffentlichungszeiten auf datierter Studiengrundlage (mindestens zwei Quellen, gegebenenfalls eigene vergleichbare Daten) ermitteln, Europe/Berlin einschließlich Sommer-/Winterzeit exakt nach UTC umrechnen.
5. Ein neues **öffentliches** Manifest `campaign-manifests/YYYY-MM-DD-slug.json` im Format unten ablegen. Jede Quality-Flag darf nur auf `true` stehen, wenn der Test tatsächlich durchgeführt und bestanden wurde. Flags allein sind kein objektiver Beweis für journalistische Richtigkeit – Quellen müssen im Redaktionsprozess geprüft werden.
6. In **einem einzigen Commit** die drei neuen JSON-Dateien `ready-for-buffer/auto-YYYY-MM-DD-slug-{linkedin,facebook,instagram}.json` in exakt Format-2 (`format_version`, `target`, `text`, `media`) anlegen. Die neuere Variante verlangt **keine** individuelle Brief-Vorabfreigabe. Das Drei-Kanal-Qualitätsgate bleibt zwingend, bevor Buffer kontaktiert wird. **Niemals** mit einer neuen automatisch generierten Datei in `ready-to-schedule/` arbeiten.
7. GitHub Actions `buffer-auto-drafts.yml` ruft VOR irgendeinem Buffer-Aufruf `scripts/autonomous_campaign_gate.py` auf. Der neue Sender prüft zusätzlich den vorbereiteten Brief, vollständige Bild-/Textqualität und kanalspezifische Manifesttermine – ohne Vorabgenehmigung. Danach kontrollieren: drei feste Empfangsbelege und je einen unabhängigen Buffer-Readback mit `status=draft` und exakt dem geplanten `dueAt`. Bestehende historische Entwürfe ohne Datum werden nicht rückwirkend verändert.
8. In `campaign-manifests/` gespeicherte `posting_times` sind autorisierte **Terminpläne**, keine freigegebenen Buffer-Publikationsaufträge. Josef erhält eine Übersicht zur einmaligen Freigabe der späteren Veröffentlichung. Eine spätere Aktivierung muss ausschließlich die bestehenden Buffer-Entwürfe mit gegebenenfalls direkt in Buffer vorgenommenen Änderungen verwenden; der bisherige Legacy-Releaseweg ist dafür noch nicht geeignet.

**Achtung GitHub Actions**: Ein Commit eines Workflows mit dem standardmäßigen `GITHUB_TOKEN` löst normalerweise keinen zweiten `push`-Workflow aus. Die neue Integrationsvariante legt geprüfte Kampagnen-Assets und Auto-Draft-Dateien einmalig auf einem isolierten `automation/campaign/<kampagne>`-Branch ab und überträgt sie im selben Orchestrator-Job. Sie pusht keine Bot-Dateien nach `main`. Der ältere direkte `ready-for-buffer/`-Mechanismus ist ein separater Legacy-Pfad.

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

## Aktueller Bildweg für neue KI-Agent-Builder-Kampagnen (20.11.2026)

Der frühere quadratische Drei-Karten-Renderer `scripts/social_visual_from_spec.py` und sein in älteren Tests verwendeter Workflow `social-visual-auto-from-spec.yml` sind **kein aktuell aktivierter Produktionsweg**. Der aktuelle `scripts/social_orchestrator.py` verlangt ausdrücklich eine bereits visuell geprüfte, SHA256-fixierte **4:5-Quelldatei** und verweigert ungeprüfte Karten-Grafiken. Die früheren Techniktests bleiben historische Nachweise, nicht die heutige Ausführungsanleitung.

Der am 20.11.2026 **interaktiv** erfolgreiche Weg ist:

1. Ein neues thematisch passendes, ungebrandetes 4:5-Bild mit ChatGPTs eingebauter Bildfunktion erzeugen. Die Bilddatei muss mindestens 1080×1350 Pixel haben; keine Menschen/Roboter, Fremdlogos oder generierte Beschriftungen. Die tatsächlichen PNG-Bytes und SHA256 lokal prüfen, das Motiv visuell kontrollieren und `visual-reviews/YYYY-MM-DD-slug.json` mit `chatgpt_review` und klarer Kennzeichnung `draft_only` erstellen. Das ist **keine** menschliche Publikationsfreigabe.
2. **Direkter Byteweg ohne Adobe:** Über die aktuell geprüfte GitHub-Verbindung **ausschließlich** `derJosef-agents` das Original-PNG per GitHub-Blob mit `encoding=base64` hochladen und die zurückgegebene Git-Blob-SHA mit `git hash-object` der Originaldatei abgleichen. Die Quelle, das SHA-fixierte Review und genau **ein** vollständiger neuer `orchestration/briefs/YYYY-MM-DD-slug.json`-Auftrag mit `prepared_content` und `execution_mode=drafts` gehören in denselben Branch/PR. Wenn `image_review` bereits auf die beim Merge vorhandene Datei zeigt, ist kein `chatgpt_image`-/Adobe-Import erforderlich.
3. Nach den Required Checks den dafür autorisierten PR nach `main` bringen. Ein **neu hinzugefügter** Brief startet `.github/workflows/social-campaign-orchestrator.yml` und erzeugt auf einem isolierten Output-Branch das Bild mit geprüftem Original-Logo, Bild-Receipt, Manifest und drei Posts. Der Orchestrator sendet sie über den bereits abgesicherten Buffer-Weg **nur als Drafts mit `dueAt`**.
4. Den unabhängigen Readback unter `automation-receipts/orchestration/reports/` auswerten: `state=buffer_drafts_verified`, `buffer_verification.status=PASS`, pro Kanal eine eindeutige Post-ID, `status=draft`, `dueAt`, Bild in Buffer und `published=false`. Ohne diesen Beleg niemals Erfolg melden und keine Mutation blind wiederholen.

**E2E-Nachweis:** [PR #90](https://github.com/derJosef/social-assets/pull/90), [GitHub-Lauf #44725991863](https://github.com/derJosef/social-assets/actions/runs/44725991863) und [unabhängiger Buffer-Readback](https://github.com/derJosef/social-assets/blob/automation-receipts/orchestration/reports/2026-11-20-eu-ai-act-kmu-2026-run-44725991863.json) mit drei echten Drafts (LinkedIn/Facebook/Instagram), korrektem `dueAt` und Bild. **Der vollständig unbeaufsichtigte Montag-/Donnerstag-Lauf mit Bildgenerierung ist damit noch nicht separat bewiesen.** Fehlt dem Hintergrundlauf eine Bild- oder GitHub-Fähigkeit, muss er fail-closed stoppen und den konkreten Blocker melden. Keine zusätzliche kostenpflichtige Modell-API ohne eigene Freigabe.

Der zuvor getestete Adobe-Transfer bleibt ein zulässiger alternativer Bildweg, wenn Original-Bytes und Hash wieder nachweislich übereinstimmen. Weder Adobe noch die direkte GitHub-Übertragung erlauben Queueing, Scheduling oder Publikation ohne Josefs gesonderte Freigabe.

**Nachgewiesener Live-Pilot** (bestehende, ebenfalls verifizierte Grafik): [GitHub-Lauf #37898575725](https://github.com/derJosef/social-assets/actions/runs/37898575725), QA-Gate PASS, drei neue Buffer-Entwürfe. [Statusprüfung #37898698353](https://github.com/derJosef/social-assets/actions/runs/37898698353): alle drei `status=draft`, `dueAt=None`.

## Sicherheitsgrenzen und Tests

- **Autonome Entwürfe** nur für Marke `ai-agent-builder`; nicht für Picture Fix oder Sticken-Lasern.
- **Auto-Quality-Gate** in `scripts/autonomous_campaign_gate.py`: fail-closed, verarbeitet genau eine dreikanalige Kampagne pro Push; kein Buffer-API-Zugriff im Gate. Ungeprüfte Texte, fehlende Bilder, fehlerhafte Zeitrechnungen oder verlorene Logos blockieren den gesamten automatischen Transfer.
- **Legacy-/manuell freigegebene Buffer-Entwürfe** bleiben wie bisher möglich; sie folgen ihren bisherigen Freigaben.
- **Bestehende geplante Posts** bleiben unverändert.
- **Keine Weitergabe von Geheimnissen/privaten Kundenfällen** an das öffentliche GitHub-Repository.
- `scripts/buffer_schedule.py` und `buffer-auto-schedule.yml` behalten die explizite Veröffentlichungsfreigabe; sie dürfen nicht durch autonome Kampagnenerstellung ausgelöst werden.
- Offline: `python3 -B -m unittest discover -s tests -v` und Bildtests in `scripts/test_logo_composite.py`. Das Erstellen einer Demo-Datei im Repo ist **kein** Live-Test des Buffer-Transfers.

Für PersonalOS-Regeln ist `derJosef/personalos@main` die führende Referenz; PersonalOS wird in diesem Workflow ausschließlich lesend verwendet. Keine Schreibvorgänge in lokale PersonalOS-Stände.
