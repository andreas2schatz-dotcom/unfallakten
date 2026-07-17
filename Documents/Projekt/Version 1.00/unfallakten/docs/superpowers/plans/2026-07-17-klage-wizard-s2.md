# Plan: PRD-33 Session 2 — Konsistente Beträge & Tatsachenbehauptungen im DOCX

> Branch: `klage-wizard-fixes-s2` (von `main` @ 578c93e0). Tracking: `docs/BUGFIX_KLAGE_WIZARD.md`.
> Scope: KW-11, KW-04, KW-07, KW-05, KW-03 (Reihenfolge = Abhängigkeitsreihenfolge).
> Ist-Erhebung 2026-07-17 (nach S1) — alle Zeilennummern aktuell.

## Globale Constraints (verbatim bindend)

1. **TDD strikt**: erst fehlschlagender Test, dann Fix. Kein Refactoring über den Fix hinaus. Stellt sich ein Fund als falsch heraus → nicht fixen, sondern als `entfällt` mit Begründung melden.
2. **RA-MICRO ist read-only** — niemals in die RA-MICRO SQL Server DB schreiben, nur SQLite.
3. **Baseline**: Backend-Failures nur in bekannten Alt-Clustern (204f-Baseline, `test_modul2/3/4/7` etc.), **null neue Failures**. Frontend 97 Tests + Build grün. Keine Migration erwartet.
4. **Keine Kommentare** im Code außer bei nicht-offensichtlichem Verhalten. Zielsprache der UI/Texte: Deutsch (Nutzer ist Rechtsanwalt).
5. **Grundsatzentscheidungen (RA Schatz, 2026-07-17) — nicht neu diskutieren, exakt umsetzen:**
   - **KW-03 Fall A — gegnerische Quote** (HPV hat nur nach ihrer Quote reguliert): Schadentabelle UND Klagebetrag bleiben **100 %**; die gegnerische Quote wird nur in der rechtlichen Würdigung erwähnt (und bestritten). Der Satz „Die Klageforderung wurde entsprechend gekürzt" ist hier falsch und fliegt raus.
   - **KW-03 Fall B — eigene Quote** (wir akzeptieren selbst eine Mithaftung): Schadentabelle bleibt auf 100 %, aber der Klagebetrag wird quotiert. **Rechenweg: erst quotieren, dann Zahlungen abziehen** (Anspruch = Gesamtschaden × Quote; davon reguliert abziehen → Klagebetrag). **Schmerzensgeld wird NICHT automatisch quotiert.** **Die eigene Quote gilt auch für den vorgerichtlichen Streitwert** (Basis der Geschäftsgebühr Nr. 2300 = quotierter Betrag).
   - **KW-03 UI:** Step 7 braucht eine Auswahl, wessen Quote gemeint ist: „gegnerisch angenommen (nur Darstellung)" vs. „von uns akzeptiert (kürzt Forderung + Gebührenbasis)". Beide Fälle bekommen eigene RW-Textbausteine.
   - **Schadentabelle immer 100 %** (auch bei Fall B).
6. **Eine Rechenquelle (KW-04)**: Antrag 1, Schadentabelle und Differenz-Satz speisen sich aus den **checked cfg-Positionen** (`betrag` = genettet für Antrag 1, `betragOriginal` = 100 % für die Tabelle). Der Differenz-Satz muss arithmetisch exakt beim Antrag-1-Betrag enden.
7. Seit S1 kommt `antraege_override` real im Backend an: Frontend-`baueAntraegeText()` und Backend-Rechenwege müssen bei jeder Betragsänderung konsistent mitziehen (KW-03 Fall B!). Stale-Text-Gesamtproblem (KW-22) bleibt Session 5 — hier nur keine NEUEN Widersprüche einführen.
8. Neue Prozentanzeigen: runden/formatieren (Komma-Dezimal), keine `int()`-Truncation neu einführen (KW-36 bleibt Session 6, aber neu geschriebener Code macht es gleich richtig).

## Architektur-Fakten (Ist-Stand, für alle Tasks)

