# PictureFix PF-01 → Buffer: geprüfte Entwürfe statt Veröffentlichung

Stand: 2026-11-07. Nur eine **technische Erweiterung** von `scripts/buffer_draft.py` und der **bestehenden** `.github/workflows/buffer-draft.yml`. Kein zweiter Buffer-Adapter. Quelle: `derJosef/agent-workspace` PR #71, Stil PR #64, Social-Copy PR #65, gesonderter Website-Artikel-Entwurf PR #70.

## Historisch geprüft; nicht mit Produktionsabnahme verwechseln

- Die Buffer-Free-Organisation **PictureFix** hat laut Codex-Handoff vom 06.11.2026 3/3 verbundene Kanäle: Facebook Page `PictureFix Fotorestaurierung`, Instagram Professional `picturefix.de`, Pinterest Business `picturefixde`. Das ist **kein** API-Token-, Kanal-ID- oder Post-Readback-Nachweis.
- Original-Logo unverändert in `derJosef/picturefix-de-website@main/app/public/assets/brand/PictureFixLogo_Web.png`, Git-Blob-SHA-1 `0cd926e6631209dd4e5c8029dfb72c29bbf89ea8`; Bildbytes sind **nicht** aus dem AI-Agent-Builder-Logo abzuleiten. Das Original-Logo muss nicht in diesem öffentlichen Repository dupliziert werden.
- Freigegebene Illustration `a_realistic_cinematic_vintage_photo_styled_illust.png`: SHA-256 `a6856a58c56bbe2789a4bf825ce428ea5a5ae7c59cc4d94708735f6a1e8bb333`. Die beiden **ohne** Original-Logo erstellten PNGs sind im PF-01-Dokument mit SHA-256 verzeichnet. Original-Bytes liegen im ChatGPT-Social-Media-Projekt; am 07.11.2026 schlug `files.materialize(raw_file)` auf Originalmotiv, Entwurfs-ZIP und Bibliothekslogo mit `This Project file does not have an authorized raw-byte materialization path` fehl. Ohne erlaubte Bytes **keine** stille Nachgenerierung, keine unbewiesene Bildübernahme.
- GitHub-Connector von ChatGPT bietet einen Schreibweg für Branch/PR/Issue-Kommentar, **nicht** für `workflow_dispatch`. Das ist eine Werkzeuggrenze, kein Beleg eines Buffer-Ausfalls.

## Phase 1 – Originalbilder bytegenau sichern (blockiert, wenn nicht autorisiert lesbar)

1. Auf einem autorisierten Rechner/Agenten oder durch eine direkt im aktuellen Chat hochgeladene Originaldatei die **tatsächlichen Bytes** von `PictureFix_Post_01_Entwurfspaket.zip` oder den beiden unveränderten PNGs beschaffen. Keine Library-API-Umgehung. Im ZIP ausschließlich reguläre Dateien, kein ZIP-in-ZIP. Soll-Hashes:
   - Facebook/Instagram, 1080×1350: `93c33a57e070626427c43e68327041a7b5c5a648256f045ccace793802ea7a92`.
   - Pinterest, 1000×1500: `77c977abebd8d8b420586fe0efd16590eab08e4908434d4aded51c039586fcbe`.
2. Original-Logo aus der **berechtigten GitHub-Quelle** beziehen; live Blob-SHA + Dateiintegrität prüfen. Niemals nachzeichnen/generieren.
3. Vorhandenen Renderer `scripts/picturefix/pf01_render_verified.py` mit den beiden unveränderten Entwürfen und Original-Logo ausführen; Renderer prüft vor jedem Output exakte Fingerprints, Bildabmessungen, unveränderte Bildpixel außerhalb der Logo-Fläche und erstellt flaches QA-Paket. Die visuelle Sichtprüfung (auch Illustrationskennzeichnung) bleibt separat erforderlich.
4. Finale 1080×1350-PNG `PictureFix_PF01_Facebook_Instagram_1080x1350_zur_Freigabe.png` mit tatsächlichem SHA-256 im **bestehenden** öffentlichen `derJosef/social-assets/media/images/` über autorisierten Branch/PR dauerhaft sichern; anschließend **Git-Blob und Dateibytes unabhängig zurücklesen**. Keine Platzhaltergrafik, keine behauptete SHA ohne die echten Bytes. Für Pinterest das ebenfalls im vorhandenen Renderer erzeugte finale `PictureFix_PF01_Pinterest_1000x1500_zur_Freigabe.png` eigenständig in `media/images/` sichern und auf **1000×1500** und SHA-256 prüfen. Der Buffer-Adapter unterstützt die dritte PictureFix-PF01-Entwurfsvariante auf dem PR-Branch; es erfolgt vor dem echten `createPost` eine Buffer-Pinnwandprüfung.
5. Den **vollständigen** Commit-SHA der finalen Public-Media-Datei als unveränderlichen URL-Ref verwenden (kein `main`-Ref im PictureFix-Draft).

