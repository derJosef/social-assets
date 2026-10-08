# Freigabeordner für Buffer-Entwürfe

**Nur durch Josef ausdrücklich freigegebene Beiträge** dürfen hier als neue `.json`-Datei auf `main` angelegt werden.

Jede **neu hinzugefügte** Datei `ready-for-buffer/*.json` startet automatisch die GitHub Action [Buffer – automatisch nur freigegebene Entwürfe](../.github/workflows/buffer-auto-drafts.yml).

- Es wird nur ein **Buffer-Entwurf** angelegt. Keine Terminierung oder Veröffentlichung.
- Noch nicht freigegebene Texte gehören in `drafts/`.
- Dateien müssen das Format des vorhandenen [Beispielentwurfs](../drafts/beispiel-linkedin.json) haben.
- Die Dateien sind **öffentlich** einsehbar.
- Bestehende Dateien nicht wiederverwenden oder ändern, um erneut zu senden: Empfangsbelege verhindern doppelte Übertragung.
- Der bestehende Testentwurf wurde bereits übertragen und soll **nicht** hierher kopiert werden.
- Weitere Details: [Anleitung](../docs/BUFFER_DRAFTS.md).

Noch kein automatischer Live-Test dieses neuen Triggers durchgeführt.
