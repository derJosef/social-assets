# Freigabeordner für Buffer-Entwürfe

**Zwei zulässige Freigabewege:** (a) manuell, ausdrücklich durch Josef freigegebene Beiträge; (b) für die Marke **AI Agent Builder** durch seine Dauerfreigabe vom 09.10.2026 automatisch qualitätsgeprüfte Kampagnen unter `auto-YYYY-MM-DD-<slug>-<kanal>.json`. Alle automatischen Kampagnen benötigen ein geprüftes Manifest in `campaign-manifests/` und den erfolgreichen `autonomous_campaign_gate.py`-Check. Ohne positive Prüfung wird die gesamte automatische Kampagne blockiert.

Jede **neu hinzugefügte** Datei `ready-for-buffer/*.json` startet automatisch die GitHub Action [Buffer – automatisch nur freigegebene Entwürfe](../.github/workflows/buffer-auto-drafts.yml).

- Es wird nur ein **Buffer-Entwurf** angelegt. Keine Terminierung oder Veröffentlichung.
- Die KI darf Postingzeiten festlegen und im Manifest ablegen, sie jedoch nicht ohne ausdrückliche Veröffentlichungsfreigabe in Buffer aktivieren.
- Technische Details: [Dauerberechtigung und QA-Gate](../docs/AUTONOMOUS_BUFFER_POLICY.md).
- Nicht markenkonforme oder unvollständig geprüfte Texte gehören in `drafts/`; die AI-Agent-Builder-Dauerberechtigung hebt die Einzelgenehmigung für geprüfte Entwürfe auf.
- Dateien müssen das Format des vorhandenen [Beispielentwurfs](../drafts/beispiel-linkedin.json) haben.
- Die Dateien sind **öffentlich** einsehbar.
- Bestehende Dateien nicht wiederverwenden oder ändern, um erneut zu senden: Empfangsbelege verhindern doppelte Übertragung.
- Der bestehende Testentwurf wurde bereits übertragen und soll **nicht** hierher kopiert werden.
- Weitere Details: [Anleitung](../docs/BUFFER_DRAFTS.md).

Der GitHub-Entwurfsweg wurde im zentralen Orchestrator-Lauf #37926453890 erfolgreich getestet. Der neue manuelle Veröffentlichungs-Gate-Entwurf aus PR #2 ist noch nicht produktiv und noch nicht live erprobt.

## Keine Veröffentlichungsfreigabe durch diesen Ordner

Eine Datei unter `ready-for-buffer/` löst ausschließlich eine **Draft-Erstellung** aus. Sie stellt niemals eine Freigabe zur Terminierung oder Veröffentlichung dar. Auch ein gespeicherter Postingzeitvorschlag reicht nicht.

Der in [PR #2](https://github.com/derJosef/social-assets/pull/2) vorgeschlagene zukünftige Weg zur Terminierung nutzt einen bewusst gestarteten `workflow_dispatch`, eine Format-v2-Anfragedatei mit Post-ID und Datei-Hash, ein geschütztes GitHub-Environment und eine über die GitHub-Approvals-API nachgewiesene unabhängige Prüfung. GitHub-Settings sowie der gemeinsame Buffer-Zugang bleiben bis zur gesonderten Freigabe kritische Voraussetzungen. Siehe [Terminierungsanleitung](../docs/BUFFER_SCHEDULING.md).
