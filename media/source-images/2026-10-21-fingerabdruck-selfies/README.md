# Fingerabdruck-Selfies: 3 Social-Rohmotive + Website-Desktopentwurf

Status: **RAW ASSETS ONLY – no Buffer drafts, no website deployment, no publishing approval**.

Die 4 JPGs sind Adobe-Preview-Renditions der am 21.10.2026 individuell erzeugten Bildmotive. Sie sind **keine byteidentischen Original-PNGs**; Original-Chatausgaben befinden sich im ChatGPT-Freigabepaket (ZIP). JPG-Renditions müssen vor produktivem Einsatz visuell und technisch geprüft werden.

- 01-selfie: Victory-Zeichen mit strukturierten Fingerkuppen.
- 02-smartphone: Bildschirm mit Sperrsymbol und Fingerabdruckdarstellungen.
- 03-datenschutz: drei visuelle Sicherheitsaspekte.
- technikinside-desktop: separates breites Website-Rohmotiv.

**Für Social-Entwürfe:** 1080x1350 PNG mit technischer Überschrift in Inter erzeugen; Original-Logo `media/brand/logo-pauderer-original.png` unverändert, inklusive gleichmäßiger weißer Außenkontur über `scripts/logo_composite.py` an der diagonal gegenüberliegenden Ecke hinzufügen; anschließend `verify` tatsächlich ausführen. Headline oben links bedeutet Logo unten rechts; Motiv/Konturen dürfen nicht überlagert werden. Pro Quelle brauchen wir die originale Qualitätsprüfung und ein QA-Manifest, dann 3 kanalbezogene JSON-Entwürfe je Beitrag (insgesamt 9), mit datierten `dueAt` und `saveToDraft:true`. Erst nach bestandenen Gates in `ready-for-buffer/`, andernfalls STOP. Kein `scheduled` ohne Freigabe.

**Redaktionelle Quellen der Beiträge:**
https://github.com/derJosef/agent-workspace/blob/main/work/drafts/social-media/2026-10-21-fingerabdruck-selfies-serie.md

**TechniKInside Artikel:**
https://github.com/derJosef/agent-workspace/blob/main/work/drafts/social-media/2026-10-21-fingerabdruck-selfies-technikinside-artikel.md

**Website-Übergabe:**
https://github.com/derJosef/agent-workspace/blob/main/work/handoffs/2026-10-21-technikinside-fingerabdruck-selfies-website-uebergabe.md

**Keine automatische Ausführung/Veröffentlichung durch diesen Assets-Commit.**

## QA-Ergebnis 21.10.2026

Die drei Bildvarianten sind jetzt im selben Feature-Branch **mit dem originalen unveränderten Logo** unter `media/images/2026-10-21-fingerabdruck-selfie-0{1,2,3}.png` erzeugt. Das kanonische Compositing-Skript hat für alle drei Entwürfe den Test bestanden (Original-SHA `15dc410d1a05b96c13466ddf3052ba9cc783cdd7252b74f4fb5c3f886510dea0`, 1080×1350, Logo mit weißer Kontur). Maschinenlesbare Einzelbelege: `visual-reviews/2026-10-21-fingerabdruck-selfie-0{1,2,3}-build-receipt.json`. GitHub-Actions-Protokoll: https://github.com/derJosef/social-assets/actions/runs/39618529301 (success). Die einmalige Build-Hilfsroutine wurde nach dem Erfolg aus dem Branch entfernt.

**Status:** drei technisch geprüfte Artikel-/Social-Grafiken. Nicht mit bereits erstellten Buffer-Drafts oder Veröffentlichungsfreigabe verwechseln. Für die Beiträge weiterhin 3 × 3 kanalbezogene Draft-JSONs, drei Kampagnenmanifeste und der gesonderte Buffer-Readback erforderlich.
