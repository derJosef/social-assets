# GitHub-Actions-Orchestrator – AI Agent Builder

Stand: 09.10.2026. **Technischer End-to-End-Test über GitHub → Buffer-Entwürfe erfolgreich.** Autonome KI-Textgenerierung ist separat durch einen funktionsfähigen Modell-API-Zugang abzusichern.

## Hintergrund und Architektur

Bisher starteten die Workflows für Medienproduktion und Buffer nur dann, wenn fertige `artwork-requests/*.json` bzw. `ready-for-buffer/*.json` bereits vorhanden waren. Die ChatGPT-Hintergrundaufgabe hat diese Übergabe nicht zuverlässig erreicht.

Jetzt gibt es den zentralen Workflow [social-campaign-orchestrator.yml](../.github/workflows/social-campaign-orchestrator.yml). **Ein neuer Auftrag unter `orchestration/briefs/YYYY-MM-DD-slug.json` auf `main` löst einen eigenständig protokollierten GitHub-Job aus.** Dieser erledigt alle technischen Schritte im **selben Job**. Bei Fehlern werden Buffer und Veröffentlichung nicht angerührt.

Schritte:

1. GitHub-Repo auschecken, Python und Bildbibliotheken bereitstellen, gesamte Offline-Testsuite ausführen.
2. Genau einen neuen oder geänderten Auftrag bestimmen; Schema, Marke und ID validieren; bereits existente Kampagne blockieren.
3. Verlinkte Quellen live per HTTPS abrufen; **mindestens zwei verschiedene Quellen-Domains**, sowie **zwei verschiedene Domains für Posting-Zeiten-Studien** müssen ausreichend Text liefern.
4. Zwei Modi zur redaktionellen Produktion:
   - **`prepared_content` vorhanden:** drei bereits redaktionell vorbereitete Texte, das Bildkonzept und die sechs Denkhüte stammen aus der Auftragsdatei. Textprüfung ist **kein Beleg für eine autonome KI-Textgenerierung**. Geeignet für die fachliche Bearbeitung durch ChatGPT/Claude außerhalb des Runners.
   - **`prepared_content` fehlt:** Der Runner fragt GitHub Models mit `models:read` oder alternativ einen als GitHub-Secret hinterlegten OpenAI-API-Schlüssel ab. Er fordert strukturiertes JSON und eine zweite kritische Modellprüfung; bei Fehlern Abbruch vor Buffer. Die API-Nutzung ist unabhängig vom ChatGPT-Abonnement.
5. Das logo-freie Bild mit `social_visual_from_spec.py` erzeugen; das Original-PNG anhand SHA256 `15dc410d1a05b96c13466ddf3052ba9cc783cdd7252b74f4fb5c3f886510dea0` prüfen, proportional und mit gleichmäßigem weißem Konturrahmen **unten rechts** montieren. `logo_composite.py verify` prüft das Ergebnis gegen Original und Hintergrundpixel.
6. Drei Terminvorschläge in Europe/Berlin plus UTC ermitteln, vorgeschlagene Slots früherer Kampagnen berücksichtigen. Nur eine **redaktionelle Planung**, keine Buffer-Terminierung.
7. Das unabhängige `autonomous_campaign_gate.py` ausführen, inklusive aller drei Draft-JSON, Manifest, Quellennachweisen, Bild und Zeitumrechnung.
8. Die **neun neuen Dateien** als Commit nach `main` übertragen. Ein eigener `GITHUB_TOKEN`-Commit startet kein weiteres Push-Workflow-Ereignis; daher werden die drei Buffer-Entwürfe im **selben Runner** mit `buffer_draft.py --send` erstellt. Die bestehende GitHub-Receipt-Reservierung verhindert blindes Doppelsenden.
9. `orchestrator_verify_buffer.py` verifiziert aus den GitHub-Empfangsbelegen die drei Post-IDs über die Buffer-API: **`status=draft` und `dueAt=null`**.
10. Unabhängig von Erfolg/Fehler wird ein dauerhafter Bericht nach `orchestration/reports/<kampagne>-run-<id>.json` geschrieben und zusätzlich als GitHub-Actions-Artefakt gesichert.

## Betrieb

### Auslösen
- Ein neuer/aktualisierter `orchestration/briefs/YYYY-MM-DD-slug.json` startet automatisch den Workflow.
- Alternativ GitHub → Actions → **AI Agent Builder – Recherche bis geprüfter Buffer-Entwurf** → Run workflow, dort Brief-Pfad und Modus auswählen.
- `execution_mode: smoke`: nur lokale Validierung, keine Quellen-/Modellaufrufe, keine Buffer-Mutation.
- `execution_mode: drafts`: Quelle abrufen, Inhalte (entweder über Modell oder aus `prepared_content`) bearbeiten, Bild produzieren, Quality Gate, drei Buffer-Entwürfe und Statusprüfung.

