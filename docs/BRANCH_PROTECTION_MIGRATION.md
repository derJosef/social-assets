# Migrationsplan: geschütztes main ohne Stillstand der Wochenkampagne

**Status 12.10.2026: Review-Zweig PR #13, kein Live-Rollout.**
Die zwischenzeitlich verlangte persönliche Brief-Freigabe **vor** Buffer-Drafts
ist widerrufen. Josef gibt erst die vollständig erstellten, vorab datierten
Buffer-Drafts frei, nicht den vorbereitenden Brief.

## Schreib- und Vertrauensgrenzen

| Objekt | Ziel | Berechtigung / Kontrolle |
| --- | --- | --- |
| Redaktioneller Kampagnen-Brief, geprüfter Quellbildreview und Workflow-Code | geschütztes `main` | kontrollierte Änderungen; neue Briefdatei startet Qualitätsprüfung und Draft-Produktion |
| Neues Original-Logo-Markenbild, Manifest und drei Postdateien | einmaliger `automation/campaign/<kampagne>`-Branch | Bot; SHA-256-Bildcheck, 4:5-Review, Original-Logo, optional Powered by AI |
| Media-Links der drei Buffer-Drafts | exakter, unveränderlicher 40-stelliger Git-Commit-SHA | unabhängiger öffentlicher Download und Byte-Hashprüfung vor Buffer |
| Delivery-Receipts und Kampagnen-Reports | `automation-receipts`-Branch | niemals blind erneut senden; `pending` verhindert Duplikate |
| Finale Entscheidung zur Veröffentlichung | Josef nach ChatGPT-/Buffer-Draft-Ansicht | keine vorherige Brief-SHA-Freigabe; keine Bot-Queue ohne konkrete finale Freigabe |

Der Orchestrator läuft aus geschütztem `main` und bietet nun einen
**vollständig automatischen Owner-Issue-Eingang**, der ohne wöchentlichen
Brief-Merge auskommt: ChatGPT erstellt genau ein neues Issue
`AIAGENT_BRIEF:YYYY-MM-DD-slug` als Eigentümer `derJosef`, der GitHub-
`issues: opened`-Trigger verwendet den vertrauenswürdigen Code auf
`main`, und `issue_brief_intake.py` schreibt den strikt geprüften
JSON-Brief nur lokal im Runner. Der Original-Brief wird im isolierten
Kampagnen-Branch archiviert. Kein öffentlicher Fremd-Issue darf einen
Draft-Prozess starten. Der zuvor bestehende Pfad über neue
`orchestration/briefs/*.json`-Dateien auf `main` bleibt als manuelle
PR-Alternative erhalten, ist aber **nicht** der autonome Wochenweg.
`prepared_brief_preflight.py` und volle fachliche, technische und
bildseitige QA bleiben verpflichtend. Änderungen bestehender Briefe,
Issues und alte `orchestration/approvals/*.json` starten keine erneute
automatische Kampagne.
Das historische `brief_approval_gate.py` ist kein produktives Draft-Gate mehr.
Die fachliche Qualitätsprüfung liegt unmittelbar vor Buffer nochmals im
gemeinsamen Sender `buffer_draft.py`; dies schützt alle drei Einstiegspfade.

Der Output-Branch wird einmalig und atomar in zwei Commits aufgebaut:
zuerst das geprüfte Bild, danach die mit diesem Bild-Commit-SHA verbundenen
fünf Plan-/Postdateien. Kein Bot-Direktpush auf `main`.

## Receipt- und Wiederholungsschutz

Die bisherigen Receipts auf `main` bleiben lesbar und gelten vorrangig.
Fehlt dort ein Receipt, muss der `automation-receipts`-Branch existieren;
neue Reservierungs- und Erfolgsbelege werden nur dort geschrieben.
Ein vorhandener Erfolgs- oder Pending-Beleg sperrt einen erneuten Buffer-
Aufruf. Ein fehlender Ledger-Branch stoppt den Versand, niemals automatische
Ledger-Erstellung oder ungesicherte Wiederholung.

