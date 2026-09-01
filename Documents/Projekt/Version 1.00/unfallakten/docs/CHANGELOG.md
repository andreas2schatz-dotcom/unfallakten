# Changelog – Unfallakten-Verwaltungssystem

> Archiv der Umsetzungs-Protokolle (was wurde wann gebaut, Branch/Commits, Besonderheiten).
> **Keine Pflichtlektüre** — nur bei Bedarf nachschlagen.
> Aktuelle Arbeit: `docs/TODO.md` · Entscheidungen mit Begründung: `docs/DECISIONS.md` · Deploy/Betrieb: `docs/STATE.md`.
> Neueste Einträge oben.

---

## 2026-09-01 — Wiedervorlagegrund: sieben Auslegungsstellen auf eine Registry vereinheitlicht

Branch `wiedervorlage-registry`. Die Tagesübersicht liest für Fristen- und Wiedervorlagen-Kachel das Feld `iWiedervorlageGrund` aus RA-MICRO. Sieben Stellen legten diesen Code unabhängig voneinander aus: vier Bezeichnungslisten (`RAMICRO_WV_GRUENDE` 40 Einträge, `_RAMICRO_GRUENDE` 16, `_FRIST_LABELS` 7, `_TERMIN_LABELS` 3) und vier Codelisten direkt im SQL — drei davon für die Kachel-Abfragen, eine vierte im Stellungnahme-Filter.

**Umgesetzt:** `backend/registry/wiedervorlage_codes.yaml` (46 eingebaute RA-MICRO-Codes) als SSOT, gelesen über `backend/services/wiedervorlage_code_registry.py` (`loese_wv_grund`, `codes_fuer_art`, `sql_codeliste`, `stellungnahme_codes`). `dashboard_routes.py` und `wiedervorlage_service.py` lesen nur noch von dort; die vier Bezeichnungslisten und vier hartcodierten Codelisten sind entfernt. Begründung + Freitext-Vorrang → `docs/DECISIONS.md`.

Die vier Bezeichnungslisten widersprachen sich nicht, wo sie sich überschnitten — sie unterschieden sich nur im Umfang. Der Zusammenzug ändert deshalb keine bestehende Beschriftung. Anders bei `_RAMICRO_GRUENDE`, der Liste hinter der Wiedervorlagen-Kachel: Sie kannte nur 16 der 46 Codes. **537 Wiedervorlagen, die bisher pauschal „Wiedervorlage" anzeigten, zeigen jetzt einen konkreten Grund** — diese Bezeichnungen sind bislang unverifiziert (`verifiziert: false`, siehe Guard-Test unten).

Der tote Endpunkt `/dashboard/ramicro-fristen` (definiert, von niemandem aufgerufen) ist entfernt, ebenso `ramicroFristen` aus `frontend/src/api.js`.

**Frontend:** `sBemerkung` (~10 % der Zeilen, 155 von 1.610) erscheint jetzt als dritte Zeile in Fristen- und Wiedervorlagen-Kachel (`ZeileText`-`zusatz`-Prop in `boardUi.jsx`, verdrahtet in `FristenKachel.jsx` und `WiedervorlagenKachel.jsx`).

**Guard-Test** `test_wiedervorlage_registry_guard.py` durchsucht den Quellcode statisch nach neuen Codelisten auf `iWiedervorlageGrund` außerhalb der Registry-Datei und gibt bei jedem Testlauf aus, wie viele der 46 eingebauten Codes noch unverifiziert sind (aktuell alle 46).

Vollsuiten: Backend **2142 passed / 69 skipped / 0 failed**, Frontend **607 passed**.

---

## 2026-08-31 — Zeugen standen als Gegner in der Akte: fünf Kürzel-Auslegungen auf ein Verzeichnis vereinheitlicht

Meldung RA Schatz: *„in der Beteiligtenliste tauchen Zeugen als Gegner auf."* Branch `fragebogen-favoritenliste`.

### Befund

RA-MICRO führt je Beteiligtem eine **Beteiligtenart** (1 = Mandant, 2 = Gegner, 4 = weitere Beteiligte …) und ein **Kennzeichen** (`GHPV`, `SV`, `Z` …). `word_service._klassifiziere` las Art 4 nach dem Prinzip *„alles ist Gegner, außer …"* gegen eine Ausschlussliste aus sieben Kürzeln. `Z` (Zeuge) stand nicht darauf — ebenso wenig Polizei, Gerichtsvollzieher, Finanzamt oder die finanzierende Bank.

Das blieb nicht bei der Anzeige: dieselbe Einstufung speiste den Klage-Wizard. Abruf von `/akten/13-26/klage/daten` am Echtsystem zeigte beide Zeugen mit `rolle_klage=beklagter` und `vorschlag_beklagter=true` — vorausgewählt.

Die eigentliche Ursache war nicht das Kürzel, sondern **fünf Stellen, die dieselbe Frage unabhängig beantworteten**:

| Stelle | Prinzip | Folge |
|---|---|---|
| `word/word_service.py` `_klassifiziere` | Ausschlussliste | fehlerhaft — der gemeldete Bug |
| `routers/beteiligte_routes.py` `_gegner_rolle` | zweite Nachsortierung darauf | wirkungslos |
| `routers/ramicro_akte_routes.py` `_klassifiziere` | Positivliste, 6 Gruppen | richtig, kannte aber weder RSV noch Polizei unter Art 4 |
| `routers/belege_routes.py` `_KZ_ROLLE_MAP` | 10 Kürzel, dann Art 2/4/9 → Gegner | derselbe Zeugen-Fehler, eigenständig |
| `routers/klage_routes.py` | eigene Beklagten-Logik auf der bereits falschen Rolle | Zeuge als Beklagter |

Zweiter, gravierenderer Teil des Befunds: **1.029 Beteiligte** lagen pauschal unter „Sonstige Beteiligte", obwohl die Rolle bekannt war — sämtliche 180 Rechtsschutzversicherer, 61 Gegneranwälte, 259 Polizeidienststellen, 135 Gerichte. Ein Feld `rolle` musste zwei Fragen zugleich beantworten: *wer ist das* und *wird derjenige verklagt*.

### Umsetzung

Eine Registry als SSOT, nach dem Muster der Dokumentenklassen:

* `backend/registry/beteiligten_kuerzel.yaml` — je Kürzel `bezeichnung`, `rolle`, `beklagter_vorschlag`. Bezeichnungen aus der **Kürzelliste der Kanzlei** (RA Schatz), 54 Kürzel plus die Mandanten- (`M`, `M1`–`M3`) und Gegner-Familie (`G`, `G1`–`G3`).
* `backend/services/beteiligten_kuerzel_registry.py` — `bestimme_beteiligten_rolle(art, kuerzel)`. Fail-loud beim Laden: unbekannte Rolle oder ein Beklagten-Vorschlag bei nicht passivlegitimierter Rolle verweigern den Start.
* Alle fünf Stellen lesen jetzt dort. `_lade_beteiligte_aus_ramicro` liefert zusätzlich `alle` — jeden Beteiligten mit seiner Rolle; das ist die Quelle der Beteiligtenliste. `alle_gegner` enthält weiterhin genau die Beklagten-Kandidaten, damit die Brief-Adressierung (GHPV-Vorrang) unverändert bleibt.
* Frontend: `ROLLEN_ANZEIGE` + `rolleLabel(rolle, bezeichnung)` in `constants.js`, Farben je Rolle, Fragezeichen mit Erklärung bei unbekanntem Kürzel. Das Auswahlfeld beim Anlegen bleibt bei den Rollen, die die SQLite-`CHECK`-Klausel zulässt — die neuen Rollen kommen ausschließlich aus RA-MICRO und werden nie in `beteiligte` geschrieben, deshalb **keine Migration**.

### Zwei Funde während der Abnahme

**Akte 668/23** führt die Mandantin unter Art 1 mit dem Kürzel `g` (klein) — vermutlich ein Vertipper. Die erste Fassung hätte sie zur **Beklagten** gemacht, weil das Kürzel die Beteiligtenart schlug. Jetzt gilt: Art 1 plus Gegner-Kürzel ist ein Widerspruch → `sonstiger`, nie Beklagter, mit sichtbarem Hinweis.

Ein Feld `gegnerseite` je Kürzel wurde eingeführt und nach den Entscheidungen zu `SAB`/`GR` wieder **entfernt**: Es war zeilenweise deckungsgleich mit `beklagter_vorschlag` und lud zum Fehlschluss „Gegenseite = Beklagter" ein. Ein Test verhindert die Rückkehr.

### Zahlen

Bestandslauf über 4.186 Beteiligte in 928 Akten: **1.752 Rollen korrigiert.** Beklagten-Vorschläge **1.456 → 1.316** (735 gegnerische Haftpflicht + 581 Gegner, sonst niemand). Die 140 entfernten: 23 Zeugen, 55 `SO`, 17 Kreditinstitute, dazu Polizei, Gerichtsvollzieher, Inkasso, Finanzamt, Hausverwaltung.

Nur noch **drei** Beteiligte tragen ein Kürzel ohne Verzeichniseintrag (`KOAN` 2×, `OA` 2×, `UB` 1×); sie laufen sicher in die Auffangregel. `HV`/`VS` sind als `offen: true` markiert — das Kürzel nennt die Sparte, nicht die Seite.

### Tests

`test_beteiligten_kuerzel.py` (111 Einheitstests inkl. Vollständigkeits- und Schranken-Prüfungen der Registry) und `test_beteiligten_rollen_ramicro.py` (33 Tests **echt gegen RA-MICRO**, Akten 13/26, 20/25, 249/26, 108/26 — `RAMICRO_INTEGRATION=1`), Frontend `BeteiligteSection.rollen.test.jsx` (9). Vollsuiten: Backend **2.105 grün / 71 übersprungen**, Frontend **603 grün**.

Alle Tests wurden vor der Umsetzung geschrieben und rot gesehen — die 21 Integrationstests scheiterten zunächst genau an den Zeugen.

---

## 2026-08-28 — Review-Queue für den Testbetrieb entlastet: 879 Altdokumente archiviert, Rauschfilter erweitert

Anlass RA Schatz: *„Die Review-Queue ist nur im Testbetrieb. Aktuell sind fast 900 Einträge drin … mich erschlägt es so.“* Branch `fragebogen-favoritenliste`, Commit `9cf71a31`.

### Befund

Die Queue ist im Testbetrieb ein zweiter Posteingang: **876 der 879 wartenden Dokumente stammen aus IMAP**, nur 9 aus der E-Akte. Der Zufluss beträgt **40–80 Dokumente pro Tag** (am 28.08. bis mittags 56). Einmaliges Leeren hätte also nur rund zwei Wochen Ruhe gebracht — deshalb Altbestand und Zufluss zusammen behandelt.

Absender-Verteilung: Placetel-Anrufbenachrichtigungen (107, bereits per Rausch-Regel body-verworfen), Allianz (70), Sachverständigenbüro Neubauer-Käswurm (50), HUK (46), AXA (26) — überwiegend echte Post. 864 der wartenden Dokumente trugen die Klasse `sonstiges`.

### Umsetzung

**Nichts gelöscht.** Der Soft-Delete aus `intake/verwerfen.py` war bereits da: `verworfen_grund/am/von` plus `korrektur_log`-Zeile, die Queue filtert `verworfen_am IS NULL`, das Frontend hat einen Papierkorb-Reiter mit Wiederherstellen-Knopf (187 Dokumente lagen dort schon als Spam/Rauschen). Neues Werkzeug `tools/queue_altbestand_archivieren.py` setzt denselben Zustand in einer Transaktion, mit `--stichtag`, `--ausnehmen` und `--dry-run`; neuer Verwerfen-Grund `altbestand` (Backend-Menge + Frontend-Label „Altbestand Testbetrieb“), damit ein Sammellauf im Papierkorb erkennbar bleibt. Ausgenommen wurden die acht Unfallfragebögen (474, 475, 476, 527, 613, 672, 727, 834) — sie werden für die Abnahme der Favoritenliste gebraucht. Das Skript nimmt zu geschützten Dokumenten automatisch deren Anhänge mit aus, sonst bliebe der Bogen stehen und seine Anlagen verschwänden.

Lauf am 28.08., vorher Backup nach `/app/data/bak_vor_queue_archiv_20260828.db` (`conn.backup()`, nicht `cp`): **879 archiviert, 879 Korrektur-Log-Zeilen, 8 in der Queue verblieben.** Ein kompletter Lauf lässt sich über sein Datum zurückholen:

```sql
UPDATE intake_dokumente SET verworfen_grund=NULL, verworfen_am=NULL
WHERE verworfen_grund='altbestand' AND verworfen_am LIKE '2026-08-28%';
```

**Rauschfilter** (`backend/registry/rausch_absender.yaml`) um acht Werbedomains erweitert, alle mit Policy `komplett`: `eiden-seminare.com`, `newsletter.anwaltverlag.de`, `news.deubner-verlag.de`, `anwaltakademie-event.de`, `zorn-seminare.de`, `mails.nomos.de`, `stempel-fabrik-mail.de`, `facebookmail.com`.

**Bewusst nicht aufgenommen** (Grund als Kommentar in der YAML): `anwaltverein.de` verschickt neben der DAV-Depesche Einladungen zu Mitgliederversammlungen der Arbeitsgemeinschaften; `iww.de` neben dem BGH-Newsletter Abo- und Kündigungskorrespondenz. Beide sahen in der Häufigkeitsliste nach reinem Newsletter aus — erst die Sichtung **aller** Betreffzeilen je Domain zeigte die echte Post. Ebenso außen vor: Versicherer, Sachverständige, Behörden und die Freemailer (`gmail.com`, `outlook.com`, `web.de`), über die Mandanten schreiben — die Regel matcht domainweit.

### Grenzen, bewusst so

* **Der Filter löst das Volumen nicht:** die acht Domains fangen rund 7 % des Zuflusses, der Rest ist echte Post. Die Queue läuft weiter voll, solange sie im Testbetrieb niemand abarbeitet — bis zum Live-Gang ist regelmäßiges Archivieren der Weg.
* **Die Dublettenprüfung ignoriert den Papierkorb** (`_persistenz.py`: `WHERE sha256 = ?` ohne Filter). Ein archiviertes Dokument kommt bei erneutem Import nicht zurück; der einzige Weg zurück ist Wiederherstellen. E-Mails im Postfach und Dokumente in RA-MICRO bleiben unberührt.
* Nach einer YAML-Änderung ist ein `docker restart unfallakten-backend-dev` nötig — der Flask-Reloader reagiert nur auf `.py`, und `rausch_regel.lade_regeln()` cached.

Tests: `test_rausch_aussortieren_e2e`, `test_auto_verwerfen`, `test_papierkorb_routes`, `test_intake_routes` 51 grün; Frontend `ReviewQueueView.papierkorb` + `.favoriten` 26 grün.

---

## 2026-08-28 — Priorisierte Fragebogen-Liste in der Review-Queue (Branch `fragebogen-favoritenliste`)

Spec `docs/superpowers/specs/2026-08-27-fragebogen-favoritenliste-design.md`, Plan `docs/superpowers/plans/2026-08-27-fragebogen-favoritenliste.md` (8 Aufgaben, TDD). Commits `60e28ef4`..`b15bcd24`. Backend 1994 grün (38 skipped), Frontend 594 grün. Codeseitig komplett, Abnahme im Betrieb offen.

**Anlass.** Unfallfragebögen von der Website landeten in der Review-Queue als Klasse `sonstiges` — optisch ununterscheidbar von Spam und Rundschreiben. Am 2026-08-27 lagen acht Bögen seit dem 4. bis 15. August unbearbeitet. Nachprüfung gegen RA-MICRO: **alle acht gehörten zu bestehenden Akten**, kein einziges Neumandat.

### Warum die Bestandsprüfung versagte

| Befund | Ursache |
|---|---|
| Sechs von acht Bögen fanden gar keine Akte | `akten_matching.py` übergab `mails[0]` — den Mail-Absender, also `unfall@anwalt-offenbach.de`, das eigene Postfach. `mandant.email` aus dem Bogen wurde nie benutzt |
| Kennzeichen trafen nicht | Der Regex verlangte `OF-BR 1612`; eingetippt wurde `WÜ PG 777`, `OF A-418`, `OFGM891`, `OF CJ 828`. Einer von sechs traf das Muster |
| Kennzeichen trafen fremde Akten | `_suche_kfz_in_sqlite` suchte ohne `rolle`-Filter — ein Gegner-Kennzeichen konnte eine fremde Mandantenakte treffen |
| „Name + Unfalltag" fiel immer still aus | Der Bogen liefert ISO (`2026-03-28`), das Muster erwartete `28.03.2026` |
| Die Queue-Liste kannte keine Fragebögen | `GET /intake/queue` las aus `signale_json` nur `absender_kategorie`, nicht `dokument_art` |
| Doppelweg | `_fragebogen_neuer_mandant_stub` war die einzige Fragebogen-Funktion **ohne** `review_pflicht_aktiv()`-Guard |

### Gebaut

**Signalbildung** — neues Modul `backend/intake/fragebogen_signale.py`. Reine Lesefunktion ohne DB-Zugriff: Mandanten-E-Mail, eigenes und gegnerisches Kennzeichen, Nachname, Unfalltag kommen aus den **strukturierten Bogenfeldern** statt aus Regex-Raten im Volltext. Kennzeichen werden normalisiert (alles außer Buchstaben/Ziffern raus, großschreiben) und plausibilisiert — `k.A. Fußgänger` und `siehe Akte` werden verworfen, die vier realen Schreibweisen alle erkannt.

Die Signale entstehen **in der Pipeline**, bei jedem Lauf neu aus dem gespeicherten Bogen-JSON — nicht beim Einliefern in `signale_json`. Dadurch ist die Ableitung idempotent, es gibt nur eine Wahrheitsquelle, und die acht Altfälle heilen allein über den vorhandenen Reparse-Knopf: kein Einmal-Skript, keine Datenmigration.

**Dokumentenklasse `fragebogen`** (Registry-YAML, `bezeichnung_label: "Unfallfragebogen"`). Nicht über den Textklassifikator — ein Signal allein erreicht nur `SIGNAL_KONFIDENZ = 0.55` und bliebe unter der Schwelle. Ein Bogen ist aber schema-validiert und keine Vermutung, deshalb stempelt die Pipeline die Klasse selbst mit `klasse_quelle='fragebogen'` und Konfidenz 1,0. Der Zweig für bindende Klassen (bisher nur `manuell`) wurde erweitert, damit eine manuell gesetzte Klasse weiter Vorrang behält. Kein Ereignistyp — ein Bogen löst kein Geld- oder Belegereignis aus.

**Suche.** `akten_matching.py` liest die neuen Schlüssel mit; die bisherigen bleiben unangetastet, damit andere Dokumentarten unverändert laufen. Neu in `ramicro/email_matching.py`: `suche_kandidaten_in_ramicro()` über `varM-KZ`, `varG-KZ`, `varU-TAG` und Nachname — liefert **mehrere** Kandidaten statt eines Einzeltreffers; `suche_akte_in_ramicro()` blieb unverändert. Alle Adress- und Namenssuchen laufen rollenrichtig über `iBeteiligtenArt = 1` (Auftraggeber), sonst treffen Versicherer-, Gutachter- und Behördenadressen mit.

Gewichtung: Aktenzeichen 1,0 · Mandanten-E-Mail 0,8 · eigenes Kennzeichen 0,8 · Unfalltag + Nachname 0,7 · Unfalltag allein 0,5 · Gegner-Kennzeichen 0,5 · Nachname allein 0,4.

**Ampel** (`backend/intake/fragebogen_zuordnung.py`) — vier Zustände statt der geplanten drei:

| Zustand | Bedingung | Anzeige |
|---|---|---|
| 🟢 grün | genau ein laufender Kandidat ab Score 0,7 | `→ 751/26 · Hartmann/Guthier` |
| 🟡 prüfen | mehrere starke Kandidaten oder nur schwache Merkmale | `PRÜFEN · n Kandidaten` |
| 🔵 abgelegt | passt nur zu einer abgeschlossenen Akte | Ablagedatum, **kein** Anlage-Knopf |
| 🔵 neue Akte | kein Kandidat | `NEUE AKTE` + Knopf „Akte anlegen" |

Der vierte Zustand kam während der Umsetzung dazu (Freigabe RA Schatz, `24d82f5a`): Bogen 672 gehört zu Akte 749/26, die am 26.08. abgelegt wurde. Der Ablage-Filter hätte sie ausgeblendet, der Bogen wäre als „NEUE AKTE" erschienen und hätte eine Dublette zu einem abgeschlossenen Fall erzeugt. Die Rückfall-Suche ohne Ablage-Filter läuft nur, wenn sonst **kein starker** Kandidat vorliegt — ein zufälliger schwacher Nachnamens-Treffer darf eine perfekt passende abgelegte Akte nicht verdecken.

