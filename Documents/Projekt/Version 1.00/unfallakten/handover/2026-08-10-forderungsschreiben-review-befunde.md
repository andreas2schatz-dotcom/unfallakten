# Code-Review: Modul „Forderungsschreiben" (2026-08-10)

Review-Agent nach etabliertem Muster (requesting-code-review), read-only.
Branch `abschlussbericht` (HEAD `4f76ca27`), Diff-Basis `40c9143e` (merge-base main).
Scope: `models/forderung.py`, `routers/forderung_routes.py`, `word/forderungsschreiben.py`,
`word/forderungsschreiben_wv.py`, Forderungs-Anteile `word/word_service.py` (inkl. Branch-Diff),
`registry/klassen/forderungsschreiben.yaml`, FE `WordSection.jsx` + `ForderungshistorieKarte.jsx`, Tests.

**Assessment: riskant** — DOCX-Erzeugung handwerklich ordentlich; riskant ist die
Forderungshistorie als Datenprodukt (C-1) plus fehlende Tests genau dort (I-11).
C-1 + I-1 vor dem Branch-Merge adressieren.

---

## Stärken

- RA-MICRO strikt read-only: alle drei Zugriffe (`word_service.py:584-767`, `:770-886`, `:889-969`) reine SELECTs.
- SQL durchgängig parametrisiert; f-String-Stellen (`forderung.py:193-196, 342-345, 361-366`) injectionsicher (nur Platzhalter-Anzahl/interne Spaltennamen).
- Best-Effort-Architektur `generiere_und_speichere` (`word_service.py:190-238`): Historie/Fristen/Ereignis brechen die Dokumentgenerierung nie.
- Branch-Diff `name_aus_ramicro_adresse` (`word_service.py:574-581`) setzt den sNachname-Befund sauber um, beide Einbaustellen (`:685`, `:848-849`).
- Geteilte Bausteine statt Kopien: `_berechne_abrechnungsart` (SSOT), `sg_text_builder.baue_sg_abschnitt`, `_netto_oder_brutto`/`_baue_tabelle` (auch von Klage-Tests geprüft).
- Unkostenpauschale None-vs-0 (`forderungsschreiben_wv.py:795-801` + `word_service.py:351-353`) dokumentiert + getestet.
- Fail-loud-Platzhalter `KEINE ADRESSE ERFASST` (`forderungsschreiben_wv.py:300-305`).
- Doppelte Status-Validierung Route (422) + Model (ValueError).

---

## Befunde

### Critical

**C-1 · Forderungshistorie erfasst andere Beträge als das Schreiben fordert**
`word_service.py:193-203` vs. `models/forderung.py:32-52, 143-168` vs. `forderungsschreiben_wv.py:748-835` (`_baue_tabelle`).
`erfasse_forderung()` dupliziert die Tabellenlogik des Generators und driftet in 5 Punkten:
1. **Stale Key `rep_fiktiv_netto`** (`forderung.py:34`) — Spalte per Migration in `rep_gutachten_netto` umbenannt (`db/schema_manager.py:2220-2227`); `s_dict()` liefert nur noch den neuen Key. Folge: bei **fiktiver Abrechnung (Standardfall)** fehlen die Reparaturkosten komplett in der Historie. **[Key-Verifikation bestätigt: `rep_fiktiv_netto` existiert nur noch an dieser einen Stelle im Live-Code.]**
2. **Doppelerfassung**: `POSITION_LABELS` enthält `rep_rechnung_netto` UND `rep_rechnung_brutto` UND `reparaturkosten` UND `wiederbeschaffung` — mehrere gefüllt → mehrere Zeilen; das Schreiben zeigt genau eine Fahrzeugschaden-Variante.
3. **Restwert positiv summiert** (`forderung.py:149`), aber `forderungs_zusammenfassung` (`:284`), `/schreiben`-Route (`forderung_routes.py:120`), FE-Klagepotential (`ForderungshistorieKarte.jsx:72-74`) und Streitwert-Fallback (`word_service.py:540-543`) **addieren** ihn → Totalschaden-Summen um 2×Restwert zu hoch.
4. **Unkostenpauschale**: Schreiben fordert 30 €-Default, Historie überspringt sie (None → 0 → Filter).
5. **Nebenkosten brutto/netto**: Schreiben rechnet je Vorsteuer-Status um, Historie nimmt stur Legacy-Brutto.
Warum relevant: Historie füttert Klagepotential, Klage-Flags und (branch-neu) den Gebühren-Streitwert des Abschlussberichts — RVG-relevante Zahlen weichen systematisch vom versendeten Brief ab.
Fix-Skizze: `_baue_tabelle` liefert bereits `(positionen, gesamt)` — genau diese gerenderten Positionen an `erfasse_forderung` übergeben. Minimal-Hotfix: Key korrigieren + Fahrzeugschaden-Variante exklusiv nach `berechne_abrechnungsart` wählen.