## Sichere Aktivierungsreihenfolge – noch NICHT ausgeführt

1. Vollständigen Draft-first-Integrationszustand aus PR #13 zusammen mit den
   Vorläufer-PRs #7/#11/#12 sowie #6/#9 überprüfen; kein Merge ungefragt.
   Gestaffelte Alt-PR-Merges dürfen die Wochenkampagne nicht zwischenzeitlich
   wieder an einen persönlichen Brief-Freigabe-PR koppeln. Bevorzugt eine
   einzige überprüfbare Integration oder ein klarer atomarer Aktivierungsplan.
2. `automation-receipts` einmalig initialisieren, Inhalt und Rechte
   unabhängig lesen; Branch gegen Löschen und Force-Push schützen, aber
   normale append-artige Belegschreibungen des Bots erlauben.
3. `main` erst nach Entfernung aller Bot-Direktpushes über GitHub Ruleset
   oder Branch-Protection schützen: PR-Pflicht, vorher grün beobachtete
   erforderliche Checks, kein ungeprüfter Administrator-Bypass, keine
   Force-Pushes oder Löschung. Nicht aus Versehen den einzigen Eigentümer
   mit fremder Review-Pflicht aussperren.
4. `branches/main.protected == true` lesen und genau drei Wege offline/
   read-only prüfen: Kampagnenorchestrator, `auto-*`-Sender und manueller
   Draft-Dispatch. Asset-Branches, Receipts, Kollisions- und DST-Planung
   sowie öffentliche Bild-URLs ebenfalls prüfen. Kein weiterer Live-Probe-
   Buffer-Post: Test [38179032859](https://github.com/derJosef/social-assets/actions/runs/38179032859)
   belegt `draft` mit `dueAt` bereits.
5. Die neue, rein offline getestete Bildvorstufe
   (`automatic_image_source.py`: GPT Image → zwei Maschinenprüfungen →
   4:5 → kanonisches Original-Logo) braucht **noch** einen Live-API-Test
   sowie den Nachweis ihrer vollständigen Verbindung zu GitHub/Buffer.
   Echte Buffer-Draft-Links müssen in der ChatGPT-Wochenaufgabe gesichert
   ausgabefähig sein. Grüne synthetische Tests allein genügen nicht.

## Finale Freigabe: Buffer-Bearbeitungen erhalten

Bei `freigegeben` müssen die **drei bestehenden Buffer-Post-IDs** erneut
gelesen und Draft-Status, Kanal, Zukunftstermin, Text, Bilder/Medien und
mögliche manuelle Änderungen berücksichtigt werden. Keine zweite Post-
Anlage und kein erneutes Zurückspielen eines alten GitHub-Texts.

**Offener technischer Blocker:** Der bisherige `buffer_schedule.py`-
Workflow unterstützt datierte Receipts und in Buffer veränderte Texte/
Medien noch nicht verlustfrei. Deshalb keine Nutzung dieses Legacy-
Releasewegs für diese neuen Posts, bis eine gesonderte sichere Lösung
mit unabhängigen Tests und Live-Readback vorliegt. Der alte Weg darf
keinesfalls stillschweigend in dieser Migration aktiviert werden.

## Weitere Grenzen

- Mindestens zwei methodisch unabhängige aktuelle Postingzeiten-Studien
  pro Kanal; Datumsvergleich, Aktualitätsprüfung, eigene verfügbare
  Accountdaten und Europe/Berlin-DST.
- Neue 4:5-Basisgrafik plus geprüftes Original-Logo; KI-Personenbilder
  inklusive notwendiger Kennzeichnung.
- Veraltete `ready-to-schedule`-Anfragen bleiben gesondert,
  explizit genehmigungspflichtig. Sie sind kein Mechanismus, um
  datierte Drafts mit ungeprüften Änderungen freizugeben.
- Kein Queue- oder Veröffentlichungsaufruf ohne Josefs abschließende
  persönliche Freigabe. Kein Merge oder Buffer-Live-Test durch dieses Dokument.

Offline-Tests: `python3 -B -m unittest discover -s tests -q`.