Jeder Eintrag nennt die Trefferbegründung im Klartext („Mandanten-E-Mail", „eigenes Kennzeichen", „Unfalltag + Name").

**Queue-Endpunkt.** `GET /intake/queue` liefert je Eintrag zusätzlich `ist_fragebogen`, `bogen_kopf` und `zuordnung` — ohne zweiten Endpunkt und ohne Nachladen je Zeile, da alles bereits in `parse_json` steht.

**Frontend** (`ReviewQueueView.jsx`): angepinnte Sektion „⭐ Unfallfragebögen (n)" oben, darunter „Übrige Dokumente"; ist sie leer, entfällt sie ganz. Die Darstellungsentscheidung fällt **je Eintrag** (Dispatcher `KindZeile`), nicht je Gruppe — sonst wurden Anhänge eines Bogens verschluckt und ein Bogen als Anhang einer fremden E-Mail blieb eine gewöhnliche Zeile ohne Ampel. Ampelfarben nutzen die Gestaltungstoken `T.green/T.amber/T.blue`, nicht feste Hex-Werte (Dunkelmodus- und clio-fähig). `zeigeAktenanlageVorschlag` greift jetzt auch beim Fragebogen; der `AktenanlageDialog` wird aus den Bogendaten vorbefüllt (Name, Anschrift, Telefon, E-Mail, Kennzeichen, Unfalltag), das Anlage-Banner nennt dabei den Mandanten statt „Gutachten".

**Doppelweg stillgelegt** (`b15bcd24`). Der Guard `review_pflicht_aktiv()` sitzt jetzt in `_fragebogen_neuer_mandant_stub`; entfernt wurden `FragebogenErstkontaktKarte` samt Einbindung, die API-Helfer `fragebogenErstkontakt`/`fragebogenErstkontaktStatus`, die beiden Routen in `email_routes.py` und der Zähler `fragebogen_neu` im Dashboard (`gesamt` = `emails_nicht_zugeordnet`). Die Tabelle `fragebogen_erstkontakt` bleibt bestehen — sie ist leer, eine Migration nur zum Löschen wäre unnötiges Risiko.

### Besonderheiten aus den Prüfrunden

**K-1 (kritisch, `539ad70f`):** `import_service` legt beim Einliefern zuerst ein dünnes `{"dokument_art": "fragebogen"}`-Signal ohne Merkmale an, die Pipeline hängt das reiche Signal-Dict erst danach an. `finde_kandidaten` griff das **erste** Signal mit `dokument_art == 'fragebogen'` heraus — produktiv immer das dünne. Die RA-MICRO-Bogensuche lief dadurch nie mit brauchbaren Merkmalen. Jetzt wird der Bogen-Modus über „irgendein Signal trägt `dokument_art`" erkannt und die Merkmale kommen aus den über alle Zustellungen aggregierten Listen — reihenfolge- und mengenunabhängig.

**K-1 (kritisch, `f1ec75a5`):** RA-MICRO liefert `dtAblage` als `datetime`, nicht als String; `json.dumps` in der Pipeline hatte kein `default=`, das Dokument fiel in den Fehlerzustand — die Ampel „abgelegt" erschien nie. Wandlung jetzt an der Quelle über `ablage_service._datum()`.

**Reloader-Falle Migration 71 → Migration 72 + Guard (`9f107861`, `50b12fd3`).** Migration 71 wurde vom Flask-Reloader mitten in der Bearbeitung erwischt: Eintrag im `MIGRATIONS`-Dict vorhanden, Dispatch-Zweig noch nicht — der generische `else`-Zweig führte den Kommentar-Platzhalter als No-Op aus und stempelte die Version trotzdem. Dasselbe Muster wie bei 54/55/58/60/66. **Der Mechanismus ist jetzt geschlossen:** `run_migrations()` bricht mit `RuntimeError` ab, sobald ein reiner Kommentar-Platzhalter ohne Dispatch-Zweig auftaucht, und stempelt die Version nicht. `_ist_reiner_kommentar_platzhalter()` prüft inhaltlich, keine Ausnahmeliste nötig. Neuer Guard-Test `test_migration_dispatch_guard.py` sichert zu, dass jeder Platzhalter einen Zweig hat — nachgezählt: 67 von 71 Einträgen sind Platzhalter, alle 67 haben einen Zweig.

**RA-MICRO-Verbindungssperre in Tests (`1b81fb9c`, `080881b7`, `be0cd214`).** Der Dev-Container hat `RAMICRO_AKTIV=true` und echte Netzwerksicht auf den Kanzleiserver — vergessene Mocks liefen unbemerkt lesend gegen die Produktivdatenbank, weil die Matching-Logik Verbindungsfehler großzügig abfängt (per Timing-Vergleich über 12 Testläufe verifiziert). Die dateilistenbasierte Sperre deckte weder neun weitere Testdateien noch die RA-MICRO-Module ab, die sich die Verbindung selbst holen. Der Haken sitzt jetzt an der einzigen Stelle, an der wirklich eine Verbindung aufgeht: **`pymssql.connect`, autouse für die gesamte Suite.**

Dabei wurden 18 Tests in 6 Dateien sichtbar, die **absichtlich** echt gegen RA-MICRO laufen (Entscheidung RA Schatz: nicht auf nachgestellte Daten umstellen, die echten Daten bleiben die Prüfung). Beide Anliegen — „habe ich etwas kaputtgemacht" und „stimmt unsere Annahme über RA-MICRO noch" — saßen im selben roten Kreuz. Neue Markierung `@pytest.mark.ramicro_integration` (registriert in `conftest.py`, keine `pytest.ini`): ohne Umgebungsvariable werden sie mit Klartext-Grund übersprungen, mit `RAMICRO_INTEGRATION=1` laufen sie und die Sperre bleibt für genau sie aus.

```bash
RAMICRO_INTEGRATION=1 pytest -m ramicro_integration backend/tests/
```

**W-2 (`838a5454`):** Der Queue-Endpunkt erkennt Bögen jetzt über `payload_typ == 'text'` statt über `klasse == 'fragebogen'` — sonst lieferten Queue- und Detail-Endpunkt für dieselbe Zeile gegenteilige Antworten, solange kein Reparse gelaufen war (alle acht Altbögen tragen noch `sonstiges`).

---

## 2026-08-27 — Abschlussbericht auf dem Kanzleibriefbogen + Umsatzsteuer der RA-Gebühren

Branch `geld-ssot-abrechnungsvorschlag`. Ausgelöst durch RA Schatz beim Gegenlesen des Berichts zu 589/26. Backend 1923 grün (20 skipped), Frontend 571 grün.

### Layout und Formulierungen (Abschluss-/Sachstandsbericht)

Der Bericht baute seinen Briefkopf selbst über `styling.py` nach, statt den echten Kanzleibriefbogen zu verwenden. Er läuft jetzt auf `word/abschlussbericht_vorlage.docx` — derselben Briefbogen-Datei wie Forderungsschreiben, Sachstandsanfrage und Abrechnungsübersicht. Der Renderer öffnet sie mit python-docx, füllt die Platzhalter in **allen** Textknoten (auch Textrahmen und Kopfzeilen), entfernt den `{{ABSCHLUSSINHALT}}`-Absatz und hängt den Brieftext an. Das trägt, weil dieser Platzhalter der letzte Body-Absatz vor `sectPr` ist.

`styling.py` blieb dabei **unangetastet** — der Bericht bringt seine Absatz- und Tabellenbausteine jetzt selbst mit, damit die Sachstandsanfrage (nutzt dieselbe Datei) nicht mitgezogen wird.

Im Einzelnen:

| Befund | Korrektur |
|---|---|
| Acht Schriftgrößen (8,5–14 pt), Calibri | Arial 12 pt im gesamten Brieftext; Briefkopf/Fußzeile bleiben Briefbogen-Rahmen |
| Anrede immer „Sehr geehrte Damen und Herren“ | `_anrede_zeile()` nimmt die RA-MICRO-`briefanrede`, sonst das Anrede-Feld — als **Klartext** („Herr“) **und** als Code („1“). Der Code prüfte nur auf `"1"`/`"2"`, RA-MICRO liefert an dieser Stelle Klartext |
| Tabellenspalten linksbündig, Kopf zentriert | Erste Spalte links, alle weiteren rechts **inkl. Kopfzeile**; „Gesamt“ fett + `#EBF2FB` hinterlegt |
| Grußformel = Kanzleiname | Unterschriftsbild + Name + Titel des Aktensachbearbeiters (`_hole_sb_info`, `_unterschrift_bytes`) |
| Navy/Gold | Kanzleiblau `#5488D4`, Tabellenkopf `#2C3E50`, Kachel `#D6E8FF` |
| — | Betreffblock unter der Kurzbezeichnung: Aktenlangbezeichnung + „Abschlussbericht“/„Sachstandsbericht“; die frühere blaue Betreffzeile im Fließtext entfällt |
| — | Einleitungssatz nach der Anrede (nur Abschluss): „Ihre Unfallsache ist abgeschlossen. Nachfolgend erhalten Sie eine Übersicht über den Regulierungsverlauf:“ |
| „Zahlungsverlauf“ | → „Regulierungsverlauf“, Spalte „Datum“ → „Abrechnung“ (siehe DECISIONS) |
| Schlusssatz + grauer Bewertungshinweis | Neuer Schlusssatz vor der Grußformel (nur Abschluss); Bewertungsabsatz schwarz mit klickbarem Link |

**Aktenlangbezeichnung** (`tblAkten.sAktenBezeichnung`) stand nirgends im System — SQLite führt nur die Kurzbezeichnung. Neuer Loader `word_service._lade_aktenbezeichnung()`. Nebeneffekt: das Forderungsschreiben las `akte["aktenbezeichnung"]` längst als Betreff-Rückfall, bekam es aber nie geliefert — der Rückfall funktioniert jetzt.

**Datumsformat:** `varU-TAG` liefert deutsch und oft zweistellig („11.06.26“), SQLite ISO. Neuer Helfer `_datum()` bringt beides auf TT.MM.JJJJ; `_jahr_vierstellig()` ergänzt zweistellige Jahre in der RA-MICRO-Langbezeichnung, ohne RA-MICRO zu verändern.

**Zwei Layoutfehler aus der PDF-Sichtprüfung** (LibreOffice-Rendering im Container): python-docx' Zellbreiten wurden ignoriert, weil die Tabelle auf Automatik stand — „Nachbesichtigungskoste-n“ brach mitten im Wort um. Jetzt `tblLayout=fixed` + `tblGrid`, Breiten als Anteil der aus der Vorlage gelesenen Textbreite (16 cm). Dazu `tblHeader` (Kopfzeile wiederholt sich), `cantSplit` und `keep_with_next` für Abschnittstitel.

### Folgeseiten-Kopfzeile (alle vier Vorlagen)

„Seite N zum Schreiben vom …“ enthielt kein eingetipptes Datum, sondern ein `TIME`-Feld: es hätte beim Öffnen das **Tagesdatum** eingesetzt, nicht das Briefdatum, und zeigte bis zur nächsten Feldaktualisierung den eingefrorenen Stand („12. März 2026“). Ersetzt durch `{{DATUM}}`; die Renderer (`forderungsschreiben_wv._render_docx` — nutzt auch die Gebührennote —, `abrechnungsuebersicht_service._render_docx`, `sachstandsanfrage_wv`) ersetzen dafür jetzt auch in `word/header*.xml`. Die Seitenzahl bleibt ein automatisches `PAGE`-Feld.

**Werkzeug `tools/patch_briefvorlagen.py`** (idempotent) legt die neue Vorlage an, benennt den Platzhalter um, ergänzt die von python-docx benötigte Formatvorlage „Table Grid“ (die Kanzleivorlagen bringen sie nicht mit → `KeyError`) sowie die Betreffzeilen, und zieht die Kopfzeile in allen vier Dateien nach.

### Umsatzsteuer der Rechtsanwaltsgebühren

Gemeldet von RA Schatz: *„Bei vorsteuerabsatzberechtigten Mandanten erhalten wir ja nur die Nettogebühren. Wird das in diesem Absatz berücksichtigt?“*

**Befund:** Nein. `berechne_rvg()["gesamt"]` ist immer brutto, und `_berechne_anwaltskosten_cta_plausi()` bekam das Vorsteuer-Kennzeichen gar nicht übergeben — es steuerte nur die Schadenpositionen. Gegenprobe an 589/26 mit `vorsteuer = Y`: zeichengleiches Dokument. Der Absatz nannte 756,30 € (635,55 netto + 120,75 USt) und erklärte sie pauschal für „kostenfrei“.

**Korrektur** (Begründung → DECISIONS):
- `anwaltskosten` weist `rvg_netto` / `rvg_ust` / `rvg_brutto` / `vorsteuer` getrennt aus; `rvg_betrag` ist das, was die Gegenseite tatsächlich trägt.
- Brieftext verzweigt: bei Vorsteuerabzug Nettobetrag und der von RA Schatz vorgegebene USt-Hinweis statt „für Sie kostenfrei“.
- **Klageschrift** (`klage_service.py`): Antrag 2 fordert bei Vorsteuerabzug den Nettobetrag; die Gebührentabelle endet ohne Zwischensummen- und USt-Zeile beim Nettobetrag. Beispiel Gegenstandswert 4.000 €: vorher immer „weitere 480,17 €“, jetzt „weitere 403,50 €“. `rvg_ausserg_override` bleibt maßgeblich.
- **Frontend nachgezogen** (`KlageWizard.jsx` Schritt 9 + Zusammenfassung, `KlageSection.jsx` Gebühren-Karte) — der Wizard rechnet die Anzeige selbst und hätte sonst brutto gezeigt, während das Dokument netto fordert. Dabei fiel auf, dass das Frontend das Kennzeichen nur als `"J"` erkannte, das Backend aber `J/JA/Y/1/TRUE` — bei einem als „Y“ erfassten Mandanten wären Bildschirm und Dokument auseinandergelaufen.
- Die **Kostennote ist nicht betroffen** — sie ist eine Rechnung, dort gehört die USt hin.

**Nicht behoben, gemeldet:** Die IF-Felder in der Fußzeile vergleichen ein fest eingetipptes `"AS"` gegen die Sachbearbeiterkürzel (`if "AS"="AS" "D90" ""`), deshalb trägt jeder Brief den Präfix D90 statt D2/D1/D6. Betrifft die Druckdatei-Nummerierung aller vier Dokumente → Entscheidung RA Schatz.

### Tests

Neu: 4 Fälle im Übersichts-Service (USt-Aufschlüsselung, beide Vorsteuer-Wege, Kennzeichen-Varianten), 12 im Brieftext (Briefbogen-Bestandteile, keine offenen Platzhalter, Betreffblock, Schriftgröße/-art, Tabellenausrichtung und -layout, Grußformel, Formulierungen, Bewertungslink, „freuen“ nur einmal), 5 in der Klageschrift, 3 im Wizard (`KlageWizard.vorsteuer.test.jsx`).

---

## 2026-08-26 — Nachbesichtigungskosten als eigene Schadenposition (Migration 70)

Gemeldet von RA Schatz: „Wir haben in der Schadentabelle keine Position für die Kosten der Nachbesichtigung. Diese Position kommt immer wieder." Er hatte den Betrag in 589/26 deshalb als *Sonstiges* eingebucht.

**Befund:** Die Spalte `kostennb` existiert seit Migration 8 und wird von Forderungsschreiben, Klage-Wizard, Abrechnungsübersicht und der Registry längst geführt — es fehlte nur das Eingabefeld. Entsprechend nutzte sie **keine einzige Akte**.

Dabei fiel eine Inkonsistenz auf: `kostennb` war die einzige Nebenposition ohne `_netto`-Geschwister. Das Hauptfeld galt als NETTO und `kostennb_ust` wurde separat aufaddiert, während `sv_kosten`, `mietwagenkosten` & Co. den Bruttobetrag im Hauptfeld führen (`X_netto` / `X_ust` / `X`). Wer den Rechnungsbetrag eingetippt hätte, wäre in `_netto_oder_brutto()` auf die 19-%-Hochrechnung gelaufen: aus 29,75 € wären 35,40 € geworden.

**Migration 70** ergänzt `schadenpositionen.kostennb_netto` und zieht die Position auf die Hausregel: `kostennb` = brutto, `kostennb_netto` + `kostennb_ust` = Aufteilung. Kein Datenumzug nötig (0 betroffene Akten). Nachgezogen in `models/schaden.py` (Spaltenliste, Dataclass, `gesamt_brutto`, `berechne_abrechnungsart`), `schaden_routes.py`, `word_service.py`, `abrechnungsuebersicht_service.py`, `forderungsschreiben_wv.py`, `klage_routes.py` (jetzt über `_netto_oder_brutto()` wie die Geschwister), `klage_service.py`. Registry-Label `kostennb` von „Kostennebenschaden" auf „Nachbesichtigungskosten" korrigiert — die vier anderen Fundstellen hießen schon so.

**Frontend:** neue Zeile im Schaden-Tab, „Kosten der Nachbesichtigung (brutto)", direkt über der Unkostenpauschale; `calcBrutto()` zählt den Bruttobetrag nur noch einmal.

**Akte 589/26 bereinigt:** 29,75 € von `sonstiges` auf `kostennb` umgebucht (netto 25,00 + USt 4,75 laut Rechnung B26/089602 vom 23.07.2026), `sonstiges_beschr` geleert. Die Zahlung lag bereits auf `kostennb` — Forderung und Zahlung treffen sich jetzt auf derselben Zeile:

```
kostennb               gefordert=   29.75 anerkannt=   29.75 offen=0.00  anerkannt
nutzungsausfall        gefordert=  172.00 anerkannt=  172.00 offen=0.00  anerkannt
rep_gutachten_netto    gefordert= 4882.48 anerkannt= 4882.48 offen=0.00  anerkannt
sv_kosten              gefordert=  992.34 anerkannt=  992.34 offen=0.00  anerkannt
unkostenpauschale      gefordert=   30.00 anerkannt=   30.00 offen=0.00  anerkannt
wertminderung          gefordert=  150.00 anerkannt=  150.00 offen=0.00  anerkannt

UEBERSICHT  gefordert=6256.57  reguliert=6256.57  offen=0.00
BERICHT     gefordert=6256.57  gezahlt=6256.57  differenz=0.00
```

Backup vor der Bereinigung: `/app/data/unfallakten.db.bak_pre_kostennb_20260826`.

TDD: `backend/tests/test_kostennb_position.py` (8), vorher rot — inklusive Schutzplanke gegen die 19-%-Hochrechnung. Vollsuiten: Backend **1879 passed / 20 skipped / 0 failed**, Frontend **568/568**.

---

## 2026-08-26 — Eine Geld-Wahrheit: Kopfzahl liest die Schadenpositionen

Grundsatzentscheidung RA Schatz, festgehalten in `docs/DECISIONS.md` („Die erfassten Schadenpositionen und die Abrechnungsart sind aktenwahr — immer und überall"). Sie hebt den Beschluss vom 2026-08-10 auf, das Ereignismodell zur Geld-SSOT auszubauen.

**Umgesetzt:** `leite_positionsstatus_ab()` (`positionsstatus_service.py`) bildet die Beträge nicht mehr selbst aus Ereignissen, sondern liest sie aus der aktenwahren Quelle — `gefordert` über `_schadenpositionen_rows()` (Schadenpositionen + Abrechnungsart), `anerkannt` über `_baue_pos_map()` (Regulierung). Aus den Ereignissen kommen weiterhin `gekuerzt`, `abgelehnt`, `zustand`, `stand`, `checkliste`, `eskalationsstufe`, `has_unbestaetigt`. Weil Kopfzahl, `PositionsDashboard` und Phasenberechnung schon seit dem Redesign an derselben Response hängen, rechnen sie damit automatisch wie Abschlussbericht und Word-Abrechnungsübersicht.

Die parallele Alt-Formel im Frontend (`liveBrutto × HQ` bzw. `Σ gesamt_reguliert`) ist ersatzlos entfernt, ebenso die Markierung `quelle: "alt"` / `"ereignismodell"`.

**Ein Schlüsselraum:** Ereignis-Keys laufen jetzt ebenfalls durch `_normalise_key(key, fahrzeug_zielkey)` — Kürzung, Ablehnung und Checkliste landen damit zwingend auf derselben Zeile wie Forderung und Zahlung. Der Fahrzeugschaden erscheint überall unter dem Key, den die Abrechnungsart bestimmt (bei 589/26: `rep_gutachten_netto`).

**Zusatzbefund beim Nachrechnen:** Eine Zahlung auf eine Position ohne Forderung fiel aus der Berichtssumme (589/26: die Reparaturbestätigung ist unter `sonstiges` gefordert, RA Schatz hat sie auf `kostennb` gebucht — 29,75 € fehlten). `_schadenpositionen_rows()` legt für solche Zahlungen jetzt eine eigene Zeile mit Forderung 0 an, statt sie zu verschlucken.

**Stand 589/26 danach** — Übersicht und Bericht identisch:

```
UEBERSICHT  gefordert=6256.57  reguliert=6256.57
BERICHT     gefordert=6256.57  gezahlt=6256.57
```

TDD: `test_positionsstatus_ssot.py` (8) + zwei neue Fälle in `test_abschluss_fahrzeugkey.py`, vorher rot. Neun Bestandstests trugen das alte Ereignismodell-als-Geldquelle fest; sie seeden jetzt die aktenwahre Quelle mit und prüfen weiter dieselben Zustandsübergänge (`test_positionsstatus_service.py`, `test_p15a_regulierung.py`, `test_p15c_gutachten.py`, `test_p15_vorbereitung.py`, `test_positionen_routes.py`). Vollsuiten: Backend **1871 passed / 20 skipped / 0 failed**, Frontend **568/568**.

**Noch nicht nachgezogen:** Die Regulierungs-Tabelle und die Forderungshistorie bauen ihre Zeilen weiterhin im Frontend selbst zusammen — gleiche Zahlen, eigener Code. Umstellung auf `/akten/<az>/positionen/status` steht aus (in DECISIONS vermerkt).

**Datenhinweis 589/26:** Die Zahlung von 29,75 € liegt auf `kostennb`, die zugehörige Forderung auf `sonstiges`. Beträge stimmen in der Summe, die Position bleibt aber „offen" — beim nächsten Anfassen der Akte auf `sonstiges` umbuchen.

---

## 2026-08-26 — Übersicht rechnete Reparaturkosten + Wiederbeschaffungswert zusammen; Zahlungen erreichten den Abschlussbericht nicht

Zwei Befunde RA Schatz an Akte 589/26, beide dieselbe Wurzel: derselbe Sachverhalt wird an mehreren Stellen unterschiedlich normalisiert.

### Befund 1 — Übersicht zeigte 18.532,48 € statt 6.256,57 €

`_gutachten_positionen()` schrieb jedes Feld, das der Gutachten-Parser fand, als `wirkung='gefordert'` — also Reparaturkosten (4.882,48) **und** Wiederbeschaffungswert (13.500) nebeneinander, dazu den Restwert positiv. Die beiden stehen im Alternativverhältnis; bei fiktiver Reparatur ist der WBW nur Vergleichsgröße. `summenAusPositionsstatus()` und das PositionsDashboard summieren alle Schlüssel stumpf, die Aggregationszeile las wörtlich „reparaturkosten + wertminderung + wiederbeschaffung + rep_gutachten_netto".

**Behoben:** neuer Helfer `waehle_fahrzeugschaden()` in `eingehende_ereignisse.py` liefert genau **eine** Fahrzeugschaden-Position und fragt dafür `berechne_abrechnungsart()` (`models/schaden.py`) — dieselbe Quelle, aus der Schaden-Tab, Regulierung und Klage rechnen. fiktiv → `reparaturkosten`, totalschaden → `wiederbeschaffung` (WBW abzüglich Restwert), konkret → nichts (den Betrag trägt das Ereignis der Reparaturrechnung). Der Restwert wird nie mehr als eigene Forderung geschrieben. Eine manuell gesetzte Abrechnungsart der Akte hat Vorrang. Verdrahtet in beiden Schreibwegen: Review-Freigabe (`erzeuge_aus_freigabe`) und KI-Dialog-Korrektur (`erzeuge_aus_gutachten`).

**Datenkorrektur:** DB-weit war genau ein Datensatz betroffen (Akte 589/26, Ereignis 17). `ereignis_positionen`-Zeile 40 (wiederbeschaffung 13.500) entfernt, `rebuild_cache('589/26')`. Backup vorher: `/app/data/unfallakten.db.bak_pre_fahrzeugschaden_20260826`. Kopfzahl danach 5.032,48 € (Gutachten-Positionen).

### Befund 2 — manuell geänderte Zahlung fehlte im Abschlussbericht

`_normalise_key()` in `abrechnungsuebersicht_service.py` ließ `fahrzeugschaden` bewusst roh stehen (Kommentar: „Ziel-Key hängt von der Abrechnungsart ab und kann hier ohne Kontext nicht aufgelöst werden") und kannte `reparaturkosten` überhaupt nicht. `_schadenpositionen_rows()` baut die Fahrzeugzeile aber unter `rep_gutachten_netto` / `rep_rechnung_netto` / `wiederbeschaffung` — der Nachschlag ging ins Leere und die Zahlung verschwand **lautlos** (Position blieb „offen"). Die Regulierungs-Tabelle führt dagegen alle Fahrzeug-Keys auf eine Zeile zusammen und zeigte die Zahlung, der Bericht nicht.

**Behoben:** `_fahrzeug_zielkey(schaden, vorsteuer)` liefert den Key, den der Bericht tatsächlich druckt (aus `berechne_abrechnungsart().fahrzeugschaden_key`); `_normalise_key(raw, fahrzeug_zielkey)` bildet alle Fahrzeug-Schreibweisen (`fahrzeugschaden`, `reparaturkosten`, `reparatur_netto`, `wbw`, `wba`, …) darauf ab. Der Restwert bleibt eigene Abzugszeile. Gilt für Abschlussbericht **und** Word-Abrechnungsübersicht.

Der Befund traf auch das tags zuvor gebaute Abrechnungs-Vorschlagsfeature: „fiktive Abrechnung" bucht auf `fahrzeugschaden` — genau den Key, den der Bericht nicht auflöste.

TDD: `test_gutachten_fahrzeugschaden_alternative.py` (10) + `test_abschluss_fahrzeugkey.py` (7), vorher rot. Zwei Bestandstests trugen das alte Verhalten fest und wurden mit Begründung nachgezogen (`test_p15c_gutachten.py`, `test_intake_routes.py`). Vollsuiten: Backend **1862 passed / 20 skipped / 0 failed**, Frontend **568/568**.

**Offen (Design, keine Entscheidung getroffen):** Die Kopfzahl der Übersicht kommt aus dem Ereignismodell und kennt nur belegte Positionen — Nutzungsausfall, Unkostenpauschale und die als Auffangklasse `rechnung` freigegebenen SV-Rechnungen fehlen dort (589/26: 5.032,48 € statt 6.256,57 €). Ob der Kopf stattdessen aus `berechne_abrechnungsart().gesamt_brutto` speisen soll, ist zu entscheiden — siehe TODO „Zwei getrennte Positions-Modelle abgleichen".

---

## 2026-08-26 — Abrechnungsschreiben schlagen ihre Beträge zur Übernahme vor

Gemeldet von RA Schatz an Akte 589/26: zwei freigegebene AXA-Abrechnungsschreiben, aber in der Regulierungs-Tabelle bleibt die Spalte „Gezahlt" leer.

**Ursache:** `erzeuge_aus_freigabe()` schreibt Positionen nur für `gutachten_eingegangen` und `rechnung_eingegangen`; für `abrechnung_eingegangen` entsteht bewusst ein Fakt-Ereignis ohne Positionen (`backend/services/eingehende_ereignisse.py:512-548`). Die geparsten Beträge stehen als Freitextzeilen im `intake_dokumente.parse_json` und wurden nirgends abgeholt. Die Übersetzung Freitext→position_key existierte bereits (`positions_synonyme.yaml` + `normalisiere_positionslabel()` aus Kürzungstaxonomie Phase 1), hatte aber **keinen einzigen produktiven Aufrufer** — nur Tests.

**Entscheidungen RA Schatz:** „fiktive Abrechnung" läuft auf `fahrzeugschaden` (nicht `reparaturkosten`), und die Beträge werden als **Vorschlag** angeboten statt direkt gebucht — OCR-Fehler (im Juli-Schreiben `201,758 €` statt 201,76 €) sollen nicht ungeprüft in die Akte laufen.

**Gebaut:** `backend/services/abrechnung_vorschlag.py` (`baue_vorschlaege(akte_az)`) sammelt freigegebene Abrechnungsschreiben ohne zugehörigen `abrechnungsschreiben`-Eintrag, holt die Felder aus `dokumente.parse_json` oder über `freigaben` → `intake_dokumente.parse_json` und mappt die Zeilen; unbekannte Labels bleiben bewusst ohne Key. Neuer Endpunkt `GET /akten/<az>/abrechnungen/vorschlaege`. Im Frontend `components/AbrechnungVorschlagDialog.jsx` (Zuordnung je Zeile korrigierbar, Beträge editierbar, Parser-Warnungen sichtbar) plus Hinweisleiste in der RegulierungSection; „Übernehmen" geht durch den bestehenden `POST /abrechnungen`, damit Kürzungen, Klage-Vormerkung und Abrechnungsrunden greifen. `positions_synonyme.yaml`: `fiktive abrechnung` + `konkrete abrechnung` → `fahrzeugschaden`.

Zwei Eigenheiten des LLM-Parsers sind mitabgedeckt: das Positions-Label heißt je Dokument `text` oder `beschreibung`, und der Regex-Parser liefert stattdessen `art`.

TDD: `backend/tests/test_abrechnung_vorschlag.py` (8) + `frontend/src/components/AbrechnungVorschlagDialog.test.jsx` (12), vorher rot. Vollsuiten: Backend **1845 passed / 20 skipped / 0 failed**, Frontend **568/568**, `vite build` grün. Offen: Browser-Abnahme an 589/26.

**Nebenbefund (nicht angefasst):** `AbrechnungFormular` und `ManuelleAbrechnungFormular` in `RegulierungSection.jsx` (~340 Zeilen) sind toter Code — sie werden nirgends gerendert.

---

## 2026-08-26 — Beleg-Zuordnung zeigt die Dokumentbezeichnung statt des Hash-Dateinamens

Gemeldet von RA Schatz: In der SchadenSection listet „+ Beleg" die Dokumente mit ihrem Dateinamen — bei allen Dokumenten aus der Intake-Pipeline ist das der SHA-256-Hash (`6ac609ea…cfad58ac.pdf`), also unbrauchbar für die Auswahl.

**Ursache:** Die Pipeline schreibt zwar eine sprechende `bezeichnung` in `dokumente` („Rechnung SV-HO vom 18.06.2026 (992,34 €)"), aber die Beleg-Oberfläche rendert ausschließlich `dateiname` — und `GET /akten/<az>/belege` sowie `…/belege/kandidaten` lieferten das Feld überhaupt nicht mit.

**Behoben:** Beide Beleg-Endpunkte geben `bezeichnung` jetzt mit aus (E-Akte-Kandidaten `null`, deren `dateiname` ist bereits die Bemerkung). Neuer Helfer `dokumentAnzeige()` in `frontend/src/config/utils.js` als einheitliche Anzeigelogik: `bezeichnung` → nicht-Hash-Dateiname → Klassen-Label aus der Registry + Dokumentnummer. Verdrahtet in SchadenSection (Auswahl-Dropdown, zugeordneter Beleg, Referenz-Dokumente, Kandidat-Split-View) und DokumenteSection (Beleg-Zeile, Kandidatenzeile, Vorschau-Kopf, Diagnose-Dialog); der Hash bleibt als Tooltip erhalten. Die Bezeichnung ist in der Dokumentenkachel weiterhin editierbar, Korrekturen schlagen also direkt in der Beleg-Auswahl durch.

TDD: `backend/tests/test_belege_bezeichnung.py` (4) + `frontend/src/config/utils.dokumentAnzeige.test.js` (8), vorher rot. Vollsuiten: Backend **1837 passed / 20 skipped / 0 failed**, Frontend **556/556**.

---

## 2026-08-21 — SV-Portal für Sachverständige nutzbar gemacht (Branch `sv-portal-laufende-akten`)

Spec: `docs/superpowers/specs/2026-08-20-sv-portal-laufende-akten-design.md`, Plan: `docs/superpowers/plans/2026-08-20-sv-portal-laufende-akten.md`. Anlass: erster echter SV-Zugang (Ninnivaggi, RA-MICRO-Adressnr. 25982, 578 Akten). Der Laufend/Abgeschlossen-Filter im Portal existierte bereits, griff aber ins Leere — der Ablage-Status aus RA-MICRO wurde nirgends übernommen, und die Zuordnung SV↔Akte existiert ausschließlich in RA-MICRO (`beteiligte` enthielt genau einen SV-Eintrag).

**Gebaut:** `ramicro/ablage_service.py` (Ablage-Status lesen — maßgeblich ist `iAblageNummer`, **nicht** `dtAblage`: RA-MICRO trägt dort für nicht abgelegte Akten den Nullwert `1899-12-30` ein), `services/ablage_abgleich.py` (beidseitig; eine Reaktivierung stellt den in `status_vor_ablage` gesicherten Aktenstand wieder her, ein selbst gesetzter Abschluss bleibt unangetastet), nächtlicher Lauf 03:30, `services/sv_zugriff_sync.py` + Portal-Endpunkt `POST /api/sync/sv-zugriffe` (Berechtigung getrennt vom Akteninhalt), Kurzbezeichnung im Payload, Freigabe zur **Ausnahme-Sperre** umgestellt (`portal_gesperrt`; der Knopf „alle aktivieren" entfällt — er hatte 545 leere Akten-Hüllen erzeugt).

**Migration 69** — neben den neuen Spalten eine Schema-Reparatur der Bestands-DB: Es fehlten `portal_sync_queue`, `portal_einladungen`, `fragebogen_erstkontakt` sowie `beteiligte.gutachten_nr`, `dokumente.portal_sichtbar`, `unfallakte.regulierung_status`, `unfalldetails.erstellt_am` — sämtlich aus als erledigt gestempelten Migrationen (38/39/45/46), die nie ausgeführt wurden. Zusätzlich: Fremdschlüssel von `forderung_positionen`/`abrechnungsschreiben` zeigten auf die entfallene Tabelle `dokumente_alt`, wodurch bei eingeschalteter Fremdschlüsselprüfung **jedes** Löschen einer Akte scheiterte; und `beteiligte.id` hatte seinen Primärschlüssel verloren (9 von 17 Zeilen ohne Nummer) — beides repariert.

**Behobene Anzeigefehler:** „bezahlt ✓" bei Akten ohne erfasste Forderung (Karte **und** Rechnungsblock zeigen jetzt einen Strich); abgelaufene Sitzung führte in den Einstellungen zu einer leeren SV-Liste statt einer Meldung.

**Abnahme 2026-08-21:** Ablage-Abgleich zweistufig (Vorschau → Freigabe RA Schatz → Schreiben): 329 geprüft, 40 auf `abgeschlossen`, 21 Bezeichnungen. Endstand deckungsgleich mit RA-MICRO: 578 Akten / 109 laufend / 469 abgeschlossen, alle mit Kurzbezeichnung. Testsuiten: Backend **1827 passed / 20 skipped / 0 failed**, Portal **230/230**, Frontend **548/548**. Offen: Sichtprüfung im Browser (Cockpit-Startseite, Aufklappen des Chips, Reaktivierungs- und Sperr-Szenario) sowie die Veröffentlichung des Portals — es läuft bisher nur lokal.

---

## 2026-08-12 — Sachbearbeiter-Verwaltung in den Einstellungen (Branch `sachbearbeiter-verwaltung`)

Spec: `docs/superpowers/specs/2026-08-12-sachbearbeiter-verwaltung-design.md`, Plan: `docs/superpowers/plans/2026-08-12-sachbearbeiter-verwaltung.md`. Vier hartcodierte Sachbearbeiter-Listen (Frontend `ALLE_SB`/`DEFAULT_SB`, Backend-Dict `SACHBEARBEITER`, `_KALENDER_ZU_SB`, Vorauswahl) durch eine einzige Tabelle ersetzt. Backend-Vollsuite **1769 passed / 20 skipped / 0 failed** (455.82 s), Frontend **530/530** (87 Testdateien).

**Migration 68 — Tabelle `sachbearbeiter`, elf Startzeilen:**

| Kürzel | Name | Rolle | Status |
|---|---|---|---|
| AS | Andreas Schatz | Anwalt | aktiv |
| PK | Peter Koch | Anwalt | aktiv |
| CO | Claudia Ostarek | Anwalt | aktiv |
| MM | Monika Mieth | Anwalt | aktiv |
| AH | Alexander Herbert | Anwalt | aktiv |
| CS | Carina Salvagnin | Anwalt | aktiv |
| TB | Tanja Brunner | ReFa | aktiv |
| SK | Sophie Koch | ReFa | aktiv |
| EI | Elsa Ihl | ReFa | aktiv |
| SN | Susanne Neumann | ReFa | aktiv |
| JH | Jochen Hofmann | Anwalt | inaktiv (Partner bis 2011) |

Spalten: Kürzel, Name, Titel, Anrede, Rolle, aktiv, ignoriert, dashboard_vorauswahl, kalender_name (mit partiellem Unique-Index), sortierung.

**RA-MICRO-Bestandsaufnahme (2026-08-12, `tblAkten`):** PK 7608 · AH 4255 · AS 3201 · MM 3120 · **JH 2182** · CO 205 · ME 20 · EM 5 · EY 2 · EI 1. JH war dem System bisher unbekannt (Altakten zeigten nur `[JH]` statt Klarname) und wurde deshalb als inaktiv angelegt statt gelöscht — Altschreiben behalten so ihren Namen. ME/EM/EY (20/5/2 Akten) sind Fehlanlagen und wurden ignoriert.

- **Backend liest aus der Tabelle statt aus dem Dict** (`backend/ramicro/sachbearbeiter.py`): `hole_sachbearbeiter()` behält seine bisherige Signatur, damit die fünf DOCX-Generatoren unangetastet bleiben. Fällt nur dann auf das eingebaute Dict zurück, wenn die Tabelle fehlt (z. B. Migration noch nicht gelaufen). Bewusst kein Cache.
- **Kalender-Zuordnung:** `_KALENDER_ZU_SB` in `dashboard_routes.py` durch `kalender_zu_kuerzel()` ersetzt, das die Tabelle abfragt.
- **CRUD-Endpunkte** `/einstellungen/sachbearbeiter` (GET/POST/PUT/DELETE) mit Validierung: Kürzel exakt zwei Großbuchstaben, Kalendername eindeutig, Rolle/Anrede aus fester Menge; Fehler als 400/404/409.
- **RA-MICRO-Abgleich** `GET /einstellungen/sachbearbeiter/ramicro-abgleich` — read-only, blockiert nie: Verbindungsfehler landen als WARNING im Log, unerwartete Fehler als ERROR inklusive Stacktrace (unterscheidbar von reinem RA-MICRO-Ausfall).
- **Neuer Einstellungen-Reiter „Sachbearbeiter":** Liste anzeigen/ändern, Anlegen, Löschen mit Rückfrage, RA-MICRO-Abgleich mit „anlegen"/„ignorieren" je Fund.
- **Tagesübersicht:** Chips, Vorauswahl und Klarnamen-Tooltips kommen jetzt aus der Tabelle; die beiden bestehenden Sicherheitsverhalten bleiben erhalten (unbekannte Kürzel werden nie versteckt, vor dem Laden der Sachbearbeiter-Liste wird nicht gefiltert).

**Zwei echte Befunde aus den Reviews behoben:**
- JSON `null` wurde beim Kalendernamen als Text „None" gespeichert — die Zuordnung ließ sich danach nicht mehr entfernen (Geisterkonflikt beim erneuten Speichern). Fix: `null` wird vor dem SQL-Insert/Update in echtes SQL-`NULL` übersetzt.
- Das Speichern einer Zeile im Einstellungen-Reiter hat bislang alle ungespeicherten Eingaben in Nachbarzeilen verworfen (`laden()` ersetzte den kompletten Entwurf). Fix: `laden()` merged jetzt in den bestehenden Entwurf, statt ihn zu ersetzen — trägt auch für die späteren Auslöser Anlegen/Löschen/Abgleich.

**Commits:** `b3321cde`..`3dcfa48a` (15 Commits ab dem Plan-Commit, Branch `sachbearbeiter-verwaltung`, SDD-Workflow mit Review je Task).

**Offen:** Browser-Sichtprüfung im Produktivbetrieb (Reiter „Sachbearbeiter" + Tagesübersicht-Chips) steht noch aus — siehe `docs/TODO.md` unter Produktiv-Nachtests.

**Nacharbeit — Abschlussprüfung, vier Befunde behoben (2026-08-12):**
- **W-1:** `PUT .../sachbearbeiter/<kuerzel>` mit `aktiv: true` setzt `ignoriert` jetzt auf 0 zurück — sonst blieb eine „reaktivierte" ignorierte Zeile trotz vollständig gepflegtem Namen wirkungslos (Sackgasse ohne Datenbankeingriff). Reiter unterscheidet „ignoriert (nicht gepflegt)" von „ausgeschieden"; RA-MICRO-Abgleich erklärt in einem Satz, was „ignorieren" bedeutet.
- **W-2:** Schutzplanken-Test ergänzt, der `hole_sachbearbeiter("JH")` mit `aktiv=0` gegen ein künftiges `AND aktiv = 1` in der Abfrage verriegelt (würde sonst 2.182 Altakten auf `[JH]` zurückwerfen, unbemerkt von der Vollsuite).
- **W-3:** `GET /einstellungen/sachbearbeiter` liest jetzt über `alle_sachbearbeiter()` (Modul-SSOT) statt über eine eigene Abfrage — bei fehlender Tabelle (Bestands-DB ohne Migration 68) liefert der Endpunkt die eingebaute Fallback-Liste statt eines 500ers.
- **W-4:** Ein neu gepflegtes Kürzel verschwand aus der Tagesübersicht, weil die gespeicherte SB-Auswahl (`localStorage`) Vorrang vor der Vorauswahl hatte und ein neues Kürzel darin nie enthalten war — träfe **Fristen** ebenso wie Termine. Fix in zwei Schritten: zuerst ein neuer „bereits gesehen"-Bestand (`dashboard.bekannteSB`), der neue Kürzel beim Neuladen der Seite automatisch zur Auswahl hinzufügt; eine Nachprüfung deckte auf, dass der Aktualisieren-Knopf und Kachel-Retries ein neues Kürzel innerhalb derselben Sitzung trotzdem verschluckten (der Bestand wurde bei jedem Laden fortgeschrieben, die Auswahl aber nur beim allerersten Laden abgeleitet) — zweiter Fix merged neue Kürzel jetzt auch in eine bereits bestehende Auswahl, sichtbar sofort nach „Aktualisieren", nicht erst nach Neuladen der Seite.
- Dazu: Schutzplanken-Test für `kalender_zu_kuerzel()` mit ausgeschiedenem Sachbearbeiter (die bewusste Nicht-Filterung war bisher nur für `hole_sachbearbeiter()` verriegelt, nicht für die Kalender-Zuordnung selbst — `docs/DECISIONS.md` korrigiert).
- **W-4, zweite Nachbesserung:** Der Aktualisieren-Fix mergte neue Kürzel zwar in eine bestehende Auswahl, aber der allererste Mount-Ladevorgang gab die erweiterte Auswahl nur zurück, ohne sie in localStorage zu schreiben — das neue Kürzel wäre beim nächsten Seitenaufruf wieder verloren gegangen (bekannteSB kannte es schon, aktiveSB nie). Der Mount-Pfad persistiert die Auswahl jetzt ebenfalls, wenn sie von der gespeicherten abweicht. Zusätzlich überschreibt eine leere Serverantwort den „bereits gesehen"-Bestand nicht mehr (sonst hätten beim nächsten Laden alle Kürzel als neu gegolten und bewusst abgewählte wären ungewollt reaktiviert worden).
- **W-4, dritte Nachbesserung:** Der Mount-Pfad-Fix (vorheriger Punkt) hatte kein Gegenstück zum Leer-Antwort-Guard -- bei einer Antwort ohne Kürzel (HTTP 204, leere Tabelle, alle Zeilen inaktiv/ignoriert) verwarf initialeAuswahl() eine gespeicherte, nicht-leere Auswahl als „ungültig" und der Mount-Zweig persistierte die dadurch leere Menge sofort in dashboard.aktiveSB, während dashboard.bekannteSB dank des vorigen Guards erhalten blieb. Weil eine geleerte Auswahl bewusst klebrig ist, war der Verlust endgültig -- alle Vorgänge mit bekanntem Kürzel, inklusive Fristen, blieben dauerhaft weggefiltert. Fix: ein einziger Guard aktiveKuerzel.length > 0 um den kompletten Auswahl-/Bestand-Block, beide localStorage-Schlüssel bleiben bei leerer Antwort unangetastet.
- **W-4, vierte Nachbesserung:** Auswahl fehlt + Bestand gefüllt war real erreichbar (Fallback-Liste ohne Vorauswahl, oder Nutzer entfernt alle Vorauswahl-Haken) und führte zu `aktiveSB = ∅` bei nicht-leerer Kürzelliste -- Banner „Kein Sachbearbeiter ausgewählt", jede Frist/jeder Termin ausgeblendet. `initialeAuswahl()` wählt jetzt alle aktiven Kürzel, wenn weder eine gespeicherte Auswahl noch eine gepflegte Vorauswahl existiert („lieber zu viel zeigen als eine Frist verschlucken"); eine vom Nutzer selbst geleerte Auswahl bleibt unberührt. Ursache mitbehoben: die Fallback-Liste (`_fallback_zeilen()`) trägt jetzt dieselbe Vorauswahl (AS, PK, CO, MM, AH) wie die Migration-68-Startzeilen.

**Commits:** `a209c74f` (Backend W-1/W-2/W-3), `585b38c4` (Frontend W-1/W-4), `274fc824` (Doku), `3336b50c` (W-4-Nachbesserung Aktualisieren-Pfad), `514a3ae8` (Schutzplanke `kalender_zu_kuerzel()` + DECISIONS-Korrektur), `daa0ed01` (Doku), `fcfb23ae` (Mount-Pfad-Nachbesserung), `4d786ac8` (Doku), `ba19d15a` (Leer-Antwort-Guard), `a6d2f677` (Doku), `9ac8c94a` (fehlende Auswahl + Fallback-Vorauswahl), plus der zugehörige Doku-Commit dieses Abschnitts. Backend-Vollsuite **1774 passed / 20 skipped / 0 failed** (442.38 s), Frontend **540/540** (87 Testdateien).

---

## 2026-08-12 — Feinschliff Dashboard-Hell (Nacharbeit, `main`)

Die in `docs/TODO.md` gesammelte Nacharbeit zum Dashboard-Hell-Umbau, alle Punkte TDD mit RED-Nachweis. Backend-Vollsuite **1733 passed / 20 skipped / 0 failed**, Frontend **516/516**.

- **Doppelte React-Keys (Befund Playwright-Abnahme 2026-08-10):** Keys kollidierten bei mehreren Einträgen derselben Akte am selben Tag — `FristenKachel` (`az+frist_datum`), `TermineKachel` (`az+datum+uhrzeit`), `WiedervorlagenKachel` (`az+datum`), `JetztDranLeiste` (`prio+az+tage`). Jetzt zusätzlich Frist-Art/Termin-Art/Grund **plus Listenindex**. Vier Tests fangen die React-Warnung „same key" per `console.error`-Spy ab.
- **A11y:** SB-Filter-Chips mit `aria-pressed`, Fehlerblock der Kacheln als `role="alert"`, Lade-Platzhalter (Shimmer) `aria-hidden`.
- **Button-Semantik `boardUi`:** alle Knöpfe (`Zeile`, `MehrKnopf`, Retry) mit `type="button"`; Retry ist während des Nachladens deaktiviert und zeigt „Lädt …" (neue Prop `retryLaeuft`, von `ActionBoardView` aus `laedtGerade` durchgereicht).
- **Badge-Logik konsolidiert:** `tageBadgeText()` liegt jetzt einmal in `boardUi.jsx`; Fristen- und Wiedervorlagen-Kachel nutzen sie gemeinsam (`JetztDranLeiste` behält ihre eigene Wortform „N Tage überfällig").
- **Toter Code entfernt:** `pendingEmailId` wurde nie gesetzt, nur genullt — die ganze Kette raus (`App.jsx` → `EmailImportView` → `UnfallEmailView` inkl. `letzteInitialId`-Ref und Auto-Öffnen-Effekt). Dazu `api.nachrichtenNeu` und der Backend-Endpoint `GET /dashboard/nachrichten-neu` samt Helfer `_lade_nachrichten_neu` (nirgends aufgerufen). Guard-Tests: `api.dashboard.test.js` (Frontend), `test_nachrichten_neu_entfernt` (Backend).
  **Notiz:** Eine entfernte GET-Route liefert in dieser App **405, nicht 404** — der CORS-Preflight-Catch-all (`/<path:path>`, nur OPTIONS, `app.py:326`) matcht jeden Pfad. Im Test vermerkt.
- **Sidebar-Icons vereinheitlicht:** die vier Emoji (🔍 📋 📥 ⚖️) durch SVG-Icons ersetzt — `Ic.search`, neu `Ic.liste`, neu `Ic.inbox`, `Ic.scale`. Guard-Test `App.navIcons.test.js` verbietet künftige Emoji in `navItems`.
- **Offen geblieben:** SB-Klarnamen-Tooltips — daraus wurde ein eigenes Vorhaben (Spec `docs/superpowers/specs/2026-08-12-sachbearbeiter-verwaltung-design.md`), weil die Kürzel an vier Stellen hartcodiert sind. Nebenbefund: `apiDashboard.onboardingOffen` + `GET /dashboard/onboarding-offen` sind ebenfalls ungenutzt (nicht angefasst).

---

## 2026-08-11 — Testsanierung Backend-Vollsuite: 123 vorbestehende Failures → 0 (Branch `abschlussbericht`)

Auftrag: `handover/naechste_session_testsanierung_vollsuite_prompt.md` (Fortsetzung der modul6/7-Sanierung). Vorher 123 failed / 1610 passed, nachher **0 failed / 1735 passed / 20 skipped**. Kategorisierung: überwiegend Test-Verrottung (die ältesten Suiten modul1–4 + Nachbarn), 2 Isolationsprobleme, **3 echte Produkt-Befunde** (separat ausgewiesen, alle TDD mit RED-Nachweis).

**Echte Befunde (Produktcode geändert):**
- **Frisch-DB-Schema: FK auf nicht existierendes `unfallakte(id)`** (`schema_manager.py` Migration 3): `abrechnungsschreiben` + `pruefberichte` referenzierten `unfallakte(id)` — die Spalte gibt es nicht (PK ist `az`). Auf Alt-DBs hat der Migration-5-Rebuild das längst korrigiert (Live-DB verifiziert: FK auf `az`), Migration 5 überspringt aber frische DBs → dort crashte jedes INSERT/DELETE mit „foreign key mismatch" (deshalb auch die `PRAGMA foreign_keys=OFF`-Workarounds in `models/abrechnungsschreiben.py`, jetzt obsolet → Vermerk in `bugfixes.md`). Fix im Migration-3-DDL: `akte_id TEXT REFERENCES unfallakte(az)`; Bestands-DBs (Version ≥ 3) unberührt. Guard-Test `test_fk_abrechnungsschreiben_und_pruefberichte_zeigen_auf_az` in modul1.
- **`todos` blockierte den Akten-Delete** (Migration 23 + 32): FK ohne `ON DELETE`-Klausel; da jede neue Akte automatisch Verjährungsfristen-Todos bekommt (PRD-25a), schlug `DELETE /akten/<az>` auf frischen DBs immer fehl (Live-DB hat gar keinen todos-FK — Bestand unberührt). Fix: `ON DELETE CASCADE` im Frisch-DDL, entspricht der dokumentierten Route-Semantik („löscht inkl. aller verknüpften Daten").
- **„Rechnung (Auffang)" in der nutzersichtbaren Dokumentbezeichnung** (`rechnung.yaml` + `services/dokument_bezeichnung.py`): Die SSOT-Klassen-Registry setzte `label: Rechnung (Auffang)` (Dropdown-Unterscheidung zu Spezialrechnungen) — `baue_bezeichnung()` übernahm das 1:1 in `dokumente.bezeichnung` („Rechnung (Auffang) Autohaus Müller vom …"). Fix: optionales `bezeichnung_label: Rechnung` in der YAML, Service nutzt es mit Fallback auf `label`. Dropdown behält „(Auffang)".

**Test-Verrottung (nur Tests portiert):**
- **modul2 (16) + modul3-Basis + modul4-Basis + prd27 + dashboard_uebersicht (9):** Auth-Bootstrap veraltet — `erstelle_app()` seedet seit v41 Admins (`_ensure_admin_exists`), conftest.py setzt dafür `ADMIN_EMAIL=admin@test.de`; die alten Tests registrierten per `register/erster` (→ 409) bzw. nutzten die Kanzlei-Default-Credentials oder das tote `benutzername`-Login-Format.
- **modul3 (50):** AZ-Format-Validierung `####/YY(SB)` (Tests nutzten `25-T-001` etc.), Response-Shape (`regulierungsstatus` statt `regulierungen`), Duplikat-AZ liefert heute die bestehende Akte (on-demand-Semantik) statt 422, `pruefe_akte` behandelt AZ-förmige IDs als potenzielle RA-MICRO-Akten (404-Tests auf nicht-AZ-förmige Kennung umgestellt), `v_regulierungsstatus` speist sich seit Option B aus `regulierung_positionen` (Legacy-`regulierung` zählt bewusst nicht mehr).
- **modul4 (32):** Setup-AZ ungültig; Upload-POST liefert unter `INTAKE_REVIEW_PFLICHT` 202 → Review-Queue (keine dokumente-Zeile, kein typ-Check, keine Auto-Schaden-Übernahme = S1.9c BREAKING #2, jetzt explizit getestet); Routen-Tests an bestehenden Dokumenten seeden über den Upload-Service (Alt-Pfad).
- **modul1 (6):** `_ns` rief nur `create_schema()` ohne `run_migrations()` (check_schema erwartet Migrations-Tabellen); Duplikat-AZ/Haftungsquoten-Validierung auf heutige Semantik (IntegrityError via CHECK-Constraint) portiert.
- **migration_46 (1):** Test entfernte nur Migration 46 aus MIGRATIONS und lief dann in Migration 48, die die intake-Tabellen aus 46 voraussetzt — jetzt werden alle ≥ 46 entfernt/restauriert.
- **s19-Guard (1):** reiner Zeilen-Drift durch die E-Mail-Hotfixes `34342daa`/`8e9b50ea` — per git-Diff seit `2a358bd8` verifiziert, dass KEIN `registriere_dokument`-Aufruf hinzukam; Whitelist auf {324, 784, 814, 1182} nachgezogen.
- **sv_portal (4, Isolationsproblem):** `app_client`-Fixture setzte nie `DB_PATH` und hing vom zufällig zuletzt gesetzten Wert des vorher gelaufenen Testmoduls ab → eigene frische DB je Test. Toggle-Test auf die heutige On-demand-Semantik portiert (Akte wird per `INSERT OR IGNORE` angelegt statt 404 — RA-MICRO ist SSOT).
- **intake_akten_matching (1, Isolationsproblem):** Der Score-Test lief gegen das **echte** RA-MICRO (im Dev-Container erreichbar) — der Fallback lieferte 1.0 statt des SQLite-Basis-Scores 0.9. `_suche_in_ramicro` jetzt klassenweit gemockt (analog `_RAMICRO_VERFUEGBAR=False` aus der modul6/7-Runde).
- **Minor ausgewiesen (kein Fix):** `GET /akten` liefert `gesamt` = Seitengröße statt Gesamtzahl (FE nutzt das Feld nicht) → `bugfixes.md`.
- Testbilanz: Backend-Vollsuite **1735/1735 grün** (20 skipped, 7:05 min). Frontend unberührt (keine FE-Änderungen; Registry-`label` fürs Dropdown unverändert).

---

## 2026-08-11 — Sachstandsanfrage: Code-Review + Sofort-Fixes M-1/M-2/G-1/G-2/G-3/G-7 (Branch `abschlussbericht`)

Review-Auftrag RA Schatz („weiß die STA, was abgefragt wurde, ob es schon eine gab, und eskaliert sie?"). Befund-Katalog: `handover/2026-08-11-sachstandsanfrage-review-befunde.md` — Bestandsaufnahme ergab DREI parallele Erzeugungswege (StaDialog/PRD-25d · RA-MICRO-Vorlage · Legacy-word_route) und drei Kernbefunde (K-1 Antworten werden ignoriert, K-2 Vorlagen-Weg unsichtbar für die Stufenlogik, K-3 keine Rundenlogik) → gehören zur PRD-25d-Neuplanung aufs Ereignis-Modell. In dieser Runde nur die Sofort-Fixes, alle TDD (RED verifiziert):

- **M-2 Genus/Kasus im Brieftext (`sta_service.py`):** Der Fehler war größer als im Review notiert — „unser Sachstandsanfrage vom …" (Genus), „mit unser Forderungsschreiben" (Dativ fehlte in Stufe 2/3 für ALLE Typen) und „…, mit dem wir" nach femininen Typen (Relativpronomen, Stufe 1). Lösung: `_SCHREIBEN_REF`-Map (Nominativ/Akkusativ + Dativ je Typ), neuer Template-Platzhalter `{SchreibenDativ}`, Stufe-1-Default mit invariantem „womit". Platzhalter-Hinweis in den Einstellungen ergänzt. Live-DB hat keine Text-Overrides → korrigierte Defaults greifen sofort.
- **M-1 AZ-Format der Dialog-Einstiege (`WordSection.jsx`):** StaDialog + AbschlussberichtDialog bekamen `akte.az`, das je nach Öffnungsweg (z. B. ActionBoard) die volle RA-MICRO-AZ mit SB-Kürzel trägt („312/26 AS") — Backend-Queries liefen dann ins Leere (leerer Kontext, 404 beim Generieren). Jetzt `az_roh || id || az` wie in AkteDetailView.
- **G-2 Fristanzeige StaDialog:** Stufen-Chip zeigte hartcodiert „14/7/5 Tage" statt der in den Einstellungen konfigurierten Werte. `GET /sta/kontext` liefert jetzt `frist_tage` (neues `hole_frist_tage()` in sta_service), Dialog zeigt den Live-Wert und aktualisiert beim Stufenwechsel.
- **G-1 PII-Debug-Logging entfernt (`wiedervorlage_routes.py`):** als „temporär" markiertes `logger.warning` loggte bei jeder WV-Generierung sämtliche Empfänger-Adressdaten.
- **G-3:** ungenutztes `textareaRef` im StaDialog entfernt.
- **G-7 Testlücke geschlossen:** `test_sta_service.py` neu (19 Tests): `_empfohlene_stufe`-Grenzwerte, Genus-/Platzhalter-Ersetzung, `analysiere_regulierung` (Todo-Vorrang, Fallback, leere Akte), Route-Test `frist_tage`. FE: `StaDialog.test.jsx` neu (2 Tests Fristanzeige/Stufenwechsel) + 2 M-1-Tests in `WordSection.test.jsx`.
- Testbilanz: `test_sta_service` 19/19, Frontend-Vollsuite 502/502. Backend-Vollsuite: vorbestehende Failures unabhängig von dieser Runde (test_modul4/test_prd27/test_sv_portal/test_s19-Guard, per Stash-Gegenprobe verifiziert; Guard schlägt auf verschobene Whitelist-Zeilen in `email_import/import_service.py` an — vorbestehend, separates Thema).

---

## 2026-08-11 — Testsanierung test_modul6/test_modul7: 95 vorbestehende Failures behoben (Branch `abschlussbericht`)

Auftrag: `handover/naechste_session_testsanierung_modul6_7_prompt.md` (Befund aus der Forderungsschreiben-Bugfix-Runde vom selben Tag). Reine Test-Verrottung — **kein Produktcode geändert**, nur Tests + Dev-Compose. Commits `cf4641f1`, `df749801`, `c5602cb9`.

- **modul6 (47 Failures): Infra-Dateien fehlten im Container.** Die Infra-Guard-Tests (Dockerfile/Compose/Nginx/Makefile/.gitignore/Backup — u. a. der bewusste `TestBackupInfra`-Guard aus N-10) prüfen Repo-Dateien relativ zur Projektwurzel, die im Backend-Container `/app` ist; dort waren nur `backend/`, `tools/`, `requirements.txt`, `gunicorn.conf.py` gemountet. Alle Inhalts-Assertions waren gegen die Host-Dateien korrekt — reines Umgebungsproblem. **Entscheidung:** Dateien read-only in den Dev-Container mounten (docker-compose.yml) statt Skip-wenn-fehlt, damit die Guards im kanonischen Testlauf (Container) scharf bleiben und bei fehlendem Mount laut fehlschlagen. **Deploy-Hinweis:** einmalig `docker compose up -d --force-recreate backend` nötig, sonst bleiben die modul6-Tests rot. Dazu 1 verrotteter Health-Test repariert (Bootstrap-Admin → 409 bei Neuregistrierung; AZ-Format `####/YY`).
- **modul7 (48 Failures): Tests prüften die tote `email_import.parser`-API** (vor dem E-Mail-Workflow-Umbau). Auf die heutige Produktiv-API portiert, kein Rückbau: Modul `email_parser`, `finde_akte()` liefert `(az, erkannt, match_methode)`, `unfallakte`-PK ist az (TEXT), Log-/Statistik-Status `zugeordnet`/`nicht_zugeordnet` (v9), AZ-Pflichtformat `####/YY(SB)`, Anhang-Semantik unter `INTAKE_REVIEW_PFLICHT` (Anhänge → `intake_dokumente`/Review-Queue, `dokumente` bleibt bis zur Freigabe leer — Assertions prüfen genau das). Ersatzlos gestrichen wurde nichts; einzig `test_az_variante_slash` (totes Format `25/0042`) durch SB-Kürzel-Tests am realen Format `955/25AS` ersetzt.
- **Test-Härtung:** Import-Lauf-Tests deaktivieren das RA-MICRO-Matching (`_RAMICRO_VERFUEGBAR=False`) — die portierten Läufe hätten sonst in die echte, aus dem Container erreichbare RA-MICRO-DB gegriffen (Determinismus + read-only-Gebot). `teste_verbindung` im Status-Routen-Test gemockt (vorher echter IMAP-Connect-Versuch auf `mail.test.de`).
- **Befund ohne Fix (kein Test betroffen, Produktcode-Tabu):** `backend/email_import/import_service.py:39` nutzt `logger` im `except ImportError`-Zweig vor dessen Definition (Zeile 48) — latenter NameError, falls `backend.ramicro.email_matching` je fehlen sollte. Als Minor in `bugfixes.md` vermerkt.
- Testbilanz: modul6 74/74, modul7 56/56 (vorher zusammen 35 passed / 95 failed), Gesamtlauf modul5–7 + `test_forderung_modell` 222/222 grün, Frontend-Vollsuite unangetastet 498/498.

---

## 2026-08-11 — Forderungsschreiben-Modul: Code-Review-Fixes C-1 + I-1..I-9 + Aufräumen (Branch `abschlussbericht`)

Modul-Review vom 2026-08-10 (Befund-Katalog: `handover/2026-08-10-forderungsschreiben-review-befunde.md`, Arbeitsliste: `bugfixes.md` im Projektroot). Alle Fixes TDD (23 neue BE- + 4 neue FE-Tests, jeweils RED verifiziert). Commits `520e75af..1b8d2402`.

- **Aufräumen (`a4cf92ca`):** Toter Alt-Generator `word/forderungsschreiben.py` + 8 ungenutzte Vorlagen gelöscht (nur `forderungsschreiben_vorlage.docx` wird geladen); `TestForderungsschreiben` auf die Produktiv-Variante `_wv` portiert; Fantasie-IBAN-Totcode raus. Nebenbei 15 verrottete `TestWordRouten`-Tests repariert (Setup-AZ scheiterte seit der AZ-Normalisierung an `####/YY`).
- **C-1 (Critical, `9e787541`):** Forderungshistorie erfasste andere Beträge als der Brief (staler Key `rep_fiktiv_netto` → Reparaturkosten fehlten bei fiktiver Abrechnung; Doppelerfassung; Restwert-Vorzeichen; Unkostenpauschale; Nebenkosten brutto/netto). Neu: `berechne_positionen()` als SSOT für Brief-Tabelle UND `erfasse_forderung(akte_id, positionen)`; Restwert wird negativ gespeichert; word_service übergibt das kanonische AZ. **Aggregat-Semantik (I-8):** Zusammenfassung + Gebühren-Streitwert-Fallback zählen je `position_key` nur den Stand des letzten Schreibens.
- **Quick-Wins (`ed797f17`):** I-3 Freitext-`varSCHMGELD` crasht nicht mehr; I-1 Registry-Typen ohne Generator (mahnschreiben/klagedrohung) → 422 statt KeyError-500; I-6 `varSSTF`-Vorsteuer-Override las leeres Dict, greift jetzt; I-7 PATCH auf Forderungspositionen ist akte-gescoped.
- **Juristische Texte (`9d93a951`):** I-4 Schmerzensgeld-Block sprach vorgerichtlich vom „Kläger" — jetzt „Unser(e) Mandant(in)/Mandanten" mit korrektem Numerus (auch wurde/wurden, war/waren); I-5 Pseudo-Variante „grunde" (erzeugte Höhe-Dokument mit 30-€-Tabelle) → 422 „Keine Schadenpositionen erfasst".
- **Frontend (`1b8d2402`):** I-2 Adressat-Dropdown wirkt jetzt (BE reichte `adressat_id` nie durch; FE-Vorbelegung zog bei spät geladenen Beteiligten nicht nach; RA-MICRO-Fallback überschreibt explizite Auswahl nicht mehr); I-9 `ForderungshistorieKarte` mit Ignore-Guard, Ladezustand-Reset und sichtbarem Fehlerzustand.
- Testbilanz: `test_modul5` 84/84, `test_forderung_modell` 8/8 (neu), angrenzende Suiten (Klage, P1.4, Abschlussbericht) 69/69, Frontend-Vollsuite 498/498. `test_modul6`/`7`: 95 vorbestehende Failures (vor/nach identisch) — separates Sanierungsthema.
- **Offen:** I-10 Haftungsquote (Alleinschuld-Baustein trotz erfasster Teilhaftung; HQ=0-Semantik) — braucht Formulierungsentscheidung RA Schatz; Minors laut `bugfixes.md` opportunistisch.

---

## 2026-08-10 — Übersicht-Redesign A+B: Summen-SSOT, 3 Akkordeons, Onboarding-Fächer, Aktions-Pills (Branch `abschlussbericht`)

Umsetzung der Redesign-Mockups A+B (`handover/2026-08-10-uebersicht-redesign-mockups.md`, von RA Schatz freigegeben), SDD-Plan mit 11 Tasks im Anschluss an die Review-Session vom selben Tag (Befund-Katalog: `handover/2026-08-10-uebersicht-review-befunde.md`, löst B3 sowie die dort unter „Bewusst offen" vermerkten Doppel-Requests/-Logiken). Frontend-Vollsuite 491/491 grün.

- **Task 1 (`ddcccc82`):** Summen-Helfer extrahiert, `PositionsDashboard` bekommt eine `daten`-Prop statt eigenem Fetch — Vorbereitung für die gemeinsame Summen-Quelle.
- **Task 2 (`837ac355`, Befund B3):** Header-KPI rechnet jetzt aus den Ereignismodell-Summen (`/akten/<az>/positionen/status`); die Alt-Berechnung (`liveBrutto × HQ`) läuft nur noch als Fallback für Bestandsakten ohne Ereignisse. Siehe DECISIONS.md.
- **Task 3 (`68a8bed9`):** Redesign A umgesetzt — FinanzBand, RegulierungsTabelle und Forderungshistorie aus der Übersicht entfernt, durch 3 Akkordeons ersetzt, Phasenberechnung liest dieselben SSOT-Summen; `PositionsDashboard`-Titel zu „Positionen" vereinfacht.
- **Task 4 (`11e417c6`):** Forderungshistorie in den Regulierung-Tab verschoben (neue Komponente `components/ForderungshistorieKarte.jsx`).
- **Task 5 (`bae596fd`, Fix `723d51a4`):** Check-Pills mit Aktions-Popover, `mandantAktionen.js` als wiederverwendbare Helfer; Review-Fix hebt `AktionsPill` auf Modulebene, damit der Popover-State Re-Renders übersteht.
- **Task 6 (`4029846a`):** Onboarding-Checks als pure Funktion (`onboardingChecks.js`) — Vorbereitung für die Fächer-Darstellung.
- **Task 7 (`8d65f540`):** Redesign B umgesetzt — Onboarding-Fächer im PhasenStrip ersetzen den bisherigen Hub-Banner, `OnboardingHub` komplett entfernt.
- **Task 8 (`4703fb03`):** RA-Micro-Akkordeon zeigt nur noch Beteiligte, Kachel-Checks raus, `mandant-checks` nur noch 1 Request pro Akte statt 3.
- **Task 9 (`a326ab08`):** Tab-Leiste mit Farbpunkten/Badges statt Status-Emojis, 💰-Icon für den Gebühren-Tab, Button-Einrückung gefixt.
- **Task 10 (`7d4c3487`):** `dringlichkeit()`-Ampel zu `todoDringlichkeit()` dedupliziert (vorher 3× kopierte Logik).
- **Task 11 (dieser Eintrag):** Doku-Abschluss — DECISIONS.md (Summen-SSOT-Entscheidung), CHANGELOG.md, TODO.md.
- **Final-Review-Fixes (`dece57ef` + `70b2cee4`):** Whole-Branch-Review fand 1 Critical + 2 Important, alle behoben: (1) Aktions-Popover wurde vom `overflow:hidden` der Leisten-Box abgeschnitten (im Browser unsichtbar, jsdom-blind) — Rundung jetzt auf den Kind-Elementen, dazu Escape-/Click-Outside-Schließen; (2) `posDaten`-Fetch ohne Abbruch-Guard konnte bei schnellem Aktenwechsel fremde Summen anzeigen — Cleanup-Flag ergänzt; (3) PositionsDashboard fetchte parallel zum Header selbst (Doppel-Request + mögliche Header/Tabelle-Divergenz) — neuer `ladeStatus`-Durchgriff, Parent lädt exklusiv; dazu mailto-Guard ohne bekannte E-Mail. +3 Tests, Vollsuite danach 494/494. Re-Review: READY.
- **Offen (Human-Gate):** Browser-Abnahme durch RA Schatz (Fächer, Pill-Popover, KPI-Zahlen an echter Akte, Bestandsakten-Fallback) — siehe TODO. Merge-Strategie `abschlussbericht` → `main` weiterhin ungeklärt (Branch stapelt auf Intake-Branch). Mockup C (Cockpit) nur bei Bedarf.

---

## 2026-08-10 — Übersicht-Review: 7 Befunde gefixt + toter Code entfernt (Branch `abschlussbericht`)

Review der ÜbersichtSection/AkteDetailView vom selben Tag (Befund-Protokoll: `handover/2026-08-10-uebersicht-review-befunde.md`, Redesign-Mockups separat). Alle Fixes TDD (11 neue Tests RED→GREEN), Frontend-Vollsuite 476/476 grün.

- **B1 (Crash):** `RegulierungsTabelle` referenzierte `effRep`/`ist130`, die dort nie definiert waren (unvollständig aus `constants.js` kopiert) — ReferenceError, sobald keine Abrechnungsart gesetzt und WBW > 0. Definitionen ergänzt (identisch zu `positionenVorlage`).
- **B2 (OnboardingHub):** prüfte Phantomfelder (`schaden.positionen`, `schaden.unfalldatum`, `a.typ`, kleingeschriebene Rollen, `d.klasse`) → 4 Kacheln konnten nie grün werden, Hub erschien wegen `!mandant.iban` quasi immer. Jetzt echte Quellen (`akte.unfalldatum`/`unfallort`, `gesamt_brutto`, `dokumentenklasse`, Rollen case-insensitive inkl. GHV/GBEV); Sichtbarkeit hängt an der eigenen Checkliste (verschwindet, sobald alle Pflichtbereiche ✓); Zähler dynamisch statt hartem „von 6".
- **B4:** „+ Todo" im Akten-Header öffnet jetzt wirklich das Inline-Formular (vorher nur Navigation zur Übersicht).
- **B6:** Akten-Chronik sortierte über formatierte Datums-Strings (innerhalb eines Jahres nach Uhrzeit statt Monat); jetzt ISO-`sortKey` vor der Formatierung.
- **B7:** §3a-Frist-Pill matchte `frist_typ === "gerichtlich"`, das To-Do-Formular vergibt aber `gericht` — beide Werte akzeptiert.
- **B8:** RSV-Kachel zeigte das Aktenzeichen doppelt (`zeigeBetreff` + `zeigeAktenzeichen`); dazu Doppel-Chevron `⌄⌄` korrigiert.
- **B5 (toter Code):** `AkteActionBoardHeader`, `TodoKachelKompakt`, `InfoZeile`, `InfoRow` + verwaiste Berechnungen (`regGrad`, `klageSumme`, brutto/netto-Block, `mandantName`) entfernt (~10,5 kB); `StaDialog` in `AkteDetailView` direkt importiert statt über den UebersichtSection-Re-Export; ungenutzte Importe bereinigt. Für Tests neu exportiert: `AktenTimeline`, `StatusBand`, `RechtsschutzKlappkachel`, `TodoInlineForm`.
- **Bewusst offen (Redesign-Session, `handover/2026-08-10-uebersicht-redesign-mockups.md`):** B3 — Header-KPI (mit HQ) und FinanzBand (ohne HQ) rechnen Summen unterschiedlich; Design-Entscheidung „eine Summen-SSOT" nötig. Ebenso: 3× `mandant-checks`-Request pro Aktenöffnung, 3× kopierte `dringlichkeit()`-Logik, 2× posMap-Aggregation.

---

## 2026-08-07 — Referenzwerkstatt editierbar in der ReviewQueue (Befund RA Schatz, Branch `abschlussbericht`, `a0d38d13`)

Befund bei der Browser-Abnahme: Das Feld `referenzwerkstatt` im Prüfbericht-Review erschien nur als JSON-Box, nicht korrigierbar — obwohl die Extraktion danebenliegen kann (Dok 555/Akte 332/26: Name „Postanschrift:", Ort „14329 Berlin\nFirmensitz"). Falsche Werkstatt-Adressen hätten die Entfernungsprüfung mit Müll gefüttert; Heilung ging nur über „Erneut parsen".

- **Neuer `ObjektFelderEditor`** in `ReviewQueueView.jsx`, analog zur Positions-Tabelle vom selben Tag: Werkstatt-Daten (name, adresse, plz_ort, telefon, km_genannt) als editierbare Zeilen, numerische Felder parsen auf Blur als Zahl (`parseBetragDe`, deutsches Format).
- **Maschinelle Prüfwerte bleiben schreibgeschützt** (`MASCHINELLE_OBJEKT_FELDER`: quelle, km_echt, minuten, abweichung_km, bewertung, geprueft_am, geprueft_gegen_akte) — sie kommen aus der Entfernungsprüfung bzw. der Extraktions-Herkunft und werden nur angezeigt.
- Verschachtelte Unterobjekte (z. B. `stundensaetze`) und nicht-flache Arrays bleiben JSON-Anzeige (`JsonBox` extrahiert).
- **Speicherweg unverändert bestätigt:** `PATCH /intake/dokument/<id>/felder` aktualisiert nur geänderte Felder, loggt ins `korrektur_log`, lässt übrige Felder unangetastet — Werte werden korrekt persistiert.
- **Tests (TDD, RED→GREEN):** 6 neue in `ReviewQueueView.objektfelder.test.jsx`; 2 Alt-Tests vom Vortag (Objekt = read-only-JSON) auf das neue Verhalten umgestellt. Frontend-Vollsuite 465/465 grün.

---

## 2026-08-07 — Firmen-Beteiligte: „Firma" statt echtem Namen (Befund 1280/25, Branch `abschlussbericht`, `6801be75`)

Befund RA Schatz: Die Beteiligten-Section der Akte 1280/25 zeigte einen Eintrag „Firma" mit leeren Feldern statt des echten Gegners „RCR GmbH". Ursache: RA-MICRO speichert den Namen (auch Firmennamen) IMMER in `sNachname`; `sErsteAdresszeile` ist nur die Anredeform des Adressfelds („Herrn", „Frau", „Firma", „Anwaltskanzlei", „c/o …") — per Datenanalyse bestätigt (12.559× „Herrn", 6.990× „Frau", 3.327× „Firma", nie ein echter Name). Unsere Heuristik „kein Vorname → `sErsteAdresszeile` ist Firmenname" verwarf dadurch bei Firmen den echten Namen; der Code-Kommentar „sErsteAdresszeile = offizieller Firmenname" war falsch.

- **Neue Helferfunktion `name_aus_ramicro_adresse(nachname, erste_adresszeile)`** (`word_service.py`, modulweit): Nachname zuerst, erste Adresszeile nur Fallback wenn Nachname leer. In Brief-Adressblöcken bleibt `sErsteAdresszeile` als eigene Zeile ÜBER dem Namen unverändert korrekt.
- **7 Fundstellen umgestellt:** `_beteiligter_dict` in `_lade_beteiligte_aus_ramicro` (Beteiligten-Section — der gemeldete Fall) und `_lade_gegner_adresse_aus_ramicro` (Forderungsschreiben-Gegneradresse; bevorzugte `erste` sogar bedingungslos) in `word_service.py`; `belege_routes.py` (Beleg-Kandidaten); `klage_routes.py` (Gerichts-Ermittlung); `wiedervorlage_routes.py` (Empfänger im Aktivitätslog, 2×); `personenschaden_routes.py` + `ramicro_akte_routes.py` (2×) (Adressanzeige/Adresssuche/Mandantenname — Muster `firma if firma else …` gedreht).
- **Anrede-Code „4" = Firma** ins Mapping aufgenommen (`ANREDE_CODES`, vorher wurde „4" roh angezeigt).
- **Tests (TDD, RED→GREEN):** 5 neue in `test_ramicro_firmen_name.py` (Helper-Units + nachgebautes 1280/25-Szenario über `_lade_beteiligte_aus_ramicro` mit Fake-Cursor). Gegenprobe per Stash: die 5 `test_modul8`-Fehlschläge im Kombi-Lauf sind vorbestehend (Testreihenfolge), nicht durch diesen Fix.
- **Live verifiziert (1280/25):** Mandantin „Anita Petrovic", Gegner „RCR GmbH" (Anrede: Firma), VHV als GHPV, SV Ninnivaggi.
- Bekannter Rest (bewusst nicht angefasst): Alt-Heuristik setzt bei Gegnern ohne Vorname `versicherung = name` — die RCR GmbH zeigt daher „RCR GmbH" auch im Versicherung-Feld.
- Memory: `feedback_ramicro_erste_adresszeile`.

---

## 2026-08-07 — Abrechnungs-Positionen: fehlender Hauptbetrag + editierbare Positions-Tabelle (Befund 1280/25, Branch `abschlussbericht`)

Befund RA Schatz: Im VHV-Abrechnungsschreiben (Dok 517, Akte 1280/25) fehlte „Abrechnung nach Prüfbericht 5.448,62 EUR" in `felder.positionen` — die LLM-Extraktion las die Zeile als `abrechnungsart`, die Summen-Validierung meldete korrekt die 5.448,62-Differenz, korrigieren ließ es sich aber nicht, weil `positionen`/`zahlungen` im Review nur als rohes JSON angezeigt wurden.

**Backend (`abrechnungsschreiben_parser.py`, `intake/extraktion.py`):**
- Neues Positions-Pattern „Abrechnung nach Prüfbericht" → `reparatur_netto` (VHV-Layout für regulierte Reparaturkosten).
- `sv_kosten`-Suchfenster endet jetzt an Summen-/Zahlungszeilen (`_SUMMENZEILEN_RE`) — die Maximum-Heuristik griff sonst den Auszahlungsbetrag der Folgezeile (VHV: 7.751,54 statt 1.316,62).
- Sicherungsnetz `_ergaenze_abrechnungspositionen` (nur Klasse `abrechnungsschreiben`, nach der LLM-Extraktion): Regex-Positionen als deterministische Kandidaten. Leere LLM-Liste → Kandidaten komplett übernehmen; sonst wird nur ergänzt, was die Differenz zum Gesamtbetrag **exakt** erklärt (einzelner Kandidat oder Summe aller fehlenden; Toleranz 1 Cent wie `validierung.py`; Abzugs-Arten `mwst_abzug`/`pruefbericht_abzug`/`restwert` nie). Erklärt nichts die Differenz, bleibt die ehrliche Validierungswarnung stehen — kein Raten.

**Frontend (`ReviewQueueView.jsx`):**
- `FelderEditor`: Listen flacher Objekte (`positionen`, `zahlungen`) werden als editierbare Tabelle gerendert (Spalten = Key-Union, Zeile hinzufügen/entfernen) statt als JSON-Box. Betragsspalten (Regex `betrag|summe|mwst` oder numerischer Wert) zeigen deutsches Format; Parse auf Blur via `parseBetragDe` („5.448,62" → 5448.62 als **Zahl** — Strings würden von der Summen-Validierung still ignoriert). Verschachtelte Objekte (`referenzwerkstatt`) bleiben bewusst schreibgeschützte JSON-Anzeige.

**Tests (TDD, RED→GREEN):** 8 neue BE-Tests (`test_abrechnung_positionen_sicherungsnetz.py`: Parser-Pattern, SV-Fenster, Ergänzen einzeln/mehrfach, Kein-Junk, LLM-Ausfall-Fallback, Abzugs-Sperre), 8 neue FE-Tests (`ReviewQueueView.positionen.test.jsx`). Frontend-Vollsuite 459/459 grün. Backend: modulnahe Suiten grün (extraktion/validierung/entfernung/s18 + neu); Vollsuite-Fehlschläge (auth-/env-lastig: modul4-Routen, sv_portal, s19-Whitelist-Zeilendrift `email_import`) vorbestehend — Stash-Gegenprobe ohne diese Änderung liefert identische Fehlschläge.

**Live verifiziert:** echter Worker-Reparse Dok 517 (LLM aktiv) → 5 Positionen inkl. „Abrechnung nach Prüfbericht 5.448,62", Validierungswarnung weg, keine Degradation.

---

## 2026-08-07 — Referenzwerkstatt-Extraktion + Entfernungsprüfung ReviewQueue + Restbefunde a/c (auf Branch `abschlussbericht`)

Fortsetzung des Befunds Akte 1280/25 (3 Arbeitspakete laut Handover, Entscheidungen RA Schatz vom 2026-08-07: deterministischer Regex-Weg statt LLM-Fenster-Erweiterung; Entfernungsprüfung nur manuell per Button, da die Mandanten-Adresse an den externen Dienst OpenRouteService geht). Alle Pakete SDD-umgesetzt (TDD, Task-Reviews + Whole-Branch-Final-Reviews inkl. Fix-Wellen, alle Approved/Ready). 10 Commits `19e9467e..1aa59f79`.

**Paket 1 — Referenzwerkstatt-Extraktion VHV-Blockformat (`19e9467e`, `b9bb7dc8`, `284970b3`, `b3ae0680`):**
- `werkstatt_service.extrahiere_verweisbetrieb`: neue Stufe 1b für das VHV-Blockformat („Für die Korrekturberechnung haben wir den Reparaturbetrieb …"); Suchfenster endet bei „berücksichtigt." → es wird der VERWENDETE Betrieb gezogen, nicht die danach gelisteten Alternativbetriebe. Neuer `quelle`-Wert `vhv_block`.
- **Verhaltensänderung Bestand:** Stufe 3 (Trigger-Kontext) liefert nur noch Treffer mit PLZ-Zeile — der Floskel-Satz „Wird eine Referenzwerkstatt benannt, …" erzeugte vorher Scheintreffer. Betrifft auch den Alt-Endpoint `/distanz/prüfen-aus-dokument` (alte RegulierungSection): km-only-Treffer ohne Adresse melden jetzt „Kein Verweisbetrieb gefunden" statt „Adresse unvollständig" — gewollt, diese Treffer waren nie geocodierbar.
- Intake-Fallback in `extraktion.py` (Muster Prüfdienstleister-Fallback): füllt `felder.referenzwerkstatt` nur bei Klasse `pruefbericht` und nur wenn das LLM nichts liefert. Kanonische Keys `{name, adresse, plz_ort, telefon, km_genannt, quelle}`.
- Review-Fix `b3ae0680`: LLM-gelieferte `referenzwerkstatt`-Dicts werden per `setdefault` auf die kanonischen Keys normalisiert (`quelle: "llm"`), YAML-`beschreibung` in `pruefbericht.yaml` nennt die Keys explizit. **Deploy-Hinweis: YAML-Änderung → Backend-Restart in der Zielumgebung nötig.**
- Verifiziert am echten Dok 516 (Reparse): Möser Arno – Karosseriefachbetrieb, Philipp-Reis-Straße 9, 63128 Dietzenbach, 16,0 km, `quelle: vhv_block`.

**Paket 2 — Entfernungsprüfung in der ReviewQueue (`665a5bf4`, `c331545c`, `dd073e74`):**
- Neuer Endpoint `POST /intake/dokument/<id>/entfernung` (Body `{akte_az}`): Werkstatt aus `felder.referenzwerkstatt`, Mandanten-Adresse via `_mandant_adresse` (distanz_routes) aus dem übergebenen Akten-Kandidaten, `pruefe_entfernung` (ORS Geocoding+Routing). Bei Erfolg werden `{km_echt, minuten, abweichung_km, bewertung, textbaustein, geprueft_am, geprueft_gegen_akte}` ins Feld persistiert (bleibt in `intake_dokumente.parse_json`, via `freigaben`-Join zur Akte auflösbar — Datenbasis für den späteren Stellungnahme-Workflow). `textbaustein` nur bei `unzumutbar` (> 15 km), sonst wäre die Rüge inhaltlich falsch. Bei ORS-Fehler keine Persistierung.
- Frontend: Button „📍 Entfernung prüfen" im Review-Detail (nur Klasse `pruefbericht`; ohne gewählten Akten-Kandidaten deaktiviert mit Hinweis — Auswahl liefert die Mandanten-Adresse) + `EntfernungDialog`-Popup (genannte vs. echte km, Fahrzeit, Bewertung, Textbaustein mit Kopieren-Button). Fehler (404/422) erscheinen im Popup statt als Panel-Fehler.
- Review-Fix `dd073e74`: `FelderEditor` rendert Objekt-Werte (z. B. `referenzwerkstatt`) schreibgeschützt als JSON statt als editierbares `[object Object]`-Input — schützt die geprüften Werte vor versehentlichem Überschreiben. Plus Docstring-Präzisierungen.
- ORS-Smoke am echten Werkstatt-Standort ok (Offenbach→Dietzenbach: 16,9 km, 22 Min.). **Befund:** Akte 1280/25 hat lokal keine `beteiligte`-Zeilen → Button zeigt dort den (gewollten) Fehler „Mandanten-Adresse nicht gefunden". Laut Final-Review Regelfall bei frischen RA-MICRO-Akten → Backlog: RA-MICRO-read-only-Fallback in `_mandant_adresse` (Muster `_lade_beteiligte_aus_ramicro`, `word_service.py`).

**Paket 3 — Restbefunde a+c (`80120bb2`, `1aa59f79`):**
- (a) Marker-Matching in `klassifikator.py` von Substring auf Wortgrenzen umgestellt (`_marker_im_text`, Lookarounds `(?<!\w)…(?!\w)` statt `\b` wegen Sonderzeichen-Markern wie „Control€xpert"). „Rechnung" trifft nicht mehr „**Ab**rechnung". Golden-/E2E-Gates grün. Konvention: Bindestrich zählt als Wortgrenze („Reparaturkosten-Rechnung" trifft Marker „Rechnung" — gewollt, vgl. Marker „Reparatur-Rechnung"); Flexionsformen bei Bedarf als eigene YAML-Marker nachpflegen.
- (c) `llm_konflikt`-Vergleich normalisiert Datumswerte (nur DD.MM.YYYY ↔ YYYY-MM-DD, beidseitig) vor dem Vergleich — der Scheinkonflikt „2026-04-28" vs. „28.04.2026" entfällt, echte Datums-Konflikte bleiben.
- Verifiziert am echten Dok 517 (Reparse): `llm_konflikt` leer, Klasse korrekt `abrechnungsschreiben`.

**Tests:** 31 neue Backend-Tests (RED→GREEN, TDD) über `test_werkstatt_verweisbetrieb.py` (neu), `test_intake_entfernung.py` (neu), `test_intake_extraktion.py`, `test_intake_klassifikator.py`; 5 neue Frontend-Tests (`ReviewQueueView.entfernung.test.jsx`, neu). Frontend-Vollsuite 451/451 + Build grün. Vorbestehend unverändert: 2× `test_intake_routes` „Rechnung (Auffang)", `test_modul7`.

**Nachtrag (gleicher Tag, Freigabe RA Schatz):** RA-MICRO-read-only-Fallback für die Mandanten-Adresse (`1b74f938` + Fehlerpfad-Tests): `_mandant_adresse` (distanz_routes.py) fällt bei lokal fehlendem/adresslosem Mandanten auf `_lade_beteiligte_aus_ramicro` (word_service.py, nur SELECTs — read-only-Regel gewahrt) zurück; lokaler Treffer verhindert den RA-MICRO-Zugriff. Live verifiziert: 1280/25 löst jetzt die echte Mandanten-Adresse aus RA-MICRO auf. Bewusste Nebenwirkung: Auch der Alt-Endpoint `/distanz/prüfen-aus-dokument` profitiert; bei lokal fehlendem Mandanten kommt dessen 404 nun erst nach einem zusätzlichen RA-MICRO-Roundtrip (vorher sofort) — gewollt, konsistentes Verhalten.

**Offen (Human-Gates):** Browser-Abnahme des Entfernungs-Popups durch RA Schatz (jetzt direkt an 1280/25 möglich); Merge-Strategie unverändert (Branch stapelt, siehe TODO „In Arbeit").

---

## 2026-08-06 — Prüfbericht-Extraktion Akte 1280/25, Runde 2 (auf Branch `abschlussbericht`)

Anlass: RA Schatz meldete, das Prüfbericht-Parsing (Dok 516, VHV-Drei-Spalten-Format) sei trotz Schema-Erweiterung vom Vormittag weiter fehlerhaft. Befund: Die Altfelder des ControlExpert-Schemas passen nicht auf das VHV-Format — das LLM erfand `abzug_gesamt` (1.585,89 = selbst errechnete Differenz Gefordert−Fiktiv), belegte `reparaturkosten_brutto` mit dem Brutto NACH Prüfung und mischte Konkret-/Fiktiv-Spalte; `pruefdienstleister` (Pflichtfeld) und `auftraggeber` blieben leer bzw. wurden mit der Anspruchstellerin befüllt; die Schadennummer-Regex brach am Leerzeichen ab.

- **Schema-Feldbeschreibungen (neu):** Registry-`schema`-Werte dürfen jetzt statt reiner Typangabe ein Mapping `{typ, beschreibung}` sein (`registry_loader`-Validierung fail-loud, `llm_service` gibt die Beschreibung im Prompt als `- feld (typ): beschreibung` aus). `pruefbericht.yaml` nutzt das für alle Betragsfelder („niemals selbst errechnen", Spaltenzuordnung konkret/fiktiv, Brutto = VOR Prüfung) + `auftraggeber` (nicht der Anspruchsteller). Extraktor-Systemprompt generell verschärft: „Errechne keine Werte selbst".
- **2 neue Validierungsregeln** in `intake/validierung.py`: `netto_nach_abzug_konsistent` (vor − Abzug = nach) und `nach_pruefung_gleich_konkreter_erstattung` (Spaltenvermischung konkret/fiktiv wird als amber Warnung sichtbar); beide in `pruefbericht.yaml` registriert.
- **Prüfdienstleister-Fallback** in `intake/extraktion.py`: fehlt der LLM-Wert, wird der Dokumentkopf (erste 1.500 Zeichen) auf ControlExpert/DEKRA und ersatzweise `VERSICHERER_PATTERNS` geprüft. Nur der Kopf zählt — „Dekra-Zertifizierung" in der Werkstatt-Merkmalliste (Seite 3) erzeugte sonst ein falsches „DEKRA". Dok 516 bleibt korrekt leer (VHV nennt sich im Bericht selbst nicht).
- **Schadennummer-Regex mit Leerzeichen:** `abrechnungsschreiben.yaml` fängt jetzt „SD0 0003 2129 28 T01" komplett (Token-Muster `[^\S\n]`-getrennt, bricht an Zeilenende); `pruefbericht.yaml` bekam zusätzlich ein `Schaden-Nr.`-Muster für `vorgangsnummer`. Der `llm_konflikt` „SD0" bei Dok 517 ist damit weg.
- **Verifiziert am echten Dokument** (Container-Restart + Reparse): Dok 516 liefert jetzt konsistent 7.034,51 (gefordert) / 6.506,29 (nach Prüfung = konkret) / 5.448,62 (fiktiv), keine erfundenen Werte mehr; Dok 517 volle Schadennummer + Positionssummen-Warnung unverändert aktiv.
- **Tests:** 18 neue (RED→GREEN, TDD): `test_intake_validierung.py` (2 Regeln), `test_llm_service_s16b.py` (Beschreibungen im Prompt, Systemprompt), `test_intake_extraktion.py` (Fallback inkl. DEKRA-Fehltreffer), `test_registry_felder.py` (Regexe + Schema-Form), `test_registry_loader.py` (Schema-Mapping-Validierung). Betroffene Suiten grün (84 + 61 E2E); vorbestehend unverändert: 2× `test_intake_routes` „Rechnung (Auffang)".
- **Offen:** `referenzwerkstatt` bleibt leer (Werkstatt-Block liegt außerhalb des N-06-LLM-Seitenfensters) → TODO-Backlog (d); Marker-Wortgrenze (a) + Datums-Scheinkonflikt (c) weiter offen.

---

## 2026-08-06 — E-Mail-Import Endlos-Poll-Loop gefixt · Intake-Fixes Akte 1280/25 · Dubletten-Bereinigung (auf Branch `abschlussbericht`)

Anlass: RA Schatz meldete unbefriedigendes Parsing zweier VHV-Dokumente (Akte 1280/25) und 353 Dokumente voller Dubletten in Akte 543/26. Die Dubletten-Analyse deckte einen seit Ende Juni wiederkehrenden Endlos-Loop im E-Mail-Import auf.

**Endlos-Poll-Loop (`34342daa`):** Ursachenkette: RA-MICRO-Match auf lokal fehlende Akte → On-demand-Anlage tot (verweistes Modul `backend.ramicro.ramicro_liste`, ImportError still verschluckt) → `email_import_log`-INSERT verletzt FK auf `unfallakte(az)` → Mail weder geloggt noch als gelesen markiert → jeder Poll (1-Min-Takt) verarbeitete sie erneut. Zwei Wellen: 2026-06-28..07-14 (Alt-Pfad schrieb `dokumente`-Zeilen + Anhangs-Dateien) und ab 2026-08-04 (nach Scheduler-Reaktivierung; nur noch `.eml`-Kopien). Fix doppelt: `_stelle_sqlite_akte_sicher` nutzt `erstelle_oder_hole_akte` (+ Stammdaten best-effort aus RA-MICRO) und neuer FK-Guard in `_verarbeite_eine` degradiert lokal nicht anlegbare Akten zu `nicht_zugeordnet` statt Crash. 3 Tests `test_email_import_fk_guard.py` (RED→GREEN). Live verifiziert: die 5 festhängenden Mails wurden zugeordnet (Akten 431/22, 1043/25, 241/22, 732/26, 288/26 on-demand angelegt), Folgeläufe 0 Fehler.

**Intake-Fixes Akte 1280/25 (`8e9b50ea`):**
- `pruefbericht.yaml`: Schema um `erstattung_konkrete_reparatur_netto` + `erstattung_fiktive_abrechnung_netto` erweitert — die VHV-Drei-Spalten-Tabelle (gefordert/konkret/fiktiv) hatte kein Zielfeld, der regulierungsentscheidende Fiktiv-Wert (5.448,62 €) ging verloren. Reparse Dok 516 verifiziert. Achtung: Registry-YAMLs werden beim Backend-Start geladen; der Flask-Reloader reagiert nicht auf YAML-Änderungen → Container-Restart nötig.
- Neu `backend/intake/validierung.py`: die YAML-`validierungsregeln` (`summe_positionen_gleich_gesamt`, `abzug_gesamt_summe`) werden erstmals ausgeführt (waren reine Doku). Warnungen landen in `parse_json.validierung_warnungen`, Detail-Route reicht durch, ReviewQueue zeigt amber Hinweis. Reparse Dok 517 (VHV-Abrechnungsschreiben): Warnung nennt exakt die vom LLM ausgelassene Hauptposition (Differenz 5.448,62 €). 11 Tests `test_intake_validierung.py` (RED→GREEN).

**Dubletten-Bereinigung (Freigabe RA Schatz, „aufräumen"):** Backup `/app/data/unfallakten.db.bak_pre_dubletten_cleanup_20260806_155109` (SQLite `.backup`-API). `dokumente` 53.216 → 789 Zeilen — behalten: älteste Zeile je (akte_id, dateiname, dateigröße) plus alle aus 9 Referenz-Tabellen (`pruefberichte`, `forderung_positionen`, `abrechnungsschreiben`, `schadenposition_belege`, `freigaben`, `ereignisse`, `position_ereignis_cache`, `klassifikation_training`, `todos`) und `email_import_log.importierte_dok`-JSON referenzierten IDs. Danach Verwaisten-Sweep in `/app/uploads` (nur Top-Level-Dateien, Unterordner unangetastet; behalten wurde alles, was eine der 6 Pfad-Spalten referenziert). Ergebnis: 106.266 Dateien gelöscht, ~222 GB frei, VACUUM 50 → 4 MB. 543/26: 353 → 6 Dokumente.

**Tests/Regressionen:** Fokussierte Suiten grün (Intake-Pipeline/Extraktion/Routen/Review-E2E 72 passed, E-Mail-Import-Suiten 22+3, Registry 21). Frontend-Vollsuite 446/446. Vorbestehend (per stash-Gegenlauf verifiziert, nicht durch diese Arbeit): `test_modul7` importiert gelöschtes Modul `email_import.parser` (48 F), 2× `test_intake_routes` Bezeichnungs-Label „Rechnung (Auffang)".

**Offen:** Marker-Wortgrenze „Rechnung" trifft „**Ab**rechnung" (Auto-Klassifikation schlug abrechnungsschreiben→rechnung vor); Schadennummer-Regex bricht an Leerzeichen ab („SD0"); Datums-Scheinkonflikt im LLM/Regex-Konsens-Check (ISO vs. deutsch) → TODO Backlog.

---

## 2026-08-05 — Abschluss-/Sachstandsbericht (Branch `abschlussbericht`, basiert auf `intake-review-sichtbarkeit`)

Design-Spec `docs/superpowers/specs/2026-08-05-abschlussbericht-design.md` · Plan `docs/superpowers/plans/2026-08-05-abschlussbericht.md`. Neuer Dokumenttyp `abschlussbericht`: ein kuratiertes Schlussfeld (`abschluss_status.schluss_typ`) schaltet zwischen Abschluss- und Sachstandsbericht um — derselbe DB-freie Übersichts-Service liefert Positionen, Zahlungsverlauf, Empfänger-Split und Anwaltskosten-CTA sowohl an den DOCX-Renderer als auch an einen internen Vorschau-Endpoint. Die alte automatische Auto-Summary (`abschluss_summary.py`) entfällt ersatzlos zugunsten des kuratierten Wegs.

- `228ecc0b` Migration 67 — Tabelle `abschluss_status` (+ `test_migration_67.py`, 4 Tests).
- `bb1857bd` pos_map mit Zahlungsverlauf + RA-Gebühren-Filter (`services/abschluss_uebersicht.py`).
- `3a7f3b0d` Übersichts-Objekt: Positionen, Empfänger-Split, Summen, Modus.
- `df73fd80` Anwaltskosten, Bewertungs-CTA, Plausi-Kontrolle (`test_abschluss_uebersicht.py`, insgesamt 19 Tests).
- `73532e03` DOCX-Renderer `word/abschlussbericht.py` im Hausstil (+ `test_abschlussbericht_docx.py`).
- `cbc24d74` Fix: Verjährungs-Hinweis unabhängig vom Schlusstext rendern (Review-Fund, 4 DOCX-Tests).
- `7a5d5e60` Typ-Verdrahtung word_service + Datenlader (`abschluss_status`, `gebuehren_kontext`).
- `23ea6792` Fix: Streitwert-Fallback — toter `COALESCE(rep_rechnung_brutto, rep_gutachten_netto, 0)` durch >0-Vorrang ersetzt (Review-Fund; + `test_gebuehren_kontext_loader.py`, 2 Tests).
- `64aa203b` Routen `GET /akten/<az>/abschluss-uebersicht` + `PUT /akten/<az>/abschluss-status` (+ `test_abschluss_routes.py`).
- `cac4d939` Rückbau alte Auto-Summary (`abschluss_summary.py` gelöscht, Guard-Test; insgesamt 5 Route-Tests).
- `6a0a9ad7` Frontend: Kurationsdialog + WordSection-Kachel + API-Client (+ `AbschlussberichtDialog.test.jsx`, 3 Vitest; Vollsuite 446, Build grün).
- `4d343077` Fix: Amber-Rohwerte durch `theme.js`-Tokens ersetzt (Review-Fund).
- `b4d7f289` Fix: „für Sie kostenfrei"-Aussage nur noch bei Vollhaftung (Spec §15; Fund des Whole-Branch-Final-Reviews) — `getragen_von = "gegner"` nur wenn keine Abrechnung `haftungsquote < 100`; sonst neutraler „Kostentragung … gesondert"-Satz im Schreiben. +2 Tests. **Revidiert am 2026-08-06 (s. u.).**
- **2026-08-06 — Folgefund Gebührenassistent gefixt (Freigabe RA Schatz):** derselbe tote `COALESCE(rep_rechnung_brutto, rep_gutachten_netto, 0)` im Streitwert-Fallback existierte auch in `gebuehren_routes.py` (Anzeige) und `gebuehren_word.py` (Kostennote-DOCX, „Gegenstandswert") — bei fiktiver Abrechnung ohne Forderungsschreiben fehlte der Fahrzeugschaden. Beide Stellen auf `>0`-Vorrang-CASE umgestellt; 3 Regressionstests (`test_gebuehren_streitwert_fallback.py`, inkl. DOCX-Inhaltsprüfung, RED→GREEN).
- **2026-08-06 — Klarstellung RA Schatz (revidiert `b4d7f289`):** „kostenfrei" gilt auch bei Teilhaftung — die Kanzlei rechnet die Geschäftsgebühr aus dem **regulierten** Streitwert ab, der Versicherer trägt sie vollständig. `getragen_von` wieder immer `"gegner"`; RVG-Fallback-Betrag wird jetzt aus `summen.gezahlt` (reguliert) statt aus der Forderung berechnet, DOCX-Satz nennt die Basis („berechnet aus dem regulierten Betrag"). Spec §15 entsprechend präzisiert. Tests umgedreht + neuer Basis-Pin-Test (`test_rvg_basis_ist_regulierter_betrag`).
- **Endabnahme (2026-08-05):** voller fokussierter Testlauf im Container — `test_migration_67.py`(4) + `test_abschluss_uebersicht.py`(20) + `test_abschlussbericht_docx.py`(5) + `test_abschluss_routes.py`(5) + `test_word_gueltige_typen.py`(3) + `test_gebuehren_kontext_loader.py`(2) = **39/39 passed**. Frontend: 3 neue Vitest, Vollsuite **446/446** grün, Build grün. Whole-Branch-Final-Review: Ready to merge (nach `b4d7f289`), keine offenen Critical/Important.
- **Offen:** Browser-Abnahme RA Schatz (DOCX-Sichtprüfung beide Modi), Merge nach Klärung der Branch-Reihenfolge (stapelt auf `intake-review-sichtbarkeit`), Portal-Auslieferung als eigenes Stakeholder-Portal-Teilprojekt. Siehe TODO.md.
- **Folgefund (Review, außerhalb dieser Runde):** `gebuehren_routes.py` (Streitwert-Fallback) enthält denselben toten COALESCE-Bug wie der in `23ea6792` gefixte — bei fiktiver Abrechnung ohne Forderungsrunde zeigt der Gebührenassistent den Fahrzeugschaden-Anteil als 0. Separater Fix nötig (Bestandsfeature, Entscheidung RA Schatz aussteht).

---

## 2026-07-30 — Dashboard-Hell-Umbau (Branch `dashboard-hell`, basiert auf `aktenanlage`)

Design-Spec + Mockup `docs/superpowers/specs/2026-07-30-dashboard-hell-*` (von RA Schatz freigegeben, danach Umsetzung). Anlass: UI-Review des Dashboards (Nielsen-Score 14/40). P0-Befunde: komplett dunkler Viewport (~100 % statt Soll ~18 %) sowie stille API-Fehler, die eine grüne Entwarnung bei Fristen vortäuschten; automatischer Detektor fand 4× `borderLeft`-3px-Streifen als Farbcode-Krücke; 5 WCAG-Kontrast-Fails, schlimmster Wert 1,9:1. 8 Commits `5449beae..36e4581d`, Subagent-Driven Development.

- **Task 1** `5449beae` Design-Spec + Mockup (Freigabe RA Schatz).
- **Task 2** `49ce39e6` gemeinsame `boardUi`-Bausteine (`Kachel`/`KachelInhalt`/`Zeile`) als echte Buttons/Badges statt Divs mit Klick-Handler — Grundlage für die spätere Tastaturbedienung.
- **Task 3** `c909f3e8` `FristenKachel` auf Pergament-Tokens (`tokens.css`) umgestellt, dadurch ohne Zusatzaufwand auch im clio-Scheme lesbar; Positionierung links oben im 3:2-Raster.
- **Task 4** `09e493b8` `WiedervorlagenKachel`: gleiche Token-Umstellung, Liste ohne WV-Eintrag auf 5 gedeckelt + Sprung zur Vollansicht.
- **Task 5** `2d7f6d41` `TermineKachel` auf Pergament-Tokens umgestellt.
- **Task 6** `adaa7ed5` `JetztDranLeiste`: 3 dringendste Einträge aus Fristen + Wiedervorlagen, reine Client-seitige Ableitung ohne eigenen Endpoint.
- **Task 7** `8e62bd08` `ActionBoardView`+`App.jsx`: Posteingang-Kachel ersatzlos entfernt (E-Mail-Arbeit läuft über E-Mail-Import/Review-Queue), Lade-/Fehler-/Leer-Zustand je Kachel (Fehlerzustand: roter Hinweisblock mit „Erneut laden" ersetzt den Kachelinhalt; die zuletzt geladenen Daten bleiben im State erhalten und erscheinen nach erfolgreichem Neuladen sofort wieder), eine einzige Farbachse (Rot nur überfällig, Gelb heute), SB-Filter jetzt persistiert in `localStorage` (`dashboard.aktiveSB`) — leere Auswahl zeigt einen Hinweis statt der bisherigen Invertierungslogik.
- **Task 8** `36e4581d` Aufräumen: verwaistes `openEmail` entfernt.
- **Tests:** 28 neue Frontend-Tests (`boardUi` 5, `FristenKachel` 5, `WiedervorlagenKachel` 4, `TermineKachel` 3, `JetztDranLeiste` 5, `ActionBoardView` 6 — je vorher RED verifiziert), Vollsuite **434/434 grün**, Lint ohne neue Befunde.
- **Review:** jeder Task einzeln subagent-reviewed (Spec + Qualität) — alle Approved.
- **Offen:** Browser-Abnahme durch RA Schatz gegen das Mockup (siehe TODO.md). **Merge-Reihenfolge: erst `aktenanlage` → `main`, dann `dashboard-hell`.**
- **Fixwelle (Whole-Branch-Review):** SB-Filter lässt Einträge ohne oder mit unbekanntem SB-Kürzel jetzt immer durch (`ActionBoardView`), `badgeText`-Guard in `FristenKachel` korrigiert (positive Tage zeigen „+N T" statt fälschlich „−N T"), CHANGELOG-Korrektur zum Fehlerzustand. Vollsuite **435/435 grün**.
- **Playwright-Browsertest gegen die laufende Dev-App (2026-07-30): 20/20 bestanden.** Geprüft im echten Chromium: Pergament-Hintergrund + Bricolage-Titel, alle Kacheln inkl. Jetzt-dran, kein Posteingang, keine 3px-Streifen, Einträge als Buttons, SB-Persistenz über Reload, Fehlerblock bei abgebrochenem `/dashboard/fristen`-Request (kein falscher Leertext, Jetzt-dran ausgeblendet, Erholung per „Erneut laden"), Klick auf Eintrag öffnet Akte 97/25AS. Beobachtung (Bestand, nicht Teil des Umbaus): Die App verlangt nach jedem Browser-Reload einen erneuten Login (Benutzer nur im React-State).

---

## 2026-07-30 — Aktenanlage aus der ReviewQueue (PRD-NEW, Branch `aktenanlage`)

Design-Spec `docs/superpowers/specs/2026-07-30-aktenanlage-design.md` · Plan `docs/superpowers/plans/2026-07-30-aktenanlage.md`. Anlass: Kommt ein Gutachten per E-Mail herein und existieren Mandant/Unfall noch nicht im Bestand (Absender per Gutachter-Identifier bestätigt, keine Akten-Kandidaten), gab es bislang keinen Weg weiter — Freigabe blieb ohne `akte_az` gesperrt (422), die Akte musste manuell in RA-MICRO angelegt werden. 12 Tasks, Subagent-Driven Development, 20 Commits `b15c6669..ee486332` + Task 12 (diese Session).

- **Task 1** `b15c6669` Migration 66: Tabelle `aktenanlage_vorgaenge` (`status` CHECK `laeuft|akte_erkannt|abgeschlossen|abgebrochen`, `formular_json`, `xml_pfad`, `mandant_*`, `erkanntes_az`, `angelegt_am/von`, `erkannt_am`).
- **Task 2** `a8388b94`+`98c2eaa9`+`b96bf5af` OMA-XML-Generator `backend/ramicro/oma_xml.py` (`erzeuge_oma_xml`/`schreibe_oma_xml`) nach dem Muster `beispieloma.xml` — atomares Schreiben (Temp-Datei + `os.replace`), Mikrosekunden-genaue Dateinamen gegen Kollision, `short_empty_elements=False` für referenztreue Leerfeld-Serialisierung, Options-Labels `HERR`/`FRAU`/`FIRMA`, ISO-Datumsformat.
- **Task 3** `e8e0d1f1`+`31afa74b` RA-MICRO-Helfer (strikt read-only): `adress_service.hole_adresse_details`/`akten_zu_adresse`, neues Modul `akten_erkennung.finde_neue_akten` (Read-Only-Abfrage auf `tblAkten`↔`tblAktenBeteiligte`↔`tblAdressen`, Adressnummer hat Vorrang vor Nachname-Suche).
- **Task 4** `76173b0d`+`e688a4f7`+`20565355` Service `aktenanlage_service.py` + Blueprint `/aktenanlage` (`POST /aktenanlage`, `GET /aktenanlage/offen` inkl. lazy Erkennung im 30-s-Poll, `POST /aktenanlage/<id>/abbrechen`, `.../abschliessen`); 409-Guard gegen doppelten laufenden Vorgang pro Intake-Dokument (transaktional), Schattenakte wird beim leeren Einstieg **vor** dem Statuswechsel angelegt (Reihenfolge-Bugfix).
- **Task 5** `2e193685`+`1994158b` `GET /aktenanlage/adressen?q=` (Dubletten-Check) + Gutachter-Vorlage aus dem Identifier-Treffer; Adressnr als Int, 422-Präzisierung.
- **Task 6** `4659beaa` Freigabe-Hook in `post_freigabe`: schließt Aktenanlage-Vorgänge der E-Mail-Gruppe, übernimmt Unfalldatum/-ort aus `formular_json` in die Schattenakte, Response-Feld `aktenanlage`.
- **Task 7** `1d5e5b42` Review-Queue liefert `absender_kategorie` aus `zustellungen.signale_json` (Banner-Voraussetzung: Klasse `gutachten` + `absender_kategorie=gutachter` + keine Akten-Kandidaten).
- **Task 8** `2cc98de4` `gutachten.yaml`-Registry um Auftraggeber-Felder erweitert (Vorbefüllung des Dialogs aus dem Gutachten-Parse).
- **Task 9** `d94f8929`+`015cfb35` `apiAktenanlage` (Frontend-API-Client) + neue Komponente `AktenanlageDialog.jsx` mit debouncter Dubletten-Suche gegen `tblAdressen`; Stale-Response-Guard per Generationszähler (schnelles Tippen wirft keine veralteten Treffer mehr an).
- **Task 10** `6fe9bbbb`+`086ae420` ReviewQueue-Integration: Hinweis-Banner „Vermutlich neue Akte", Button „➕ Neue Akte anlegen" im Zuordnen-Abschnitt, Status-Chip (`⏳ läuft`/`✅ Akte … angelegt`), schmale Status-Leiste über der Queue-Liste; Null-Guard gegen Klicks auf durch den Poll bereits entfernte Einträge.
- **Task 11** `91a3a054`+`ee486332` Aktensuche nutzt denselben `AktenanlageDialog` (leerer Einstieg ohne Vorbefüllung); die bisherige inline `NeueAkteModal`-Komponente in `AktensucheView.jsx` entfällt, toter `apiAkten`-Import entfernt.
- **Task 12** (diese Session) Infrastruktur: `OMA_EXPORT_PFAD` (Container-Pfad `/app/oma_export`) in `docker-compose.yml`+`docker-compose.prod.yml` als Env+Volume ergänzt, Host-Pfad über `OMA_EXPORT_HOST_PFAD` (Default `./oma_export`) in `.env.example` dokumentiert.
- **Kern-Invarianten:** RA-MICRO bleibt strikt read-only (geschrieben wird nur die XML-Datei + SQLite); Review-Freigabe bleibt der einzige Schreibweg für Dokumente (INTAKE_REVIEW_PFLICHT unangetastet); kein eigener Navigationspunkt.
- **Endabnahme:** Backend voller Lauf (docker exec, force-recreate nach Compose-Änderung) **230 failed/1308 passed/15 skipped** — Failure-Set deckungsgleich mit dem seit Monaten bekannten lokalen Alt-Cluster (test_modul1-7/dashboard/sv_portal/prd27/migration_46, u. a. verursacht durch `_ensure_admin_exists`-Bootstrap-Kollision mit `/auth/register/erster` in den jeweiligen `setUp()`s, sowie — neu identifiziert — `test_modul6`-Konfigurationsdatei-Checks, die im Dev-Container strukturell nicht auflösbar sind, weil `docker-compose.yml`/`Dockerfile`/`nginx/`/`Makefile`/`.gitignore` dort nie gemountet werden; siehe DECISIONS/STATE bei Bedarf); **die 49 aktenanlage-spezifischen Tests (`test_aktenanlage_routes.py`, `test_oma_xml.py`, `test_ramicro_aktenanlage.py`) sind alle grün**, keine neue Datei im Failure-Set. Frontend **404/404** grün (61 Dateien, inkl. `AktenanlageDialog.test.jsx`, `ReviewQueueView.aktenanlage.test.jsx`).
- **Offen (RA Schatz, außerhalb dieser Session):** manueller Abnahmetest am echten System — die drei Verifikationspunkte aus Spec Abschnitt 9 (Adressnummer-Referenz „Bekannt=Ja", konkreter `OMA_EXPORT_HOST_PFAD`, Options-Labels/ISO-Datum + `dtAnlage`-Spalte beim ersten echten Import). Siehe TODO.md.
- **Final-Review-Fixwelle** (diese Session): Gruppen-Schließregel korrigiert (Vorgang schließt erst beim letzten offenen Geschwister-Dokument der E-Mail-Gruppe, Unfalldaten-Übernahme bleibt sofortig, Spec 5.4 angepasst); AZ-Übernahme aus dem Dubletten-Check wirkt jetzt tatsächlich im Zuordnen-Abschnitt der ReviewQueue; Offline-Hinweis für die RA-MICRO-Adresssuche im Dialog (`suche_adressen_status`, Response-Feld `verfuegbar`); Namens-Warnung beim leeren Einstieg (zweiter Klick legt trotzdem an); AZ-Feld bleibt nach Vorbelegung leerbar (Einmal-Vorbelegung per Ref); 409-Pfad in `lege_vorgang_an` löscht die XML jetzt fehlertolerant (`OSError` abgefangen, kein 500 auf Windows-Share-Sperren).

---

## 2026-07-28 — Review-Queue: Sortier-Toggle Eingangsdatum (Branch `review-queue-sortierung`, in `main`)

Design-Spec `docs/superpowers/specs/2026-07-24-review-queue-sortierung-design.md`, Plan `docs/superpowers/plans/2026-07-24-review-queue-sortierung.md`. Anlass: manuell importierte Dokumente waren in der Review-Queue (fest sortiert nach `erstellt_am ASC`) schwer wiederzufinden.

- **Task 1** `23d0f8bc` reiner Helfer `sortiereGruppen(gruppen, absteigend)` in `ReviewQueueView.jsx` (kehrt die von `gruppiereQueue()` gelieferten Gruppen-Blöcke um, keine Backend-Änderung), 3 Unit-Tests.
- **Task 2** `edb4f763` State/Toggle-Button „🕓 Älteste zuerst" ↔ „🕓 Neueste zuerst" im Queue-Header (nur in der Queue-Ansicht, nicht im Papierkorb), Persistenz über `localStorage` (`reviewQueueSortAbsteigend`).
- Subagent-Driven Development: 2 Tasks je Implementierung+Review (Spec ✅/Approved), Abschluss-Review „Ready to merge" — keine Critical/Important-Funde.
- **Browser-Nachtest (Playwright, gegen echte Dev-DB, 111 aktive Queue-Einträge, rein lesend)** 11/11 PASS. Wichtig: Umkehrung wirkt auf **Gruppen-Ebene** (E-Mail-Anhang-Blöcke bleiben zusammen, nur ihre Reihenfolge untereinander dreht sich um), nicht als flache Element-Umkehr — mit den 20 Mehrfach-Dokument-Gruppen der Live-Queue verifiziert.
- Fast-Forward-Merge nach `main` (`cc415175..edb4f763`), Branch gelöscht. `main` nicht gepusht.

---

## 2026-07-24 — Klage-Wizard Paket 4: Standardtexte pflegbar, V11 Stufe 1 (Branch `standardtexte-v11`)

Plan `docs/superpowers/plans/2026-07-24-klage-wizard-standardtexte-v11-stufe1.md` (Design-Spec: `docs/superpowers/specs/2026-07-19-klage-wizard-standardtexte-design.md`; Stufe 1 = 44 Bausteine Kategorie A+B; Kategorie C/vorflektierte Platzhalter bewusst als Stufe 2 vertagt, siehe TODO.md). Baut auf der `TextbausteinEditor`-Komponente der Kürzungstaxonomie Phase 1 auf.

- **Task 1** `497d9caf` Golden-Paritäts-Matrix (16 Szenarien, `test_klage_standardtexte_golden.py` + `backend/tests/golden/klage_standardtexte/*.txt`) als Regressionsschutz **vor** dem Registry-Umbau; Aktualisierung der Golden-Files über `KLAGE_GOLDEN_UPDATE=1`.
- **Task 2** `ff9aa8f3`+`2013df3b` Nebenbefund-Fix Beklagten-Grammatik: bei mehreren Beklagten heißt es jetzt einheitlich „Die Beklagten haben …" (`nom_gross`/`hat`) statt „Die Beklagte zu 2) hat …" — das „zu N)"-Suffix entfällt in genau diesen zwei Sätzen (Fall-B-/Regulierungssatz), BE (`klage_service.py`) und FE-Spiegel (`buildRwVorschau`) wortgleich nachgezogen.
- **Task 3** `adc811b1` YAML-Registry `backend/registry/klage_standardtexte.yaml` (44 Bausteine, 23 Platzhalter) + fail-loud Loader `backend/services/standardtext_registry.py` (App-Start bricht bei defektem YAML, wie bei der Kürzungstyp-Registry).
- **Task 4** `513aa47b` Migration 65: Tabelle `standardtext_override` + Model, kanzleiweit je Baustein überschreibbar (ein Override pro Baustein, gilt kanzleiweit — nicht je Akte).
- **Task 5** `29701bec` `klage_service.py`/`sg_text_builder.py` beziehen 36 Call-Sites aus der Registry statt aus eingebranntem Text — golden-paritätisch, **null YAML-Korrekturen nötig** (Matrix aus Task 1 blieb durchgehend grün).
- **Task 6** `59bc7751` REST `/klage-standardtexte` (5 Routen: Liste, Override, Reset, Vorschau, `/aufgeloest`), 422/409-Validierung für unbekannte Bausteine/Platzhalter.
- **Task 7** `a140d203`+`6e3cdfaf` Einstellungen-Tab „📄 Standardtexte" (`StandardtexteTab.jsx`, Wiederverwendung des `TextbausteinEditor`), Vite-Proxy ergänzt; Fehlerbehandlung Zurücksetzen + toter Import nachgezogen.
- **Task 8+9** `a21439b1`+`81f7284a` Klage-Wizard bezieht die 8 Stufe-1-Texte live über `/klage-standardtexte/aufgeloest` (Fetch aus `KlageWizard` in `KlageSection` geliftet, Seed-Race-Fix, sichtbarer Fehlerzustand statt stillem Fallback).
- **Wichtige Befunde:**
  1. Der Teilregulierungssatz ist im Backend strukturell unerreichbar (`klage_service.py`, KW-04-Altlast) — im Golden-Test (`teilregulierung.txt`) dokumentiert, kein neuer Bug, nicht in dieser Runde behoben.
  2. `sg_text_builder` wirkt auch im Forderungsschreiben mit — Overrides der Schmerzensgeld-Bausteine ändern **beide** Dokumente (bewusst, freigegeben: einheitliche Formulierungen).
- Endabnahme: Backend voller Lauf **204f/1277p/18s + 88 Subtests** (Alt-Cluster identisch verteilt: `test_modul3/4/7` 151, `test_modul2` 16, `test_modul5` 15, `test_dashboard_uebersicht` 9, `test_modul1` 6, `test_sv_portal` 4, `test_prd27`/`test_modul6`/`test_migration_46` je 1 — exakt wie Bestand, keine neue Datei im Failure-Set); Frontend **382/382** grün.
- **Browser-E2E per Playwright BESTANDEN (2026-07-24, 24/24 Checks):** Einstellungen-Tab komplett (Gruppen, Suche, Chip-Einfügung, Live-Vorschau mit Beispielwerten, Speichern-Sperre bei unbekanntem Platzhalter, Override + „geändert"-Badge, Reset), Wizard an Akte 285/26 (Schritt 9 Verzug-Text aus Registry, Gesamtvorschau Schritt 11 zeigt Override im Schlusssatz), Test-Override danach entfernt (System unverändert). Nach dem Merge-Checkout zusätzlich CRLF-Falle gefixt: `.gitattributes eol=lf` für die Golden-Fixtures (core.autocrlf hätte sie bei jedem frischen Checkout mit CRLF materialisiert und den Byte-Vergleich gebrochen). Sichtabnahme RA Schatz im Betrieb weiterhin sinnvoll, aber kein Blocker mehr.

---

## 2026-07-23 — Phase-1-Nachtrag: Genus-Platzhalter (Weg 2, Freigabe RA Schatz)

18 Genus-Platzhalter für die Mandantschaft (`<PRON>`, `<POSS_EM>`, `<ANREDE_DEKL>`, `<MANDANT_NOM>`, `<UNSERES>` …), gespeist aus RA-MICRO `sAnrede` (Erkennung wiederverwendet: `bestimme_geschlecht` aus `forderungsschreiben_wv._grammatik_vars` extrahiert, verhaltensgleich). Stellungnahme-Kontext löst sie akten-genau auf (ohne Anrede-Daten bewusst maskulin = Bestandsverhalten); Klage-Einwände lösen sie über den neuen wortgleichen FE-Helfer `platzhalterLogik.js` (`weiblich`-Flag des Wizards) auf, Unauflösbares wird sichtbarer `[FEHLT: <X>]`-Marker.
**Kernfund:** 5 Bausteine (1, 16, 21, 24, 32) enthielten noch **rohe RA-MICRO-Grammatikcodes** (`<@a2A> Mandant<@S2A>`, `<@PP1A>` …) — beim RTF-Import nie übersetzt, standen wörtlich in Briefen. `tools/genus_umstellung_bausteine.py` (Dry-Run/--write, JSON-Backup im Datenverzeichnis) hat 7 Bausteine umgestellt; danach 0 @-Codes. Dabei 3 Alt-Textfehler behoben (id 16 fehlendes Subjekt, id 24 fehlendes „ist", `$WZ`-Währungsmarker global entfernt). Die maskulinen Pronomen der übrigen Bausteine beziehen sich auf Gerichte/SV/BGH-Zitate — bewusst unangetastet. Offen sichtbar bleiben `<V-KRVON>/<V-KRBIS>` (id 32, Krankschreibung — Kontextwerte erst Phase 2). Tests: +12 Backend (`test_genus_platzhalter.py`), +11 Vitest (`platzhalterLogik.test.js`, `KlageWizard.einwaende-genus.test.jsx`), Vitest gesamt 362 grün.

---

## 2026-07-23 — Kürzungstaxonomie Phase 1 KOMPLETT (12 Tasks, Branch `kuerzungstaxonomie-phase1`)

Plan `docs/superpowers/plans/2026-07-23-kuerzungstaxonomie-phase1.md` (freigegeben inkl. der 3 Detail-Entscheidungen A05a–c/Varianten-Suffix/A09). Umsetzung über mehrere Sessions; eine Session brach mittendrin ab (Task 8 lag fertig, aber uncommittet vor — nach Prüfung ohne Verlust committet).

- **Task 1** `a8248f67` Migration 64: `kuerzungsarten.typ_code`+`verifiziert_am` (UNIQUE-Partial-Index) + 13 neue Seeds (→ 32), Stammtabelle `pruefdienstleister` (+FK-Spalten auf pruefberichte/abrechnungsschreiben), `ereignis_positionen.begruendung_roh`, `regulierung_positionen.typ_quelle`.
- **Task 2** `1257c157`+`0f97084a` YAML-Registry `backend/registry/kuerzungstypen/` (32 A–F-Typen) + fail-louder Loader (`kuerzungstyp_registry.py`, App-Start bricht bei defektem YAML).
- **Task 3** `3c2a6d74`+`99369b07` Baustein-Import 19→32 (ghpfansprort.doc→RTF konvertiert, Masken-Zeilen/&&-Artefakte gestrippt).
- **Task 4** `7c9d795f`+`6cf32afb` `textbaustein` REST-fähig, `GET /kuerzungsarten/platzhalter`, `POST /kuerzungsarten/vorschau`.
- **Task 5** `e35a2002`+`b11b2e68` Regel-Matching (`kuerzungstyp_matching.py`): Wortgrenzen, Briefkopf-Filter, Kontext-Pflicht-Keywords — Phase-0-Fehlerfälle als Fixtures.
- **Task 6** `114372af` LLM-Fallback (closed-label, nur wenn Regeln leer) + Positions-Synonymik je Versicherer-Template (`positions_synonyme.yaml`).
- **Task 7** `ba38f4f2` Verkettung Abrechnungsschreiben↔Prüfbericht (Auto-Kandidat ±90 Tage/Schadennummer, PATCH, `pruefdienstleister_id`-Befüllung, Frontend-Dropdown).
- **Task 8** `3e1a626b` Typ-Zuordnung im Regulierungs-UI: Vorschlag-Chips aus verkettetem Prüfbericht, **Pflicht-Begründung** (PATCH ohne Begründung → 400), `typ_quelle`, `begruendung_roh` bis ins Ereignis. Vitest `RegulierungSection.typvorschlag.test.jsx`.
- **Task 9** `90f74758` Runde-1↔Runde-2-Vergleich: `abrechnungsrunden_service.py` (reine Lese-Faltung, `ersetzt_durch`-Filter kollabiert ReguWizard-Ersetzungen), `GET …/abrechnungen/runden`, `RundenVergleichKachel` (grün=Nachzahlung, grau=aufrechterhalten, rot=neu/erhöht). 9 Tests.
- **Task 10** `03b2018c` `TextbausteinEditor.jsx` (Chips mit Cursor-Insert, 400-ms-Debounce-Vorschau, `pruefePlatzhalter` blockiert Speichern) + `KuerzungskatalogView` auf A–F-Gruppierung, typ_code-Badge, verifiziert_am. Nebenbefund behoben: CardHead-Prop `titel`→`title` an der Runden-Kachel.
- **Task 11** `cbe8a77f` Baustein-Fallback vereinheitlicht: Positions-JOIN liefert jetzt `ka.textbaustein` (Kette gespeichert→textbaustein→standard_gegenargument greift erstmals wirklich); `begruendung_roh` je Gruppe in Vorschau+DOCX; neuer Platzhalter `<ZITAT>` (Versicherer-Wortlaut); ReguWizard zeigt Zitat kursiv überm Textarea.
- **Task 12** Messanker `tools/kuerzungsmatching_report.py` (3 Zielwert-Kennzahlen, via docker exec), Doku nachgeführt (DATAMODEL Mig 64, ARCHITECTURE Taxonomie-Pfad, TODO). **Baseline 2026-07-23** (aktive DB, Schema 64, vor Betrieb): Abdeckung 17,4 % (4/23) · Trefferquote 0 % (0/4, alle 4 Alt-Zuordnungen manuell) · Betragszuordnung n/a (0 Ereignisse seit Stichtag) — naturgemäß niedrig, Messung ~2026-08-20.
- **Bekannte Alt-Failures** der lokalen Windows-Testumgebung (ModuleNotFound-Cluster) unverändert; alle taxonomie-relevanten Suites grün, Vitest komplett grün.
- **Offen zur Abnahme RA Schatz:** Browser-Kurztest Katalog-Editor (Task 10 Step 4) + Typ-Chips/Runden-Kachel im echten Betrieb; Messung der Zielwerte nach ~4 Wochen (TODO-Eintrag).

---

## 2026-07-23 — Kürzungstaxonomie: Konzept-Verifikation + Klage-Wizard-Fix „[FEHLT]-Marker"

Konzeptionelle Session (Kritik + Codebasis-Verifikation des Papiers `handover/KONZEPT-Kuerzungstaxonomie-Vorgangsautomat.md`), direkt in `main`.

- **Papier Abschnitt 12** neu: zwei 11.4-Befunde korrigiert (Textbausteine: 14/19 in aktiver Dev-DB befüllt, nicht 0/19 — Prüfung war gegen falsche DB; Fallback-Kritik gilt nur für Klage-Pfad), Migrations-Delta 56–63 als unkritisch verifiziert, RA-MICRO-Aktenkonto per Katalogabfrage negativ geprüft (keine Zahlungsdaten auf dem SQL Server), Differenz-Mathematik in `eingehende_ereignisse._regulierungs_wirkungen()` als bereits vorhanden identifiziert (stützt Option b aus 10.3.1).
- **3 DECISIONS-Einträge** (2026-07-23): Phase 1 vor V11 (Editor-Komponente entsteht in Phase 1) · Urteilscheck für Bestand entfällt (handverifiziert) · kommentarlose Zahlungen als Kaskade Betrags-Matching → Versicherer-Anfrage → protokollierte Not-Zuordnung.
- **Bugfix (TDD):** `EinwaendeAuswahl.uebernehmen()` erzeugte bei Kürzungsart ohne `textbaustein`/`standard_gegenargument` eine Überschrift ohne Argumentation. Jetzt sichtbarer `[FEHLT: Kein Textbaustein zur Kürzungsart „…" hinterlegt]`-Marker; neue Tests `KlageWizard.einwaende-fehlt.test.jsx` (3). Frontend-Suite **342/342** grün.
- TODO.md: PRD-39 als „durch PRD-27 abgedeckt" umgeschrieben; Kürzungstaxonomie Phase 0 (Handtest) als nächstes Vorhaben eingetragen; V11 wartet bewusst.
- **Browser-Nachtests RA Schatz (gleiche Session): Paket 2 (UI-Führung: Status-Symbole, Schließen-Dialog, Vertreter-Lookup) und Paket 3 (Gesamtvorschau-E2E inkl. DOCX-Kontrolle) BESTANDEN** — inkl. Sichtprüfung des neuen [FEHLT]-Markers. Klage-Wizard-Runde damit abgeschlossen bis auf V11 (wartet auf Phase 1).
- `main` erstmals seit Wochen gepusht (58 Commits, bis `80e2f044`).

---

## 2026-07-20 — Klage-Wizard Paket 2: UI-Führung

Branch `klage-wizard-ui-fuehrung`, 14 Commits `65f657bc..22ae53a3`, **noch NICHT in `main` gemergt**.
Spec `docs/superpowers/specs/2026-07-19-klage-wizard-ui-fuehrung-design.md` · Plan `docs/superpowers/plans/2026-07-19-klage-wizard-ui-fuehrung.md`. Subagent-Driven (9 Tasks + Fix-Welle + Test-Nachzug), Whole-Branch-Review (Opus): Ready to merge, keine Critical/Important.

- Status-Symbole (✓/⚠/●) im Fortschrittsbalken; Einwände als eigener Schritt (10→11 Schritte, Schnell-Durchlauf ohne Kürzungen möglich); Inline-Wort-Diff „Änderungen anzeigen".
- Neu: reine Logik `frontend/src/sections/wizardFuehrungLogik.js` (`wortDiff` LCS, `schrittStatus`/`schrittWarnung`/`firmenOhneVertreter`); Komponenten `DiffAnsicht`/`EditorMitDiff`/`StepEinwaende`/`EinwaendeAuswahl`.
- `ENTWURF_FORMAT_VERSION` 1→2 (Alt-Entwürfe → „Neu beginnen").
- Endabnahme: Frontend-Suite **314/314** (45 Dateien) + Build grün.

**Browser-Nachtest RA Schatz 2026-07-20 → 3 Punkte, auf demselben Branch behoben:**
(a) Schließen-Dialog als klare Messagebox „Verwerfen & schließen" / „Speichern & schließen" / „Zurück".
(b+c) Vertreter-Lookup direkt im Wizard (Knopf an Firmen ohne Vertreter in Schritt 2 + Schritt 11, öffnet das bestehende Modal über dem Wizard) statt „schließen → Lookup → neu öffnen" (`00e3f820`); stille Vertreter-Speicherfehler jetzt als Toast (`5e5b438b`).
**Root-Cause-Fund dabei:** `beteiligte.vertreter_name`/`vertreter_funktion` (Migration 23) fehlten auf der Dev-DB trotz `schema_version=61` → Dev-DB per ALTER nachgezogen (Backup `…bak_20260720_vertreter_drift`). Deploy-Konsequenz siehe STATE.md.

**Offen** (→ nächster Schritt in TODO.md): Für Akten **ohne** SQLite-Beteiligte (z. B. 828/24 — Versicherung als synthetischer § 115-VVG-Beklagter `id -1`) kann der Vertreter nicht per `UPDATE beteiligte WHERE id=?` persistiert werden → globaler Firmen-Vertreter-Speicher nötig.

---

## 2026-07-19 — Klage-Wizard Paket 1: Entwurf speichern

**Umgesetzt + in `main` gemergt.** Expliziter Speichern-Knopf, Schließen-Guard, Fortsetzen-Dialog, Positions-Abgleich mit Hinweis; Tabelle `klage_entwurf` (JSON + `format_version`, Migration 61), Endpoints `GET/PUT/DELETE /klage/entwurf`.
Subagent-Driven (9 Tasks) + Final-Review (READY): 2 Review-Fixes (`suche_gerichte`-Splice `4b9b4bc8`; frischer Wizard nicht „ungespeichert" `22654940`). FF-Merge `715126d2..22654940` (11 Commits, Branch gelöscht).
Endabnahme: Backend voller Lauf **204f/1098p/18s + 24 Subtests** (Alt-Cluster, null neue), neue Tests `test_migration_61.py` (4) + `test_klage_entwurf.py` (8) grün; Frontend **251** Vitest + Build grün.
Spec `docs/superpowers/specs/2026-07-19-klage-wizard-entwurf-speichern-design.md` · Plan `docs/superpowers/plans/2026-07-19-klage-wizard-entwurf-speichern.md`.

**Nachtest-Bugfixes (Akte 828/24 — vier ALT-Bugs seit April, nicht vom Entwurf-Feature; Branch `klage-beklagte-dubletten-fix`, 4 Commits, TDD):**
1. `fd9b7af3` Versicherung doppelt als Beklagte — synthetischer GHPV-Eintrag trotz echtem GHPV-Beteiligten (WDM-Kurzname „ADAC" ≠ „ADAC Autoversicherung AG"); jetzt `_ghpv_bereits_vorhanden` (Kürzel GHPV/GH/GHV zählt immer, sonst Namens-Containment).
2. `bf1c3a35` Wizard-Rubrum zeigte den Fahrer als Versicherung + pauschal „vertreten durch den Vorstand"; Parteien-Karte verlor Lookup-Button/Vertreter-Warnung → neues Modul `parteiLogik.js` für `StepRubrum` + Karte.
3. `d36c61a1` Vertreter-Lookup: HTML-Entities wurden gelöscht statt dekodiert (Umlaute weg), GF-Treffer bei AGs → `_extrahiere_vertreter` pure + Rechtsform-Widerspruchs-Filter.
4. `07cb5bbf` Lookup übernahm Organe fremder/Sammel-Impressen → `_seite_passt_zur_firma` + blockbezogene Extraktion. Live-Probe „ADAC Autoversicherung AG" → korrekt „Vorstand: Stefan Daehne".
5. `9384184c` Expliziter Lookup-Klick zeigte dauerhaft den still vorgefetchten Sitzungs-Cache → Klick sucht jetzt immer frisch, Cache nur für den stillen Vorab-Lookup.
Tests: 8 GHPV + 22 Parser + 12 parteiLogik/Rubrum-Vitest; 178 firmen+klage-Backend grün, Frontend 267 + Build grün.

---

## 2026-07-19 — PRD-33: Klage-Wizard Feintuning KOMPLETT (40 Bugs KW-01–KW-40, Sessions 1–6)

Ist-Analyse (2026-07-17): Multi-Agent-Code-Research → 40 Bugs KW-01–KW-40 + 11 Verbesserungen V1–V11, Tracking `docs/BUGFIX_KLAGE_WIZARD.md`. DOCX-Direkttest-Muster `test_klage_service_docx.py`. Grundsatzentscheidungen → DECISIONS.md.

- **Session 1** (2026-07-17, Branch `klage-wizard-fixes`, in main `578c93e0`): KW-23 Platzhalter-Guard Step 10 (`a6711c2d`) vor KW-01; KW-01 Merge-Lücke (`antraege_override`/`mit_feststellung_sg`/`mit_feststellung_sach` erreichen `klage_cfg`, `e668f50f`+`f239a1fe`); KW-02 RVG-Faktor nicht ins Euro-Override-Feld (`b1c1fbfb`); KW-14 `klage_generiert`-Ereignis trägt Positionen (`d42f09eb`). Backend 204f/965p, Frontend 97/97.
- **Session 2** (2026-07-17, Branch `klage-wizard-fixes-s2`): KW-03 Quote-Fälle A/B (BE+FE), KW-04 eine Rechenquelle + DOCX-Direkttest, KW-05 Eigentum/§1006, KW-07 SG-Ausschluss, KW-11 Unkostenpauschale, KW-39 vorgezogen. Backend 204f/1000p null neue, Frontend 122 + Build.
- **Session 3** (2026-07-18, Branch `klage-wizard-fixes-s3`, in main `d856a8d4`): KW-06 + KW-15–21 als V3-Partei-Grammatik-Cluster (BE-Helfer `_anrede_norm`/`_ist_maennliche_privatperson`/`_beklagten_grammatik`/`_beklagten_rolle`/`_vertreter_suffix`/`_rechtsform_klasse` + FE `kanonischeBeklagte`/`beklagtenGrammatik`/`versichererSuffix`). Backend 204f/1044p, Frontend 141 + Build.
- **Session 4** (2026-07-18, Branch `klage-wizard-fixes-s4`, 9 Commits `36ca8ec6..2076e83e`, in main `ec53900b`): KW-09/10/12/13/08 + KW-35. **V5** Datumsvertrag (`_fmt_datum`/FE-Port `fmtDatumDe`), **KW-10** Verzugseintritt ≠ Schreibdatum (cfg `verzug_schreiben_datum`; Eintritt-Default Schreibdatum+14 Tage), **KW-08** Legacy-Generieren-Button entfernt, **KW-35** RVG-Fallback `_rvg_anlagedatum`, **V6/KW-13** „RVG gerichtlich"-Duplikat entfernt, **V4/KW-12** `AnlagenZaehler` (fortlaufende K-Nummern). Backend 204f/1056p, Frontend 159 + Build.
- **Session 5** (2026-07-18, Branch `klage-wizard-fixes-s5`, 8 Commits `6752215e..e3c1ab68`, in main `c003e962`): KW-22/24–29 als **V7**. Manuell-Flags (`wizardSachverhaltManuell`/`wizardGebuehrenManuell`/`wizardAntraegeManuell`), `antraegeBasis`-Fingerprint + `AntraegeSync` + `TextVeraltetBadge`, `komponiereAntraege` statt Einbrennen, `kannSpringen` kumulativ, Gericht-Persistenz, Verzugsdok-Datum aus `forderung_positionen`, stiller Vertreter-Lookup. Plan `docs/superpowers/plans/2026-07-18-prd33-s5-wizard-state-ux.md`. Backend 204f/1059p, Frontend 198 + Build.
- **Session 6** (2026-07-19, Branch `klage-wizard-fixes-s6`, 15 Commits `c003e962..81706b67`, in main `68ba3e49`): KW-30–34/36–38/40 + **V10**. Bedingte Segmente `unfall_seg`/`ereignis_seg`, zeilenweiser Sachverhalt-Parser, laufender Abschnittszähler `_abschnitt_kopf` (nummerierter Verzug), RVG-0-Suppression + Fall-B-Klemmsatz, `_round2_half_up` (FE half-up vs. BE banker's angeglichen), zentrale Registry `frontend/src/config/klagePositionKeys.js` + Contract-Tests, 10 tote Symbole raus, `<w:tab/>`-Runs, GHPV/Label-Fixes. **V10 Golden-File-Matrix** (`TestV10RenderSmoke` + `TestV10Matrix` 24 Kombinationen) als Regressionsschutz. Backend 204f/1086p + 24 Subtests, Frontend 223 + Build.

**PRD-33 KOMPLETT:** alle 40 KW-Bugs behoben oder mit Begründung als entfallen dokumentiert. FF-Merges nach Freigabe RA Schatz 2026-07-19.

---

## 2026-07-16 — Rausch-Absender automatisch aussortieren + Papierkorb

Aus Topic „Filterregeln für die Review-Queue", im Brainstorming zugespitzt: wertloses Rauschen auf `info@` gar nicht erst in die Queue lassen.
Spec `docs/superpowers/specs/2026-07-16-rausch-absender-auto-aussortieren-design.md` · Plan `…/plans/2026-07-16-rausch-absender-auto-aussortieren.md`. 7 Commits `f0ca50ac..49f53f1e` (Subagent-Driven, TDD, Opus-Whole-Branch-Review + Fix-Wave + Re-Review), per FF in `main` (`49f53f1e`).

- YAML-Registry `backend/registry/rausch_absender.yaml` (fail-loud, eager beim App-Start) mappt Absender-Domain→Policy; reine Funktion `backend/intake/rausch_regel.py::policy_fuer_domain`. Placetel→`nur_body` (Fax-PDF bleibt), beA→`komplett`.
- `adapter_imap.verarbeite_email` ruft `backend/intake/verwerfen.py::auto_verwerfen` (Soft-Delete, `verworfen_von=NULL`, `grund='rauschen'`); `_VERWERFBARE_STATUS` enthält `laeuft` (Worker-Race-Fix).
- Papierkorb: `GET /intake/papierkorb` + `POST …/wiederherstellen`, Queue⇄Papierkorb-Toggle in `ReviewQueueView`. Keine Migration.
- Backend 204f/961p, Frontend 91 + Build. **DEV-Smoke ✅** (verify-Skill, rückstandsfrei).

---

## 2026-07-16 — Bugfix: AZ-Normalisierung + Personenschaden-Schema-Drift

Commit `991095e1` auf `main`. systematic-debugging + TDD. Fund: Unfallbogen freigegeben, Reiter Unfalldetails leer.
- (a) `AktenLiveSuche` nahm die RA-MICRO-Anzeigeform mit SB-Kürzel (`670/26AS`) als Speicherschlüssel → Phantom-Akte. Fix: `t.az_roh`; `post_freigabe` normalisiert `akte_az` via `_basis_az`. Daten `670/26AS`→`670/26` repariert.
- (b) `personenschaden.krankenhaus_aufenthalt` fehlte in Bestands-DBs (Schema-Drift) → stiller Datenverlust via Best-Effort-Swallow. **Migration 60** (additiv/idempotent). Deploy-Konsequenz siehe STATE.md.

---

## 2026-07-15 — PRD-37: Dokumentenbezeichnung vorschlagen + Feld

Regelbasiert vorgeschlagene, editierbare Dokumentenbezeichnung im Review + in der E-Akte.
Spec `docs/superpowers/specs/2026-07-15-dokumentenbezeichnung-design.md` · Plan `…/plans/2026-07-15-dokumentenbezeichnung.md`. 13 Commits `12b31f14..b19decb8` (Subagent-Driven, TDD, Opus-Final-Review READY), per FF in `main` (`b19decb8`).
- Reine Funktion `backend/services/dokument_bezeichnung.py::baue_bezeichnung` → `«Label» «Aussteller» vom «Datum» («Betrag»)`; Sonderfall `sonstiges` = „Schreiben"/„E-Mail".
- Je Klassen-YAML `label` + `bezeichnung_felder`; `hole_detail` liefert `bezeichnung`+`bezeichnung_vorschlag`; `PATCH /intake/dokument/<id>/bezeichnung`; Freigabe schreibt nach `dokumente.bezeichnung`; E-Akte nachträglich editierbar.
- **Migration 59** (additiv/nullable/idempotent). Deploy-Konsequenz siehe STATE.md. Frontend 88 + Build, Backend zero neue Failures.

---

## 2026-07-15 — PDF-Splitting im Review-UI (Option C)

Mehrseitige Sammel-PDFs im Review-Dialog entlang Seitengrenzen auftrennen, bevor freigegeben wird.
Spec `docs/superpowers/specs/2026-07-15-pdf-splitting-review-design.md` · Plan `…/plans/2026-07-15-pdf-splitting-review.md`. 7 Commits `f7b5191b..e3492e9d` (Subagent-Driven, TDD), in `main` `c093ad70`/gepusht.
- **Ansatz A:** Teile = neue Intake-Dokumente (`queue_status='neu'` → Worker klassifiziert), Original soft-deleted + verlinkt via `aufgeteilt_aus_id`; Zustellungs-Signale vererbt.
- **Migration 58** (`intake_dokumente.aufgeteilt_aus_id`), `backend/intake/split_service.py` (PyMuPDF), Endpoints `/split`+`/seiten`+`/thumbnail`+Guard, Frontend `splitLogik.js`+`SplitDialog.jsx`.
- Abschluss-Review (Opus) READY TO MERGE. **DEV-E2E-Smoke ✅** (Reloader-Trap Mig 58 auf DEV gefunden+gefixt).

---

## 2026-07-15 — Prod-Rollout intake-stufe1 (Git-Teil)

`intake-stufe1` → `main` per Fast-Forward gemergt (`a06aaae5`, 201 Commits) + beide Branches nach origin gepusht; Backup-Tag `pre-rollout-main-20260715` (alter main `e8313486`, lokal+remote); Home-Repo-Guardrail angelegt.
**Prod-Deployment bewusst vertagt** (Nutzer 2026-07-15) — Details/Runbook siehe STATE.md.

---

## 2026-07-14 — Fragebogen-Feld-Übernahme bei Freigabe (Folge aus BUG-01)

Branch `intake-stufe1`, Commits `362a0895..367f44de` (10 Commits). Subagent-Driven (7 Tasks, TDD), Abschluss-Review Opus READY WITH FOLLOW-UPS.
Spec `docs/superpowers/specs/2026-07-14-fragebogen-feld-uebernahme-design.md` · Plan `…/plans/2026-07-14-fragebogen-feld-uebernahme.md`.
- Freigabe-Dialog zeigt geparste Felder als editierbare Vorschau; nur leere Aktenfelder werden übernommen, abweichende überschreibbar. Abschnitts-Checkboxen + Auto-Collapse.
- Service `backend/services/fragebogen_uebernahme.py` (eigene Transaktion je Abschnitt); `GET /intake/dokument/<id>/fragebogen-vorschau`, Übernahme in `post_freigabe` (Best-Effort). Frontend `FragebogenUebernahme`.
- Voraussetzung mitgefixt: Text-Dokument-Freigabe (ohne Arbeitskopie) via `_sichere_text_arbeitskopie`. Keine Migration.
- Guards `test_s19_intake_write_guard.py` + `test_s19d_e2e_no_intake_writes.py` bleiben grün; `uebernehme` in die Guard-Whitelist verboten aufgenommen (nur `post_freigabe` erlaubt, Commit `29285840`).
- **Smoke-Test in DEV ✅** (13 Felder geschrieben, rückstandsfrei). Nebenbefund: Reloader-Migrations-Trap `llm_degradiert` fehlte → per ALTER nachgezogen.

---

## 2026-07-14 — Pipeline-Qualität N-03 + N-04

- **N-03 Retry-Differenzierung + Degradations-Hinweis** (Commits `7142b73b..ad7fcfe9`, Subagent-Driven, Whole-Branch-Review READY). Spec/Plan `…2026-07-14-n03-retry-differenzierung*`. `klassifiziere_fehler(meldung)` → timeout (Backoff) / ressourcendruck (+900s, kein Zähler) / reproduzierbar (sofort `pipeline_fehler`). `extrahiere_felder` liefert `llm_status`; **Migration 57** `intake_dokumente.llm_degradiert`; Frontend `DegradationBadge` „nur Regex". „Arbeitskopie fehlt" ist jetzt reproduzierbar → kein Retry. Backend 204f/846p, Frontend 60.
- **N-04 Seiten-Triage vor OCR** (Commits `e806c281..e8d3fca1`, Subagent-Driven, READY nach 1 Fix). Spec/Plan `…2026-07-14-n04-seiten-triage*`. Triage über **Textabdeckung** (Flächenanteil Wort-Boxen) statt Wortzahl → robust gegen Fotoseiten. `_ocr_seite` Tesseract-zuerst → `text_abdeckung`/`ist_bildseite` → GLM nur auf Textseiten. Migrationsfrei (`SeitenText.ist_bildseite`, `parse_json.bildseiten_anzahl`). Frontend `BildseitenBadge`. Backend 204f/857p, Frontend 62. **SDD-Lehre:** nach Signaturänderung volle Suite, nicht nur Golden-Subset (Critical `TestBug12OcrLinear` gebrochen → Fix `e8d3fca1`).

---

## 2026-07-13 — Bugfix-Reihe BUG-01–30 (Intake-Pipeline v7) + N-01/N-02/N-06 + N-09/N-10 + Druckbutton

Code-Review 2026-07-12 fand 30 Bugs (Multi-Agent, `docs/BUGFIX_INTAKE_V7.md`). Alle behoben (TDD), Branch `intake-stufe1`, nicht gepusht.
- **P0 (BUG-01–04)** `6c858aa1` — stiller Datenverlust unter `INTAKE_REVIEW_PFLICHT` geschlossen (Fragebogen→Queue, Anhang-Fehler, Upload-Ziel-Akte, Alt-Mail-Fallback).
- **P1 (BUG-05–07)** `b6826d91` — Betrags-Korrektheit (`_feld_zu_zahl` nutzt `parse_betrag`, kein 100×-Fehler), Freigabe-Guards (409), `_anker_dokument_id` filtert per `akte_az`.
- **P2 (BUG-08–13)** `7b95be7a` — RA-MICRO-only-Akte on-demand in SQLite, Fristablauf-Job ohne Write-Lock, Scheduler-Loopback-Lease (`scheduler_lease.py`), Upload-Validierung 422, OCR pro Seite via `first_page`/`last_page`, Migration 50 ohne executescript.
- **P3 (BUG-14–19)** `88271a6a` — Signal-Vererbung an Anhänge, E-Akte-Key `az`, KFZ-Umlaut-Muster, Kurz-Body-Schwelle weg, Queue-Sortierung.
- **P4 (BUG-20–30)** `8bac957f`/`1f469367`/`f175fe2c`/`b9254e09`/`b822cfa8` — `hole_queue` per `json_extract`+JOIN, AZ-Norm-Helper, IMAP-Config-Dedup, Poll-Abbruch bei Unmount u. a. Frontend 48 grün.
- **N-01 + N-06** `c5a46c13` — N-01 Wörterbuch-Check → OCR-Fallback bei korruptem Font-Encoding (`_WOERTERBUCH`/`woerterbuch_quote`); N-06 Seitenauswahl (Seite 1 + letzte + Regex- + Tabellen-Seiten) via `llm_text`-Param, Regex bleibt auf Volltext.
- **N-02** `34b50e63` (Mig `94c18ea1`) — OCR-Qualitätsmetriken (**Migration 56** `ocr_ratio_salat`+`ocr_quote_woerter`), `dokument_ocr_qualitaet` (Schlechteste-Seite auf Finaltext), Frontend `OcrBadge`.
- **N-09 + N-10 + Druckbutton** — N-09 `busy_timeout=30000`-PRAGMA (verify+harden, `timeout=30` setzte es ohnehin); N-10 Backup repariert (`scripts/backup.sh`, SQLite `.backup` statt `cp`, stündlich) — **Fund:** `.backup` läuft NICHT von `:ro`-Mount (WAL braucht `-shm`-Schreibzugriff) → `/data` auf read-write; Guard `TestBackupInfra`. Druckbutton `druckZiel(detail, pdfSrc)`, Frontend 52.

---

## 2026-07-12 — P1.5e: Review-Freigabe schreibt Ereignisse für alle Klassen

Branch `intake-stufe1`, Commits `6863f918..a0c50f6a`. Spec/Plan `…2026-07-11-p15e-freigabe-ereignisse*`. Subagent-Driven (5 Tasks, TDD). Grundsatzentscheidungen → DECISIONS.md.
- Registry `backend/registry/klasse_ereignistyp.yaml` (7 Klassen → eingehender Ereignistyp) + fail-loud Loader-Feld.
- Helper `eingehende_ereignisse.erzeuge_aus_freigabe()` — Positionen nur bei `gutachten_eingegangen`/`rechnung_eingegangen`, sonst Fakt-Ereignis; `herkunft='freigabe'`, Best-Effort, Doppelerfassungs-Guard.
- `post_freigabe` schleift über bestätigte `kandidaten_ereignisse`; Gutachten-Sonderfall entfernt; `_anker_dokument_id` liefert stabile dokument_id. Serverseitiger `eingehend`-Guard (Defence-in-depth).
- Frontend: `default_ereignistyp` belegt das Dropdown vor. Keine Migration. Backend 204f/732p, Frontend 41.
- **Follow-up** `74400131`: Polling-Tick überschrieb offene Dialog-Eingaben → `naechsterFormState(detail, {skipFormReset})`. Frontend 44.

---

## 2026-07-10 — P1.7 (UI Positionsmodell) + Text-Pfad + N-08/N-07

- **P1.7** (UI-Umsetzung Positionsmodell): `AbleitungBadge.jsx` (Wissensgrenze „nach Aktenlage, letztes Ereignis vom …", technisch erzwungen); Backend `has_unbestaetigt` + Registry-Metadaten; `PositionsDashboard` in `UebersichtSection.jsx` (Datenquelle ausschließlich `GET /akten/<az>/positionen/status`, Toggle getrennt/aggregiert, WDM-Kennzeichnung); Ereignisliste-Endpoint; `DokumentAktionsmenue.jsx` (Kebab je PDF-Zeile). Vitest-Setup (vitest+jsdom+testing-library) eingeführt. 36 Tests. (DetailPanel-State-Reset via `key={aktivId}`, `d4c9cda`.)
- **Text-Pfad für Intake-Pipeline** (6 Commits `e73ab003..e2b5815a`). Spec/Plan `…2026-07-10-text-pfad-intake*`. Text-Zweig in `verarbeite_dokument` (`_synth_seite`, `payload_typ='text'`, `textquelle='email_text'`); `hole_detail` liefert `payload_typ`+`eltern_email`; Frontend `TextVorschau`+`EmailKontextBox`+`gruppiereQueue`. **Migration 54** (`textquelle`-CHECK erlaubt `email_text`). Backfill 51 Text-Dokumente (`scripts/backfill_textpfad.py`).
- **N-08** Baseline „Sekunden pro Freigabe": **Migration 55** (`review_geoeffnet_am`), `sekunden_bis_freigabe` als `korrektur_log`-Zeile.
- **N-07** Bestandsakten-Hinweis (Ersatz für zurückgestelltes P1.8): `positionsstatus_service.berechne_historie_hinweis()` + `EREIGNISMODELL_EINGEFUEHRT_AM` (env, Default `2026-07-09` — beim Prod-Cutover setzen). Frontend-Hinweisbox in `PositionsDashboard.jsx`.

---

## 2026-07-09 — Intake-Refactoring: S1.9 + Positionsmodell P1.1–P1.6

**Großprojekt Pipeline v7 + Positionsmodell.** Maßgebliche Dokumente: `freigabe.md`, `PIPELINE-REFACTORING-PLAN.md`, `POSITIONSMODELL-PLAN.md` (Projekt-Root). Arbeitsbranch `intake-stufe1`.

- **S1.9a–d** — `INTAKE_REVIEW_PFLICHT` (Default True) macht die Review-Freigabe zum einzigen Schreibweg in Akten-Tabellen (Grundsatz → DECISIONS.md). **Migration 49** (`email_import_log.ausgeblendet`). Alt-Pfade (Anhang-Auto-Registrierung, Upload-Route, E-Akte-Import, `_ergaenze_*`) hinter dem Flag stillgelegt; Guard-Test `test_s19_intake_write_guard.py` als Rollback-Anker + `test_s19d_e2e_no_intake_writes.py`.
- **P1.1** — Registries `positionsarten.yaml`/`ereignistypen.yaml`/`aktionen.yaml` + fail-loud Loader `positionsmodell_registry.py` mit Konsistenzchecks.
- **P1.2** — **Migration 51** `ereignisse` / `ereignis_positionen` / `position_ereignis_cache` (K-M1 UNIQUE). `ereignis_service.schreibe_ereignis()` einziger Schreibpunkt; `rebuild_cache()`; AST-Guard-Test blockiert Fremd-Writes.
- **P1.3** — `positionsstatus_service.leite_positionsstatus_ab()` (liest nur `position_ereignis_cache.status='aktuell'`); Blueprint `positionen_routes.py` (`/positionen/status`, `/aktionen`).
- **P1.4** — `ausgehende_ereignisse.erzeuge()` an 5 Generierungs-Stellen (word_service, gebuehren_word, klage_routes, sta_routes, stellungnahme_routes).
- **P1.5a–d** — vier Bestätigungswege (`eingehende_ereignisse.py`): ReguWizard→`abrechnung_eingegangen`, Beleg→`rechnung_eingegangen`, Gutachten→`gutachten_eingegangen` (K-M2a positionsscharfe Ersetzung), WDM→`abrechnung_eingegangen` (unbestätigt, `herkunft='wdm'`). Registry `rechnungstyp_mapping.yaml`.
- **P1.6** — System-Ereignisse via APScheduler. **Migration 52** (`todos.fristablauf_ereignis_id`). `fristablauf_service.verarbeite_faellige_todos()`, cron-Job täglich 03:15, Endpoint `/system/fristablauf/manual`.

**P1.8 (Backfill) ZURÜCKGESTELLT** (Entscheidung RA Schatz 2026-07-13, forward-only) → siehe DECISIONS.md. Prompt archiviert: `handover/naechste_session_P1_8_prompt.md`.

---

## 2026-07-08 — Bugfixing-Session (Testsuite-Sanierung)

Branch `intake-stufe1`. Baseline 294f/385p/26e → **211f/524p/0e/18s** (−83 failures, −26 errors).
- `a6fb6f4` Test-Stub-Kontamination in `test_prd23b.py` entfernt (Modul-Ebenen-`sys.modules`-Stub kontaminierte Reihenfolge); Guard `test_prd23b_kontamination.py`.
- `12d78c5` `TestKlassifiziereEakteDok` an Listen-Signatur angepasst; SV-Domain-Tests korrigiert.
- `9ffcbe6` `conftest.py` setzt `FLASK_SECRET_KEY` vor Collection.
- `746f731` `test_modul6.py` `TestBackupScript` entfernt, Gitignore-Erwartungen aktualisiert.
- `70c77c4` **Migration 50** legt `unfalldetails`-Tabelle nachträglich an (Root-Cause: `CREATE TABLE unfalldetails` fehlte im Schema-Manager → Mig 28 SKIPPED → `POST /klage/generieren` crashte 500). Handover `handover/2026-07-08-datenmodell-bugs-unfalldetails-cleanup.md`.
- `d5916d3` `cleanup_abrechnungen.py` DB_PATH-Default gefixt.
- `6572abf` `test_portal_sync.py` Fixture um `gutachten_nr`.
- `e7bdad9` Auth-Bootstrap in `conftest.py` (`JWT_SECRET_KEY`+`ADMIN_*`).
- `9fcdcb5` nginx.conf Config-Bugs + self-signed Zertifikat lokal.

**Offen (Alt-Cluster, kein Blocker):** Testsuite-Modernisierung `test_modul3/4/7` (~150 Failures, kein 1-Zeilen-Fix, eigenes Ticket); `test_prd23b.py`/`test_modul8.py` Alt-Failures; kleinere `test_migration_46`/`test_sv_portal`/`test_modul1`.

---

## Ältere abgeschlossene PRDs (Kurz-Index)

Detail in den jeweiligen Session-Handovers (`handover/`, `session_handover_v38–v56.md`) und der Git-Historie.

| PRD / Feature | Beschreibung |
|---|---|
| PRD-01 (Basis) | To-Do-System + Header-Widget |
| PRD-02 | Textbaustein-Feld Kürzungsarten |
| PRD-03 K-01–K-15 | Klageschrift-Formatierung |
| PRD-04 / 04b | Dokumentenklassen + Dispatcher + Registry; Feedback-Loop |
| PRD-14 | SSOT Abrechnungsart |
| PRD-15 | WDM Auto-Load |
| PRD-16 | Tab-Reihenfolge als Workflow-Ablauf |
| PRD-18 | Phasen-Strip (UebersichtSection) |
| PRD-20 | App.jsx Refactoring (26 Dateien) |
| PRD-21 Ph. 1–3a | E-Akte Auto-Import |
| PRD-22a/b/c/d | Gutachten-Reiter; Regulierung+Löschen; Mandanten-Fragebogen; E-Mail-Import-UI |
| PRD-23a/b | Schadenposition-Belege; Rechnungs-Parser (59 Tests) |
| PRD-24 | Aktivlegitimation + Klage-Wizard A–D |
| PRD-25a/b | Automatische Fristen; Action-Dashboard |
| PRD-26 | Klage-Wizard 10-Step (Umbau) |
| PRD-27 | ReguWizard – Stellungnahme-Wizard |
| PRD-28 | Gebührenassistent Nr. 2300 VV RVG + Kostennote DOCX |
| PRD-29b | E-Akte E-Brief-Filter via Schlagwort |
| PRD-30 | OCR + SSE-Streaming (pytesseract, pdf2image) |
| PRD-31 (KI) | KI-Parsing Gutachten (Shadow-Mode, Konflikt-Dialog) |
| PRD-32 Ph. 1 | Rechnungstypen-Subklassen im Classifier |
| PRD-34 | Inbox-Pattern Dokumente-Kachel |
| PRD-35 | Klage-Wizard Bug-Fixes (5 Bugs) |
| PRD-36 (a–d) | Code-Konsolidierung (`_helpers.py`, `utils/datum.py`, `models/beteiligte.py`) |
| PRD-US01/02/05/06 | RA-Micro Heartbeat; IMAP Auto-Polling (Schema-43); E-Akte Hover-Vorschau; Health-Dashboard |
| PRD-US19 | RA-Micro DMS Integration (read-only) |
| B-08 / B-09 | Netto/Brutto bei Vorsteuer; Gegenstandswert |
| Regulierungs-Workflow Option B | 5 Phasen, Legacy deprecated, Delete-Bug v14c |
| KI-Parsing Regulierungsschreiben | Qwen Shadow-Mode, Modell-Switcher, Few-Shot |
| Action Board Global + OnboardingHub | ActionBoardView, OnboardingHub (7 Kacheln) |
| E-Mail-Workflow Redesign | EmailDetailView, UA-Ordner, Migration 42/44 |
