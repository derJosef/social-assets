# Mehrkanal-Planung: belegte Reservierungen blockieren 35 Tage

Datum: 16.10.2026. **Nur Offline-Korrekturvorschlag; kein Buffer-Schreibzugriff.**

## Auslöser

Der neue, vom Benutzer genehmigte reguläre Kampagnenauftrag [Issue #32](https://github.com/derJosef/social-assets/issues/32) zum Thema „Dokumentversionen statt bloßer Duplikaterkennung“ erzeugte den GitHub-Lauf [#38877416602](https://github.com/derJosef/social-assets/actions/runs/38877416602). Die Checks für Quellen, sieben Bildsichtmerkmale, Adobe-Transfer, SHA256 und vorbereitete Texte bestanden. **Vor** Original-Logo-Compositing und **vor jeglichem Buffer-Create** stoppte `posting_time_planner.py` mit `TimePlanningBlocked: Kein konfliktfreies Zeitfenster für linkedin in 35 Tagen`.

Das ist **kein Adobe-, Bild- oder Buffer-API-Fehler**. Der Workflow verweigerte zurecht das Erzeugen ungesicherter, terminloser Beiträge; Ergebnis für #32 **BLOCKED**. Kein GitHub-Kampagnen-Asset-Branch und kein neuer Buffer-Draft dieser Kampagne existieren.

## Ursachenprüfung der GitHub-Reservierungen

Der Planner reserviert auch vorgeschlagene Daten in vorhandenen `campaign-manifests` – einschließlich bereits entstandener `automation/campaign/*`-Branches mit einem **gescheiterten** Buffer-Versand. Dieses Vorsichtsprinzip und der Mindestabstand von **drei Kalendertagen je Kanal** bleiben unverändert.

| LinkedIn-Slot | Quelle |
| --- | --- |
| 21.10.2026, 16:00 CEST | `ready-to-schedule`, bereits autorisierte frühere Kampagne |
| 28.10.2026, 16:00 CET | `automation/campaign/2026-10-13-lieferanten-pdf-prueftor-e2e-003` |
| 04.11.2026, 16:00 CET | `main/campaign-manifests/2026-10-09-ein-agent-drei-tests` |
| 11.11.2026, 16:00 CET | `automation/campaign/2026-10-15-drei-kontrollpunkte-e2e`, **obwohl Buffer-Create fehlgeschlagen** |
| 18.11.2026, 16:00 CET | `main/campaign-manifests/2026-10-09-ki-chatdaten-drittanbieter` |
| 02.12.2026, 16:00 CET | `main/campaign-manifests/2026-10-10-kundenmail-kein-befehl-005` |

Innerhalb der ursprünglichen 35 Tage lässt diese dichte Abfolge für LinkedIn **keinen** der zulässigen bevorzugten Dienstags-, Mittwochs- oder Donnerstag-Slots mit mindestens 72 Stunden Kanalabstand offen. **Keine einzige Reservierung wird aufgehoben**, insbesondere nicht die alten fehlgeschlagenen E2E-Kampagnen.

## Minimaler Patch

- `MAX_LOOKAHEAD_DAYS = 35 → 56` in `scripts/posting_time_planner.py`. Die fünf Tage Mindest-Redaktionsvorlaufzeit, Quellen-Frischegrenze 30 Tage, Mitteleuropa-Zeitkonvertierung, optimierten Wochen-/Uhrzeitkandidaten und `MIN_CHANNEL_GAP = 3 Tage` bleiben unangetastet.
- Fehlermeldung ist jetzt an das tatsächliche Maximum gebunden statt hartkodiert.
- Zwei neue Regressionstests: a) Konstellation der belegten Termine – nächster erlaubter LinkedIn-Terminvorschlag **25.11.2026, 16:00 CET**, dabei Facebook und Instagram ohne entsprechende Verschiebung; b) bei vollständig belegten 56 Tagen **fail closed**, keine stille Rücksetzung des Abstands.
- Bestehende allgemeine Testgrenze von 35 auf 56 Tage angepasst. Keine Änderung an `buffer_draft.py`, bestehenden Manifesten, `workflow_dispatch`, originaler Logosicherungslogik, ImageGen oder Adobe.

## Wiederanlauf erst nach separater Merge-Entscheidung

**Issue #32 nicht erneut auslösen:** Sein Workflow scheiterte nach geprüfter Adobe-Quelle, aber vor Asset-/Buffer-Schreiben. Ein einmaliges neues Kampagnenbriefing braucht eine **neue Kampagnen-ID**, dieselbe zuvor importierte und anhand SHA geprüfte 4:5-Quelle sowie neue Duplikat- und Zukunftsdatumsprüfung. Ein bloßer `Re-run jobs` ist keine zulässige neue Kampagne.

Wird die Korrektur freigegeben und auf `main` gemergt, kann ChatGPT den neuen, eindeutig identifizierten regulären, datierten **Draft-only**-Auftrag vorbereiten und den GitHub-Live-Gates übergeben. Das ist keine Freigabe zur Veröffentlichung, kein Queue/Publish und keine Umwandlung zu `scheduled`. Buffer-Erfolg erst nach separatem Readback behaupten.
