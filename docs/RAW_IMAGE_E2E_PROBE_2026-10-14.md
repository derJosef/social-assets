# E2E-Zwischentest – Rohbild-Compiler → ChatGPT-Bild → unabhängige Eingangskontrolle

**Stand:** 14.10.2026. **Nur isolierter PR, keine Änderung an `main`, Workflows, Adobe oder Buffer.**

## Belegter echter Test

Das reale ChatGPT-Bild ist in dieser Projektunterhaltung am 14.10.2026 entstanden. Es wurde lokal direkt als Original-PNG mit `scripts/cleanroom_image_probe.py` geprüft; kein Compositing, Crop oder Export dazwischen.

- SHA256 der tatsächlich geprüften PNG-Bytes: `22df4bff1d1043929272e93f2c1ace3c7d273efa7c3617db8ee417747033982d`
- Bild: PNG, 2.024.527 Bytes, **1122 × 1402 px**.
- Gegen den zuvor mit `scripts/cleanroom_image_brief.py` kompilierten Standard-Auftrag `scene=document-review; steps=receive,inspect,release; composition=connected-three; figure=none` geprüft.
- SHA256 des ausschließlich strukturiert kompilierten Motivprompts: `4e2e4bad6f6f173cbf6420756e82ce57ebfa6a7f812eda472aa240da978b25bb`.
- Die ChatGPT-Sichtprüfung fand eine **eindeutige blaue holografische Menschengestalt**. Keine eindeutig erkennbaren markenfremden Logos oder Buchstaben; **kein menschliches Abnahmeprotokoll**.
- Das Test-CLI gab **`BLOCKED`** mit `wrong_pixel_dimensions` und `visual_no_people` zurück (Exit-Code 2). Keine Adobe-Übertragung, keine Original-Logo-Montage, keine Buffer-Aktion.

**Wichtig:** Die Umgebung kann nicht beweisen, welchen Modell-Payload die integrierte ChatGPT-Bildgenerierung tatsächlich verarbeitet hat. Ihr Kontroll-/Prompt-Zugang erlaubt nicht, ausschließlich die Ausgabe des Python-Compilers in einem nachweislich leeren Kontext zu übergeben. Daher **`actual_model_prompt_verified=false` und `actual_generator_context_verified=false`**. Dieser Versuch demonstriert einen **negativen Vorstufentest**, keinen geglückten isolierten Generationseinsatz. Das Motiv darf nicht als freigegeben gekennzeichnet oder weitertransportiert werden.

## Was der neue Prüfbaustein kann

`scripts/cleanroom_image_probe.py` vergleicht die exakte Positivlisten-Kompilierung aus `scripts/cleanroom_image_brief.py` erneut mit dem angeblichen Job. Er prüft die vorliegende Bilddatei objektiv auf gültiges PNG, Höchstgröße und genau 1080 × 1350 px. Er bewertet ein **explizit bereitgestelltes, wahrheitsgemäßes ChatGPT-Sichtprüfergebnis**, ohne darin eine menschliche Freigabe zu behaupten. Klare Motivelementverletzungen sperren, uneindeutige winzige Logo-/Textspuren können ausschließlich offen dokumentiert werden. Sein Prüfbericht enthält den Bild-SHA256, den Prompt-SHA256, Prüfergebnis und getrennte Wahrheitswerte für Kontextnachweis.

**Er stellt keine Bild-KI, keinen isolierten Host und keine visuelle Erkennung bereit.** Ein als visuell positiv beschriebener, fehlerfreier Roh-PNG-Test bekommt deshalb nur `PROVISIONAL_ONLY_UNVERIFIED_CONTEXT`, niemals automatisch `transfer_permitted=true`. Die CLI liefert **immer einen Nicht-Null-Exitcode (2)**, auch bei ausschließlich vorläufig positiv bewerteten Rohbildern, um keine unbewiesene Kontextisolierung als Erfolgssignal an Shell-Caller durchzureichen. Diese Vorstufe ist nicht in den produktiven Orchestrator eingebaut.

## Nachweise und Abnahmegrenzen

- Zwölf lokale synthetische Offline-Unit-Tests: **12/12 PASS**, kein Netzwerk; explizit getestet sind dimensionsfalsche PNGs, sichtbare Personen, Bildformat, manipulierte Prompts trotz selbstkonsistentem Hash, Referenz-Injektion, unklare Marken ohne Behauptung eines sicheren Fehlers und nicht vorhandenene Sichtprüfbelege.
- Ein echter, lokal geprüfter, ungeeigneter Bildlauf: **bewusster Negativfall** mit zwei belegten Sperrgründen.
- Nicht nachgewiesen: isolierte Modellkontextübergabe, deterministisch exaktes Ausgabeformat ohne technische Normierung, Live-Adobe-Transfer des neuen Motivs oder Buffer-E2E.
- Die von Josef gewünschte holografische Person ist weiterhin **ein eigener genehmigungspflichtiger Personensonderfall**, nicht ein stilles `no_people=true`.
- Bestehender, bereits erfolgreich demonstrierter ChatGPT→Adobe-Transfer, der kanonische Logo-Compositor, alle Buffer-Draft-/Freigabegates und der bestehende Rückfallweg bleiben unberührt.

## Der nächste technische Entscheidungspunkt

Für eine nachweisliche Clean-Room-Erzeugung wird **eine von der Bild-KI getrennte, kontrolliert ansprechbare Host-Schnittstelle** benötigt, die nur den exakten kompilierten Prompt und keine Referenzbilder übergibt und den tatsächlich gesendeten Payload protokolliert. Ein frischer Chat allein oder eine deklarierte Positivliste beweist diese Eigenschaft nicht. Ein zusätzlicher kostenpflichtiger Bild-API-Dienst soll nicht ohne erneute ausdrückliche Entscheidung eingeführt werden. Solange diese Schnittstelle nicht vorhanden ist, den isolierten E2E **nicht** als bestanden ausgeben.

*Owner der dauerhaften Bild- und Kennzeichnungsregeln bleibt PersonalOS; diese Datei ist lediglich ein technischer Testbericht in `social-assets`.*

## Korrektureinordnung vom 15.10.2026 (noch nicht gemergter PR #26)

Die damals als `visual_no_people` gewertete **eindeutig künstliche holografische Figur** ist **nach Josefs mittlerweile im PersonalOS korrigierter Personenregel zulässig**. Dieser damalige Sperrgrund basierte auf einer überholten technischen Hürde und darf nicht als fachlicher Designverstoß verstanden werden. Der bisherige Echtbild-Test bleibt trotzdem `BLOCKED`: Die Native-PNG-Dimensionen 1122 × 1402 entsprechen nicht dem für den Import verlangten 1080 × 1350, und es gibt keinen geprüften Nachweis der Prompt-/Kontextisolation.

Der Folge-Patch unterscheidet nun im Testpfad `figure: hologram` von Fotopersonen, indem er eine explizite, dokumentierte `figure_review` verlangt. `no_people: false` wird **nur** für eine als nicht fotorealistisch belegte Hologrammfigur akzeptiert. Eine fotorealistische Figur wird auf dieser Route weiterhin blockiert. Eine Bildprüfung ist keine nachgewiesene Personenerkennung und keine Freigabe von Veröffentlichung/Buffer.
