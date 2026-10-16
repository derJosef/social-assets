# Buffer-Fehlerdiagnose ohne Datenabfluss – 16.10.2026

**Status:** Entwurf, rein offline geprüft, **nicht produktiv aktiviert**. Marken-, Personen- und Buffer-Draft-Regeln aus PersonalOS bleiben führend; diese Datei ist nur ein technischer Beleg.

## Anlass und Evidenz

Der echte [Actions-Lauf #38748011264](https://github.com/derJosef/social-assets/actions/runs/38748011264) am 15.10. scheiterte erst nach erfolgreichem Rohbild-Import, Adobe-SHA-Abgleich, Original-Logo-Compositing und Asset-Sicherung beim **ersten LinkedIn-Buffer-`createPost`** mit dem Typ `InvalidInputError`. Der auf dem geschützten Receipt-Ledger vorhandene Sicherheitsbeleg

`delivery-receipts/f0361bec557d3fb7e6f4d75b.json`

steht weiterhin auf `pending_manual_reconciliation_on_failure`. Für Facebook und Instagram wurde nach dem ersten Fehler keine Mutation gestartet. Ein vorhandener [read-only Audit-Lauf #38749047157](https://github.com/derJosef/social-assets/actions/runs/38749047157) erfasste 26 bestehende Posts ohne diesen neuen Testentwurf. Er hat keine Buffer-Objekte geschrieben.

Laut [Buffer Error Handling](https://developers.buffer.com/guides/error-handling.html) kann ein fehlgeschlagener `createPost` im `MutationError.message` eine konkrete Erklärung liefern. Unsere `CREATE_DATED_DRAFT`-Mutation fragt dieses Feld bereits ab, aber `scripts/buffer_draft.py` hatte nur `__typename` protokolliert. Die originale Fehlermeldung des gescheiterten Live-Laufs ist daher **nicht rückwirkend rekonstruierbar**.

## Gezielter Code-Patch (ohne neue Aktionen)

- `scripts/buffer_error_diagnostics.py` ordnet **untrusted** `message`-Inhalte ausschließlich **statischen, vorher definierten Kategorien** zu: `media_dimensions`, `media_access`, `media_format`, `posting_time`, `post_text`, `channel`, `post_metadata`, `permissions`, `limits`, `media_other`, `unknown`.
- Auch der GraphQL-`__typename` wird auf eine kleine feste Positivliste abgebildet. Ein fremder oder manipuliert aussehender Typ wird im Log ausschließlich als `OtherMutationError` ausgegeben.
- Der rohe API-`message`-Text, URLs, Geheimnisse, personenbezogene Daten, Benutzerkommentare, Kundentexte oder Buffer-IDs werden **nicht** als Meldung, Log, Exception oder Receipt persistiert. Überlange, fehlende oder nicht-stringförmige Nachrichten liefern `unknown`; alle Protokollausgaben sind rein vordefinierte Konstanten.
- `scripts/buffer_draft.py` erhält **nur** den Austausch seiner bisherigen Fehler-Ausgabe um die gekapselte Klassifikation; das bestehende `raise RuntimeError` bleibt. Original-Mutationsdefinition, `createPost`-Argumente, `saveToDraft:true`, `dueAt`, Github-Pending-Receipt, Statusprüfung und fehlender Retry bleiben **unverändert**.
- Offline-Tests: offizielle Beispiel-Fehlermeldung `Text is required`, relevante Fehlerthemen, falsche Datentypen, extrem lange Nachrichten, manipulierte Typen, injizierte GitHub-Logkommandos/Secrets/URLs und der tatsächliche **Fail-Closed-Sendpfad** (genau ein synthetischer `createPost`, genau ein Pending-Receipt, keine zweite Mutation oder Leseoperation).

**Sicherheitshinweis:** Eine Kategorie ist ein **Indiz zur Eingrenzung, kein nachgewiesener Root Cause**. Bei uneindeutigen Provider-Texten wird `unknown` gemeldet; es wird niemals frei auf mögliche Rückschlüsse/Anweisungen aus dem Text reagiert. Die API-Dokumentation beschreibt gegebenenfalls auch aktuell andere erforderliche Eingabefelder (z. B. `needsApproval`); daraus folgt nicht, dass der historische Fehler dadurch ausgelöst wurde. Änderungen an Mutation/Metadaten sind **nicht** Teil dieses Patches.

## Unveränderte Betriebsgrenzen

1. Kein Buffer-Kontakt oder Adobe-Transfer im Test; GitHub-Workflow und Secrets bleiben unverändert.
2. **Kein erneuter Versand** des E2E-Testauftrags `2026-10-15-drei-kontrollpunkte-e2e`; der Pending-Beleg bleibt unberührt.
3. Nach Review/Merge würde die Diagnose **erst bei einer später separat legitimierten neuen Buffer-Anfrage** eine Kategorie ausgeben. Der PR erklärt nicht nachträglich, was beim Lauf #38748011264 der Fehler war.
4. Jeder spätere Live-Test braucht einen **neuen eindeutigen Auftrag**, vorherige Bestandsprüfung und die weiter gültigen Rechtemanifeste; keine automatische Veröffentlichungsfreigabe.

[Offizielle Buffer-Fehlerbehandlung](https://developers.buffer.com/guides/error-handling.html).
