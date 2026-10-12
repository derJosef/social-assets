# AI Agent Builder: datierte Buffer-Drafts zuerst, Josefs Freigabe danach

**Status 12.10.2026: Review-Zweig PR #13 – nicht nach main gemergt, nicht produktiv aktiviert.**

## Verbindliche Freigabereihenfolge

Josef hat am 12.10.2026 die vorübergehend vorgesehene persönliche
Kampagnen-Brief-Freigabe **vor** dem Draft-Transfer aufgehoben.

1. Die wöchentliche Recherche und Produktion erstellt drei **redaktionell,
   technisch und markenbezogen geprüfte** Beiträge für LinkedIn, Facebook
   und Instagram samt geprüftem 4:5-Markenbild.
2. Der Automationslauf überträgt diese Beiträge ohne vorherige individuelle
   Brief-Freigabe nach Buffer als **datierte, aber unveröffentlichte Drafts**.
   Die Quellen-, Brand-/Original-Logo-, Bildkennzeichnungs-, Kanal-, Media-Hash-,
   Termin- und Drei-Kanal-Qualitätsprüfungen bleiben verbindlich.
3. Der Sender verwendet ausschließlich `createPost` mit
   `saveToDraft:true`, `mode:customScheduled` und `dueAt` aus dem
   manifestgebundenen UTC-Termin. Keine Aktion mit `saveToDraft:false`.
4. Die Erstellung wird nur als PASS gemeldet, wenn für jeden Beitrag ein
   dauerhafter Einmal-Receipt mit Buffer-Post-ID vorliegt und der unabhängig
   zurückgelesene Buffer-Status exakt `draft`, passender Kanal und passender
   `dueAt` lautet. Unklare Ergebnisse: STOP ohne erneute Sendung.
5. Der ChatGPT-Wochenbericht zeigt Bild, drei Texte, kanalbezogene Termine,
   tatsächliche Buffer-Post-IDs und **nachweislich gültige** Links. Niemals
   Deep Links aus einer bloßen Post-ID raten.
6. Erst **nach** der Prüfung der fertigen Entwürfe sagt Josef `freigegeben`,
   bearbeitet einen Draft direkt in Buffer oder gibt Änderungshinweise. Seine
   Änderungen in Buffer sind verbindlich und dürfen nicht durch alte
   GitHub-Dateien überschrieben werden.
7. Eine spätere Freigabe zur Veröffentlichungswarteschlange bezieht sich
   ausschließlich auf diese **bereits bestehenden** Post-IDs. Vor einer
   technischen Aktivierung sind aktuelle Buffer-Text-, Bild-, Zeit-, Kanal-,
   ID- und Draft-Daten zu prüfen. Derzeit ist `scripts/buffer_schedule.py`
   hierfür **noch nicht geeignet**: Er verwendet alte GitHub-Bilder/Texte
   und verweigert geänderte Drafts. Deshalb darf dieser alte Weg für
   datierte Drafts nicht freigeschaltet werden. Änderungen an Medien, deren
   aktuelle Version die API nicht vollständig lesen kann, müssen bis zur
   verifizierten, verlustfreien Freigabefunktion manuell in Buffer freigegeben
   werden. Kein stilles Überschreiben.

## Live nachgewiesener Buffer-Draft

Der einmalig von Josef freigegebene [Run 38179032859](https://github.com/derJosef/social-assets/actions/runs/38179032859)
hat `saveToDraft:true` plus `mode:customScheduled` plus `dueAt`
erfolgreich geprüft. Buffer antwortete mit `status=draft` und
`dueAt=2027-02-08T12:00:00Z` (nur technischer Zukunftstest, kein
Kampagnentermin), Post-ID `6acc083fea568e911a4249f0`.
Der [Receipt](../delivery-receipts/2026-10-11-prescheduled-draft-probe.json)
belegt das Ergebnis. **Diesen Einmaltest niemals wiederholen.**

## Architekturgrenzen

- Der alte `brief_approval_gate.py` bleibt als historische, isolierte
  Proof-of-Concept-Datei bestehen. Er darf nicht mehr vom aktuellen
  Draft-Sender oder dem Kampagnen-Orchestrator aufgerufen werden.
- Ein **neuer** Brief wird durch eine neue
  `orchestration/briefs/YYYY-MM-DD-slug.json` angestoßen; ein
  Freigabe-JSON triggert keine Entwurfserzeugung. Updates existierender
  Briefs sind keine automatische Wiederholung.
- `scripts/buffer_draft.py` führt vor dem ersten Buffer-Zugriff das volle
  `autonomous_campaign_gate.check_campaign` samt Bildprüfung aus und
  vergleicht die drei lokalen Posts mit ihren vorbereiteten Texten.
  `posting_times` aus dem Manifest sind vorab als lokale Zeit und UTC
  wechselseitig zu prüfen.
- Schutz gegen Mehrfachversand: unveränderliche Media-Commit-SHA,
  Hashprüfung des tatsächlich ausgelieferten Bildes, Einmal-Receipts
  (inklusive offenem `pending`), isolierte Output- und Receipt-Branches.
- Die aktuelle Produktionsarchitektur und der Receipt-Ledger benötigen
  noch eine eigenständig geprüfte sichere GitHub-Branch-Schutzkonfiguration;
  **kein Merge, keine GitHub-Settings-Änderung und kein Live-Buffer-Test**
  durch dieses Dokument.
- Das derzeitige Bildverfahren setzt weiterhin eine vorhandene geprüfte
  Quellbilddatei und ein `visual-reviews/<campaign>.json` voraus. Die
  automatische Erzeugung/Bereitstellung eines wirklich neuen 4:5-Quellbilds
  über die ChatGPT-Wochenautomation ist als End-to-End-Schnittstelle
  **noch nicht nachgewiesen**. Deshalb keinen vollständig funktionierenden
  Wochenlauf behaupten, nur weil die Draft-Vorabfreigabe entfällt.
- Die PersonalOS-Recherche verlangt mindestens **zwei unabhängige aktuelle
  Postingzeit-Studien pro Kanal**. Die bisherigen PR-#13-Slotwerte stützen
  sich nur auf Buffer und sind deshalb noch nicht produktionsreif.
- Die separate finale Freigabe schaltet niemals ohne Josef-Entscheidung
  automatisch die Warteschlange oder Veröffentlichung frei.

## Offline-Prüfung

```bash
python3 -B -m unittest discover -s tests -q
```

Die Tests simulieren Buffer und GitHub. Sie beweisen keinen neuen Live-Transfer
und auch keine nachträgliche Bearbeitungs-/Freigabefunktion in Buffer.
