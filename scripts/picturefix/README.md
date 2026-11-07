# PictureFix PF-01 – gesicherte Logo-Montage (noch keine Veröffentlichung)

Dieses Werkzeug gehört **nur** zu PictureFix PF-01 („Kleine Fotos. Große Erinnerungen.“). Es verändert weder PictureFix-Appcode noch den gemeinsamen Marken-/Buffer-Workflow. Es erzeugt **keine Buffer-Drafts, Queues oder Veröffentlichungen**. Kein Ersatz der durch Josef gesperrten Restaurierungs-, Slider- oder PayPal-Module.

## Ursprünge, nicht duplizieren

- Verbindlicher Bildstil und Benutzerfreigabe: `derJosef/agent-workspace`, PR #64 (Stand nach Merge prüfen).
- Beitragsentwürfe, Status und Bildhashes: `derJosef/agent-workspace@main/work/drafts/social-assets/2026-11-07-picturefix-post-01-kleine-fotos-grosse-erinnerungen.md` (PR #65 gemergt).
- Original-Logo **als Originaldatei**: `derJosef/picturefix-de-website@main/app/public/assets/brand/PictureFixLogo_Web.png`; Git-Blob-SHA `0cd926e6631209dd4e5c8029dfb72c29bbf89ea8`. Keine Logo-Rekonstruktion, keine zweite kanonische Kopie.
- Die zwei logo-freien Bildentwürfe liegen derzeit in Josefs ChatGPT-Social-Media-Projekt/Bibliothek im geprüften ZIP `PictureFix_Post_01_Entwurfspaket.zip`. **Sie liegen noch nicht als Binärdateien in diesem GitHub-Branch.** Die Codex-/Claude-Geräte haben nach bisheriger Prüfung keinen Direktzugriff auf die ChatGPT-Bibliothek; ein fehlender Zugriff ist nicht mit fehlendem Asset gleichzusetzen.

## Technischer Ablauf (nur mit vorhandenen Originalbytes)

Voraussetzung: Python 3.11+ und Pillow. Der ausführende Agent muss die drei Eingabedateien tatsächlich erreichen. **Keine** Zugangsdaten oder unfreigegebenen Kundendateien beschaffen oder in GitHub ablegen.

```bash
python -m unittest -v scripts/picturefix/test_pf01_render_verified.py
python scripts/picturefix/pf01_render_verified.py \
  --draft-dir /sicherer/pfad/zu/PF01-Entwuerfen \
  --logo /berechtigter/originalpfad/PictureFixLogo_Web.png \
  --output-dir /sicherer/ausgabe/PF01
```

Der Prozess verweigert die Ausgabe bei abweichenden SHA-256-Werten der beiden Entwürfe oder abweichendem Git-Blob-SHA des Original-Logos. Er skaliert das echte Logo **nur proportional**, montiert es über einer dezenten hellen Trägerfläche und testet, dass alle Bildpixel außerhalb dieser Fläche unverändert bleiben. Er erstellt je einen 1080×1350- und 1000×1500-Entwurf sowie ein QA-Manifest und ein **flaches ZIP ohne ZIP-in-ZIP**. Die finale visuelle Freigabe durch Josef bleibt notwendig.

## Abnahme

1. Exakte Originaldateien sicher bereitstellen und Hashes nachprüfen. Bei `No authorized raw-byte materialization path` **nicht** andere Rechte oder Identitäten verwenden; zulässigen GitHub-/Asset-Weg wählen oder die Blockade melden.
2. Offline-Tests ausführen; die vier Testfälle wurden im ChatGPT-Arbeitscontainer am 07.11.2026 bestanden. Das ist noch **kein GitHub-CI-PASS**.
3. Tatsächlich produzierte PNGs auf Logo-Lesbarkeit, vollständige Bildausschnitte, Disclaimer und Originaltreue ansehen; nach SHA-256-Readback dauerhaft im autorisierten Asset-System speichern.
4. Erst dann Text/Bild/Plattformzuordnung als konkreten PictureFix-Post durch Josef freigeben lassen. Der AI-Agent-Builder-Draft-Autopilot gilt nicht für PictureFix.

**Status dieses PR:** Reproduzierbare Produktionshilfe, **keine fertigen Bilder, keine Buffer-Aktivierung und keine Freigabe**.