## Phase 2 – getrennte PictureFix-API-Berechtigungen (noch nicht verifiziert)

- Nur aus der autorisierten PictureFix-Buffer-Organisation den eigenen Token und die **expliziten Kanal-IDs** ermitteln. GitHub-Actions-Secrets **`BUFFER_PICTUREFIX_API_KEY`**, **`BUFFER_PICTUREFIX_FACEBOOK_CHANNEL_ID`**, **`BUFFER_PICTUREFIX_INSTAGRAM_CHANNEL_ID`**, **`BUFFER_PICTUREFIX_PINTEREST_CHANNEL_ID`** sowie **`BUFFER_PICTUREFIX_PINTEREST_BOARD_SERVICE_ID`** durch zuständigen Berechtigten setzen. Secret-Inhalte nie in PR, Issue, Logs oder `brand.json`. **Keine** Übernahme von `BUFFER_API_KEY` / AI-Agent-Builder-Secrets. Der bestehende AI-Agent-Builder-Job behält seine bisherige Umgebung.
- Neue Secrets und PictureFix-Channel-ID-Zuordnung gehören zum GitHub-Repo-`social-assets`. Bei fehlender Berechtigung zum Setzen der Secrets nur diesen Freigabepunkt melden, kein anderes Konto oder Credential nutzen.
- Der ungemergte `social-assets` Multi-Marken-Entwurf PR #41 ist keine aktive produktive Markenisolierung; seine Regeln nicht duplizieren. Der bestehende Buffer-Adapter enthält hier nur den minimalen fest adressierten PictureFix-PF01-Pilot-Gate.

## Phase 3 – exakt drei formatierte PF-01-Drafts vorbereiten

Dateinamen **`drafts/picturefix-pf01-facebook.json`**, **`drafts/picturefix-pf01-instagram.json`** und **`drafts/picturefix-pf01-pinterest.json`**. Erst **nach** Phase 1 aus tatsächlich vorhandenem finalem Bild erzeugen. Schema `format_version: 3`; Schlüssel **genau**:

```json
{
  "format_version": 3,
  "brand": "picturefix",
  "target": "facebook",
  "text": "<Plattformtext aus dem noch nicht veröffentlichten PF-01-Textentwurf PR #65, inklusive Werbeillustrationshinweis>",
  "media": {
    "type": "images",
    "images": [
      {
        "url": "https://raw.githubusercontent.com/derJosef/social-assets/<ECHTER_40_STELLIGER_GIT_COMMIT>/media/images/PictureFix_PF01_Facebook_Instagram_1080x1350_zur_Freigabe.png",
        "alt_text": "KI-generierte Werbeillustration – kein Restaurierungsbeispiel."
      }
    ]
  },
  "image_sha256": "<ECHTER_SHA256_DER_FINALEN_PNG>",
  "logo_git_blob_sha1": "0cd926e6631209dd4e5c8029dfb72c29bbf89ea8"
}
```

