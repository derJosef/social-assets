# PictureFix: wiederverwendbarer Weg in drei datierte Buffer-Entwürfe

**Geltungsbereich:** ausschließlich PictureFix. Bestehender AI Agent Builder,
die Produktions-Bildverarbeitung von PictureFix, PayPal und Wasserzeichen werden
nicht verändert. Dieser Workflow erstellt **nur datierte Buffer-Drafts**;
Josef veröffentlicht nach eigener Prüfung selbst in Buffer.

## Vom Auftrag zum Buffer

1. KI recherchiert eigenständig ein aktuelles relevantes Thema und hinterlegt
   überprüfbare Quellen. Sie schreibt je eine konkrete Facebook-, Instagram-
   und Pinterest-Fassung mit deutschsprachiger Kennzeichnung **„KI-generierte
   Werbeillustration – kein tatsächliches Restaurierungsergebnis.“**
2. KI erzeugt das ungebrandete Motiv im freigegebenen Stil (historische
   Person/Objekt tritt räumlich aus dem alten Foto heraus; epochengerechte
   Gesichter/Kleidung). `scripts.picturefix.brand_artwork` komponiert mit dem
   unveränderten Original `media/brand/PictureFixLogo_Web.png` die endgültigen
   Facebook/Instagram- (1080×1350) und Pinterest-PNGs (1000×1500). Der
   Compositor prüft den originalen Git-Blob-Fingerprint und die exakten
   Logo-Bildpixel. Visuelle Sichtprüfung bleibt zusätzlich verpflichtend.
3. KI legt exakt **vier neue Dateien** über `derJosef-agents` auf einem Branch
   mit PR an: `picturefix/campaigns/PF-NN.json`,
   `picturefix/quality/PF-NN.json`, `media/images/PictureFix_PFNN_Facebook_Instagram_1080x1350.png`,
   `media/images/PictureFix_PFNN_Pinterest_1000x1500.png`.
4. Nach CI, Medienprüfung, Sicherheitsprüfung und Merge per `derJosef-agents`
   löst der **main-Push selbstständig** den PictureFix-Campaign-Workflow aus.
   Das ist kein manueller Issue-Kommentar und kein kampagnenbezogener Code.
   Der Push muss direkt von der berechtigten Agent-Identität erfolgen, nicht
   vom `GITHUB_TOKEN` einer anderen Action (dieser erzeugt keine neue Action).
5. Der GitHub-Action-Job akzeptiert nur einen originalen Push des
   `derJosef-agents` (GitHub-ID 350701981), nur neue Kampagnendateien, und
   ausschließlich PictureFix-Token/-Kanäle. Er prüft *alle* Termine, Dateien,
   Texte, offengelegten KI-Illustrationen und immutable Main-Commit-PNGs,
   bevor er irgendetwas in Buffer anlegt.
6. Jeder Kanal erhält einen **vorher** geschriebenen One-shot-Receipt in
   `automation-receipts`; anschließend wird `createPost` nur mit
   `saveToDraft: true`, `mode: customScheduled` und Bild versendet. Buffer
   wird für jede ID unabhängig wieder abgefragt. Erst die bestätigte
   Kombination aus Kanal, Status `draft`, Text, UTC-Datum und exakt passender
   Bild-URL gilt als Erfolg. Keine automatische Freigabe/Veröffentlichung.
7. Bei unbekanntem API-Status, unvollständiger oder bereits reservierter
   Zustellung: **Stop**, keine automatische Wiederholung der entsprechenden
   Buffer-Mutation. Ein bestätigter Receipt kann bei späterer Prüfung
   nachgelesen werden und verhindert erneute Zustellung.

## Datenvertrag

```json
{
  "version": 1,
  "campaign_id": "PF-04",
  "brand": "picturefix",
  "topic_key": "familienarchiv-geschichte-beispiel",
  "topic": "Aktuelles, recherchiertes Thema mit Begründung",
  "sources": [{"title":"Autoritative Quelle", "url":"https://example.org/source", "accessed_at":"2026-11-20"}],
  "logo_git_blob_sha1": "0cd926e6631209dd4e5c8029dfb72c29bbf89ea8",
  "creative_qa": "picturefix/quality/PF-04.json",
  "posts": {
    "facebook": {"text":"…", "alt_text":"…", "image_path":"media/images/PictureFix_PF04_Facebook_Instagram_1080x1350.png", "image_sha256":"<SHA256>", "due_at_utc":"2026-12-08T11:00:00Z", "due_at_local":"2026-12-08T12:00:00+01:00"},
    "instagram": {"text":"…", "alt_text":"…", "image_path":"media/images/PictureFix_PF04_Facebook_Instagram_1080x1350.png", "image_sha256":"<SHA256>", "due_at_utc":"2026-12-08T17:00:00Z", "due_at_local":"2026-12-08T18:00:00+01:00"},
    "pinterest": {"text":"…", "alt_text":"…", "image_path":"media/images/PictureFix_PF04_Pinterest_1000x1500.png", "image_sha256":"<SHA256>", "due_at_utc":"2026-12-10T09:00:00Z", "due_at_local":"2026-12-10T10:00:00+01:00", "pinterest_title":"…", "pinterest_url":"https://picturefix.de"}
  }
}
```

Die `picturefix/quality/PF-NN.json` enthält `campaign_id`,
`real_picturefix_logo_blob_sha1`, `historical_scene_pops_out: true`,
`period_accurate_faces_and_clothing: true`,
`ai_ad_illustration_not_a_restoration: true` und
`artwork_sha256.facebook_instagram`/`artwork_sha256.pinterest`.

Das Paket enthält das **einmalig geprüfte Original-Logo** (Git Blob
`0cd926e6631209dd4e5c8029dfb72c29bbf89ea8`) unter
`media/brand/PictureFixLogo_Web.png`. Für beide Illustrationen sind folgende
Kommandos vorgesehen (mit vorher visuell geprüften Source-PNGs):

```bash
python3 -m scripts.picturefix.brand_artwork --variant facebook_instagram \
  --source /PF04-fb-source.png \
  --out media/images/PictureFix_PF04_Facebook_Instagram_1080x1350.png
python3 -m scripts.picturefix.brand_artwork --variant pinterest \
  --source /PF04-pin-source.png \
  --out media/images/PictureFix_PF04_Pinterest_1000x1500.png
```

Die Bild-Pixelprüfung erzwingt ein echtes Logo auch dann, wenn jemand
Manifest und Hashwerte gleichzeitig verändern würde. **Echte Bildansicht**
und gegebenenfalls Korrektur vor Merge bleiben notwendig, um historische
Korrektheit und den räumlichen Effekt zu gewährleisten. Die Bildbytes,
Abmessungen, Checksummen und Buffer-Rücklesung werden zusätzlich technisch
geprüft.

## Noch getrennt abzusichern

- Eine autonome Recherche-/Bildgenerierung mit tatsächlich laufendem
  ChatGPT-Scheduler braucht einen **eigenen End-to-End-Probelauf**. Dieser
  Workflow automatisiert zuverlässig die Strecke ab einem korrekt gemergten
  Kampagnenpaket. Ein Scheduler oder eine kostenpflichtige Bild-API wird hier
  **nicht** stillschweigend eingerichtet.
- Ein vollständiger Live-Probelauf muss in Buffer **3/3** drei unterschiedliche
  IDs mit Bildern, korrekten Daten und Status `draft` nachweisen. Bis dahin
  ist die End-to-End-Autonomie **noch nicht nachgewiesen**.
