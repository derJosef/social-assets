# Website-News aus bestehenden Postings: verbindliches Herkunfts- und Freigabe-Gate

**Stand 20.10.2026, Draft-PR #41 – Offline-Tests bestanden, nicht produktiv aktiviert.**

## Anlass: konkreter Fehlgriff vom 20.10.2026

In `derJosef/pauderer-de-website` [PR #29](https://github.com/derJosef/pauderer-de-website/pull/29) wurden alte `main/media/images`-Dateien aus den 09./10.10.2026 ohne Status-/finale Bildprüfung übernommen. Der Text gehörte teils zu alten Buffer-Drafts ohne Veröffentlichung; die Bildversion der später tatsächlich publizierten Kampagne „Wer liest bei deinem KI-Chat mit?“ stammte **nicht** aus diesen alten Dateien. Der technische SHA-/WebP-Erfolg war daher kein redaktioneller Freigabenachweis. PR #29 wurde als ungültig geschlossen, ohne Merge/Deployment.

## Verifizierte Ist-Fakten

- [Freigegebene Release-Aktion #39019298703](https://github.com/derJosef/social-assets/actions/runs/39019298703): „Wer liest bei deinem KI-Chat mit?“ Facebook `6ac8d5ab26e224ee545ee761` und Instagram `6ac8d5ae26e224ee545ee809` am 17.10. `sent`; LinkedIn `6ac8d5a926e224ee545ee6b5` am 19.10. ebenfalls `sent` laut [Audit #39380753924](https://github.com/derJosef/social-assets/actions/runs/39380753924).
- Tatsächlich freigegebenes finales Bild: `ac03f948b5ed24dd49c3363dfdef7c82de01810b/media/images/2026-10-16-legacy-wer-liest-mit-4x5-branded.png` SHA256 `27229315d6fd2135b1c0cdc4be20eb94023e25818c7c7fe34c93fe9b715ada55`. Die ursprüngliche Adobe-Rohquelle zeigt eine räumliche leuchtende Dateninfrastruktur, nicht drei textlastige Kacheln. Nicht das verworfene `main/media/images/2026-10-09-ki-chatdaten-drittanbieter-branded.png`.
- „Ein Agent. Drei Tests“ (drei alte Buffer-Post-IDs `6ac896...`) und „Kundenmail ist kein Befehl“ (`6aca9...`) waren am 20.10. laut Audit **draft**, kein `sent`. Sie dürfen nicht als bereits veröffentlichte Kampagnen automatisch zu Website-News werden.
- Geplant/terminiert (Status `scheduled`) ist **nicht** `sent`. Die separate Regel für maximal zwei neue Social-Themen/Woche betrifft nicht die Wiederverwendung tatsächlich bestehender Themen für Website-News.

## Das neue Safety-Gate

`scripts/news_source_provenance_gate.py` akzeptiert genau:
1. Eine frische **READ ONLY Buffer-GET-Antwort** über den existierenden offiziellen Connector/API (nicht alten GitHub-Posttext).
2. Exakte Buffer-Post-ID, Kanal `linkedin`/`facebook`/`instagram`, **`status=sent`** und aktuell gelesenen Posttext.
3. Genau eine Bild-URL aus derselben Buffer-Antwort, die auf `https://raw.githubusercontent.com/derJosef/social-assets/<40-hex-commit>/media/images/<final>.png` zeigt; `main` und alte Kandidatenpfade werden gesperrt.
4. Echte heruntergeladene PNG-Bytes in **1080×1350**, mit SHA256 übereinstimmend zur vorgegebenen finalen Bildversion.
5. Andernfalls `BLOCKED`; auch `PASS` heißt nur Quellenauthentizität, **niemals** Website-Veröffentlichung.

Ein unveränderlich gepinntes PNG allein genügt **nicht**: Es muss exakt dem aktuellen Bild des aus Buffer verifizierten veröffentlichten Posts entsprechen.

**Wichtig:** Diese Quelle ist nur die Eingangssperre. Für News-Desktop 1672×941 und Mobil 1200×900 müssen Motive visuell passend eigenständig komponiert oder ein geeigneter Rohbild-Canvas vorbereitet werden; nicht die verworfene Kachelvorlage künstlich auf einen Navy-Hintergrund kopieren. Blogtext in `Sie`-Ansprache, externe Quellen, Bildrechte und CTA separat prüfen. News-Artikelbild bleibt dauerhaft am Artikel und nimmt an keiner Menübildrotation teil. Immer erst auf einer echten Testseite visuell abnehmen, dann ausdrücklich genehmigter Release.

## Realer Code-/Testnachweis

- `scripts/news_source_provenance_gate.py`
- `tests/test_news_source_provenance_gate.py`
- GitHub-Offline-Akzeptanzlauf [#39452807107](https://github.com/derJosef/social-assets/actions/runs/39452807107): **414 Tests PASS** inklusive positiver verifizierter Quellstruktur und Negativfälle verworfener alter `main`-Bilder, `draft`/`scheduled`, falscher IDs/Kanäle, falscher SHA/Abmessungen; vier zusätzliche Offline-Gates bestanden. Keine Produktion/Veröffentlichung/Buffer-Mutation.

Nächster Schritt: Diese strikt prüfende Quellenprüfung in den späteren WEBSITE-News-Adapter einbinden und für die echte publizierte Quelle separat bildgestalterisch geeignete News-Formate erstellen. Aktuell kein neuer produktiver News-Workflow.
