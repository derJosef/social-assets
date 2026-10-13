# ChatGPT-Bild ohne zusätzliche Bild-API – geschützter Draft-only-Pfad

**Stand 13.10.2026: nur isolierter Entwicklungsbranch/PR. Noch kein produktiver Merge und kein Live-PNG-Test mit neuer Schema-Route.**

## Bewiesener Weg vom 10.10.2026

Das bestehende, in ChatGPT erstellte 4:5-PNG wurde über den verbundenen Adobe-Dateidienst als zeitlich begrenzt abrufbare Datei übertragen, unter einem Adobe-Kurzlink in GitHub Actions bezogen und durch SHA256, PNG-Signatur sowie Abmessungen geprüft: [Import-Action 38082634118](https://github.com/derJosef/social-assets/actions/runs/38082634118). Nach separater unveränderter Original-Logo-Montage [38082774496](https://github.com/derJosef/social-assets/actions/runs/38082774496) wurde das Bild auf GitHub übernommen [Commit e00340b](https://github.com/derJosef/social-assets/commit/e00340b40407becdcbdd35c3d984e778ea9cfb4c) und in drei tatsächlichen Buffer-Drafts genutzt [Action 38083224273](https://github.com/derJosef/social-assets/actions/runs/38083224273). Dies ist ein **konkreter erfolgreicher manueller Chat-Lauf**, nicht die Abnahme einer unbeaufsichtigten wöchentlichen Bild-Tool-Funktion.

## Neue Schnittstelle ohne Modellschlüssel

Die GitHub-Issue-Route `AIAGENT_BRIEF:YYYY-MM-DD-slug` bleibt erhalten; `issues:opened` nur von `derJosef` mit `author_association=OWNER`. Der Brief besitzt die bisherige Pflichtstruktur sowie zusätzlich:

```json
"chatgpt_image": {
  "transport": "adobe_transfer",
  "url": "https://at.adobe.com/ABCD1234xyz",
  "sha256": "<64 echte Kleinbuchstaben-hex-Zeichen aus dem PNG>",
  "visual_review": {
    "no_people": true,
    "no_robot": true,
    "no_foreign_logo": true,
    "no_generated_text": true,
    "plausible_details": true,
    "matches_topic": true,
    "heading_and_logo_space": true
  },
  "review_evidence": "ChatGPT has visually inspected the actual created image, evidence ...; NOT a human review; Josef reviews Buffer drafts."
}
```

**Das Beispiel ist nicht zum Senden bestimmt!** Nur für ein wirklich vorhandenes, zuvor durch ChatGPT visuell inspiziertes PNG in **1080×1350** mit dem tatsächlichen SHA256 des exakt übergebenen binären Originalbildes diese Struktur in ein einzelnes owner-authored Issue übernehmen. Keine erdachten Quellen, Scheindaten, künstlichen Bildfreigaben oder Personen. In dem öffentlichen Issue **keine Secrets, persönlichen Daten oder vertraulichen Bildlinks** hinterlegen. Ein bereits öffentlich teilbares synthetisches Bild ist erlaubt. Der Adobe-Kurzlink muss beim Abarbeiten noch abrufbar sein.

Der GitHub-Runner prüft vor dem ersten Byte Netzwerkzugriff: Format, den eng zulässigen ursprünglichen Adobe-Kurzlink und die sichere HTTPS-Weiterleitungs-Hostklasse. Die tatsächlichen Bildbytes werden auf 16 MB begrenzt, exakt per SHA256 und PNG/Format **1080×1350** geprüft. `scripts/chatgpt_image_import.py` schreibt ohne Überschreiben die Roh-PNG und den maschinenlesbaren Sichtprüfbeleg nach `media/source-images/<campaign>-source.png` und `visual-reviews/<campaign>.json` – **nur lokal im Runner**, zunächst nicht auf `main`.

Anschließend prüfen der bestehende `social_portfolio_scene.validate_spec` und `prepared_brief_preflight` erneut den Quellhash, die sieben explizit bestätigten Bildkriterien und die Zuordnung. Der bestehende Orchestrator baut das verifizierte 4:5-Bild **mit dem unveränderten Pauderer-Original-Logo**. Dann erst werden die Pakete auf `automation/campaign/<slug>` als unveränderliches Bild-Commit gespeichert; direkt in demselben Job erzeugt Buffer anschließend genau drei unabhängige vordatierte **`draft`**-Beiträge, falls alle Gates PASS sind.

Kein `SOCIAL_OPENAI_API_KEY`, kein OpenAI-Bild-/Text-API-Aufruf aus dem Kampagnen-Workflow. Wenn das ChatGPT-Bild oder das faktische Sichtprüfungsergebnis fehlt, ist der Lauf **BLOCKED**; es gibt keinen kostenpflichtigen API-Fallback und kein unsicheres Ersatzbild.

## Wichtige Grenzen

- Dies ist weiterhin ein **Draft-only**-System. `saveToDraft:true` und tatsächliche `dueAt`-Rückleseprüfung bleiben bestehen. Keine Buffer-Queue, kein Publish, keine PR-/Branchschutz-Umgehung. Buffer-Bearbeitungen von Josef bleiben maßgeblich.
- Die Rohbildsichtprüfung durch ChatGPT ist **keine menschliche Freigabe**. Sie darf nur für menschenfreie, vollständig inspizierte Bilder eingereicht werden; keine fiktiven Menscheneinzelfreigaben.
- Die praktische Adobe-Link-Route war bewiesen, der **jetzige neue Issue-Pfad muss separat mit neuer eindeutiger Kampagne und mindestens einem wirklichen Rohbild geprüft werden**. Der fehlgeschlagene Lauf #38349167104 und Issue #16 dürfen nicht blind erneut verwendet werden.
- Die wöchentlich geplante ChatGPT-Automation muss ihre neue `chatgpt_image`-Struktur **vor dem Issue** mit echter Bilddatei, temporärem Adobe-Transport und SHA füllen. Ob der Automationskontext ImageGen und Adobe-Übergabe unbeaufsichtigt unterstützt, ist **noch nicht geprüft**. Bis zu dieser Abnahme darf ein bildloses Wochen-Issue nicht erzeugt werden. Kein weiteres Konto/Modell-API-Secret anlegen.
- Header und PR-Status dieser Datei nach dem Merge aktualisieren; historische früheren Informationen in anderen Dokumenten sind datierte Berichte und keine aktuelle Aktivierungswahrheit.