Für Instagram `target` und Text aus PR #65 separat einsetzen. Für Pinterest `target: "pinterest"`, die abweichende finale Bilddatei `PictureFix_PF01_Pinterest_1000x1500_zur_Freigabe.png` mit **echtem gepinntem Commit und eigenem SHA-256**, den Pinterest-Text von PF-01 sowie die zusätzlichen Pflichtfelder `"pinterest_title": "Kleine Fotos, große Erinnerungen – alte Familienfotos bewahren"` und `"pinterest_url": "https://picturefix.de"` verwenden. Das Pinterest-Board ist **kein Freitext- oder willkürliches Eingabefeld**: den für den tatsächlich mit PictureFix verbundenen Kanal gemeldeten `metadata.boards[].serviceId` prüfen und nur die zutreffende Pinnwand über das separate GitHub Secret `BUFFER_PICTUREFIX_PINTEREST_BOARD_SERVICE_ID` zulassen. Fehlendes Board blockiert vor dem Buffer-Schreibaufruf. Offizielle Quelle: <https://developers.buffer.com/types/PinterestPostMetadataInput.html>. **Die Platzhalter sind NICHT ausführbar** und dürfen niemals als echte Hashes/URLs ausgegeben werden. Beide Dateien mit ihrem Bild im Branch prüfen und als PR mergen lassen. Keine `dueAt`, `scheduled`- oder Publikationsfelder. Website-Artikel **PFG-01 bleibt ein eigenständiger Website-Entwurf**; kein erfundener Artikel-Link.

## Vereinfachter Kanal- und Pinnwandnachweis (07.11.2026)

Der PictureFix-spezifische Buffer-API-Key **ist in GitHub erfolgreich als Secret vorhanden**: echte read-only Action <https://github.com/derJosef/social-assets/actions/runs/42372149609> meldete, dass der Key gesetzt ist, aber die vier separaten Kanal-/Pinnwand-IDs leer sind. Ein vorangegangener Lauf #42372037928 wurde noch vor Jobstart abgebrochen; daraus keine API-Aussage ableiten.

**Neue minimalinvasive Wiederherstellung auf geprüftem Branch:** Die bestehenden Kanal-IDs müssen künftig **nicht mehr manuell als Secrets** hinterlegt werden, sofern Buffer über den **eigenen PictureFix-Token** diese eindeutig zurückgibt:
- Exakt **eine** Organisation namens `PictureFix` mit `channelCount = 3`.
- Exakt drei aktive, nicht gesperrte Kanäle mit Namen `PictureFix Fotorestaurierung` (Facebook), `picturefix.de` (Instagram) und `picturefixde` (Pinterest), alle derselben Organisation zugeordnet.
- Kein anderes Konto oder zusätzliche Profile; jede Abweichung blockiert den API-Write. Falls optionale, früher hinterlegte Kanal-IDs vorhanden sind, müssen sie exakt mit dem Live-Ergebnis übereinstimmen.
- Pinterest: Bei **genau einer** per API mit dem PictureFix-Kanal verifizierten Pinnwand wird diese automatisch verwendet. Bei mehreren Pinnwänden bleibt das separate Secret `BUFFER_PICTUREFIX_PINTEREST_BOARD_SERVICE_ID` **erforderlich**, um eine Fehlzuordnung zu vermeiden. Keine Ausgabe von geheimen Token- oder API-Kanal-IDs in öffentlich lesbaren Workflow-Logs.
- Der `PF01_PREFLIGHT_ONLY`-Check läuft weiterhin ohne Medien und ohne Schreibmutation. Die drei tatsächlichen Draft-Triggers bleiben unverändert auf Issue #64 beschränkt.

Damit wird die frühere technische Forderung nach fünf manuell zu pflegenden GitHub-Secrets zu einem **dedizierten PictureFix-API-Key** plus nur bei mehrdeutiger Pinnwand einer expliziten Boardauswahl reduziert. Diese Änderung lässt die vorhandenen AI-Agent-Builder-Buffer-Pfade unverändert, keine Generierungs-, Restaurierungs-, Slider- oder Zahlungslogik angefasst.

**Die Produktionsabnahme kann erst nach echtem erfolgreichem Preflight und später Buffer-Draft-Readback bestätigt werden.** Kein automatischer Buffer-Draft durch den Preflight. Dokumentation: <https://developers.buffer.com/guides/data-model>, <https://developers.buffer.com/types/Channel.html> und <https://developers.buffer.com/types/PinterestPostMetadataInput.html>.

## Phase 3a – PictureFix-Konto vor dem Bildtransfer nur LESEND prüfen

Nach dem Merge der bestehenden Integrationsänderungen kann über das Steuer-Issue `derJosef/social-assets/issues/64` der Kommentar **`PF01_PREFLIGHT_ONLY`** als `derJosef-agents` abgesetzt werden.

