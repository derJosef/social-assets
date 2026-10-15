# Nachtest 15.10.2026 – Personen-Prüfgate und 4:5-Rohbild

**Status:** Separater Draft-PR #27, kein automatisches Merge, keine Bild-/Logo-/Buffer-/Adobe-Produktivaktion. Die fachliche Markenwahrheit bleibt in PersonalOS, Decision vom 14.10.2026 und `skills/josefs-marke/references/social-media/DESIGN.md`.

## Ursache und Korrektur

Das frühere `social_portfolio_scene.py` forderte für **jede** als Person klassifizierte Szene `person_use_approved=true` plus `person_approval_evidence` von Josef. Diese **Einzelfreigabe** wurde ausdrücklich aufgehoben. Das neue Schema fordert stattdessen (jeweils echte Boolesche Werte):

- `photorealistic_ai_face` und `ai_altered_real_person` zur Kennzeichnungspflicht;
- `rights_checked`, `no_misrepresentation_checked` und `platform_checked` müssen bei einer realistisch dargestellten Person jeweils `true` sein;
- `person_checks_evidence` dokumentiert getrennt `rights_basis`, `misrepresentation_assessment` und `platform_assessment` mit nachvollziehbaren Beschreibungen.

Ein `true` in einem Beleg kann seine tatsächliche Richtigkeit **nicht maschinell beweisen**. Der Text darf nicht als unabhängige rechtliche Freigabe oder als Veröffentlichungsgenehmigung dargestellt werden. Wer die Prüfung nicht belegen kann, meldet `BLOCKED` und verwendet das Bild nicht. Alte Einzelfreigabefelder werden nicht stillschweigend als Ersatz akzeptiert. Bei fotorealistischen KI-Gesichtern und KI-veränderten realen Personen muss `Powered by AI` weiterhin als **eigene** typografische Ebene vor dem kanonischen Original-Logo-Compositing gesetzt und pixeltechnisch verifiziert werden. Bereits erlaubte holografische Figuren bleiben über den getrennten `stylized_hologram`-Pfad zulässig und lösen diese Kennzeichnung nicht aus.

Der ChatGPT-/Adobe-Import ist für getrennt klassifizierte Fälle erweitert, aber löst **keine** Downloads, Bildgenerierung oder Buffer-Aktion aus, solange nur Offline-Tests laufen. Die bekannten `draft`-, `dueAt`- und Publikationsfreigaben bleiben unberührt.

## Tatsächlicher PNG-Durchlauf (ohne Adobe/Buffer)

Ein ursprünglich in ChatGPT erzeugtes und im bisherigen E2E-Test vom 14.10. verwendetes Originalbild war als Datei verfügbar und wurde am **15.10.2026** erneut geprüft und lokal normiert.

| Prüfmerkmal | Ergebnis |
|---|---|
| Original | PNG, 1122 × 1402, 2.024.527 Bytes |
| Original SHA-256 | `22df4bff1d1043929272e93f2c1ace3c7d273efa7c3617db8ee417747033982d` |
| Aktion | Pillow LANCZOS, proportional nahezu unveränderte 4:5-Skalierung **ohne Zuschnitt**, keine Logo-/Schriftmontage |
| Ausgabedatei | PNG, exakt 1080 × 1350, 1.810.753 Bytes |
| Ausgabe SHA-256 | `ddf69cce1a4a781321dad84809e7f4e7896c6ed40f115c12b8548cdf7d2c8d5c` |
| Formattechnische Prüfung | **BESTANDEN**; Original unberührt |
| ChatGPT-Sichtprüfung | Eindeutig synthetische blau leuchtende Drahtgitter-Menschengestalt; keine klar erkennbaren Markenlogos oder Worte; keine fotorealistische Person oder Roboter |
| Personen-Einzelfreigabe | Für das deutlich stilisierte Hologramm **nicht erforderlich** |
| Maschinenprüfung des tatsächlichen Modellprompts oder abgeschotteten Kontexts | **NICHT MÖGLICH / NICHT NACHGEWIESEN** |
| Vollständiger Live-E2E über Adobe → GitHub → Original-Logo → Buffer-Entwurf | **NICHT AUSGEFÜHRT**, deshalb **nicht bestanden behaupten** |

Der reale lokale LANCZOS-Transformationslauf erfolgte im ChatGPT-Dateicontainer anhand der ursprünglichen Bilddatei. Der neue gleichartige CLI-Helfer `scripts/normalize_chatgpt_raw_png.py` ist zusätzlich über synthetische GitHub-Offline-Tests überprüfbar; ein separater Host- oder Adobe-Live-Lauf ist kein Teil des Patches.

**Hinweis zur Entscheidung:** Die frühere Einstufung der holografischen Figur als Personengate-Verstoß war fachlich falsch und ist durch PersonalOS korrigiert. Die damalige Auflösung war tatsächlich nicht importfähig und ist nach technischer Umrechnung jetzt normgerecht. Aus der Normierung darf keine Veröffentlichungserlaubnis, keine automatische Markenfreigabe und keine Kontextattestierung abgeleitet werden.

## Offene Schritte vor produktiver Übernahme

1. PR #27 vollständig durch GitHub CI inkl. visueller synthetischer `Powered by AI`-Pixelprüfung und unabhängiger Original-Logo-Prüfung laufen lassen; bei Fehler keine Produktivübernahme.
2. Das neue Prüfschema nur über einen expliziten, auditierten Import-/Redaktionsweg füllen; KI- oder Testbelege nicht als nachgewiesene Personenrechte ausgeben.
3. Wenn die Bildnormierung tatsächlich in den Übergabeweg soll, die neue PNG-Datei **statt** der nativen 1122×1402-Datei über den bisher bewährten Uploadkanal transportieren und den **Ausgabe-SHA-256** pinnen; keinesfalls den Original-Hash als Hash der transformierten Datei wiederverwenden.
4. Echte Content-QA, ggf. Personenschutzprüfung, Original-Logo-Compositing und Buffer-Draft-Readback getrennt nachweisen. Kein `scheduled` ohne Josefs ausdrückliche Freigabe.
5. Host- bzw. Projektkontextisolation bleibt unabhängig davon eine offene Architekturfrage. Neue kostenpflichtige Bildprovider oder Firefly-Credits sind nicht genehmigt.

**Es wurde keine Veröffentlichung, kein Buffer-Draft und kein Live-Adobe-Transfer durchgeführt.**
