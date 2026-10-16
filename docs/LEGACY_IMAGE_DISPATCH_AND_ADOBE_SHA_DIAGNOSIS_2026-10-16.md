# 16.10.2026 – Bildworkflow-Start und Adobe-SHA-Fehldiagnose

**Klarstellung:** Die verbundene GitHub-Integration in dieser Chat-Umgebung bietet keinen direkten `workflow_dispatch`-Endpunkt. Sie bietet dagegen `add_comment_to_issue`, und bestehende Workflows reagieren darauf durch `issue_comment`. Frühere erfolgreiche indirekte Workflow-Starts wurden pauschal als Beleg für einen direkt verfügbaren manuellen Start interpretiert; spätere Antworten verneinten pauschal alle Starts. Beides war ungenau. Wir müssen einen sicher eingegrenzten **alternativen Event-Trigger** bewusst in der Workflow-YAML freigeben.

**Realer Lauf:** Josef startete [#38918161125](https://github.com/derJosef/social-assets/actions/runs/38918161125) am 16.10. um 14:44Z selbst als `workflow_dispatch` auf geschütztem `main`. Ergebnis `failure` beim Adobe-Import im Script `legacy_six_draft_image_prepare.py`: `Adobe bytes do not match original ChatGPT normalized image SHA`. Alles vor diesem Schritt erfolgreich, darunter `PRODUCTION_ACTIVATION_PASS`; die beiden Bilder wurden nicht gebaut, kein GitHub-Output-Branch entstand, kein Buffer-Schreibvorgang. **Kein Re-run**.

**Originale unabhängig gegengeprüft:** Die unveränderten lokal vorhandenen, zuvor freigegebenen PNG-Dateien haben:
- `wer_liest_mit_raw_1080x1350.png`: 1.839.099 Bytes; SHA256 `74a7debcc3d5598fa328fc9a5c0376c9cd2797ed2d722ed7a9c4e6ec5c3abfd7`
- `ein_agent_drei_tests_raw_1080x1350.png`: 1.729.109 Bytes; SHA256 `95f82aa8b82c749a89d73e5f1ba34bb4a2521c31f9043bf80dffaee328406c7a`.

Adobe `asset_search` fand in Creative Cloud die **exakt gleichnamigen und gleich großen** Originale unter den vorbestehenden unveränderten URNs:
- `urn:aaid:sc:EU:ebaa449f-8851-47a9-89f1-311ff59d5373`
- `urn:aaid:sc:EU:e1c54cc5-41f1-4848-81f6-10e6668bfe7b`.

Das stützt die Vermutung, dass die **Adobe-Kurzlink-Rendition oder der tatsächliche HTTP-Download** von den hochgeladenen Originalbytes abweicht. Adobe-Dateigröße allein ist **kein** SHA- oder Abrufbeweis. Der fehlgeschlagene Runner protokollierte früher nicht den `received_sha256`, deshalb ist die Ursache nicht weiter sicher bestimmbar. Nicht alle Adobe-Kurzlinks sind automatisch Bytes-gleich zur hochgeladenen PNG. **Kein Umgehen des SHA-Gates, kein Akzeptieren einer veränderten Bilddatei als Original.**

## Dieser isolierte Draft-PR

1. Im existierenden Bildworkflow bleibt `workflow_dispatch` vollständig erhalten. Ergänzt wird `issue_comment: created` mit **Job-`if`-Bedingung** auf `github.actor=derJosef`, `refs/heads/main`, `run_attempt=1`, genau **Issue #19**, ausschließlich tatsächliches GitHub-`issue_comment` (kein PR-Kommentar), Issue-Owner und Kommentar-Owner `derJosef` sowie exakt `LEGACY_IMAGE_BUILD_ONCE_20261016`. Alle anderen Kommentare/Sender werden `skipped`. Gleiches Produktionsgate, gleicher Zweibild-Build, gleicher Einmal-Output-Branch, **kein Buffer-Token**.
2. Wenn der Adobe-Download die erwartete PNG-Prüfsumme nicht trifft, meldet `legacy_six_draft_image_prepare.py` **nur geschlossene technische Prüffelder** (Themenkennung, tatsächlich empfangene SHA256, Byteanzahl, magic-byte-Typ PNG/JPEG/HTML/unknown). Keine Body-Daten, Redirect-URLs, Adobe- oder GitHub-Tokens und keine untrusted Zeichen im Log. Das Bild bleibt gesperrt.
3. Ergänzende rein synthetische Tests für Gate-Konfiguration, präzise Formatklassifikation, Data-Leak-Schutz und Nichtausführung der Buffer-API.

**Sicherheitslage:** Dieses Patch bringt die tatsächliche Adobe-Ursache noch nicht zum Abschluss; es stellt zuerst einen selbst bedienbaren, autorisierten und diagnostisch aussagekräftigen GitHub-Bildlauf bereit. Erst nach CI und **Josefs separater Mergefreigabe** darf dieser Workflow in `main` übernommen werden. Ein späterer Issue-Kommentar nach ausdrücklicher Workflow-Freigabe startet wieder genau einmal die reine Bildarbeit, **keine Buffer-Publikation**. Bei erneutem SHA-Abbruch müssen URL-/Content-Response und gesuchte Originalbytes anhand der neuen Hash- und Formatdaten fachlich repariert werden, niemals die SHA-Kontrolle deaktivieren.
