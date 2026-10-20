# Multi-Brand Content Engine – Architektur und Übergabe (20.10.2026)

Status: **Implementierungsgrundlage im Draft-PR, keine produktive Aktivierung.**
Diese Datei dokumentiert das gemeinsam beschlossene Grundprinzip und den gegenwärtig eingebauten Offline-Vertrag. Sie ist keine Änderung von PersonalOS.

## Architekturentscheidung

**Eine Engine pro Fähigkeitstyp – nicht ein GitHub-Workflow pro Marke.**
Die drei getrennt auslösbaren JOBARTEN sind:
1. `social`: aktuelle Recherche, belegte Kanaltexte und 4:5-Bild -> zielmarkenspezifische unveröffentlichte Entwürfe (für AI Agent Builder heute Buffer).
2. `news`: denselben recherchierten Sachverhalt optional in eine eigenständige Website-News mit unveränderlicher 16:9-, 4:3- und 1:1-Bildfamilie überführen; Redaktion und Website-Freigabe getrennt.
3. `rotation`: einmal wöchentlich je freigegebenem Website-Menübereich ein **anderes neues Motiv** entwickeln, Desktop/Mobil getrennt gestalten, auf der Testseite vorschauen und nach gesonderter Freigabe freischalten. News-Artikelbilder bleiben davon ausgenommen.

Gemeinsame wiederverwendbare Funktionen: Markenprofil-Lader, Quellen-/Fakten-Gate, Promptbriefing, isolierte Bildgenerierung, technische Bildformate, unveränderte markenspezifische Original-Logos, Plagiat-/Dublettenprüfung, QA, Freigabe-/Status-Ledger und Benachrichtigungen. Unterschiedliche Auftragsarten laufen **unabhängig**; ein Bildfehler darf nicht Buffer und andere Marken mit blockieren.

## Profile, Formate, Markenidentität

`automation/multibrand/brands.json` ist eine **öffentliche, secret-freie Pilotkonfiguration**. Bei jedem Auftrag werden `brand_id` **und** `kind` explizit benötigt; es gibt **keinen Standardmarken-Fallback**. `scripts/multibrand_contract.py` validiert die Profile und erstellt nur einen deterministischen, lesenden Ausgabeplan. Es erzeugt derzeit keine Motive, Posts, Dateien in Buffer oder Website-Deployments.

- **AI Agent Builder / pauderer.de:** bestehende Marke und drei aktuelle Buffer-Kanäle. Nur hierfür gilt die dokumentierte dauerhafte Erlaubnis für **Buffer-Drafts** einschließlich künftiger `dueAt`-Werte, jedoch nie für Veröffentlichung. Website-Publizieren bleibt separat.
- **PictureFix / picturefix.de:** Eigenständige Marke, Logo-/Sprachregeln, Kanäle, Rechte und Website-Zugang sind vor produktiver Nutzung zu prüfen; keine aus AI Agent Builder geerbten Berechtigungen.
- **Sticken & Lasern:** Eigenes Logo; **niemals automatisch das Logo von Josef**. Die im Chat genannte Domain-Schreibweise „stücken-lasern.de“ weicht vom bekannten Markennamen ab. Domain deshalb bis zur belegten Zuordnung `null`.
- **Präzisionsarmaturen:** Eigenständige Inhalte und Website. Die mögliche Verwendung von Josefs ursprünglichem Logo ersetzt keine eigenen Produkt- und Freigaberegeln. Website-Repository/Zielanbindung nicht behaupten.

Produktionsdateien, Bild-Hashes, Metadaten, Briefs, Prüfreports und Zustände müssen künftig unter `generated/<brand_id>/<kind>/<run_id>/` unverwechselbar getrennt werden. Konfigurationen enthalten keine API-Schlüssel, Kundendaten oder Zugangstokens. Für echte produktive Multi-Mandanten-Sicherheit zusätzlich **technische** Isolation mit eigenen GitHub-Environments/Secrets und zur Marke geprüften Zielkanal-IDs erzwingen; ein JSON-Flag ist keine Zugangskontrolle.

Für AI Agent Builder sind nur folgende Outputformate als Pilot festgelegt:
- Social 4:5: **1080 × 1350 PNG**
- News-Desktop: **1672 × 941 WebP** (16:9 näherungsweise)
- News-Mobil: **1200 × 900 WebP** (4:3)
- News-Vorschau: **800 × 800 WebP** (1:1)
- Website-Rotation Desktop: **1672 × 941 WebP**
- Website-Rotation Mobil: **1080 × 1920 WebP**
- Sieben Bereiche: **Startseite, Leistungen, Projekte, Prozessanalyse, Arbeitsweise, Über mich, Kontakt** = sieben neue Motive, **14 Ausgabedateien pro Woche**. Mobile/desktop dürfen eigene Kompositionen aus demselben Motiv verlangen; kein blindes Strecken.

## Ausführungskontrakt und QA

```text
Ausloeser (brand_id, job_kind, eindeutige run_id)
  -> Markenprofil (Pflichtfelder, Berechtigungsnachweis, korrektes Logo)
  -> Recherche/Briefing und belegte Quellen, getrennte Jobs
  -> Bild-/Textproduktion, gegebenenfalls Variantenkomposition
  -> Hash/Pixelformat/Dubletten/Marken- und Rechtsprüfung
  -> geprüfter unveränderlicher Artefakt-/Review-Beleg
  -> Empfängeradapter: Buffer-Draft | Website-News-Vorschau | Website-Rotationsvorschau
  -> unabhängiger Readback und menschlicher Freigabepunkt
  -> Push-Nachricht mit echtem Status und Link
```