### Important

**I-1 · Branch-Regression: Registry-Typen ohne Generator → KeyError-500**
`word_service.py:59-68` (`gueltige_dok_typen`, neu) liefert `mahnschreiben`/`klagedrohung`; `generator_map` (`:137-144`) kennt sie nicht → `KeyError` außerhalb des try; `vorschau` (`word_routes.py:106-114`) fängt nur `WordFehler` → ungefilterter 500er. Fix: `generator_map.get()` + `WordFehler(422)` oder Typen mit `generator_map.keys()` schneiden.

**I-2 · `adressat_id` wird verworfen — Adressat-Dropdown wirkungslos**
`word_service.py:85-92` nimmt Parameter an, `:128` reicht ihn nicht an `_lade_akte_daten` weiter → GHPV-Fallback greift immer (`:303-309`). FE zusätzlich: `WordSection.jsx:42` initialisiert `adressatId` nur einmal (asynchron nachgeladene Beteiligte → Anzeige ≠ gesendeter Wert). Fix: Parameter durchreichen; FE per `useEffect` nachziehen.

**I-3 · Ungeschütztes `float(varSCHMGELD)` crasht Generierung**
`forderungsschreiben_wv.py:692-699`: erste `sg_mind`-Zuweisung (`:693-694`) läuft VOR dem try/except; geschütztes Duplikat darunter wirkungslos. WDM-Wert wie „ca. 2.500 EUR" → 500 fürs ganze Schreiben. Fix: Zeilen 693-694 streichen.

**I-4 · „Der Kläger" im vorgerichtlichen Schreiben**
`forderungsschreiben_wv.py:701`: `gram.get("kl_nom")` existiert nie (gram hat nur `@…`-Keys) → Fallback „Der Kläger" greift immer im Schmerzensgeld-Block (`sg_text_builder.py:69-110`). Juristisch falsch (kein Kläger vorgerichtlich) + falsches Genus bei Mandantinnen. Fix: Nominativ aus `@P1A`/`@S1A` ableiten, `verb_hat` bei Plural „haben".

**I-5 · Variante „grunde" existiert nur auf dem Papier**
`forderungsschreiben_wv.py:253-254` ignoriert `variante`; `word_service.py:102-104, 456-463` verspricht RTF-Vorlage „dem Grunde nach" (Vorlagen liegen ungenutzt). Bei leerem Schaden entsteht das „Höhe"-Dokument mit 30 €-Default — inhaltlich falsch; Historie entfällt trotzdem. Fix: grunde-Vorlage wirklich rendern ODER Variante entfernen + `WordFehler(422)` bei leerem Schaden.

**I-6 · Toter Vorsteuer-Override `varSSTF`**
`word_service.py:421-430`: `wdm_kontroll = {}` direkt vor dem `.get("varSSTF")` — echtes WDM-Laden erst Zeile 465. Override liest garantiert leeres Dict → brutto/netto-Entscheidung ignoriert WDM-Flag. Fix: Block hinter Zeile 465 verschieben.

**I-7 · PATCH ohne Akte-Scoping — Positionen fremder Akten änderbar**
`forderung_routes.py:131-187` prüft nur Existenz der URL-Akte; `aktualisiere_position` (`forderung.py:343-347`) updated `WHERE id = ?` ohne `akte_id` (`setze_klage_flag:364-366` macht es korrekt). Fix: `AND akte_id = ?` + Signatur erweitern.

