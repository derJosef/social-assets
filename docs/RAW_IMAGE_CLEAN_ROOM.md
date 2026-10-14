# AI Agent Builder – Kontextfilter für KI-Rohmotive

**Entscheidung vom 14.10.2026 (Josef im Chat):** Für die Rohbildproduktion eine datensparsame, von Markenwissen getrennte Übergabeschnittstelle verwenden. Der bisher nachgewiesene ChatGPT → Adobe → GitHub → Original-Logo → Buffer-Draft-Weg bleibt unverändert.

## Was belegt ist – und was nicht

Zwei ältere Social-Media-Grafiken enthielten ein nachgebildetes Logo und generierte Texte. In frischen Chats mit neutralem Motivauftrag – einmal außerhalb, einmal innerhalb des Social-Media-Projekts – wurden keine solchen Logos gezeigt. Die A/B-Bedingungen waren nicht vollständig identisch. Weder ein direkter Zugriff des Bildmodells auf das PersonalOS noch eine kausale Wirkung des Projektkontexts ist nachgewiesen. Ein zuvor im Projekt erzeugtes holografisches Motiv entstand nach einem **tatsächlich menschliche Gestalt erwähnenden** Bildauftrag und ist kein Beweis für heimlichen Kontextzugriff.

## Grenzen und Zuständigkeit

- Redaktioneller Agent: recherchiert Themen, prüft die **kanonischen** Markenregeln im PersonalOS, entscheidet über Motiv und nachgelagerte Logo-/Textmontage.
- Rohbild-Compiler: akzeptiert nur strukturierte Kennungen für Szene, drei Schritte und Komposition. Keine freien Themen-, Marken-, Unternehmens-, Logo- oder Bilddateifelder. Er erstellt ausschließlich einen promptbasierten **Übergabebeleg** mit SHA256, keinen Modellaufruf.
- Bildgenerator: soll ausschließlich den kompilierten Prompt erhalten. **Nicht mit dem früheren Projektthread, Referenzbildern, PersonalOS-Texten oder Brand-Assets aufrufen.** Einen wirklich getrennten Modellkontext muss der jeweilige ausführende Host technisch bereitstellen und nachweisen; das Prompt-Dokument alleine isoliert nichts.
- QA: tatsächliche Rohbildsichtprüfung anhand der bestehenden sieben Kriterien; eindeutige unzulässige Logos oder Texte = Ablehnung. Kleine uneindeutige Stellen in der bekannten ChatGPT-Draft-only-Route bleiben als `null` mit Review-Evidence offen, nicht als sicheres Fremdlogo ausgegeben.
- Montage: nach der Bildprüfung nur den kanonischen unveränderten Logo-Compositor mit Original-SHA nutzen; optional Überschrift und erforderliche KI-Kennzeichnung technisch setzen.
- Buffer: nur geprüfte **Entwürfe** mit vorgeschlagenem Termin, keine Aktivierung der Veröffentlichung ohne Josefs Freigabe.

## Ausführbare Offline-Übergabe (vorerst nicht an den produktiven Lauf angeschlossen)

`python3 scripts/cleanroom_image_brief.py --spec eingabe.json --output cleanroom-job.json`

Beispiel `eingabe.json`:

```json
{
  "version": 1,
  "scene": "document-review",
  "steps": ["receive", "inspect", "release"],
  "composition": "connected-three",
  "figure": "none"
}
```

Die Eingabe ist bewusst eine **Positivliste**. Beliebige `topic`-Texte, Referenzbilder, `brand`, URLs, Pfade, Branding-Anweisungen oder weitere Felder werden zurückgewiesen, nicht an das Modell gereicht. Die Ausgangsdatei enthält nur den generierten englischen Motivprompt, dessen SHA256, `reference_images: []` und **`isolation_verified: false`**. Sie enthält keine Credentials und ruft keine externe API auf. Nach einem späteren tatsächlichen Modellaufruf muss ein eigenständiger Beleg festhalten, welcher Prompt und welche Bildreferenzen tatsächlich übergeben wurden; erst eine überprüfte Host-Trennung darf als Kontextisolation gelten.

Derzeit ist ausschließlich `figure: none` zugelassen. Josefs Wunsch nach einer blau leuchtenden holografischen Menschengestalt ist als Motividee bestätigt, aber die bestehende automatische `no_people: true`-Prüfung würde sie blockieren. Eine kontrollierte Personenausnahme erfordert einen eigenen Review- und Freigabeweg und wird **nicht** still in diesem Patch eingeführt.

## Abnahme vor produktiver Aktivierung

1. Offline-Tests des Compilers: `python3 -m unittest discover -s tests -p 'test_cleanroom_image_brief.py' -v`.
2. In einem echten, nachweislich getrennten Aufruf kontrollieren, dass genau der kompilierte Prompt und null Referenzbilder übergeben wurden. Ein ChatGPT-Projektchat ist **kein garantierter Clean Room**.
3. Mit identischem Prompt isolierten und bisherigen Ausführungskontext vergleichen; generierte Originalbilder dokumentieren. Tests aus dem Gespräch gelten als Hinweise, nicht als streng kontrollierte Beweise.
4. Rohmotiv auf Marken, Buchstaben, Roboter, Figuren und technische Plausibilität prüfen. Finale Logo-Verifikation wie bisher.
5. Erst nach separater Integration/CI und Josefs ausdrücklicher Freigabe produktive Einbindung vornehmen. Keine Änderung an Adobe-Transport, GitHub-Briefschema, Buffer-Verhalten, Secrets, `main` oder bestehenden Kampagnen durch diesen Vorbereitungsstand.

**Quellen/Owner:** PersonalOS `skills/josefs-marke/references/social-media/DESIGN.md` und `skills/josefs-marke/SKILL.md` (nur leseweise), technische Dokumentation `docs/CHATGPT_IMAGE_TRANSFER_DRAFT_ONLY_2026-10-13.md`, `scripts/social_portfolio_scene.py`. Diese Datei ist eine technische Umsetzungsbeschreibung in `social-assets`, keine zweite PersonalOS-Markenregel.