Die Jobdaten enthalten keine gemischten Marken und dürfen ihre `brand_id` während eines Laufs nicht ändern. Für jede Marke eigene Logo-SHA und/oder getrennt bestätigtes Markenasset, Zielkanäle nur nach bestätigter Zuordnung. Logo darf nicht generativ gezeichnet werden.

**Social Media**: Fehlende Bild-/Adobe-Übertragung stoppt vor Kampagnenissue und Buffer. Echte Drafts mit exakten Post-IDs und Readback gelten als PASS; Datum als `dueAt` im Draft bedeutet keine Freigabe zur Veröffentlichung. Veröffentlichungen erfolgen ausschließlich nach Josef-spezifischer Freigabe je Beitrag. `AI Agent Builder`-Sonderberechtigung nicht auf andere Marken übertragen.

**Website-News**: Artikel und Bildfamilie erhalten eine feste Versions-/Asset-ID. Wöchentliche Rotation darf News-Bilder niemals ersetzen. Kein News-Publish durch das Social-Media-Gate.

**Menübilder**: Vorhandener PR #28 in `derJosef/pauderer-de-website` ist eine **sechswöchige Rotation eines vorbereiteten Bildpools**, nicht eine wöchentliche Neuerzeugung. Er wurde separat auf `seppls.de` getestet und ist nach Dokumentation Draft ohne Live-Merge. Der spätere Generator muss einen unabhängigen Ausgabepool anlegen, Startseite als eigenen Bereich behandeln und vorhandene Originale/Fallbacks unangetastet lassen. Für jedes Bild: Hash, Bildqualität, echter Dateinachweis und tatsächlicher Responsivtest vor dem Wechsel.

**Unbeaufsichtigte Bildgenerierung/Adobe**: Interaktiver Erfolg beweist keine Funktion in einem Scheduled-Task. Die bestehende Bildtransfer-Blockade ist nicht als behoben nachgewiesen; keine neue kostenpflichtige API und kein Workaround eines Tool-Sicherheitsblocks. Erst echter E2E-Smoke für AI-Agent-Builder samt Buffer-Readback; zusätzliche Adapter später einzeln integrieren.

## Rhythmus und Benachrichtigungen

- AI-Agent-Builder-Socialproduktion **montags und donnerstags** (max. zwei Themen pro Woche).
- Einmalige unabhängige `rotation`-Produktion künftig **freitags**; Vorschau-/Abnahme vor geplanter Aktivierung montags. Der Job wird **noch nicht** als produktiv aktiviert.
- `news` entsteht bei relevanten passenden Themen, nicht zwangsläufig bei jeder Rotationsproduktion; eigene redaktionelle Freigabe.
- Push auf dem Mobiltelefon ist durch einen einmaligen ChatGPT-Test bestätigt. Die Aktivierung der Push-Zustellung für jede einzelne neue Automationsaufgabe muss separat kontrolliert werden; Offline-Konfigurationsdateien können sie nicht einschalten.

## Abnahmephasen

1. **Jetzt in diesem PR:** getrennte Profile und Jobtypen, sichere Ausgabe-Namensräume, Rechte-Matrix und Offline-Tests; keine Änderungen an bereits aktiven Social Actions.
2. **Bestehenden Buffer-E2E vollenden:** ChatGPT-Bild -> zulässiger Dateitransport -> SHA-geprüfter GitHub-Import -> Logo -> drei echte Buffer-Drafts -> unabhängige PASS-Receipts.
3. **Website-News-Adapter:** responsive Bildausgaben, feste Asset-ID, Test-Newsseite, getrennte Freigabe, kein Live-Publish im Test.
4. **Website-Rotation-Generator:** neue Motive/QA mit getrenntem Startseiten-Pool, Testseite, Benachrichtigung, Freigabe, erst dann Rollout.
5. **Weitere Marken onboarden:** je Marke Profil, Quellen-/Logo-/Kanalregeln, technische Secrets-Isolation, Ziel-Repository, explizite Draft- und Veröffentlichungserlaubnisse, Ersttest und eigenen Readback.

## Architekturprüfung nach sechs Hüten

- **Weiß:** Social-Orchestrator und Website-Rotation sind im Ist-Code unterschiedliche Komponenten; keine nachgewiesene unbeaufsichtigte Universal-Bildgenerierung.
- **Rot:** Josef möchte einen einzigen überschaubaren Bedienweg, ohne bei Markenwechseln Konten und Abläufe zu verwechseln.
- **Schwarz:** Gemeinsamer monolithischer Workflow kann bei Fehlern alle Marken blockieren; ungeprüfte Channel-IDs, Logos oder geerbte Berechtigungen sind unzulässig.
- **Gelb:** Wiederverwendbare Prüfer und Ausgabeverträge senken Pflegeaufwand, ohne je Marke eigene GitHub Actions zu duplizieren.
- **Grün:** Gemeinsames Content-Paket als Quelle für Social und News, mit separaten Abnahme- und Release-Adaptern; Hero-Motive unabhängig.
- **Blau:** Erst fail-closed gemeinsamer Vertrag und Offline-CI, danach markenweise Anbindung mit unveränderten Freigabegrenzen.

Quellen: GitHub `derJosef/social-assets` aktueller `social-campaign-orchestrator.yml` und `AUTONOMOUS_BUFFER_POLICY.md`; `derJosef/pauderer-de-website` PR #28; read-only PersonalOS `skills/josefs-marke/SKILL.md` und `system/rules/core/social-media-planung-mit-recherche.md`.
