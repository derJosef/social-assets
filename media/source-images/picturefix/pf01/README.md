# PictureFix PF-01 – Stilreferenzen (von Josef hochgeladen)

Die Dateien in `parts/` sind **binäre, fortlaufend nummerierte Fragmente** der
von Josef am 15.11.2026 erneut in ChatGPT bereitgestellten PNG-Bilder. Die
Aufteilung ist **verlustfrei** und ausschließlich technisch bedingt, da der
GitHub-Connector die rund 3-MB-PNGs nicht in einem einzigen Request übernimmt.

## Für Vibe – sofortiger Zugriff

Nach dem Checkout dieses Git-Branches vom Repository-Root ausführen:

```bash
python scripts/picturefix/restore_pf01_sources.py
```

Die zwei Originaldateien werden nach
`media/source-images/picturefix/pf01/reconstructed/` geschrieben. Das Skript
prüft zuvor **jedes vollständige Bild** auf Dateigröße, PNG-Signatur,
Bildabmessungen und SHA-256. Bei Abweichung bricht es ab.

| Rolle | Dateiname | Pixel | Größe | SHA-256 |
| --- | --- | --- | ---: | --- |
| **Freigegebene PF-01-Stilreferenz** | `PictureFix_Stilreferenz_01_freigegeben.png` | 1122 × 1402 | 3.155.095 B | `5b4b189d7a82d6f6610f146444514f8da9955f44651cc5f56d86048c364df792` |
| Frühere Vergleichsvariante | `PictureFix_Stilvergleich_02_fruehe_Variante.png` | 1122 × 1402 | 3.009.445 B | `5c5fc47003b2fbb40be35f1c20a22b356b2441d6f0d93b3e9d2480453c04633a` |

**Freigabe:** Josef hat die erste Variante (historische Frau im gepunkteten
Kleid mit Spitzenkragen) als Bildstil bestätigt. Die andere Variante ist nur
zur Vergleichsdokumentation vorhanden.

**Abgrenzung:** Diese hochgeladenen Stilreferenzen sind **nicht** identisch
nachgewiesen mit den zwei spezifischen PF-01-Plattformentwürfen
`PictureFix_01_Facebook_Instagram_1080x1350_ENTWURF_ohne_Logo.png` und
`PictureFix_01_Pinterest_1000x1500_ENTWURF_ohne_Logo.png`. Deren vorhandene
SHA-Prüfungen im Skript `pf01_render_verified.py` bleiben unangetastet. Die
hier gesicherten Bilder dürfen nicht als diese geprüften Layouts ausgegeben
werden. Das gilt insbesondere für Logo-Montage und Buffer-Draft-Gates.

**Freigabegrenze:** Nur lesend/als Stilreferenz nutzbar. Kein automatisches
Scheduling, keine Veröffentlichung, keine Änderung an PictureFix
(Restauration, Wasserzeichen, PayPal). Der PR wird nur durch Josef geprüft
und gemergt.
