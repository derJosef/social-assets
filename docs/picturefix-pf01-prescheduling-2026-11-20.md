# PictureFix PF-01 – Freigabevorbereitung vom 20. November 2026

Josef hat die vorhandenen drei visuellen Entwürfe ausdrücklich für gut befunden und um möglichst frühe **Terminierung zur anschließenden eigenen Freigabe** gebeten. Nicht autorisiert: sofortige Veröffentlichung, Verschieben in die Warteschlange, Erstellen weiterer Posts, Änderungen an anderen Marken oder dem PictureFix-Produktionssystem.

| Kanal | Lokales Fenster (Europe/Berlin, MEZ) | UTC `dueAt` | Bestehende Buffer-ID |
| --- | --- | --- | --- |
| Facebook | Freitag, 20.11.2026, 18:00 | `2026-11-20T17:00:00Z` | `6b000e650f5eda1a57d7fda0` |
| Instagram | Freitag, 20.11.2026, 21:00 | `2026-11-20T20:00:00Z` | `6b000ee54c1afd05de096791` |
| Pinterest | Montag, 23.11.2026, 10:00 | `2026-11-23T09:00:00Z` | `6b000f2c0f5eda1a57d865eb` |

Die Tageszeiten sind erste begründete Annahmen für Familienfoto-/Fotorestaurierungsinhalte, **keine Auswertung eigener PictureFix-Reichweitendaten**. Recherche: [Buffer Facebook 2026](https://buffer.com/resources/best-time-to-post-on-facebook/), [Buffer Instagram 2026](https://buffer.com/resources/best-time-to-post-on-instagram/) und [Sprout Social 2026](https://sproutsocial.com/insights/best-times-to-post-on-social-media/). Da eine zeitnahe Freigabe gewünscht ist, kommen Facebook/Instagram am selben Freitag und Pinterest am nächsten vielversprechenden Werktag. Uhrzeiten sind Planungsannahmen, keine Wirkungsgarantie.

Die Implementierung lässt die ursprünglichen Buffer-Posts, Texte, Grafiken und Kanäle unverändert. Die GraphQL-Mutation `editPost` sendet ausschließlich ID, Terminierungsmodus, Datum, Scheduling-Typ und **`saveToDraft: true`**. Die erneute Einzelabfrage muss `status: draft`, identische Medienquelle, Text, Kanal, ID und exakten Zeitpunkt bestätigen. Erst danach gilt ein Einmal-Empfangsbeleg als bestätigt. Jeder Post erfordert einen separaten authentifizierten Kommentar am eigens hierfür angelegten [GitHub-Issue #81](https://github.com/derJosef/social-assets/issues/81). Issue #64 bleibt ausdrücklich ein reiner Draft-Erstellungs-Steuerpunkt, ohne neue Terminierungsbefugnis. Ein einmal reservierter Vorgang darf nicht blind wiederholt werden.

**Freigabeschritt durch Josef:** In Buffer den vorbereiteten Beitrag überprüfen und ausdrücklich zur Warteschlange freigeben. Ohne diese Handlung bleibt er Entwurf, auch wenn ein `dueAt` existiert. Falls die Freigabe nach dem vorgesehenen Zeitpunkt erfolgt, muss der Termin vor dem Warteschlangenwechsel aktualisiert werden.

Die GitHub-Integration benutzt ausschließlich das autorisierte Konto `derJosef-agents` und die getrennten PictureFix-Credentials. Sie nimmt keinerlei Änderungen an PersonalOS, AAB, Sticken-Lasern oder PictureFix-Produktion vor.
