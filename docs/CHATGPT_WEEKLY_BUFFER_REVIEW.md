# ChatGPT-Wochenkampagne: geprüfte Buffer-Draft-Rückmeldung

**Stand 12.10.2026 – nur Integrationsentwurf [PR #13](https://github.com/derJosef/social-assets/pull/13).**
Kein PR-Merge, keine produktiven Buffer-Mutationen durch diese Änderung.

## Was tatsächlich geschieht

Die Wochenkampagne soll automatisiert **drei datierte, aber unveröffentlichte
Buffer-Entwürfe** erzeugen, ohne persönliche Kampagnen-Brief-Vorabfreigabe.
Der Mensch entscheidet **erst nach Sichtung** aller drei fertigen Beiträge
und des Bildes im Buffer-Drafts-Bereich. Direkt in Buffer geänderte Texte,
Medien oder Daten dürfen bei einer späteren Freigabe nicht durch eine
ältere GitHub-Kopie überschrieben werden.

Nach dem Anlegen der drei Drafts verifiziert
\`scripts/orchestrator_verify_buffer.py\` sie **erneut über die lesende
Buffer-GraphQL-API** anhand der drei vorher in GitHub reservierten
Delivery-Receipts. Erforderlich sind für jeden Kanal:

- Exakt eine eigene Buffer-Post-ID und eine eigene Channel-ID, zugeordnete
  Plattform \`linkedin\`, \`facebook\` oder \`instagram\`.
- Status **\`draft\`**, niemals \`scheduled\`, \`buffer\`, \`sent\` oder
  andere Live-Zustände.
- Tatsächlich gespeichertes \`dueAt\` exakt gleich dem geprüften
  Manifest-Zeitwert in UTC und korrekte Darstellung in \`Europe/Berlin\`.
- Von Buffer lesend zurückgelieferter Beitragstext stimmt unmittelbar
  nach Anlage mit der vorbereiteten Version überein.
- Der Buffer-Post besitzt einen lesenden Bildanhang vom Typ \`image\`
  mit einer HTTPS-Asset-Quelle. Das ursprünglich geprüfte 1080×1350
  Markenbild wird zur Vorschau aus einer per Git-Commit-SHA
  unveränderlich gepinnten URL gelesen. **Der Buffer-Asset-Readback
  beweist den Bildanhang, nicht die Pixelgleichheit einer potenziellen
  Buffer-CDN-Kopie.** Das Sender-QA hat vor dem Upload die ursprünglichen
  Medienbytes separat überprüft.
- \`buffer_direct_post_url\` bleibt **null**, bis ein funktionierender
  individueller URL-Pfad tatsächlich mit der Browseroberfläche validiert ist.

Bei Unklarheit wird der nachgelagerte Freigabebericht als **BLOCKED**
ausgegeben. Niemals neue Buffer-Posts anlegen, um fehlende ID oder
unvollständigen Beleg zu „reparieren“.

## Abrufbare Belege pro GitHub-Lauf

Nach jedem GitHub-Orchestrator-Lauf werden auf dem bestehenden isolierten
Ledger-Branch \`automation-receipts\` zwei gleich benannte, run-spezifische
Dateien angelegt:

- \`orchestration/reports/<campaign>-run-<GITHUB_RUN_ID>.json\`:
  maschinenlesbares Protokoll inklusive \`buffer_verification.status\`,
  \`posts.linkedin\`, \`posts.facebook\`, \`posts.instagram\`,
  \`post_id\`, \`channel_id\`, \`dueAt\`, \`scheduled_local\`,
  \`text\`, \`review_image_url\`, \`buffer_asset_url\`,
  \`buffer_link_kind\` und \`buffer_direct_post_url\`.
- \`orchestration/reports/<campaign>-run-<GITHUB_RUN_ID>.md\`:
  lesbare ChatGPT-Wochenübersicht mit drei Beiträgen oder ehrlicher
  BLOCKED-Meldung.

Beide Dateien erscheinen zusätzlich im GitHub-Actions-Job-Summary.
Sie werden als run-spezifische Dateien **nie durch den Folgelauf
überschrieben**. Falls das Ledger-Speichern selbst fehlschlägt,
bleiben die Dateien als GitHub-Actions-Artefakt mit begrenzter
Aufbewahrung erhalten. Das ist dann **kein** bestätigter dauerhafter
Ledger-Beleg; im ChatGPT-Bericht muss der Fehler genannt werden.

Die ChatGPT-Aufgabe „AI Agent Builder Wochenkampagne“ liest über die
verbundene GitHub-Anbindung die Berichte und prüft:

1. Kampagnen- und Wochenkennung passen zum aktuellen Montag.
2. Der GitHub-Run ist \`completed/success\`, das zugehörige JSON
   sagt \`buffer_verification.status=PASS\` und
   \`state=buffer_drafts_verified\`.
3. Es liegen **genau drei** unterschiedliche Post- und Channel-IDs,
   \`draft\`-Status und passende Termine vor.
4. Nur dann die drei Beiträge samt Bild/Datum/Text tatsächlich als
   fertige Buffer-Entwürfe in ChatGPT anzeigen und eine persönliche
   Entscheidung anfordern.
5. Sonst den belegten Teilstand mit \`BLOCKED\` oder \`IN_PROGRESS\`
   mitteilen und **keine** Freigabe behaupten.

Ein GitHub-Lauf, der vor dem Buffer-Readback stoppt, ist selbst dann
nicht abgeschlossen, wenn bereits einzelne Buffer-Drafts entstanden
sein könnten. Keine automatische Wiederholung wegen Duplikatrisiko.

## Welche Buffer-Links aktuell seriös sind

Die GraphQL-Post-API dokumentiert \`id\`, \`text\`, \`channelId\`,
\`status\`, \`dueAt\`, \`assets\`, aber **keinen stabilen direkten
Editor-Link für einen unveröffentlichten Post**.

Deshalb ist derzeit nur der offizielle Einstieg
[Buffer Publish](https://publish.buffer.com) verifiziert.
In Buffer: den jeweiligen Kanal links wählen → **Drafts**;
anhand von Kanal, Termin, Text und im Bericht angegebener Post-ID
den richtigen Beitrag abgleichen. Die drei Berichte erhalten
jeweils den offiziellen Buffer-Einstieg plus eindeutige Post-ID.
Dies **ist kein individueller Post-Link** und darf nicht so
bezeichnet werden.

Sobald ein tatsächlich funktionierender individueller Link in der
authentifizierten Buffer-Oberfläche verifiziert wurde, darf ein
separat getesteter Linkresolver eingeführt werden. Bis dahin
**keine** hypothetischen URLs mit \`/posts/<ID>\`, \`/edit/<ID>\`,
Kanal-ID o. ä. erfinden.

Dokumentationsquellen:
- [Buffer: Saving and scheduling draft posts](https://support.buffer.com/en-us/articles/saving-and-scheduling-draft-posts-CBLXg1yFXp)
- [Buffer API: Post- und Asset-Schema](https://developers.buffer.com/reference.html)
- [Buffer: Drafts und Approvals](https://support.buffer.com/en-us/articles/managing-and-approving-draft-posts-57li7M8tDA)

## Nachgelagerte persönliche Freigabe

Die Ausgabe ist nur ein **Snapshot des unmittelbaren Readbacks**.
Wenn Josef einen Text, ein Bild oder die Uhrzeit später direkt in
Buffer ändert, ist ausschließlich die **jetzt aktuelle Buffer-Fassung**
maßgeblich. \`freigegeben\` im ChatGPT-Dialog erteilt erst die
individuelle Entscheidung über die **schon existierenden** Posts,
aber der bisherige \`buffer_schedule.py\` ist für bearbeitete
vordatierte Entwürfe **nicht verwendbar**. Nie drei neue Posts anlegen
oder alte Texte wieder in Buffer zurückschreiben.

Vor technischer Queue-Aktivierung sind erneut live und ausschließlich
lesend alle Post-IDs, Texte, Medien, Kanäle und tatsächlichen Zeitwerte
abzugleichen; bei Medien, die nicht vollständig auslesbar sind, bleibt
die Freigabe direkt im Buffer-Interface die sichere Möglichkeit.

## Offline-Abnahme

\`\`\`bash
python3 -B -m unittest discover -s tests -q
\`\`\`

Der neue Review-Renderer hat keine Buffer-Mutation und akzeptiert
nur einen vollständig nachgewiesenen Drei-Kanal-PASS. Die Tests sind
synthetisch und **beweisen keinen neuen Live-Buffer- oder
Browser-Deep-Link-Lauf**.
