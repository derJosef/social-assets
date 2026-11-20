# PF-03 – Vorbereitung, keine Buffer-Auslieferung (20.11.2026)

**Status: BLOCKIERT – 0/3 Buffer-Drafts verifiziert.** Dieser Branch darf nicht als Trigger für PF-02 oder PF-01 dienen. Keine Queue, keine Veröffentlichung.

## Thema
**„Wer kennt die Geschichten hinter den Fotos?“** Familienbilder nicht nur digitalisieren: Personen, Aufnahmeort, Jahr und die Erinnerung der Erzähler festhalten. Anders als PF-02 (UNESCO-Digitalisierung) liegt der Schwerpunkt auf dem *Wissen hinter dem Foto* und dem gemeinsamen Gespräch zwischen Generationen.

## Entwürfe
**Facebook:** „Ein Foto zeigt einen Augenblick. Aber wer erzählt uns, was damals passiert ist? Fragt beim nächsten Familienbesuch nach den Namen, dem Ort und der Geschichte hinter einem alten Bild. Notiert die Antworten und sichert das Foto digital – bevor die Erinnerung verloren geht. Welches Familienfoto würdet ihr gerne besser verstehen? https://picturefix.de #Familiengeschichte #AlteFotos #Erinnerungen #PictureFix

Bildhinweis: KI-generierte Werbeillustration – kein tatsächliches Restaurierungsergebnis.“

**Instagram:** „Die wertvollste Bildunterschrift schreibt oft Oma. Ein Name. Ein Jahr. Eine kleine Geschichte. Nehmt euch am Wochenende ein altes Familienfoto vor und fragt nach seiner Geschichte. Speichert Foto und Erzählung gemeinsam. Welches Foto würdet ihr auswählen? #Familienfotos #Familiengeschichte #ErinnerungenBewahren #PictureFix

KI-generierte Werbeillustration – kein tatsächliches Restaurierungsergebnis. picturefix.de“

**Pinterest:** Titel: „Alte Familienfotos: Geschichten für morgen bewahren“. Text: „Drei Angaben machen aus einem alten Familienfoto eine bleibende Erinnerung: Wer ist zu sehen? Wo entstand das Bild? Was passierte damals? Fragt Angehörige, notiert die Geschichte und digitalisiert das Foto. Mehr: https://picturefix.de. KI-generierte Werbeillustration – kein tatsächliches Restaurierungsergebnis.“ #Familienfotos #Fotoarchiv #Erinnerungen

## Zeitfenster – vorläufig, nicht an Buffer übertragen
Facebook Dienstag 01.12.2026 12:00 MEZ; Instagram Dienstag 01.12.2026 18:00 MEZ; Pinterest Donnerstag 03.12.2026 10:00 MEZ. Diese Termine vermeiden die belegten PF-02-Zeiten (25./26.11.) und den PF-01-Pinterest-Termin (23.11.). Datenlage: Buffer 2026 Facebook https://buffer.com/resources/best-time-to-post-on-facebook/ und Instagram https://buffer.com/resources/when-is-the-best-time-to-post-on-instagram/; Sprout Social März 2026 https://sproutsocial.com/insights/best-times-to-post-on-social-media/ . Die Anbieter zeigen abweichende Zeitfenster; keine eigenen belastbaren PictureFix-Kontodaten geprüft. Die Quellen wurden aus der PF-02-Dokumentation übernommen, nicht erneut live validiert. Vor Auslieferung neu prüfen.

## Bild / technischer Blocker
Ein neues sepiafarbenes Hochformatmotiv (Großmutter und Enkelin mit Fotokiste, aus altem Papierfoto herausragend) wurde in dieser Ausführung lokal erzeugt. Es ist **nicht** als GitHub-Asset oder Buffer-Bild hochgeladen und enthält **nicht** das geprüfte Original-PictureFix-Logo. Es darf deshalb nicht als fertiges Kampagnenbild ausgegeben werden. Die Bildgenerierung ist eine Werbeillustration, keine Restaurierung. Vor Upload: Original-Logo aus `derJosef/picturefix-de-website/app/public/assets/brand/PictureFixLogo_Web.png` bytegenau übernehmen, PNG-Formate 1080×1350 und 1000×1500 erzeugen, Hashes prüfen und Bild über freigegebenen GitHub-Binärweg bereitstellen.

Die vorhandene PF-02-Bridge `scripts/picturefix/pf02_dated_drafts.py` ist **hart auf PF-02** verdrahtet (Kampagnen-ID, Kommandos, SHA256, Event-Validierung, Receipt-Pfade). PF-03 darf diese Kommandos nicht wiederverwenden. Vor der Ausführung eigenen isolierten Runner/Workflow mit Tests und separater Idempotenz implementieren; danach drei separate Buffer-API-Rücklesungen (ID, Kanal, Text, Bild, dueAt, status=draft) und Receipts prüfen. Ohne diese Nachweise: kein Erfolg.

**Unverändert:** PF-01, PF-02, PersonalOS, PictureFix-Restaurierung, Wasserzeichen, PayPal, AI Agent Builder.
