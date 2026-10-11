# Nach Brief-Freigabe: datierte Buffer-Entwürfe ohne Veröffentlichungswarteschlange

**Status (12.10.2026): Draft-PR, nicht produktiv aktiviert.** Diese Datei ist
keine Kampagnenfreigabe und keine Anweisung, etwas zu veröffentlichen.

**Fortsetzung zur Branch-Protection:** Der nachgelagerte Draft-PR dokumentiert
die [Trennung von Bot-Ausgaben und geschütztem `main`](BRANCH_PROTECTION_MIGRATION.md).
Bis zur eigenständig freigegebenen Migration gelten dessen Maßnahmen nicht
als produktiv aktiviert.

## Bewiesene Buffer-Funktion

Der von Josef ausgelöste [Einmaltest #38179032859](https://github.com/derJosef/social-assets/actions/runs/38179032859)
bestätigte einen realen LinkedIn-Entwurf mit `status=draft` und
`dueAt=2027-02-08T12:00:00Z`. Der unabhängige API-Readback und der
[dauerhafte Receipt](../delivery-receipts/2026-10-11-prescheduled-draft-probe.json)
stimmten überein. Das Testdatum ist kein Kampagnentermin.

## Zielablauf – nach separater Prüfung und Produktivfreigabe

1. Redaktionelle Quellen und passende Zeitfenster werden pro Plattform
   recherchiert (Europe/Berlin mit Sommer-/Winterzeit). Die unabhängige
   Verbesserung des Zeitplaners befindet sich in **Draft-PR #9**.
2. Josef prüft den vollständigen Kampagnen-Brief, das Original-Bildreview und
   die zugehörigen Texte. Ein **eigener, ausschließlich die Freigabe enthaltender
   PR** wird nur von Josef nach bewusstem Entschluss auf geschützt `main`
   gemergt. Das SHA-256-gebundene Schema stammt aus **Draft-PR #7**;
   neuer Zweck: `dated_buffer_draft_not_queued`.
3. Alle drei möglichen Sendepfade (`social-campaign-orchestrator.yml`,
   `buffer-auto-drafts.yml`, `buffer-draft.yml`) verwenden dasselbe
   `scripts/buffer_draft.py --send`. Automatische `auto-*`-Dateien werden erst
   akzeptiert, wenn die GitHub-Merge-Provenienz und das Kampagnen-QA-Gate
   positiv sind. Der Orchestrator prüft diese Freigabe bereits **vor**
   Inhaltsquellen-Netzwerkzugriff, Bildproduktion oder GitHub-Push.
4. Der Entwurfs-Text muss exakt mit `prepared_content.posts` im freigegebenen
   Brief übereinstimmen. `posting_times[plattform]` des gültigen Manifests
   liefert `dueAt`; der Post darf selbst keinen frei editierbaren Termin
   einschleusen. Termin-Format, Europe/Berlin-Umrechnung, Zukunftsgrenze,
   Kanal und Kampagnenbindung werden unabhängig geprüft.
5. Der Sender reserviert vor dem Buffer-Aufruf einen dauerhaften
   Einmal-Beleg pro Draft-Dateiname auf GitHub. Dann **nur**
   `createPost(saveToDraft: true, mode: customScheduled, dueAt: ...)`.
   Weder `editPost`, Queue-Aktivierung noch Publikation sind enthalten.
6. Der Sender speichert zuerst die erzeugte Post-ID, verifiziert die
   Create-Antwort und liest `post` über die Buffer-API noch einmal unabhängig
   aus: **gleiche Post-ID, gleicher Kanal, Status `draft`, identisches `dueAt`**.
   Nur dann erhält der Receipt
   `state=verified_prescheduled_draft_not_queued`. Der separate Orchestrator-
   Abgleich liest alle drei Receipts und Post-IDs nochmals.
7. Bei einer unklaren Antwort oder einem `scheduled`-Status: **Alarm und
   Stopp, keine automatische Löschung, Korrektur oder Wiederholung.** Ein
   bestehender `pending`-Receipt bleibt gesperrt; Josef entscheidet über die
   manuelle Buffer-Prüfung.

## Unveränderte Grenzen

- Keine Änderung an `ready-to-schedule/`,
  `buffer-auto-schedule.yml`, `scripts/buffer_schedule.py`, alten Kampagnen
  oder bereits existierenden Buffer-Posts.
- Die separaten, manuell angestoßenen `drafts/`-Dateien behalten den alten,
  **undatierten** Modus. Die ehemals uneindeutigen Dateien direkt unter
  `ready-for-buffer/` ohne `auto-`-Schema werden sicherheitshalber blockiert.
- Die `Powered by AI`-Overlay-Prüfung in **PR #6** und die menschliche
  Vorschau in **PR #8** sind eigene Review-Vorgänge und werden nicht
  stillschweigend mitgemergt.
- Kein anderer PR-Merge und keine neue Live-Buffer-Mutation wurden durch
  die Erstellung dieser Implementierung autorisiert.
- **Wichtiger Aktivierungsblocker:** `main` muss mit tatsächlich wirksamer
  Branch-Protection und ohne ungeprüften Bot-Bypass für die Freigabequelle
  geschützt werden. Gleichzeitig verwenden aktuelle Workflows GitHub-
  Schreibrechte für die dokumentierten Assets und Einmal-Receipts. Vor einem
  Merge muss diese Wechselwirkung einschließlich Approval-Provenienz,
  Schreibrechten und Rückfallverhalten separat geprüft und gelöst sein.
- Ein freigegebener Brief ist keine Veröffentlichungsfreigabe.

## Offline-Abnahme

```bash
python3 -B -m unittest discover -s tests -q
```

Die Tests simulieren Buffer und GitHub ohne Netzwerkzugriff und decken
erfolgreiche Datumsbestätigung, ein mögliches versehentliches `scheduled`,
unpassenden Readback, doppelte Receipts, fehlende Freigaben, Textänderung,
falschen Kanal, Vergangenheit, DST und die drei Sendepfade ab. **Sie sind
keine Wiederholung des Live-Tests und dürfen nicht als neue externe
Buffer-Abnahme ausgegeben werden.**