### Modellzugang (offen für echte autonome Texterstellung)

Für den generativen Modus ohne `prepared_content` sieht das Skript `SOCIAL_OPENAI_API_KEY` als GitHub-Secret vor. Menü: **GitHub → Repository social-assets → Settings → Secrets and variables → Actions → New repository secret**. Name: `SOCIAL_OPENAI_API_KEY`; Wert: persönlicher OpenAI-API-Key mit entsprechender API-Abrechnung. **Niemals den Schlüssel in einem Chat, GitHub-Issue, Commit oder Testlog veröffentlichen.**

Falls der Key fehlt, versucht das Skript GitHub Models mit dem automatisch bereitgestellten `GITHUB_TOKEN` (`models: read`). In diesem Repository gab der isolierte Test vom 09.10.2026 auf den GitHub-Models-Inferenzendpunkt allerdings **HTTP 200, Text `OK\r\n` (4 Bytes)** zurück und keine Modellantwort. Das ist kein funktionierender Inferenzzugang; der Ablauf hält bei fehlendem Alternativ-API-Key sicher an. [Diagnoselauf #37925987036](https://github.com/derJosef/social-assets/actions/runs/37925987036).

**Wichtig:** Der am 09.10.2026 erfolgreiche Datenschutz-Pilot verwendete von ChatGPT bereits redaktionell erstellte Texte (`prepared_content`). Die Quellenabrufe, die vollständige deterministische Bildproduktion, das Quality Gate und die Buffer-Übertragung erfolgten vollautomatisch im Runner; die **autonome Modell-Textgenerierung wurde bei diesem Lauf nicht ausgeführt**. Das wird im Report ausdrücklich markiert.

### Freigaben und Sicherheitsgrenzen

- Nur Marke **AI Agent Builder**, keine anderen Marken.
- Neue Quellen nur HTTPS, kein localhost/Private-IP als Quellenhost; maximal sechs Inhaltsquellen pro Brief, kein vertrauliches Kundenmaterial.
- Vorbereitete Informationen und generierte Dateien werden im **öffentlichen** GitHub-Repository gespeichert. Keine vertraulichen Daten in Briefings, Prompts, Beiträgen oder Quellen-Extraktionen hinterlegen.
- Einzig erlaubte Buffer-Mutation: **neue Drafts erstellen**. Kein `scheduled`, keine Veröffentlichung, keine Dateien in `ready-to-schedule/`, keine Veränderungen bestehender Posts.
- Keine automatischen Wiederholungen nach einer unklaren Buffer-Antwort. Jeder Post erhält vor dem API-Aufruf einen GitHub-Pending-Receipt. Bestehende Kampagnennamen werden nicht überschrieben.
- Erfolgsbericht bedeutet 3/3 Buffer-Post-IDs mit Status `draft`, `dueAt=null`; GitHub-Job `success` allein reicht nicht.

## Nachgewiesene Testläufe

| Lauf | Ergebnis |
|---|---|
| [#37925480101](https://github.com/derJosef/social-assets/actions/runs/37925480101) | **PASS:** sicherer Smoke-Test, dauerhafter Report, keine Buffer-Änderung |
| [#37925672233](https://github.com/derJosef/social-assets/actions/runs/37925672233) | **BLOCKED:** echtes Modell reagierte nicht mit JSON |
| [#37925805399](https://github.com/derJosef/social-assets/actions/runs/37925805399) | **BLOCKED:** gesicherte Diagnose: Modell HTTP 200, `text/plain`, 4 Bytes |
| [#37925987036](https://github.com/derJosef/social-assets/actions/runs/37925987036) | **DIAGNOSE:** GitHub Models antwortet `OK\r\n`, keine Inferenz |
| [#37926453890](https://github.com/derJosef/social-assets/actions/runs/37926453890) | **PASS:** drei redaktionell vorbereitete Datenschutz-Beiträge, Quellen, Bild und Original-Logo, QA, 3 Buffer-Entwürfe und unabhängige API-Prüfung |

Erfolgsbeleg: [orchestration/reports/2026-10-09-ki-chatdaten-drittanbieter-run-37926453890.json](../orchestration/reports/2026-10-09-ki-chatdaten-drittanbieter-run-37926453890.json).

**Grenze:** Ein Workflow mit Quelle-Brief und optionalem Modell ersetzt noch keine allgemeine selbstständige Themenfindung ohne Quellen-Eingabe. Ein autonomer wöchentlicher Discovery-Lauf muss separat eingerichtet und getestet werden, bevor der vorhandene ChatGPT-Montagstimer ersetzt wird.