Das startet nur den neuen **read-only Job innerhalb der bestehenden Buffer-Action** mit `contents: read`, `persist-credentials: false` und dem separat in GitHub hinterlegten `BUFFER_PICTUREFIX_API_KEY`. Er prüft über die offizielle Buffer-API die drei explizit hinterlegten PictureFix-Kanal-IDs, den Kanaltyp und die gewählte Pinterest-Pinnwand. Er braucht **kein Bild**, erzeugt **keinen Entwurf**, reserviert **keinen** Receipt und stellt **keinen** Schedule oder Queue-Eintrag her.

Der Befehl ist absichtlich vom eigentlichen Draft-Trigger getrennt; er lässt sich aus dem verwendeten GitHub-Connector per Issue-Kommentar auslösen, obwohl `workflow_dispatch` dort nicht verfügbar ist. Ein Fehlstatus belegt **nur den exakten Preflight-Fehler**, niemals einen bereits erfolgten Buffer-Upload. Wurde der API-Key noch nicht eingerichtet, muss der Berechtigte ihn einmalig im PictureFix-Buffer-Konto unter `https://publish.buffer.com/settings/api` erstellen und als GitHub-Action-Secret hinterlegen – niemals im Chat, Issue oder PR. Der erste gültige Readback ist Pflicht vor jedem Entwurfsversand.

## Phase 4 – bestehende GitHub-Action über Issue-Kommentar auslösen

Die bestehende `buffer-draft.yml` hat nun neben `workflow_dispatch` einen **streng auf Issue #64 und die Identität `derJosef-agents` eingeschränkten** `issue_comment`-Trigger; kein neuer Workflow. Der Kommentar allein aktiviert keine Veröffentlichung.

1. Erst nach Merge **dieser** Änderungen und des echten Bild-/JSON-Pakets auf `main` den vollständigen Trigger `PF01_FACEBOOK_DRAFT_ONLY` als Agentenkommentar unter `derJosef/social-assets/issues/64` erstellen. In der Action muss ausschließlich der `picturefix-preview`-Job starten und aus `main` ausführen. `workflow_dispatch`/AI-Agent-Builder-Job darf bei Kommentaren nicht starten.
2. Vor erneutem Kommentar **zuerst** GitHub-Receipt auf `automation-receipts`, Workflow-Lauf und **Buffer** prüfen: der Kern legt vor dem `createPost`-API-Aufruf eine dauerhafte Reservierung an. Bei unklarer Rückgabe niemals blind erneut auslösen.
3. Nur nach bestandenem ersten Readback: `PF01_INSTAGRAM_DRAFT_ONLY` als zweiten getrennten Kommentar auslösen. Nach zweitem Readback und Pinterest-Board-Prüfung: `PF01_PINTEREST_DRAFT_ONLY` als dritten getrennten Kommentar auslösen.
4. Alle drei POST-IDs, exakte PictureFix-Kanal-IDs, Buffer `status=draft`, `dueAt=null`, Original-Image-SHA256 und Buffer-`assets[0]` aus einer unabhängigen Buffer-`post(id)`-Abfrage nachweisen. Receipt-Zustand `verified_unpublished_draft_with_image` gilt nur **nach** Buffer-Readback. Keinen Link zu einem vermeintlich direkt verlinkbaren Buffer-Editor erfinden: für die visuelle Prüfung `https://publish.buffer.com` im **PictureFix-Konto** und die jeweiligen Facebook-/Instagram-`Drafts` öffnen.
5. Kein Queue/Schedule/Publish, auch kein automatischer PFG-01-Artikeltransfer. Gelingt ein Prüftor nicht, Status `blocked` mit exakter Fehlerklasse, PR-/Run-Link und unverändertem Beleg melden.

## Pflichtprüfung

`python3 -B -m unittest discover -s tests -p 'test_picturefix_buffer_bridge.py' -v` sowie `python3 -B -m unittest discover -s tests -p 'test_picturefix_pinterest_bridge.py' -v` und vollständige vorhandene Offline-Suite auf dem PR. **Echter E2E nur mit echten Bildbytes, echten PictureFix-Secrets und Buffer-Rücklesen**, niemals aus Offline-Tests oder einer Action-Success-Anzeige ableiten. Original-Handoff auf `agent-workspace` PR #71 ist weiterhin führend für den Auftrag; kanonische Projekt-/Freigaberegeln liegen im PersonalOS.
