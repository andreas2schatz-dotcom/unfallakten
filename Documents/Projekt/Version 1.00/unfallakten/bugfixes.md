# Bugfixes Forderungsschreiben-Modul

Quelle: Code-Review 2026-08-10, Vollbericht → `handover/2026-08-10-forderungsschreiben-review-befunde.md`.
Branch: `abschlussbericht`. Vorgehen: TDD (Test zuerst, rot sehen, dann fixen).

## Reihenfolge & Status

### Phase 0 — Aufräumarbeiten (Verbesserungsvorschläge)
- [ ] **V-1** Toter Alt-Generator `backend/word/forderungsschreiben.py` löschen; Tests aus `test_modul5.py` auf Produktiv-Variante `_wv` portieren (deckt zugleich Teil von I-11)
- [ ] **V-2** Tote Vorlagen aufräumen: nur `forderungsschreiben_vorlage.docx` wird geladen; 9 Alt-/Backup-Vorlagen entfernen (`_hoehe_*`, `_backup`, `_bak3/4`, `_hooehe_neu`, `_neu_`, `_grunde_*.docx`, `_grund_*.rtf`)
- [ ] **V-1b** Toten Code `_KANZLEI_IBAN`/`_KANZLEI_BIC` (`forderungsschreiben_wv.py:30-31`) entfernen (Minor, Fantasie-IBAN-Risiko)

### Phase 1 — Quick-Wins / Abstürze (klein, hoher Nutzen)
- [ ] **I-3** Ungeschütztes `float(varSCHMGELD)` crasht Generierung (`forderungsschreiben_wv.py:692-699`)
- [ ] **I-1** Branch-Regression: Registry-Typen `mahnschreiben`/`klagedrohung` ohne Generator → KeyError-500 (`word_service.py:59-68` vs. `:137-144`)
- [ ] **I-6** Toter Vorsteuer-Override `varSSTF` — Block liest leeres Dict (`word_service.py:421-430` vor Laden `:465`)
- [ ] **I-7** PATCH ohne Akte-Scoping — Positionen fremder Akten änderbar (`forderung.py:343-347`)

### Phase 2 — Kernbefund Historie/Beträge
- [ ] **C-1** Forderungshistorie ≠ Brief: staler Key `rep_fiktiv_netto`, Doppelerfassung Fahrzeugschaden-Varianten, Restwert-Vorzeichen, Unkostenpauschale-Default, Nebenkosten brutto/netto. Fix strukturell via V-3: `_baue_tabelle` liefert Positionsliste → dieselbe Liste in `erfasse_forderung`
- [ ] **I-8** Aggregate zählen über mehrere Schreiben doppelt (`forderungs_zusammenfassung`, Gebühren-Streitwert-Fallback) → Aggregation aufs letzte Schreiben je `position_key`
- [ ] **I-11** Testlücke Modell/Routen schließen (Unit-Tests `erfasse_forderung`: fiktiv/konkret/Totalschaden, Zweitschreiben) — entsteht großteils durch TDD von C-1/I-8

### Phase 3 — Juristische Textfehler
- [ ] **I-4** „Der Kläger" im vorgerichtlichen Schreiben (`gram.get("kl_nom")` existiert nie) → „Unser(e) Mandant(in)" aus Genus-Vars ableiten
- [ ] **I-5** Variante „grunde" existiert nur auf dem Papier → Variante entfernen, bei leerem Schaden `WordFehler` 422 „keine Schadenpositionen erfasst"

### Phase 4 — Frontend
- [ ] **I-2** `adressat_id` wird im Backend verworfen (Dropdown wirkungslos) + FE-Init-Race `WordSection.jsx:42`
- [ ] **I-9** Fetch-Race + verschluckte Fehler in `ForderungshistorieKarte.jsx:13-19`

### Zurückgestellt — Entscheidung RA Schatz nötig
- [ ] **I-10** Haftungsquote: Produktiv-Generator behauptet immer Alleinschuld, FE-Banner quotiert, HQ=0-Semantik uneinheitlich. Der korrekte Textbaustein bei Teilhaftung ist eine juristische Formulierungsentscheidung → Vorschlag vorlegen, nicht eigenmächtig texten.

### Minors (opportunistisch, bei Anfassen der Datei)
- `naechste_schreiben_nr`-Race (eigene Connection) · `kuerzungsart_id` ohne Validierung · leerer PATCH → 404 statt 422 · `_pruefe_akte`-Rückgabewert verworfen in `word_routes.py:54,76` + `int(adressat_id)` ohne try · `vorschau` fängt nur `WordFehler` · Sofort-Download regeneriert statt E-Akte-Datei · `_merge_split_placeholders` verliert Misch-Formatierung · MwSt 19 % dreifach hartkodiert · `/zusammenfassung` FE-ungenutzt + zwei „Klagepotential"-Definitionen

### Vermerke ohne Fix-Zwang (aus Review)
- **V-3** Positionsliste berechnen / XML rendern trennen (wird mit C-1 miterledigt)
- **V-4** Status `vollreguliert` → `betrag_reguliert` automatisch nachziehen (oder warnen)
- **V-5** Frontend-Tests `ForderungshistorieKarte` nachziehen

## Protokoll
(wird je Fix ergänzt: Commit, Tests, Besonderheiten)