**I-8 · Aggregate zählen über mehrere Schreiben doppelt**
`forderung.py:284-295` + `word_service.py:540-543` (branch-neu, `SUM(betrag_gefordert)` als „Streitwert"): jedes neue Schreiben legt neue Zeilen für offene Positionen an → `gesamt_gefordert`/`offen`/`klagepotential`/Gebühren-Streitwert verdoppeln sich ab Schreiben Nr. 2. Zusatz: Kanzlei-Regel = Geschäftsgebühr aus dem REGULIERTEN Streitwert — Fallback „gefordert" auch konzeptionell prüfen. Fix: Aggregation aufs letzte Schreiben je `position_key` (MAX(forderungsschreiben_nr)) beschränken.

**I-9 · Frontend-Race in `ForderungshistorieKarte`**
`ForderungshistorieKarte.jsx:13-19`: Fetch ohne Ignore-Guard (langsame Antwort Akte A überschreibt Akte B), `laden` wird bei `akteId`-Wechsel nicht zurückgesetzt, `catch(() => {})` verschluckt Fehler. Fix: Cleanup-Flag, `setLaden(true)` am Effektanfang, Fehlerzustand rendern.

**I-10 · Haftungsquote: drei widersprüchliche Interpretationen**
Produktiv-Generator nutzt HQ gar nicht + behauptet immer Alleinschuld (`forderungsschreiben_wv.py:380-385`); FE-Banner quotiert (`WordSection.jsx:86`, HQ=0 → 0 €); Alt-Generator `forderungsschreiben.py:60` liest HQ=0 als 100 % (`or 100`). Bei erfasster Teilhaftung geht Alleinschuld-Text mit ungekürzter Forderung raus. Fix: Textbaustein bei HQ<100 umschalten (oder Warnhinweis); HQ-Semantik BE↔FE vereinheitlichen (inkl. HQ=0-Konvention).

**I-11 · Tests decken den toten Alt-Generator ab, Produktiv-Variante kaum, Modell gar nicht**
`test_modul5.py:252-320` testet nur `forderungsschreiben.py` (toter Code — produktiv läuft `_wv`, einziger Import `word_service.py:33-35`). `models/forderung.py` und `forderung_routes.py`: null Tests; FE-Komponenten: keine Testdatei. Gut: `_baue_tabelle`-Teilaspekte + `bestimme_geschlecht` (echtes Verhalten). Fix: Tests auf `_wv` umziehen; Unit-Tests `erfasse_forderung` gegen In-Memory-DB (fiktiv/konkret/Totalschaden, Zweitschreiben-Dedup) — würden C-1 sofort rot machen.

### Minor

- `forderung.py:96-104, 175` · `naechste_schreiben_nr` in eigener Connection → Race bei parallelen Generierungen. Fix: MAX+1 in derselben Transaktion.
- `forderung_routes.py:149-155, 178` · `kuerzungsart_id` ohne Typ-/Existenzprüfung; `kuerzung_begruendung` nie auf None zurücksetzbar.
- `forderung_routes.py:184-185` · Leerer PATCH-Body → 404 statt 422.
- `word_routes.py:54, 76` · Rückgabewert von `_pruefe_akte` verworfen (dokumentierte Projekt-Falle!); `int(adressat_id)` ohne try → 500 statt 422.
- `word_routes.py:106-114` · `vorschau` fängt nur `WordFehler` → sonst Flask-500 (siehe I-1).
- `WordSection.jsx:61` · „Sofort-Download" nach `generieren` lädt via `vorschau` ein NEU generiertes Dokument — ggf. ≠ E-Akte-Datei.
- `forderungsschreiben_wv.py:30-31` · `_KANZLEI_IBAN`/`_KANZLEI_BIC` ungenutzt, Fantasie-IBAN-Default — toter Code mit Risiko bei versehentlicher Nutzung.
- `forderungsschreiben_wv.py:438-478` · `_merge_split_placeholders` schreibt alle `<w:t>` eines Absatzes in den ersten Run → Misch-Formatierungen/Nachbartexte gehen verloren; fragil bei Vorlagen-Änderungen.
- `forderungsschreiben_wv.py:727, 735, 776` · MwSt 19 % dreifach hartkodiert → Konstante.
- `forderung_routes.py:91-97` · `/zusammenfassung` vom FE nicht konsumiert; FE-Klagepotential (`fuer_klage`-Flag) ≠ BE-`klagepotential` (Status-basiert) unter demselben Begriff.

---

## Verbesserungsvorschläge (Vermerk, kein Fix-Zwang)

1. **Alt-Generator entsorgen:** `word/forderungsschreiben.py` (282 Zeilen) produktiv tot, nur von `test_modul5.py` referenziert — löschen, Tests auf `_wv` portieren (I-11).
2. **Tote Vorlagen aufräumen:** Von 10 `forderungsschreiben_*`-Vorlagen wird genau EINE geladen (`forderungsschreiben_vorlage.docx`, `_wv.py:28`); `_hoehe_*`, `_backup`, `_bak3/4`, `_hooehe_neu`, `_neu_`, `_grunde_`/`_grund_.rtf` sind Ballast (Backups gehören in Git).
3. **Kanonische Positions-Erzeugung:** `_baue_tabelle` aufspalten in „Positionsliste berechnen" (pure, testbar: Key+Label+Betrag) und „XML rendern"; Positionsliste für DOCX + `erfasse_forderung` + perspektivisch P1.4-Ereignis nutzen — erledigt C-1 strukturell.
4. **Status-Semantik:** Bei manuellem `vollreguliert` `betrag_reguliert` automatisch auf `betrag_gefordert` ziehen (oder warnen) — sonst „vollregulierte" Positionen mit Differenz ≠ 0 still aus der Klagepotential-Rechnung.
5. **Frontend-Tests nachziehen:** `ForderungshistorieKarte` (Toggle/Status/optimistisches Update) als dankbarer Erstkandidat.
