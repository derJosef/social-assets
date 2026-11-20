# PF-03 – Wer kennt die Geschichten hinter den Fotos?

Recherche und Vorbereitung: 20.11.2026, Europe/Berlin. Ziel: drei **datierte Buffer-Entwürfe**, nicht Veröffentlichungen. Alle Freigaben für eine Veröffentlichung liegen allein bei Josef.

## Redaktionelle Idee und Belege

Das Alte-Fotos-Thema ist unabhängig von PF-02: Dort ging es um Digitalisierung und UNESCO-Kulturerbe; hier steht das **Wissen hinter dem Foto** im Mittelpunkt. Ein Bild ohne Namen, Aufnahmeort, zeitlichen Kontext und Erinnerung verliert oft seinen wichtigsten familiären Wert.

- Library of Congress, [Family History for Kids: Family Photographs](https://guides.loc.gov/family-history-for-kids/photographs), am 20.11.2026 geprüft: Namen, Datum, Ort und gemeinsame Gespräche können aus einem Bild einen Startpunkt der Familiengeschichtsforschung machen.
- Udruga Hrvatski obiteljski korijeni, [How to Preserve and Digitise Old Family Photos](https://obiteljskikorijeni.hr/en/guides/preserving-old-photos-documents/), aktualisiert 20.10.2026: empfiehlt, ältere Angehörige jetzt nach den Geschichten und Identitäten auf Fotografien zu fragen und Digitalisate mit Erläuterungen zu verknüpfen.
- Australian Institute of Aboriginal and Torres Strait Islander Studies, [Family History Kit](https://aiatsis.gov.au/sites/default/files/2025-10/aiatsis-family-history-kit-feb-2021.pdf), als ergänzende institutionelle Quelle: alte Fotos bei Verwandten zeigen und fragen, wer, wo, wann und was geschah. Keine KI-Gesichtserkennung oder unbelegte Identitätszuschreibung.

Konkreter Aufruf: Ein altes Familienfoto bei einem persönlichen Besuch mit Angehörigen besprechen; Namen, Ort, Jahr und Erzählung zusammen mit dem Scan archivieren. PictureFix nur für behutsame digitale Bildverbesserung nennen, keine Ergebnisgarantie.

## Historische Werbeillustrationen und überprüfbarer Markenbezug

- Zwei neu erzeugte, voneinander unterscheidbare Werbeillustrationen, aber ein freigegebener Bildstil (authentische 1950er-Jahre-Großmutter und Enkelin, echtes gealtertes Papierfoto, plastisches Herausragen der Figuren, Sepia).
- Realistisches zeittypisches Haar, Wollkleidung und häusliches Milieu statt moderner Gesichter/Kleidung. **Kein tatsächliches historisches Original, keine restaurierte Kundenaufnahme, kein Vorher/Nachher-Beweis.** Dieser Hinweis steht in jedem Plattformtext und Alt-Text und als PNG-Metadaten-Description.
- Das unveränderte Original-PictureFix-Logo wurde als Bilddatei mit Git-Blob-SHA1 `0cd926e6631209dd4e5c8029dfb72c29bbf89ea8` geprüft und erst danach programmgesteuert eingefügt. Kein KI-generierter Logo-Nachbau. Pixel außerhalb der klar begrenzten Logobox nicht nachbearbeitet.
- Facebook & Instagram: `media/images/PictureFix_PF03_Facebook_Instagram_1080x1350.png`, SHA-256 `9e2a4e8340c155d568a8cd3d39f86f320651d83473db8421e45f6c2b62cc37bd`, Git-Blob `67c5442217f18e6225417cd1a8ffd93d495330b4`.
- Pinterest: `media/images/PictureFix_PF03_Pinterest_1000x1500.png`, SHA-256 `0e008d198a3eeccf593333ffd600c586155f18bfa4cf1c63560300022656033c`, Git-Blob `737211a9f6e670d694947ccb3a25d7964abaf288`.
- Medien-Commit mit unveränderlichen URLs: `15554013fc2e4b188c26b478b4e7b596684eecb8` (PR #89). Auf GitHub die korrekte Größe und den Git-Blob-Hash beider PNGs unabhängig ausgelesen.

## Veröffentlichungsvorschläge – nur bei späterer Freigabe

Aktuelle Studien am 20.11.2026 erneut aufgerufen. Kein ausreichendes eigenes Konto-Engagementprofil; die vorgeschlagenen Zeiten sind Hypothesen. Die PF-01- und PF-02-Termine im November 2026 bleiben unberührt.

| Kanal | Europe/Berlin | UTC | Quellen und Abwägung |
| --- | --- | --- | --- |
| Facebook | Di., 01.12.2026, 12:00 MEZ | `2026-12-01T11:00:00Z` | Sprout Social 2026 meldet für Dienstag/Mittwoch 12–20 Uhr; Buffer 2026 favorisiert eher frühe Werktagsstunden. 12 Uhr liegt im belegten Sprout-Fenster und vermeidet den 25.11. Buffer 2026: https://buffer.com/resources/best-time-to-post-on-facebook/ ; Sprout 2026: https://sproutsocial.com/insights/best-times-to-post-on-facebook/ |
| Instagram | Di., 01.12.2026, 18:00 MEZ | `2026-12-01T17:00:00Z` | Buffer September 2026 meldet starke Werktags-Abende, besonders Mittwoch 18 Uhr; Sprout 2026 sieht Werktags-Nachmittag. Dienstag 18 Uhr ist ein vertretbarer naher Test, keine plattformspezifische Gewissheit. https://buffer.com/resources/when-is-the-best-time-to-post-on-instagram/ ; https://sproutsocial.com/insights/best-times-to-post-on-instagram/ |
| Pinterest | Do., 03.12.2026, 10:00 MEZ | `2026-12-03T09:00:00Z` | Sprout Social 2026 nennt Di–Do 10–13 Uhr; Hootsuite 2026 bevorzugt Donnerstagabend. Morgens gewählt, da die Suchbarkeit/Qualität des Pins im Vordergrund steht. https://sproutsocial.com/insights/best-times-to-post-on-social-media/ ; https://blog.hootsuite.com/pinterest-statistics/ |

## Technische Übertragung und Grenzen

Die drei JSON-Briefs liegen unter `drafts/picturefix-pf03-*.json`; jeder referenziert ausschließlich den verifizierten PNG-Commit. Neuer isolierter Runner `scripts/picturefix/pf03_dated_drafts.py` und Workflow `.github/workflows/picturefix-pf03-dated-drafts.yml` verwenden den vorhandenen Buffer-Adapter; sie nehmen nur die exakt erlaubten neuen PF03_Issue-Kommandos von `derJosef-agents` auf Kontroll-Issue #64 an. Kein PF-01-/PF-02-Replay und kein AI Agent Builder-Trigger. One-shot-Receipt vor der Buffer-Mutation, nie automatisch wiederholen. Buffer `createPost` mit `saveToDraft: true` und festem `dueAt`; danach separater Buffer `post(id)`-Readback mit ID, Kanal, Text, Asset-URL, Status `draft`, `dueAt` und `shareMode`. Bei Unsicherheit Stop mit Pending-Receipt. Keine Buffer-Queue, keine Veröffentlichung.

Keine Änderungen an PersonalOS, produktiver Bildverarbeitung, Wasserzeichen, PayPal, AI Agent Builder oder bestehenden PF-01-/PF-02-Assets und Workflows.