- `backend/word/klage_service.py::generiere_klageschrift(akte_daten)` (:864). `cfg = akte_daten["klage_config"]`; `details = akte_daten["unfalldetails"]`.
  - `positionen`/`klagebetrag`: :956–959 (Σ `betrag` der checked cfg-Positionen; Frontend sendet zusätzlich `betragOriginal` — wird bisher nie gelesen).
  - Gegenstandswert: :1026 (`klagebetrag + sg_mind if mit_sg`).
  - Eigentümer-Satz: :1287–1296; AktLeg-Block via `get_aktivlegitimation_text` :412–489 (`details["aktivlegitimation_typ"]`, Default `eigentum`), `_build_aktivlegitimation_xml` :1297; `sachverhalt_override` :1261–1266 ersetzt beides.
  - hq: :1004 (`details/akte`, nie cfg), nur Text :1394 + :1409–1411 („entsprechend gekürzt"). RW-Block wird bei `rw_text_override` komplett übersprungen (:1377–1387).
  - Schadentabelle: :1324–1374. `schaden_raw` = `akte_daten["schaden"]` (DB) + `setdefault` aus cfg-Positionen via `_pos_key_map` (:1334); Tabelle + `schaden_gesamt` aus `forderungsschreiben_wv._baue_tabelle` (:1340). Differenz-Satz :1369–1373 = `schaden_gesamt − gesamt_reguliert_tbl` (Reg-Tabelle :1354, nur positionsgebundene Zahlungen aus `reg_agg`).
  - SG: :993–995, Antrag :1213–1227, `mit_sg`/`sg_mind`.
  - RVG außergerichtlich: :979–991 (Antragsbetrag), :1465–1469 (`sw_ausserg` aus `rvg_ausserg.streitwert`).
- `backend/routers/klage_routes.py`:
  - Generieren-Endpoint: klage_cfg = `body["klage_config"]` unverändert + Overrides-Merge :1160–1181 (nur `overrides`-Keys brauchen Merge; **cfg-Body-Felder kommen direkt durch**).
  - `s()` :1189 gibt nie None; tote Unkostenpauschale-Weiche :1224–1226; `reg_agg` :1253–1264 (nur positionsgebunden; ungebundene Vorschüsse fehlen).
  - Daten-Lade-Endpoint: `pos_definitionen` :779–808 (SG-Position :803–804, Unkostenpauschale :796–798 mit `or 30.0` + `vorschlag: True`), checked :841–842.
- `backend/word/forderungsschreiben_wv.py::_baue_tabelle` :749 (`_f` :750, Unkostenpauschale `_f(...) or 30.0` :807, SG-Zeile :804, 0-Zeilen-Filter :828). Wird von Klage UND Forderungsschreiben genutzt.
- `frontend/src/sections/KlageSection.jsx`: `oeffneWizard` :396–443 (Netting: `betragOriginal`→`betrag` via `_regMap` + gierige Verteilung ungebundener Vorschüsse), `posOffen` :270–312, `swAusserg` :268 (= Σ ALLER Positionen, voll), `wizardGenerieren` :553–591 (cfg :571–581, overrides :556–570; **hq wird nicht gesendet**).
- `frontend/src/sections/KlageWizard.jsx`: `buildRwVorschau` :164–192 (hq-Satz „entsprechend gekürzt"), StepRw :1150–1215, StepSchaden-Badge :686–688/:849–853, `ANTRAEGE_PLACEHOLDER` :1750, `baueAntraegeText` :1752–1819 (klagebetrag :1756), `StepGebuehren` :1925 ff., `StepZusammenfassung` :1507 (benannte Exporte aus S1).
- Tests Backend: `test_klage_overrides_merge.py` / `test_klage_ereignis_positionen.py` = Route-Level, `generiere_klageschrift` gemockt, `akte_daten` aus `call_args` geprüft. **Es gibt noch KEINE Direkttests von `generiere_klageschrift`** — Task 2 etabliert das Muster (DOCX-Bytes → `zipfile` → `word/document.xml`-Text-Assertions).
- Tests Frontend: `KlageWizard.gebuehren.test.jsx`, `KlageWizard.zusammenfassung.test.jsx` (importieren die S1-Exporte).

---

## Task 1 — KW-11: Unkostenpauschale-None-Semantik (nicht gesetzt ≠ explizit 0)

**Dateien:** `backend/word/forderungsschreiben_wv.py` (:807), `backend/routers/klage_routes.py` (:1224–1226).

**Fix:**
1. `_baue_tabelle`: Unkostenpauschale-Zeile bekommt echte None-Semantik statt `_f("unkostenpauschale") or 30.0`:
   - `schaden.get("unkostenpauschale") is None` (Key fehlt oder None) → Default `30.0` (Bestandsverhalten Forderungsschreiben bleibt).
   - Key vorhanden mit Wert (auch `0`/`0.0`) → Wert verwenden; `0` fällt durch den bestehenden 0-Zeilen-Filter (:828) aus der Tabelle.
2. Router-Weiche :1224–1226 ersetzen: nicht mehr über `s()` (liefert nie None). Stattdessen den rohen DB-Wert unterscheiden: `getattr(schaden, "unkostenpauschale", None)` — `None` → Key mit `None` in `schaden_dict` (Default-30-Fall), sonst `float`-Wert durchreichen (explizite 0 bleibt 0). Toten `is None`-Zweig entfernen.

**Tests (TDD, neue Datei `backend/tests/test_klage_s2_unkostenpauschale.py` oder passend):**
- Unit `_baue_tabelle`: (a) Key fehlt → Tabelle enthält „Unkostenpauschale" mit 30,00 €; (b) Key = `None` → 30,00 €; (c) Key = `0.0` → KEINE Unkostenpauschale-Zeile, Gesamt ohne 30 €; (d) Key = `25.0` → 25,00 €.
- Router: bestehendes Route-Level-Muster (Mock `generiere_klageschrift`, `call_args`): DB-`unkostenpauschale=0` → `akte_daten["schaden"]["unkostenpauschale"] == 0.0`; DB-Feld NULL → `None` im Dict.
- Vorher rot laufen lassen (Fall c bzw. 0.0-Durchreichung schlägt heute fehl).

**Hinweis:** Verhalten des Forderungsschreibens für Bestandsakten ohne gesetzten Wert darf sich NICHT ändern (weiterhin 30 €-Default). Ein bestehender Forderungsschreiben-Test, der 30 € bei fehlendem Wert erwartet, muss grün bleiben.

## Task 2 — KW-04: Eine Rechenquelle für Antrag 1, Schadentabelle, Differenz-Satz

**Datei:** `backend/word/klage_service.py` (:1324–1374, ggf. Helfer).

**Design (entschieden):**
1. **Tabelle nur aus checked Positionen:** `schaden_raw` wird auf die Keys der checked cfg-Positionen gefiltert (Mapping `_pos_key_map`; Fahrzeugschaden ist ein Multi-Key-Fall — dessen zugehörige DB-Felder bleiben nur erhalten, wenn die Fahrzeugschaden-Position checked ist; die genauen Key-Gruppen aus `_baue_tabelle`s Zeilendefinitionen ableiten). Nicht-checked bzw. gar nicht als Position vorhandene einfache Keys → aus dem Dict entfernen; **Unkostenpauschale bei „nicht checked" explizit auf `0.0` setzen** (sonst zieht der Task-1-Default 30 € sie wieder rein).
2. **Werte = 100 %:** für einfache Keys checked Positionen gilt `betragOriginal` (Fallback: DB-Wert, dann `betrag`) statt nur `setdefault` — die Tabelle zeigt die volle Forderung (KW-03-Vorgabe „Tabelle immer 100 %").
3. **Regulierungs-Tabelle vervollständigen:** ungebundene Vorschüsse als eigene Zeile. Im Generieren-Endpoint (`klage_routes.py`) zusätzlich `gesamt_reguliert_summe` = Σ `abrechnungen.gesamt_reguliert` mitgeben (oder aus vorhandenen `abrechnungen` in `akte_daten` ableiten — was schon durchgereicht wird, prüfen); `ungebunden = max(0, Σ gesamt_reguliert − Σ reg_agg)`; wenn > 0 → Zeile „Zahlung ohne Positionszuordnung" in `_baue_regulierungs_tbl_xml`, fließt in `gesamt_reguliert_tbl` ein.
4. **Differenz-Satz aus einer Quelle:** Satz nennt `schaden_gesamt` (Tabellen-Gesamt der checked Positionen, 100 %), Zahlungen `Z = round(schaden_gesamt − klagebetrag, 2)` und endet **exakt** bei `klagebetrag` (dem Antrag-1-Betrag). Kein unabhängiger Rechenweg mehr über `gesamt_reguliert_tbl`. Wenn `Z <= 0` (nichts reguliert): vereinfachte Formulierung ohne Abzug („Der Gesamtbetrag in Höhe von X wird mit dem Klageantrag zu 1 geltend gemacht."). Fallback `schaden_gesamt = klagebetrag` (:1338) nur noch, wenn die Tabelle leer bleibt.

**Tests (TDD, neues Muster — Direkttest `generiere_klageschrift`):**
- Neue Datei `backend/tests/test_klage_service_docx.py`: Helper baut minimales `akte_daten`-Dict (akte, mandant, kanzlei, details, klage_config, schaden, reg_agg, abrechnungen …), ruft `generiere_klageschrift` echt auf, entpackt die DOCX-Bytes via `zipfile`/`io.BytesIO`, liest `word/document.xml` als Text (XML-escaped beachten). Falls die DOCX-Vorlage im Test-Env fehlt/ladbar ist → prüfen; wenn unlösbar: BLOCKED melden statt Mock-Bastelei.
- Fälle: (a) abgewählte Position (checked=false) erscheint NICHT in der Tabelle und der Differenz-Satz endet beim Antrag-1-Betrag; (b) ungebundener Vorschuss (abrechnung mit `gesamt_reguliert`, ohne `reg_agg`-Position) erscheint als Zeile und der Differenz-Satz bleibt konsistent (Gesamt − Zahlungen = Klagebetrag); (c) `betrag` (genettet) < `betragOriginal` → Tabelle zeigt `betragOriginal`, Antrag 1 den genetteten Betrag, Satz exakt konsistent; (d) nichts reguliert → vereinfachter Satz.

## Task 3 — KW-07: Schmerzensgeld nicht doppelt (Position XOR mitSG)

**Dateien:** `backend/word/klage_service.py`, `frontend/src/sections/KlageWizard.jsx` (StepSchaden), ggf. `KlageSection.jsx`.

**Fix Backend (Defence-in-depth):** In `generiere_klageschrift` direkt bei der Positionsfilterung (:956–959): wenn `mit_sg` → Position mit `key == "schmerzensgeld"` aus `positionen` ausschließen (wirkt damit automatisch auf Antrag 1, Gegenstandswert, Schadentabelle aus Task 2, Differenz-Satz). `mit_sg` (:993) muss dafür vor die Positionsfilterung gezogen werden.

**Fix Frontend (UX):** StepSchaden: wenn `mitSG === true` → SG-Positionszeile (key `schmerzensgeld`) wird enthakt + disabled, mit Hinweis „Wird als unbezifferter Antrag geltend gemacht (Schmerzensgeld-Toggle aktiv)". Beim Deaktivieren des Toggles wird die Zeile wieder bedienbar (checked-Zustand nicht automatisch wiederherstellen — einfach wieder wählbar). Klagebetrag-Badge (:849–853) bleibt konsistent, weil die Position dann unchecked ist.

**Tests (TDD):**
- Backend (Muster aus Task 2): cfg mit checked SG-Position (2.000 €) UND `mit_schmerzensgeld=true`/`schmerzensgeld_mindest=2000` → Antrag 1 OHNE die 2.000 €, Gegenstandswert = klagebetrag_ohne_SG + 2.000, Tabelle ohne SG-Zeile, unbezifferter SG-Antrag vorhanden. Gegenprobe: `mit_schmerzensgeld=false` + checked SG-Position → SG beziffert in Antrag 1/Tabelle, kein unbezifferter Antrag.
- Frontend (Vitest, StepSchaden ist nicht exportiert → exportieren wie die S1-Exporte oder über KlageWizard-Render testen; kleinstmöglicher Eingriff): mitSG an → SG-Checkbox disabled+unchecked+Hinweis sichtbar; mitSG aus → wieder bedienbar.

## Task 4 — KW-05: Einleitung behauptet Eigentum nur noch bei Eigentum

**Datei:** `backend/word/klage_service.py` (:1287–1297, ggf. `_build_aktivlegitimation_xml`).

**Fix:**
1. `eigentuemer_satz` abhängig von `details["aktivlegitimation_typ"]` (Default `eigentum`):
   - `eigentum` → Satz bleibt wie heute („… ist Eigentümer/Eigentümerin des … Fahrzeugs …").
   - `finanziert`/`geleast` → stattdessen: „{kl_nom} ist Halter{in} und unmittelbarer Besitzer{in} des bei dem Unfall beschädigten Fahrzeugs mit dem amtlichen Kennzeichen {kz}." (Genus wie beim bestehenden `eigentuemer`-Ausdruck über `anrede_m`; „Halterin und unmittelbare Besitzerin" korrekt flektieren).
2. **Dublette bei `eigentum`:** Der AktLeg-Block liefert bei `typ=eigentum` denselben Eigentumssatz nochmal (get_aktivlegitimation_text :445). In der Klage bei `typ=eigentum` und OHNE `aktivlegitimation_text_override` → `aktivleg_xml` leer lassen (der Einleitungssatz trägt die Behauptung). `get_aktivlegitimation_text` selbst NICHT ändern (wird vom Forderungsschreiben mitbenutzt).
3. `sachverhalt_override`-Pfad (:1261–1266) bleibt unangetastet (übersteuert wie bisher beides).

**Tests (TDD, Muster aus Task 2):** (a) `typ=geleast`, kein Override → document.xml enthält „Halter und unmittelbarer Besitzer", enthält NICHT „{kl_nom} ist Eigentümer des", enthält den Leasing-AktLeg-Block; (b) `typ=eigentum` → genau EIN Eigentums-Satz (Vorkommen zählen); (c) `typ=finanziert` analog (a); (d) weiblicher Mandant → korrekte Flexion.

## Task 5 — KW-03 Backend: Haftungsquote Fall A/B rechnet und spricht richtig

**Dateien:** `backend/word/klage_service.py`, `backend/routers/klage_routes.py` (nur falls nötig — cfg-Body kommt unverändert durch, voraussichtlich kein Router-Change).

**Vertrag (neu):** `klage_config` erhält zwei optionale Felder vom Frontend: `haftungsquote` (Zahl, z. B. 75 = wir fordern 75 %) und `haftungsquote_typ` (`"gegnerisch"` | `"eigen"`; fehlt → `"gegnerisch"`).

**Fix `klage_service.py`:**
1. hq-Lesen (:1004): `hq = float(cfg.get("haftungsquote") ?? details/akte-Fallback ?? 100)`; `hq_typ = cfg.get("haftungsquote_typ") or "gegnerisch"`.
2. **Fall B (`hq_typ=="eigen"` und `hq < 100`):** nach der Positionssummierung (:956–959, nach Task-3-SG-Filter):
   - `gesamt_voll = Σ (betragOriginal ?? betrag)` der checked Positionen; `zahlungen = round(gesamt_voll − Σ betrag, 2)`.
   - `klagebetrag = max(0, round(gesamt_voll * hq/100 − zahlungen, 2))` — **erst quotieren, dann Zahlungen abziehen**.
   - Wirkt damit automatisch auf Antrag 1 (:1208), Gegenstandswert (:1026, SG-Mindest wird unquotiert addiert — Vorgabe), RVG-Streitwert-Fallback (:1467).
   - **Schadentabelle bleibt 100 %** (Task-2-Logik unverändert); der **Differenz-Satz** bekommt eine Fall-B-Variante: „Von dem Gesamtschaden in Höhe von {gesamt_voll} sind unter Berücksichtigung der Mithaftungsquote von {100−hq} % {hq} %, mithin {gesamt_voll×hq/100}, ersatzfähig. Abzüglich der geleisteten Zahlungen in Höhe von {zahlungen} verbleiben {klagebetrag}, die mit dem Klageantrag zu 1 geltend gemacht werden." (arithmetisch exakt, Prozent ohne int-Truncation formatiert).
3. **Fall A / Auto-RW-Text (:1409–1411):** Satz „Die Klageforderung wurde entsprechend gekürzt" ersatzlos raus. Neu:
   - `hq_typ=="gegnerisch"` und `hq < 100`: „Die Beklagtenseite geht von einer Mithaftungsquote des {kl_dat} von {100−hq} % aus. Dies wird bestritten; die Beklagtenseite haftet in vollem Umfang. Die Klageforderung ist ungekürzt geltend gemacht."
   - `hq_typ=="eigen"` und `hq < 100`: „{kl_nom} lässt sich eine Mithaftungsquote von {100−hq} % anrechnen. Die Klageforderung ist entsprechend gekürzt." (hier ist der Satz WAHR).
   - (Der Auto-RW-Block läuft nur ohne `rw_text_override` — Legacy-Pfad; Wizard sendet eigene Texte, Task 6.)
4. **Nr.-2300-Basis:** keine Backend-Rechnung nötig — `rvg_ausserg` kommt fertig berechnet vom Frontend (Task 6 quotiert dort den Streitwert). Nur der Streitwert-**Fallback** (:1467 `or klagebetrag`) profitiert automatisch vom quotierten `klagebetrag`.

**Tests (TDD, Muster aus Task 2):**
- Fall B: 2 Positionen (Original 10.000, genettet 7.000 → Zahlungen 3.000), hq=75, typ=eigen → Antrag 1 über 4.500 € (10.000×0,75−3.000); Gegenstandswert mit SG-Mindest 1.000 → 5.500 €; Tabelle zeigt weiter 10.000; Fall-B-Differenz-Satz mit exakt diesen Zahlen.
- Fall A: gleiche Daten, typ=gegnerisch → Antrag 1 über 7.000 €, kein „entsprechend gekürzt", Auto-RW (ohne rw_text_override) enthält Bestreiten-Satz.
- hq=100 → keinerlei Quote-Text, Verhalten wie bisher.
- SG: Fall B mit mitSG+sgMind → sgMind NICHT quotiert.

## Task 6 — KW-03 Frontend: Step-7-Fallauswahl, RW-Bausteine, konsistente Beträge

**Dateien:** `frontend/src/sections/KlageWizard.jsx`, `frontend/src/sections/KlageSection.jsx`.

**Fix:**
1. **Neuer State** in KlageSection: `wizardHqTyp` (`"gegnerisch"` Default), Reset in `oeffneWizard`, als Prop in den Wizard.
2. **StepRw (Step 7):** wenn `hq < 100` → Radio-Auswahl „Gegnerische Quote (nur Darstellung — Beträge bleiben 100 %)" vs. „Eigene Quote (kürzt Klagebetrag und Gebührenbasis)". `buildRwVorschau` (:164–192): den Satz „Die Klageforderung wurde entsprechend gekürzt" ersetzen durch die zwei Varianten (Wortlaut analog Task 5 Punkt 3; Fall B zusätzlich mit dem quotierten Klagebetrag beziffern). Umschalten der Auswahl regeneriert die Vorschau (bestehendes `neuGenerieren`-Muster; manuelle Edits nicht ungefragt überschreiben — bestehendes Verhalten beibehalten).
3. **Zentrale Rechenfunktion** (exportiert, z. B. `berechneKlagebetrag(positionen, hq, hqTyp)` in KlageWizard.jsx): Fall B = `max(0, Σoriginal(checked)×hq/100 − (Σoriginal−Σbetrag)(checked))`, sonst `Σ betrag(checked)`. Verwenden in: `baueAntraegeText` (:1756), StepSchaden-Badge (:688/:849), StepZusammenfassung-Anzeige. **Antragstext und Backend-Antrag-1 müssen denselben Betrag nennen** (Backend-Formel aus Task 5 exakt spiegeln, Rundung `round(...,2)`).
4. **Nr.-2300-Basis quotieren (Fall B):** `swAusserg` (KlageSection :268) → effektiv `swAusserg × hq/100` bei `wizardHqTyp==="eigen"`, überall wo er als Streitwert verwendet wird (`apiKlage.rvgBerechnen` :317/:328, StepGebuehren-Prop, Anzeige :1352). Ein Ort für die Ableitung (kein dritter paralleler Rechenweg).
5. **cfg senden:** `wizardGenerieren` (:571–581) ergänzt `haftungsquote: wizardHq`, `haftungsquote_typ: wizardHqTyp` im `klage_config`-Body.
6. Step 5-Abwahl-Interaktion: keine Sonderlogik — `berechneKlagebetrag` arbeitet immer auf aktuellen checked-Positionen.

**Tests (TDD, Vitest):**
- `berechneKlagebetrag`: Fall gegnerisch (=Σ betrag), Fall eigen (Beispielzahlen aus Task 5: 10.000/7.000/75 % → 4.500), hq=100 (identisch), max-0-Klammer.
- `baueAntraegeText` mit hqTyp eigen → Antragstext nennt 4.500 €-Betrag (Export nötig — wie S1-Exporte).
- StepRw: Radio nur bei hq<100 sichtbar; Umschalten ändert RW-Vorschau-Text (Fall-A-Baustein enthält „bestritten", Fall-B-Baustein „anrechnen"); kein „wurde entsprechend gekürzt" mehr im Fall-A-Text.
- StepGebuehren/Streitwert: bei eigen wird der quotierte Streitwert an die Gebühren-API gegeben (Mock-Assertion).
- Build (`npm run build` bzw. Vite-Build im Docker) grün.

## Task 7 — Abschluss (Controller + Verifikation)

1. Volle Backend-Suite (Baseline-Vergleich: nur Alt-Cluster-Failures, null neue) + volle Frontend-Suite + Build.
2. Tracking-Doc `docs/BUGFIX_KLAGE_WIZARD.md`: KW-03/04/05/07/11 auf `[x]` + Commit-Hashes, Status-Tabelle aktualisieren, Session-2-Zeile.
3. `docs/TODO.md` aktualisieren.
4. Finales Whole-Branch-Review (Opus), Fix-Wave falls nötig.
5. FF-Merge nach `main` erst NACH Freigabe durch RA Schatz (finishing-a-development-branch).

## Test-Infrastruktur-Hinweis (Task 2 zuerst klären)

Der Direkttest von `generiere_klageschrift` braucht die DOCX-Vorlage. Prüfen, wo sie liegt (`backend/word/…`/`vorlagen`), ob sie im Repo ist und im Test ladbar. Wenn ja: echtes Rendern + `zipfile`-Assertion (robust gegen XML-Escaping: assertions auf normalisierten Text, `&amp;`→`&` etc. bzw. Teilstrings ohne Sonderzeichen). Wenn die Vorlage fehlt: BLOCKED melden.

## Reihenfolge & Abhängigkeiten

1 (KW-11) → 2 (KW-04, braucht 1 für Unkostenpauschale-Semantik) → 3 (KW-07, baut auf 2er-Testmuster + Tabellenfilter) → 4 (KW-05, unabhängig, nutzt 2er-Testmuster) → 5 (KW-03 Backend, baut auf 2+3) → 6 (KW-03 Frontend, spiegelt 5) → 7 (Abschluss).
