# 17.10.2026: Erstversuch der sechs Buffer-Draft-Bilder, eindeutige Medien-Reconciliation und Recovery-Fix

## Gesicherter Iststand

Der von Josef ausdrücklich genehmigte [PR #38](https://github.com/derJosef/social-assets/pull/38) wurde nach 7/7 CI-Checks auf `main` gemergt, Merge `338a39cb7d7172f855858916eb653be0b6e1efed`. Der anschließende genau einmalige autorisierte [GitHub-Lauf #39014602383](https://github.com/derJosef/social-assets/actions/runs/39014602383) scheiterte bei der **allerersten** Buffer-`editPost`-Anfrage: `Buffer meldet einen GraphQL-Fehler`. Der Fehlertext des Providers wird vom Buffer-Client sicher maskiert. Der Test beweist **nicht** die exakte Fehlerursache.

Die `automation-receipts`-Branch-Rücklese beweist:
- `delivery-receipts/legacy-six-image-edit-batch-20261017.json` ist `pending_manual_reconciliation_on_failure` für alle sechs festgelegten Post-IDs, `github_run_id=39014602383`.
- **Nur ein einziges** individuelles Pending-Receipt wurde angelegt: `delivery-receipts/legacy-six-image-edit-20261017-6ac8d5a926e224ee545ee6b5.json`, LinkedIn/„Wer liest mit?“, Originaltext-SHA256 `769759595c3f0f535f3d234f0f4fe65ff8d1e187898ce593a8c91e9d7436182b`.
- Für die weiteren fünf Post-IDs existieren **keine** Edit-Receipts, also hat der Job deren Änderungsaufrufe nachweislich nicht erreicht.

Eine neue **rein lesende**, durch ChatGPT gestartete [Buffer-Bestandsabfrage #39014680061](https://github.com/derJosef/social-assets/actions/runs/39014680061) endete erfolgreich. Das vollständige zeitlich begrenzte Prüfartefakt `buffer-editorial-review-39014680061/current-buffer-posts.json` wurde zusätzlich geprüft, nicht nur die Log-Vorschau. **Alle sechs** Post-IDs stehen weiterhin `draft` bei `due_at=null` und haben **genau die ursprüngliche Bild-URL**, einschließlich des ersten LinkedIn-Posts. Dieser erste Buffer-Text ist SHA256 `769759595c3f0f535f3d234f0f4fe65ff8d1e187898ce593a8c91e9d7436182b` und stimmt mit seinem vor dem Schreibversuch abgelegten Receipt überein.

Quell-URLs unverändert:
- „Wer liest mit?“ LI/FB/IG `https://raw.githubusercontent.com/derJosef/social-assets/main/media/images/2026-10-09-ki-chatdaten-drittanbieter-branded.png`.
- „Ein Agent. Drei Tests“ LI/FB/IG `https://raw.githubusercontent.com/derJosef/social-assets/main/media/images/2026-10-09-ein-agent-drei-tests-branded-test.png`.

**Fazit:** Keines der sechs Zielbilder wurde ersetzt, kein Post hat seinen Draftstatus oder Termin verändert. Vorherige Pending-Receipts **niemals löschen, überschreiben, zurücksetzen oder als erfolgreich kennzeichnen**.

## Wahrscheinliche technische Ursache, anhand des Buffer API-Vertrags eindeutig als Codefehler belegbar

Der erste Aufruf betrifft **LinkedIn**. Der PR #38 serialisierte aktuell gespeichertes `LinkedInPostMetadata.type=post` aus Buffer in die **Eingabe** `metadata: {linkedin:{type:"post"}}`. Das ist unzulässig. Das offizielle Inputobjekt [LinkedInPostMetadataInput](https://developers.buffer.com/types/LinkedInPostMetadataInput.html) erlaubt **nur** `annotations`, `firstComment` und `linkAttachment`; kein Feld `type`. Der Outputtyp [LinkedInPostMetadata](https://developers.buffer.com/types/LinkedInPostMetadata.html) hat dagegen sehr wohl `type`. LinkedIn-Create mit `metadata=null` wurde in derselben Integration bereits früher erfolgreich getestet.

Die **genaue Buffer-Fehlerantwort wurde vom Client nicht protokolliert**; das ist deshalb ein höchst plausibler, offiziell belegter Schemakonflikt, keine behauptete forensisch bestätigte Server-Fehlermeldung. Der Fix setzt LinkedIn-`metadata=null` ohne ersten Kommentar oder `metadata={linkedin:{firstComment: ...}}` wenn vorhanden. Für Facebook/Instagram bleibt der entsprechende Input-`type` erlaubt.

## Sichere Recovery-Konstruktion, NICHT aktiviert

Ein gesonderter, zunächst **nicht gemergter** Reparatur-PR führt einen **neuen, eindeutig anderen** `issue_comment`-Owner-Trigger `LEGACY_SIX_DRAFTS_RECOVERY_AFTER_INDEPENDENT_AUDIT_ONCE_20261017` und separate neue Receipt-Namen ein. Vor **jedem** neuen Schreibvorgang werden:

1. beide alten GitHub-Receipts vom GitHub-API read-only geholt, Base64/JSON geprüft, `state=pending_manual_reconciliation_on_failure`, genau `github_run_id=39014602383`, alter Post-ID- und Hash-Bestand;
2. alle fünf übrigen **alten** Einzelbelege als nicht existent nachgewiesen;
3. sämtliche sechs **jetzigen** Buffer-Posts samt `draft`, `dueAt=null`, Plattform, Tags, Live-Text, aus Buffer abgefragten aktuellen Metadaten und **exakter alter Medien-URL** unabhängig geprüft; erster Text muss weiterhin exakt die vorherige SHA besitzen;
4. beide neuen Original-Logo-4:5-Bilder vom festgepinnten Git-Commit `ac03f948b5ed24dd49c3363dfdef7c82de01810b` SHA- und Format-geprüft;
5. neue Recovery-Batch-Receipts erst **nach** vollständigem Preflight erstellt und vor jeder Mutation ein separates neues individuelles Pending-Receipt gespeichert.

Bei ANY Unstimmigkeit stoppt der Recovery-Code ohne Mutation. Auch beim Recovery gilt **ein Versuch, kein Retry**. Nach sechs unabhängigen Buffer-Rücklesungen wird ausschließlich der **neue** Recovery-Batch als geprüft markiert. Historische Pending-Receipts bleiben für immer erhalten.

**Freigabegrenze:** Der bisherige Benutzerwunsch `ja` berechtigte ausschließlich zum einmaligen originalen PR #38-Edit-Workflow, der jetzt beendet ist. Ein Recovery-Merge plus erneuter, tatsächlich schreibender Buffer-Auftrag braucht Josefs **ausdrückliche neue Freigabe**. Kein erneuter Trigger ohne diese Freigabe. Drei weitere Legacy-Posts bleiben unverändert. Diese Reparatur ordnet keine Veröffentlichung an.
