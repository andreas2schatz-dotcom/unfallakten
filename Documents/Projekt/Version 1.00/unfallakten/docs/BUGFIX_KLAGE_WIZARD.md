# Bugfix-Tracking: PRD-33 Klage-Wizard + Klagegenerierung

> **Quelle:** Multi-Agent-Code-Research vom 2026-07-17 (3 Research-Agenten: Backend/DOCX, Frontend-Wizard, Datenfluss/Vertrag).
> ~45 Rohfunde, nach Zusammenführung von Mehrfach-Funden **40 distinkte Bugs (KW-01–KW-40)**.
> **Verifikationsstand:** KW-01 wurde im Code verifiziert (Merge-Lücke bestätigt). Alle übrigen Funde sind mit Datei:Zeile belegt, aber noch **nicht adversarial verifiziert** — der fehlschlagende TDD-Test vor jedem Fix ist zugleich die Verifikation; stellt sich ein Fund als falsch heraus, mit Begründung abhaken (`entfällt`).
> Zeilennummern: Stand 2026-07-17 (`main`).
>
> **Arbeitsregeln für alle Fixes:**
> - TDD: erst fehlschlagender Test, dann Fix. Kein Refactoring über den Fix hinaus.
> - RA-MICRO bleibt **read-only**.
> - Baseline muss grün bleiben: Backend Failures nur in bekannten Alt-Clustern (204f-Baseline, `test_modul2/3/4/7` etc.), **null neue Failures**; Frontend 91 Tests + Build.
> - Vorsicht Wechselwirkung: **KW-01 maskiert derzeit KW-22/KW-23** (verworfene Overrides verstecken stale Texte/Platzhalter). KW-01 nie ohne mindestens den Platzhalter-Guard aus KW-23 fixen.
> - Beim Abhaken: `[x]` setzen und Commit-Hash hinter den Titel schreiben.

## Status-Übersicht

| ID | Prio | Datei | Kurztitel | Status |
|---|---|---|---|---|
| KW-01 | P0 | `backend/routers/klage_routes.py:1170` | Anträge-Override + Feststellungsanträge gehen komplett verloren | ✅ behoben `e668f50f` |
| KW-02 | P0 | `frontend/src/sections/KlageWizard.jsx:1954` | RVG-Faktor landet im Euro-Override → „weitere 1,50 €" | ✅ behoben `b1c1fbfb` |
| KW-03 | P0 | `backend/word/klage_service.py:1409` | Haftungsquote wird nie angewendet, Text behauptet Kürzung | ✅ behoben S2 (BE `ebbf7c1b`+`3947fc21`, FE `ff859255`+`db9dcfe7`+`ce18d869`) |
| KW-04 | P0 | `backend/word/klage_service.py:1338` | Antrag 1 ≠ Schadentabelle ≠ Differenz-Satz (3 Rechenwege) | ✅ behoben `974cecdd`+`f5a29ad7` |
| KW-05 | P0 | `backend/word/klage_service.py:1289` | Einleitung behauptet Eigentum trotz Leasing/Finanzierung | ✅ behoben `322fb9a1`+`633b6c95` |
| KW-06 | P1 | `backend/word/klage_service.py:1208` | Mehrere Beklagte: Singular-Anträge, kein Gesamtschuldner | offen |
| KW-07 | P1 | `backend/routers/klage_routes.py:802` | Schmerzensgeld doppelt einklagbar (Position + mitSG) | ✅ behoben `5639c72e`+`bb64829b` |
| KW-08 | P1 | `frontend/src/sections/KlageSection.jsx:380` | Legacy-Button klagt vollen statt offenen Betrag ein | offen |
| KW-09 | P1 | `backend/word/klage_service.py:972` | Zins-/Verzugsdatum erscheint im ISO-Format | offen |
| KW-10 | P1 | `frontend/src/sections/KlageSection.jsx:581` | Verzugsdatum-State-Split (3 Stellen, 3 Werte) + Schreibdatum als Verzugseintritt | offen |
| KW-11 | P1 | `backend/word/forderungsschreiben_wv.py:807` | Unkostenpauschale nicht abwählbar (`or 30.0` + tote Weiche) | ✅ behoben `5cb2acc5`+`fb695b6b` |
| KW-12 | P1 | `backend/word/klage_service.py:478` | Anlagen-Kollision: zwei Dokumente heißen „K1" | offen |
| KW-13 | P1 | `frontend/src/sections/KlageSection.jsx:317` | „RVG gerichtlich" ist außergerichtliche Gebühr; `rvg_override` wirkungslos | offen |
| KW-14 | P1 | `backend/routers/klage_routes.py:1399` | `klage_generiert`-Ereignis immer ohne Positionen (geschluckter AttributeError) | ✅ behoben `d42f09eb` |
| KW-15 | P2 | `backend/word/klage_service.py:1138` | Rubrum-Rolle immer feminin („– Beklagte –") | offen |
| KW-16 | P2 | `backend/word/klage_service.py:1121` | Vertreter-Grammatik („den Geschäftsführerin"), Anrede-Heuristik nur auf Funktion | offen |
| KW-17 | P2 | `backend/word/klage_service.py:940` | Mehrere Kläger: Numerus-Fehler, Vorsteuer ignoriert | offen |
| KW-18 | P2 | `backend/word/klage_service.py:1061` | Rubrum ohne Kläger möglich (kein Mandant-Fallback) | offen |
| KW-19 | P2 | `frontend/src/sections/KlageWizard.jsx:1528` | Generieren mit 0 Beklagten möglich | offen |
| KW-20 | P2 | `frontend/src/sections/KlageWizard.jsx:106` | Beklagten-Nummerierung Sachverhalt ≠ Rubrum; Nicht-Halter-Person fehlt | offen |
| KW-21 | P2 | `backend/word/klage_service.py:664` | Rechtsform-Heuristik matcht Substrings („UG" in „FAHRZEUGBAU") | offen |
| KW-22 | P3 | `frontend/src/sections/KlageWizard.jsx:1832` | Anträge-Text stale nach Positions-/SG-Änderung; Feststellungs-Checkboxen ohne Textwirkung | offen |
| KW-23 | P3 | `frontend/src/sections/KlageWizard.jsx:1744` | Platzhalter „[Außergerichtliche Anwaltsgebühren …]" kann im Antragstext verbleiben | ✅ behoben `a6711c2d` |
| KW-24 | P3 | `frontend/src/sections/KlageWizard.jsx:2010` | Step-9-Änderungen nach Erst-Ersetzung wirkungslos; `wizardGebuehrenText` nie gesendet | offen |
| KW-25 | P3 | `frontend/src/sections/KlageWizard.jsx:489` | Step 3: manuelle Sachverhalt-Edits beim Remount überschrieben | offen |
| KW-26 | P3 | `frontend/src/sections/KlageWizard.jsx:2271` | Fortschrittsbalken umgeht kannWeiter()-Sperren | offen |
| KW-27 | P3 | `backend/routers/klage_routes.py:946` | Gericht-Persistenz: Rückweg tot (`rolle='gericht'` wird vorab weggefiltert) | offen |
| KW-28 | P3 | `frontend/src/sections/KlageSection.jsx:165` | Verzugsdokument-Auswahl ohne jede Wirkung (Placebo) | offen |
| KW-29 | P3 | `frontend/src/sections/KlageSection.jsx:250` | Vertreter-Lookup-Modal öffnet wiederholt unaufgefordert | offen |
| KW-30 | P4 | `backend/word/klage_service.py:1271` | Leere Felder erzeugen kaputte Sätze („…Unfall vom … in  geltend") | offen |
| KW-31 | P4 | `backend/word/klage_service.py:688` | `sachverhalt_override` zerstört Absatzstruktur des Nutzers | offen |
| KW-32 | P4 | `backend/word/klage_service.py:1440` | Verzug-Abschnitt ohne Nummer/Überschrift, Nummerierungssprung | offen |
| KW-33 | P4 | `backend/word/klage_service.py:1421` | SG-Beweisantritt nicht als BEWEIS formatiert | offen |
| KW-34 | P4 | `backend/word/klage_service.py:989` | RVG-Antrag über „0,00 €" möglich | offen |
| KW-35 | P4 | `backend/word/klage_service.py:963` | RVG-Fallback nutzt SQLite-Importdatum statt RA-MICRO-Anlagedatum | offen |
| KW-36 | P4 | `backend/word/klage_service.py:1394` | Haftungsquote int-Truncation: 66,67 % → „66 % + 33 % = 99" | offen |
| KW-37 | P4 | `backend/word/klage_service.py:1478` | RVG-Faktor „(1.3)" mit Punkt statt Komma | offen |
| KW-38 | P4 | `frontend/src/sections/KlageSection.jsx:275` | Positions-Key-Vertrag ungesichert (`_KEY_MAP` nur Fahrzeugschaden) | offen |
| KW-39 | P4 | `backend/routers/klage_routes.py:783` | Vorsteuer-Inkonsistenz Nebenkosten (Antrag brutto, Tabelle netto) | ✅ behoben `e19edc64` (S2 vorgezogen) |
| KW-40 | P4 | diverse | Sammelposten Kleinkram/toter Code (Details unten) | offen |

---

## P0 — Kritisch: Eingaben gehen verloren / falsche Beträge im Schriftsatz

### - [x] KW-01 — Anträge-Override + Feststellungsanträge gehen komplett verloren **[VERIFIZIERT]** — behoben `e668f50f` (+ `f239a1fe` Test-tearDown), Session 1 2026-07-17
- **Datei:** `backend/routers/klage_routes.py:1170–1172` (Merge-Lücke), `backend/word/klage_service.py:976–978` (liest aus cfg), `frontend/src/sections/KlageSection.jsx:568–570` (sendet in overrides)
- **Problem:** Das Frontend sendet `antraege_override`, `mit_feststellung_sg`, `mit_feststellung_sach` im `overrides`-Objekt. Der Router mergt aus `overrides` aber nur `rvg_ausserg`, `rvg_ausserg_override`, `rvg_bereits_gezahlt` in `klage_cfg`. Der Service liest die drei Felder via `cfg.get()` → immer `None`/`False`. Die Text-Overrides (`sachverhalt_override` etc.) gehen dagegen den funktionierenden Weg über `_override()` → `unfalldetails`.
- **Auswirkung:** Jeder Edit am Antragstext in Step 6, jedes Feststellungsantrag-Häkchen und der in Step 9 eingesetzte RVG-Antragstext werden stillschweigend verworfen. Das DOCX enthält stets die Auto-Anträge ohne Feststellungsanträge. Die gesamte Step-6/9-Textarbeit ist ein Placebo.
- **Fix-Richtung:** Die drei Keys in die Merge-Schleife aufnehmen (oder Overrides-Vertrag vereinheitlichen, siehe Verbesserung V1). **Zwingend zusammen mit KW-23 (Platzhalter-Guard) fixen** — sonst kann der bisher maskierte Platzhalter-Text als Klageantrag im Dokument landen. Vertragstest ergänzen: jedes vom Frontend gesendete Feld wird backendseitig gelesen.

### - [x] KW-02 — RVG-Faktor landet im Euro-Override-Feld — behoben `b1c1fbfb`, Session 1 2026-07-17
- **Datei:** `frontend/src/sections/KlageWizard.jsx:1954` (`onRvgAussergOv(String(neuerFaktor))`), inkonsistent dazu `:1967` (liest als Faktor); `KlageSection.jsx:236–238` (Prefill, toter Code wegen Reset in `:524`), `:572` (Versand als Euro); `backend/word/klage_service.py:983–984, 1469` (interpretiert als Euro)
- **Auswirkung:** Nutzer führt in Step 9 die Gebühren-Analyse aus (Faktor z.B. 1,5) → Betrags-Override-Feld zeigt „1.5", Step 10 zeigt „RVG außergerichtlich: 1,50 €", DOCX-Tabelle „Gesamtbetrag: 1,50 €" und Klageantrag „weitere 1,50 €" statt ~1.300 €.
- **Fix-Richtung:** Faktor und Euro-Betrag als getrennte Felder/States führen; die Analyse darf nur den Faktor setzen und daraus neu berechnen, nie das Betrags-Override befüllen.

### - [x] KW-03 — Haftungsquote wird nie angewendet, Text behauptet das Gegenteil — behoben Session 2 2026-07-17 (BE `ebbf7c1b`+`3947fc21`, FE `ff859255`+`db9dcfe7`+`ce18d869`)
> **Umsetzung:** Neuer cfg-Vertrag `haftungsquote` + `haftungsquote_typ` („gegnerisch" Default | „eigen"); Quote wirkt nur bei eigen && 0<hq<100. Fall B: `klagebetrag = max(0, round(Σ betragOriginal(checked)×hq/100 − Zahlungen, 2))` — erst quotieren, dann Zahlungen abziehen; sgMind unquotiert; Fall-B-Differenz-Satz auf Tabellenbasis (`ersatzfaehig = round(schaden_gesamt×hq/100, 2)`), endet exakt beim Antrag-1-Betrag. Fall A/Auto-RW: „entsprechend gekürzt" ersatzlos raus, Bestreiten-Baustein (deklinationsfrei formuliert). Frontend: Step-7-Radio, exportierte `berechneKlagebetrag`/`berechneSwAussergEffektiv`/`pctStr` (backend-identisch), Nr.-2300-Basis bei eigen quotiert, `oeffneWizard`-Initialtext nutzt jetzt `buildRwVorschau` (Falsch-Satz auch aus dem Default-Pfad eliminiert; alleinige-Haftung-Satz hq=100 dorthin zurückportiert, erscheint jetzt auch bei Step-7-Regeneration).
- **Datei:** `frontend/src/sections/KlageWizard.jsx:1150–1210` (hq nur im RW-Text), `KlageSection.jsx:503–504, 560–585` (hq nicht in cfg), `backend/word/klage_service.py:1409–1411` (Auto-Text „Die Klageforderung wurde entsprechend gekürzt")
- **Auswirkung:** Bei Quote 50 % sagt der Schriftsatz „Mithaftungsquote 50 %, Forderung entsprechend gekürzt" — der Klagebetrag bleibt aber 100 %. Widersprüchliche Tatsachenbehauptung; bei Teilhaftungsfällen materiell falscher Antrag.
- **Fix-Richtung — ENTSCHIEDEN (RA Schatz, 2026-07-17), zwei getrennte Fälle:**
  - **Fall A — gegnerische Quote** (die HPV hat nur nach ihrer Quote reguliert): Schadentabelle UND Klagebetrag bleiben **100 %**; die gegnerische Quote wird nur in der rechtlichen Würdigung erwähnt (und bestritten). Der Satz „Die Klageforderung wurde entsprechend gekürzt" ist hier falsch und fliegt raus.
  - **Fall B — eigene Quote** (wir akzeptieren selbst eine Mithaftung): Schadentabelle bleibt auf 100 %, aber der Klagebetrag wird quotiert. **Rechenweg: erst quotieren, dann Zahlungen abziehen** (Anspruch = Gesamtschaden × Quote; davon reguliert abziehen → Klagebetrag). **Schmerzensgeld wird NICHT automatisch quotiert** (Mitverschulden ist dort Bemessungsfaktor, Mindestbetrag wird bereits quotenbewusst eingegeben). **Die eigene Quote gilt auch für den vorgerichtlichen Streitwert** (Basis der Geschäftsgebühr Nr. 2300 = quotierter Betrag).
  - **UI:** Step 7 braucht eine Auswahl, wessen Quote gemeint ist: „gegnerisch angenommen (nur Darstellung)" vs. „von uns akzeptiert (kürzt Forderung + Gebührenbasis)". Beide Fälle bekommen eigene RW-Textbausteine.

### - [x] KW-04 — Antrag 1 ≠ Schadentabelle ≠ Differenz-Satz (drei parallele Rechenwege) — behoben `974cecdd`+`f5a29ad7`, Session 2 2026-07-17
> **Umsetzung:** Schadentabelle nur noch aus checked cfg-Positionen (100 % = `betragOriginal`; Fahrzeugschaden-Multi-Key-Gruppe; Extras via wortgleicher `extra_…`-Key-Ableitung gefiltert; Unkostenpauschale nicht-checked → explizit 0.0). Regulierungs-Tabelle + Zeile „Zahlung ohne Positionszuordnung" (ungebundene Vorschüsse). Differenz-Satz per Konstruktion exakt: `Zahlungen = schaden_gesamt − klagebetrag`, endet beim Antrag-1-Betrag; vereinfachter Satz wenn nichts reguliert. Neues Testmuster: `test_klage_service_docx.py` (echtes DOCX-Rendering + zipfile).
- **Datei:** `backend/word/klage_service.py:957–959` (Antrag 1 = Σ checked cfg-Positionen, im Wizard genettet), `:1334–1374` (Tabelle aus vollen DB-Werten, ignoriert Checkboxen/Wizard-Beträge; Differenz-Satz „…wird mit dem Klageantrag zu 1 geltend gemacht"), `backend/routers/klage_routes.py:1249–1260` (Zahlungen nur positionsgebunden, ohne ungebundene Vorschüsse)
- **Auswirkung:** (a) Position im Wizard abgewählt → Differenz-Satz nennt Betrag inkl. der Position, Antrag 1 ohne — bezifferter Selbstwiderspruch im Schriftsatz. (b) Ungebundener Vorschuss (nur `gesamt_reguliert`, keine `regulierung_positionen`) → Antrag 1 niedriger als behauptete Differenz.
- **Fix-Richtung:** Eine Rechenquelle: Tabelle und Differenz-Satz aus denselben (genetteten, checked) cfg-Positionen speisen wie Antrag 1 — oder „offen je Position" ins Backend verlagern (Verbesserung V2) und überall konsumieren.

### - [x] KW-05 — Einleitung behauptet Eigentum trotz Leasing/Finanzierung — behoben `322fb9a1`+`633b6c95`, Session 2 2026-07-17
> **Umsetzung:** Einleitungssatz typabhängig (finanziert/geleast: „Halter und unmittelbarer Besitzer", flektiert). Bei eigentum ohne Override: Eigentumsbehauptung genau 1× — ohne Fahrer trägt sie der Einleitungssatz (AktLeg-Block leer), mit `mandant_ist_fahrer` trägt sie der AktLeg-Block (inkl. § 1006 BGB) und der Einleitungssatz entfällt. Override-/sachverhalt_override-Pfade unverändert; `get_aktivlegitimation_text` (Forderungsschreiben) unangetastet.
- **Datei:** `backend/word/klage_service.py:1289–1296` (bedingungsloser Satz „{kl_nom} ist Eigentümer des … Fahrzeugs") vs. `:468` (AktLeg-Block „Eigentum der Leasinggeberin")
- **Auswirkung:** Bei `aktivlegitimation_typ="geleast"` ohne `sachverhalt_override` stehen zwei sich widersprechende Tatsachenbehauptungen direkt hintereinander. Bei `typ="eigentum"` steht der Eigentumssatz doppelt (Einleitung + AktLeg-Block).
- **Fix-Richtung:** Eigentumssatz vom `aktivlegitimation_typ` abhängig machen (Eigentum: einmal; finanziert/geleast: Formulierung „Halter und unmittelbarer Besitzer" o.ä.); Dublette entfernen.

---

## P1 — Falsche Zahlen / rechtlich relevante Fehler

### - [ ] KW-06 — Mehrere Beklagte: Anträge Singular, keine Gesamtschuldner-Formulierung
- **Datei:** `backend/word/klage_service.py:1208, 1216–1251` (Anträge), `:1279–1283` (Einleitung); nur Kostenantrag `:1254` und VK-Abschnitt `:1493` pluralisieren
- **Auswirkung:** Fahrer + Versicherung als 2 Beklagte (vom System via synthetischem GHPV-Eintrag aktiv angeboten, `klage_routes.py:948–980`) → Zahlungsantrag benennt nicht, wer verurteilt werden soll; „als Gesamtschuldner" fehlt vollständig.
- **Fix-Richtung:** Numerus-bewusste Antragsbausteine („Die Beklagten werden als Gesamtschuldner verurteilt, an …"); siehe Verbesserung V3 (Partei-Objekt). Frontend-Pendant: `baueAntraegeText()` in KlageWizard.jsx hat dasselbe Problem (`(zu 1)` hart, `EinwandePanel:981`, `StepGebuehren:1928`).

### - [x] KW-07 — Schmerzensgeld doppelt einklagbar — behoben `5639c72e` (BE) + `bb64829b` (FE), Session 2 2026-07-17
> **Umsetzung:** Backend schließt bei `mit_schmerzensgeld=true` die SG-Position vor der checked-Filterung aus (wirkt auf Antrag 1, Gegenstandswert, Tabelle, Differenz-Satz). Frontend StepSchaden: SG-Zeile bei aktivem Toggle enthakt (echter Setter) + disabled + Hinweis; Toggle aus → wieder bedienbar.
- **Datei:** `backend/routers/klage_routes.py:802–803` (SG als bezifferte, checked Position), `backend/word/klage_service.py:957–959, 1026, 1213 ff.` (kein Ausschluss zu `mit_schmerzensgeld`), `forderungsschreiben_wv.py:804` (SG-Zeile in Tabelle)
- **Auswirkung:** SG-Position 2.000 € angehakt + „Schmerzensgeld geltend machen" mit Mindestbetrag 2.000 € → Gegenstandswert 4.000 € zu hoch, SG beziffert in Antrag 1 UND unbeziffert als eigener Antrag.
- **Fix-Richtung:** Gegenseitiger Ausschluss: bei `mit_schmerzensgeld=true` die SG-Position aus Antrag 1/Tabelle/Streitwert nehmen (oder Checkbox in Step 5 deaktivieren mit Hinweis).

### - [ ] KW-08 — Legacy-Button klagt vollen statt offenen Betrag ein
- **Datei:** `frontend/src/sections/KlageSection.jsx:380` (`generieren()` sendet volle Forderungsbeträge), UI-Kacheln zeigen offenen Betrag (`posOffen`, `:292–315`)
- **Auswirkung:** Akte mit 5.000 € Forderung, 3.000 € reguliert → Kachel zeigt 2.000 €, Klick auf den alten „Klage generieren"-Button erzeugt Klage über 5.000 €.
- **Fix-Richtung — ENTSCHIEDEN (RA Schatz, 2026-07-17): Legacy-Button entfernen. Der Klage-Wizard ist der einzige Weg.** Backend-seitig prüfen, ob der Legacy-Codepfad (`generieren()` ohne Wizard-cfg, RVG-Fallback KW-35) mit entfernt werden kann.

### - [ ] KW-09 — Zins-/Verzugsdatum erscheint im ISO-Format
- **Datei:** `backend/word/klage_service.py:972` (`f"dem {verzugsdatum}"` roh), `:1440–1444`; Quelle ISO: `forderung_positionen.datum` Default `date('now')` (`models/forderung.py:184`); `_fmt_datum` existiert (`:1581`), wird hier nicht genutzt. Auch Wizard-Auto-Verzugstext übernimmt ISO wörtlich (`KlageSection.jsx:512–513`).
- **Auswirkung:** „…nebst Zinsen … seit dem 2026-05-04" statt „04.05.2026" im Schriftsatz.
- **Fix-Richtung:** Jede Datumsausgabe durch `_fmt_datum` leiten (ein Wrapper an der cfg-Grenze); Transportformat ISO beibehalten, Formatierung nur im Renderer (Verbesserung V5).

### - [ ] KW-10 — Verzugsdatum-State-Split + Schreibdatum als Verzugseintritt
- **Datei:** `frontend/src/sections/KlageSection.jsx:581` (Wizard-Pfad sendet `verzug`, nicht `wizardVerzugDatum` — Legacy-Pfad `:383` wurde gefixt, Wizard-Pfad nicht), `KlageWizard.jsx:2394` (Step 6: `wizardVerzugDatum || verzug`) vs. `:2441` (Step 9: nur `verzug`), `:1345–1348` (Step 8 setzt nur `wizardVerzugDatum`); inhaltlich `:1313–1318` + `klage_service.py:1440–1444`: Schreibdatum des Forderungsschreibens wird als Verzugseintritt behauptet (Verzug tritt erst nach Fristablauf ein)
- **Auswirkung:** Verzugsdatum in Step 8 korrigiert → cfg und Step 9 nutzen weiter den alten Wert; Hauptantrag, Gebühren-Antrag und Verzugs-Abschnitt können drei verschiedene Daten nennen. Zudem juristisch schief: „Der Verzug ist am {Schreibdatum} eingetreten" + „BEWEIS: Schreiben vom {selbes Datum}".
- **Fix-Richtung:** Ein einziger Verzugsdatum-State; `wizardGenerieren` sendet `wizardVerzugDatum || verzug`; Schreibdatum und Verzugseintritt als getrennte Felder (Eintritt = Fristablauf, editierbar).

### - [x] KW-11 — Unkostenpauschale nicht abwählbar — behoben `5cb2acc5`+`fb695b6b`, Session 2 2026-07-17
> **Wichtige Erkenntnis:** Die DB kann „nie angefasst" nicht von „explizit 0" unterscheiden (`schadenpositionen.unkostenpauschale` ist `NOT NULL DEFAULT 0.0`). Deshalb: `_baue_tabelle` hat jetzt None-Semantik (Key fehlt/None → 30-€-Default; expliziter Wert, auch 0.0 → Wert); DB-seitig bleibt das Bestandsverhalten byte-gleich (falsy → None → 30 €) an beiden Aufbau-Stellen (Klage-Router + `word_service`/Forderungsschreiben); die Abwahl-Wirkung kommt aus den Wizard-cfg-Positionen (KW-04-Filter setzt nicht-checked → explizit 0.0).
- **Datei:** `backend/word/forderungsschreiben_wv.py:807` (`_f("unkostenpauschale") or 30.0` macht aus 0.0 → 30 €), `backend/routers/klage_routes.py:1221–1222` (Abwahl-Weiche tot: `s()` gibt nie `None`)
- **Auswirkung:** Im Wizard abgewählte/genullte Unkostenpauschale steht trotzdem mit 30 € in der Schadentabelle → verstärkt KW-04.
- **Fix-Richtung:** `None`-Semantik sauber trennen (nicht gesetzt vs. explizit 0); Default-30 nur bei „nicht gesetzt".

### - [ ] KW-12 — Anlagen-Kollision „K1"
- **Datei:** `backend/word/klage_service.py:478/486` (Freigabeerklärung/Sicherungsbedingungen = „Anlage K1") vs. `:1360` (Gutachten = „Anlage K 1"); `sg_text_builder.py:53` („K 2"); Schreibweise „K1" vs. „K 1" inkonsistent
- **Auswirkung:** Bei finanziertem Fahrzeug mit Freigabeerklärung sind zwei verschiedene Dokumente beide als K1 bezeichnet.
- **Fix-Richtung:** Anlagen-Manager: fortlaufende K-Nummern zentral vergeben, Registrierung beim Erzeugen jedes BEWEIS-/Anlagen-Bausteins (Verbesserung V4).

### - [ ] KW-13 — „RVG gerichtlich" ist die außergerichtliche Gebühr; `rvg_override` wirkungslos
- **Datei:** `frontend/src/sections/KlageSection.jsx:317–325` (`rvgData` mit `streitwert: swAusserg` berechnet) + `:328–336` (Duplikat `rvg_ausserg`), `KlageWizard.jsx:1571` (Label „RVG gerichtlich (SW: swGerichtlich)" zeigt aber `rvgData.gesamt`), `backend/word/klage_service.py:983–988` (bevorzugt `rvg_ausserg` → Kachel-6-`rvg_override` wirkungslos sobald Step 9 betreten); eine echte Verfahrensgebühr Nr. 3100 wird nirgends berechnet
- **Auswirkung:** Step 8/10 zeigen einen Betrag, der nicht zum beschrifteten Streitwert passt; zwei fast identische 2300er-Berechnungen unter zwei Labels; sichtbares Override-Feld ohne Wirkung. Nach Gebühren-Analyse divergieren `rvgData` (1,3) und `rvg_ausserg` (neuer Faktor) zusätzlich.
- **Fix-Richtung — ENTSCHIEDEN (RA Schatz, 2026-07-17): KEINE gerichtliche Gebührenberechnung bauen** — gerichtliche Gebühren gehören in die Kostenfestsetzung, nicht in die Klage. Das Streitwert-Konzept ist:
  - **Vorgerichtlicher Streitwert** = volle außergerichtliche Forderung (bei eigener Quote: quotiert, siehe KW-03) → Basis der Geschäftsgebühr Nr. 2300, wird als Nebenforderung eingeklagt (Step 9, bleibt).
  - **Gerichtlicher Streitwert** = offener Rest nach Regulierung (+ SG-Mindestbetrag) → wird **nur** als Gegenstandswert in der Klageschrift angegeben (nach dem Rubrum, `{{GEGENSTANDSWERT}}` — das passt heute schon).
  - **Konkret:** Das „RVG gerichtlich"-Anzeige-Duplikat (`rvgData`) in Step 8/10 samt irreführendem Label **entfernen**; nur `rvg_ausserg` (Nr. 2300) bleibt als Gebühren-Berechnung. Das wirkungslose `rvg_override`-Feld (Kachel 6) mit entfernen oder auf `rvg_ausserg` umleiten. Step 8/10 zeigen künftig: gerichtlicher Streitwert (Zahl, ohne Gebühren) + Nr. 2300 auf vorgerichtlichem Streitwert.

### - [x] KW-14 — `klage_generiert`-Ereignis immer ohne Positionen — behoben `d42f09eb`, Session 1 2026-07-17
- **Datei:** `backend/routers/klage_routes.py:1399` (`_p14_schaden.items()` — `Schadenposition` ist dataclass ohne `.items()`, `models/schaden.py:167`; AttributeError wird von der Best-Effort-Klammer geschluckt)
- **Auswirkung:** Die P1.4-Instrumentierung bucht das `klage_generiert`-Ereignis seit jeher **ohne Positionen** → Positions-Dashboard/Eskalationslogik sehen die Klage nicht positionsscharf. Stiller Fehler, exakt das Muster aus [[feedback_pruefe_akte_normalisierung]]/Personenschaden-Drift.
- **Fix-Richtung:** Dataclass korrekt serialisieren (`asdict()` bzw. vorhandenen Serialisierer nutzen); Test, dass das Ereignis Positionen trägt; Best-Effort-Klammer soll `logger.error` statt still schlucken.

---

## P2 — Rubrum & Grammatik

### - [ ] KW-15 — Rubrum-Rolle immer feminin
- **Datei:** `backend/word/klage_service.py:1138` (`"– Beklagte{nr_suffix} –"`); Kläger-Seite unterscheidet korrekt (`:1073–1080`)
- **Auswirkung:** Männlicher Fahrer als Beklagter → „– Beklagte –" statt „– Beklagter –".
- **Fix-Richtung:** Genus aus `beteiligte.anrede` ableiten (sAnrede-Mapping existiert); Firmen bleiben „Beklagte".

### - [ ] KW-16 — Vertreter-Grammatik im Rubrum
- **Datei:** `backend/word/klage_service.py:1121–1126`
- **Auswirkung:** (a) Artikel hart „den": „vertreten durch **den Geschäftsführerin** Frau …". (b) Anrede-Heuristik prüft nur die Funktion, nicht den Namen — Vertreterin mit leerer Funktion wird „Herrn".
- **Fix-Richtung:** Artikel aus Funktions-Genus ableiten; Anrede aus dem Vertreter-Datensatz statt Heuristik.

### - [ ] KW-17 — Mehrere Kläger: Numerus-Fehler, Vorsteuer ignoriert
- **Datei:** `backend/word/klage_service.py:940` (`kl_nom="Die Kläger"`), `:1272` („macht"), `:1291` („ist Eigentümer"), `:942` (falsche Flexion + Vorsteuer bei mehreren Klägern immer „nicht vorsteuerabzugsberechtigt"); `sg_text_builder.py:94/98` („hat … erlitten")
- **Auswirkung:** „Die Kläger macht … geltend", „Die Kläger ist Eigentümer" — Singular-Verben bei Plural-Subjekt; Vorsteuerabzug wird ignoriert.
- **Fix-Richtung:** Partei-Objekt mit Numerus (Verbesserung V3): Verbformen aus dem Objekt, nicht hart im Text.

### - [ ] KW-18 — Rubrum ohne Kläger möglich
- **Datei:** `backend/word/klage_service.py:931–937, 1061–1088` (Klägerblock nur aus `cfg.beklagte` mit `rolle_klage=="klaeger"`; kein Fallback auf `akte_daten["mandant"]`, `mandant_name` `:917` ungenutzt)
- **Auswirkung:** Fehlt der Kläger-Beteiligten-Eintrag, bleibt das Rubrum bis auf „Prozessbevollmächtigte:" leer.
- **Fix-Richtung:** Fallback auf Mandant + harte Sperre/Fehlermeldung wenn kein Kläger ermittelbar.

### - [ ] KW-19 — Generieren mit 0 Beklagten möglich
- **Datei:** `frontend/src/sections/KlageWizard.jsx:1528` (`gesperrt` prüft Beklagte nicht)
- **Auswirkung:** Alle Beklagten abgewählt → Step 2 warnt zwar, blockiert aber nichts; Generieren-Button aktiv, Anträge „Die Beklagte wird verurteilt…" ohne existierende Beklagte.
- **Fix-Richtung:** `beklagteG.length === 0` in die Sperr-Bedingungen von Step 10 aufnehmen.

### - [ ] KW-20 — Beklagten-Nummerierung Sachverhalt ≠ Rubrum
- **Datei:** `frontend/src/sections/KlageWizard.jsx:106–141` (`buildSachverhaltText`: eigene Reihenfolge Versicherung→Fahrer→Halter mit eigener Zählung) vs. StepRubrum `:457–469` (Array-Reihenfolge). Zudem: `hatFahrer` aus `fahrGegnerName` unabhängig von Beklagten-Auswahl; angehakte Nicht-Halter-Privatperson fehlt im Sachverhalt; Versicherung mit `ist_halter=1` doppelt gezählt (Filter `:109/110` überschneiden sich)
- **Auswirkung:** „Beklagte zu 2)" im Rubrum, aber im Sachverhalt nicht erwähnt oder anders nummeriert.
- **Fix-Richtung:** Eine gemeinsame Funktion liefert die kanonische Beklagten-Liste (Reihenfolge + Nummern) für Rubrum UND Sachverhalt.

### - [ ] KW-21 — Rechtsform-Heuristik matcht Substrings
- **Datei:** `backend/word/klage_service.py:664–686` (`"UG" in n` trifft „FAHRZEUGBAU"; `" AG"`/`"SE "` nur mit Leerzeichen → „…Versicherungs-AG" fällt durch)
- **Auswirkung:** Falsche Vertreter-Bezeichnung („gesetzlichen Vertreter" statt „Vorstand") bzw. falsche Rechtsform-Erkennung.
- **Fix-Richtung:** Wortgrenzen-Regex (`\b(GmbH|AG|SE|UG|KG|OHG|e\.K\.)\b` + Suffix-Varianten „-AG").

---

## P3 — Wizard-State / verlorene bzw. veraltete Texte

### - [ ] KW-22 — Anträge-Text stale nach Positions-/SG-Änderung; Feststellungs-Checkboxen ohne Textwirkung
- **Datei:** `frontend/src/sections/KlageWizard.jsx:1832–1834` (nur generieren wenn leer), `:1762–1765` (Klagebetrag als Fließtext im Antrag), `:1862–1865` (Checkbox-onChange ruft `regenerieren()` nicht)
- **Auswirkung:** Position in Step 5 abgewählt (5.000 → 3.000 €) → Zusammenfassung zeigt 3.000 €, `antraege_override` fordert 5.000 €. Feststellungsantrag anhaken ändert die Vorschau nicht. **Derzeit durch KW-01 maskiert — wird mit dessen Fix akut.**
- **Fix-Richtung:** Zentrales Dirty-Tracking (Verbesserung V7): Badge „Text veraltet — Eingaben haben sich geändert" mit Wahl Neu generieren/Behalten; Checkboxen triggern Regeneration (bzw. Backend-Flags als alleinige Quelle nutzen und die Anträge dort zusammensetzen).

### - [x] KW-23 — Platzhalter kann im finalen Antragstext verbleiben — behoben `a6711c2d` (Guard + Warnblock in Step 10), Session 1 2026-07-17
- **Datei:** `frontend/src/sections/KlageWizard.jsx:1744/1807` (Platzhalter immer eingefügt), `:2010–2015` (Ersetzung nur in Step 9), `:1528` (Generieren-Guard prüft Platzhalter nicht)
- **Auswirkung:** Step 6 neu generieren → direkt via Fortschrittsbalken zu Step 10 → Generieren: „[Außergerichtliche Anwaltsgebühren – wird in Schritt 9 ergänzt]" steht als nummerierter Klageantrag im Text. **Derzeit durch KW-01 maskiert.**
- **Fix-Richtung:** `gesperrt`-Guard in Step 10: `antraegeText.includes(PLACEHOLDER)` → roter Warnblock + Sperre. Quick Win, muss zeitgleich mit KW-01 kommen.

### - [ ] KW-24 — Step-9-Änderungen nach Erst-Ersetzung wirkungslos
- **Datei:** `frontend/src/sections/KlageWizard.jsx:2010–2015` (Ersetzung nur solange Platzhalter vorhanden), `:2003–2007` (Remount-Effect überschreibt `wizardGebuehrenText` ohne Manuell-Schutz), `KlageSection.jsx:560–574` (`wizardGebuehrenText` wird nie gesendet)
- **Auswirkung:** Nach der ersten Ersetzung sind „Bereits gezahlt"-Änderungen und manuelle Edits am Gebühren-Antrag wirkungslos für den Anträge-Text; das DOCX fordert den alten Betrag.
- **Fix-Richtung:** Gebühren-Antrag nicht per String-Ersetzung „einbrennen", sondern als eigenes Segment führen, das beim Generieren zusammengesetzt wird; Dirty-Tracking wie KW-22.

### - [ ] KW-25 — Step 3: manuelle Sachverhalt-Edits beim Remount überschrieben
- **Datei:** `frontend/src/sections/KlageWizard.jsx:489–503` (`prevAutoRef` lokal in `StepAktLeg`, beim Unmount weg → Remount überschreibt bedingungslos)
- **Auswirkung:** Manuell ergänztes Beweisangebot in Step 3 → zu Step 4 → zurück zu Step 3 → Ergänzung kommentarlos weg; betrifft genau den `sachverhalt_override`-Text der Klageschrift.
- **Fix-Richtung:** Manuell-Flag/prevAuto in den Section-State heben (wie beim gefixten `wizardVerzugManuell`), oder Dirty-Tracking V7.

### - [ ] KW-26 — Fortschrittsbalken umgeht kannWeiter()-Sperren
- **Datei:** `frontend/src/sections/KlageWizard.jsx:2271–2275` (kannWeiter nur Steps 1+5) vs. `:205` (Balken: alles ≤ maxStep klickbar)
- **Auswirkung:** Positionen in Step 5 abwählen → „Weiter" gesperrt, Klick auf Kreis „6" geht trotzdem; Auslöser für KW-23.
- **Fix-Richtung:** Balken-Klick durch dieselbe kannWeiter-Prüfung leiten (kumulativ bis Ziel-Step).

### - [ ] KW-27 — Gericht-Persistenz: Rückweg tot
- **Datei:** `backend/routers/klage_routes.py:1442–1451` (PUT speichert `beteiligte` mit `rolle='gericht'`) vs. `:946` (`alle_bet` vorab auf klaeger/beklagter gefiltert → Prio-1a-Loop `:998–1009` findet nie etwas; zweiter Filter `:1034` tot)
- **Auswirkung:** Manuell gewähltes Gericht wird gespeichert, aber beim nächsten Öffnen kommt wieder der RA-MICRO-/Unfallort-Vorschlag; die Auto-Bestätigung (`quelle === "akte"`) greift nie.
- **Fix-Richtung:** Gericht-Zeile vor dem Rollen-Filter lesen — oder strukturell: Gericht als eigenes Feld an `unfallakte` statt Missbrauch von `beteiligte` (Verbesserung V9).

### - [ ] KW-28 — Verzugsdokument-Auswahl ohne Wirkung (Placebo)
- **Datei:** `frontend/src/sections/KlageSection.jsx:165/223`, `KlageWizard.jsx:1388–1402` (`verzugDokId` wird nie gesendet, übernimmt auch nicht das Dokumentdatum)
- **Auswirkung:** Nutzer wählt das verzugsbegründende Schreiben aus — ohne jeden Effekt auf Datum, BEWEIS-Zeile oder Dokument.
- **Fix-Richtung:** Auswahl übernimmt das Dokumentdatum in „Datum des Schreibens" und sendet die Doc-ID als BEWEIS-/Anlagen-Referenz — oder das Feld entfernen.

### - [ ] KW-29 — Vertreter-Lookup-Modal öffnet wiederholt unaufgefordert
- **Datei:** `frontend/src/sections/KlageSection.jsx:250–263, 349–360` (Auto-Lookup öffnet Modal je Firma; Guard prüft nur `laden`, nicht „bereits nachgeschlagen"; jede `setBek`-Änderung triggert erneut)
- **Auswirkung:** Modal-Spam beim Tab-Aufruf; bewusst geschlossene Modals kommen nach jeder Beteiligten-Änderung wieder.
- **Fix-Richtung:** Auto-Lookup nur still cachen, Modal nur auf expliziten Klick; „dismissed"-Set je Sitzung.

---

## P4 — Textqualität / Kleinkram / toter Code

### - [ ] KW-30 — Leere Felder erzeugen kaputte Sätze
- **Datei:** `backend/word/klage_service.py:1271–1277` („…Verkehrsunfall vom 01.02.2026 in  geltend." bei leerem Unfallort), `:1233/1243` (Feststellungsanträge: „aus dem Unfallereignis vom  noch entstehen" bei leerem Unfalltag)
- **Fix-Richtung:** Bausteine mit bedingten Segmenten („ in {ort}" nur wenn gesetzt); Pflichtfeld-Warnung in Step 10.

### - [ ] KW-31 — `sachverhalt_override` zerstört Absatzstruktur
- **Datei:** `backend/word/klage_service.py:688–714` (Nicht-BEWEIS-Blöcke bis zum nächsten BEWEIS zu einem Absatz verkettet; BEWEIS-Zeile mit einfachem `\n` wird Fließtext — Split nur auf `\n\n`)
- **Fix-Richtung:** Jede Leerzeile = Absatz; BEWEIS-Erkennung zeilenweise.

### - [ ] KW-32 — Verzug-Abschnitt ohne Nummer/Überschrift
- **Datei:** Template-Reihenfolge `{{SCHMERZENSGELD}} {{VERZUG}} {{VORGERICHTLICHE_KOSTEN}}`; Nummerierung springt 4 → 5 (SG) → 5/6 (VK), Verzug hängt unnummeriert dazwischen (`klage_service.py`, Abschnittszähler `5 + int(mit_sg)`)
- **Fix-Richtung:** Laufender Abschnittszähler statt Arithmetik; Verzug bekommt eigene Nummer+Überschrift.

### - [ ] KW-33 — SG-Beweisantritt nicht als BEWEIS formatiert
- **Datei:** `backend/word/klage_service.py:1421` (`_p(sg_beweis, einzug=True)` statt `_beweis()`)
- **Fix-Richtung:** `_beweis()` verwenden (fett + Tabstopp, wie überall sonst).

### - [ ] KW-34 — RVG-Antrag über „0,00 €" möglich
- **Datei:** `backend/word/klage_service.py:989–991 + 1248` (`max(0.0, …)` → Antrag „…weitere 0,00 € … zu zahlen" samt VK-Abschnitt)
- **Fix-Richtung:** Bei 0 € Antrag + VK-Abschnitt weglassen.
- **Neu aus S2 (KW-03, hier mitzubehandeln):** Klammer-Randfall Fall B — wenn Zahlungen den quotierten Anspruch übersteigen (`klagebetrag` klemmt auf 0), nennt der Fall-B-Differenz-Satz eine geringere Zahlungssumme als real geleistet (`zahlungen_anzeige = ersatzfaehig − klagebetrag`, arithmetisch konsistent, aber juristisch schief). Zusammen mit der 0-€-Antrags-Frage lösen.

### - [ ] KW-35 — RVG-Fallback nutzt SQLite-Importdatum
- **Datei:** `backend/word/klage_service.py:963–965` (`erstellt_am` statt `_rvg_anlagedatum` aus `klage_routes.py:48–85`)
- **Auswirkung:** Alt-Akte, 2025 importiert → fälschlich 2025er-Gebührentabelle. Nur relevant wenn `cfg.rvg` fehlt (Legacy-Pfad).
- **Fix-Richtung:** `_rvg_anlagedatum` durchreichen oder Fallback entfernen (zusammen mit KW-08).

### - [ ] KW-36 — Haftungsquote int-Truncation
- **Datei:** `backend/word/klage_service.py:1394/1410` (`int(hq)`/`int(100-hq)`: 66,67 % → „66 %" + „33 %" = 99)
- **Fix-Richtung:** Runden statt truncaten; Summe = 100 sicherstellen.

### - [ ] KW-37 — RVG-Faktor „(1.3)" mit Punkt statt Komma
- **Datei:** `backend/word/klage_service.py:1478` (die tote Alt-Funktion `:386` machte den Komma-Replace korrekt)
- **Fix-Richtung:** Komma-Format wie überall.

### - [ ] KW-38 — Positions-Key-Vertrag ungesichert
- **Datei:** `frontend/src/sections/KlageSection.jsx:275–284, 407–416` (`_KEY_MAP` nur Fahrzeugschaden-Parser-Keys; Zahlungen auf nicht-mappende Keys senken `_unassigned`, reduzieren aber keine Position)
- **Auswirkung:** Offener Betrag/Klagebetrag zu hoch. Verwandter Bug-Typ war schon einmal da (`sonstiges_wdm_X ≠ extra_wdm_ssX`, siehe [[unfallakten-key-mismatch-bug]]).
- **Fix-Richtung:** Vollständiges Key-Mapping + Test, der alle `regulierung_positionen.position_key`-Werte gegen die Wizard-Keys prüft; langfristig V2 (offen-je-Position im Backend).

### - [x] KW-39 — Vorsteuer-Inkonsistenz Nebenkosten — behoben `e19edc64`, Session 2 2026-07-17 (vorgezogen aus S6, weil das KW-04-Review die Divergenz als aktiven Widerspruch Tabelle↔Antrag nachwies)
> **Umsetzung:** `pos_definitionen` berechnet die fünf Nebenkosten-Keys (Mietwagen/SV/Abschlepp/Stand/An-Abmeldung) jetzt via importierter `_netto_oder_brutto`-Logik (echte Wiederverwendung, keine Kopie); `kostennb` behielt seine äquivalente eigene Weiche.
- **Datei:** `backend/routers/klage_routes.py:783–794` (SV-Kosten/Mietwagen/Abschlepp/Stand/An-Abmeldung immer brutto, nur `fahrzeugschaden`/`kostennb` vorsteuer-bewusst) vs. `forderungsschreiben_wv.py:715–737, 798–803` (Tabelle rechnet netto)
- **Auswirkung:** Beim Vorsteuer-Mandanten: Antrag brutto, Tabelle netto → Widerspruch.
- **Fix-Richtung:** `pos_definitionen` vorsteuer-bewusst machen (dieselbe `_netto_oder_brutto`-Logik).

### - [ ] KW-40 — Sammelposten Kleinkram / toter Code
- `klage_service.py`: toter Code entfernen (`_xml_absatz`, `_xml_leerzeile`, `_xml_tabelle_schaden`, `_xml_tabelle_rvg`, `_xml_antrag`, `_tab_rechts`, `_VORLAGE_FS`, `kanzlei_str`, `mandant_anschr`, Top-Level `import zipfile`)
- `klage_service.py:808`: nicht gemappte position_keys landen als „Extra Wdm Ss1" in der Zahlungs-Tabelle
- `klage_service.py:561`: `_merge_split_placeholders` läuft nur über `{{GEGENSTANDSWERT}}`, nicht über die 15 Block-Platzhalter — erneutes Speichern der Vorlage in Word kann Platzhalter zersplittern → bleibt roh im Dokument (Absicherung: Render-Smoke-Test V10)
- `klage_service.py:1177–1178`: RVG-Antragsnummer wird bei `antraege_override` als „vorletzter nummerierter Antrag" geraten → VK-Abschnitt kann auf falsche Nummer verweisen
- `klage_service.py:1151/1196`: roher Tab in `<w:t>` statt `<w:tab/>`
- `klage_service.py:888–890`: GHPV-Auswahl filtert weder `checked` noch `nicht_partei` → Schadennummer ggf. vom falschen Beteiligten
- `KlageWizard.jsx:1160–1165`: „Text übernehmen" im Einwände-Panel hängt Block doppelt an (append statt ersetzen); negative „Kürzungen" (reguliert > gefordert) reduzieren die Summe (`:988–989`)
- `KlageWizard.jsx:596–607` vs. `KlageSection.jsx:459–465`: Mandant→Kläger-Ersetzung dupliziert (Drift); „Der Mandant" → „Der Klägerin" (Artikel bleibt)
- `KlageWizard.jsx:1515–1516, 1326`: NaN-Anzeige bei nicht-numerischem RVG-Override (`fmtEuro(NaN)`)
- Step 3 „ungeklaert": Warnkarte sagt „Kein Text wird generiert", `sachverhaltText` geht aber als Override raus — Anzeige ≠ Payload
- Tote Fracht im Vertrag: gesendet-nie-gelesen (`positionen[].vorschlag/betragOriginal`, `gericht.quelle/adressnr/telefon/email`, `beklagte[].vorschlag_beklagter`); GET-Felder nie genutzt (`reg_agg`, `gericht_quelle`); Backend liest nie Gesendetes (`aktivlegitimation_text_override`, `mandant_ist_fahrer`)

---

## Konzeptionelle Verbesserungen (aus dem Review, priorisiert)

| # | Idee | Behebt strukturell |
|---|---|---|
| V1 | **Overrides-Vertrag vereinheitlichen** (eine Ebene statt `klage_config` vs. `overrides`, oder explizite Merge-Whitelist) + **Vertragstest** „jedes gesendete Feld wird gelesen, jedes gelesene wird gesendet" | KW-01, KW-40-Fracht |
| V2 | **„Offen je Position" ins Backend** (existiert 3× dupliziert im Frontend, 0× im Backend) — speist Antrag, Tabelle, Differenz-Satz, Kacheln und Wizard aus einer Quelle | KW-04, KW-08, KW-38 |
| V3 | **Partei-Objekt mit Genus/Numerus** (`bez`, Artikel-Formen, Verbform Sg/Pl) + Gesamtschuldner-Baustein statt verstreuter Ternaries | KW-06, KW-15–KW-17 |
| V4 | **Anlagen-Manager**: fortlaufende K-Nummern zentral | KW-12 |
| V5 | **Datumsvertrag**: ISO im Transport, `_fmt_datum` nur im Renderer | KW-09, KW-10a |
| V6 | **RVG-Objekte mit Kontext** (`{zweck, streitwert, faktor}`); Faktor- und Euro-Felder getrennt; nur noch EINE Gebühren-Berechnung (Nr. 2300), gerichtlicher Streitwert als reine Zahl | KW-02, KW-13 |
| V7 | **Zentrales Dirty-Tracking** für Auto-Texte (`{text, istManuell, basisHash}` im Section-State; Badge „veraltet" mit Neu-generieren/Behalten) statt vier prevAutoRef-Varianten | KW-22–KW-25 |
| V8 | **Legacy-Button entfernen**; SG-Position und mitSG gegenseitig ausschließen | KW-07, KW-08 |
| V9 | **Gericht als eigenes Feld** an `unfallakte` statt `beteiligte.rolle='gericht'` | KW-27 |
| V10 | **Render-Smoke-Test** (kein `{{` im Ergebnis-XML) + **Golden-File-Matrix** (mit/ohne SG × 1/2 Beklagte × eigentum/finanziert/geleast × Overrides an/aus) | Regressionsschutz für alles |
| V11 | Textbausteine als echte Templates (benannte Variablen) statt f-String-Ketten im 740-Zeilen-Monolithen `generiere_klageschrift` | Wartbarkeit, Grammatik-Varianten |

---

## Session-Aufteilung (Vorschlag)

| Session | Inhalt | Begründung |
|---|---|---|
| **1** | KW-01 + KW-23 (zusammen!), KW-02, KW-14 | Verlorene Eingaben + falsche Beträge + Ereignis-Fix; kleinster Eingriff, größte Wirkung |
| **2** ✅ | KW-03, KW-04, KW-05, KW-07, KW-11 + KW-39 (vorgezogen) — erledigt 2026-07-17, Branch `klage-wizard-fixes-s2` | Konsistente Beträge & Tatsachenbehauptungen im DOCX. Baseline: Backend 204f/1000p (null neue), Frontend 122 + Build. Neues DOCX-Direkttest-Muster `test_klage_service_docx.py`. |
| **3** | KW-06, KW-15–KW-21 (Rubrum/Grammatik-Cluster) | Am besten als V3-Refactoring (Partei-Objekt) in einem Zug |
| **4** | KW-09, KW-10, KW-12, KW-13, KW-08 | Datum/RVG/Anlagen; V5+V6 |
| **5** | KW-22, KW-24–KW-29 (Wizard-State/UX) | V7 Dirty-Tracking als gemeinsames Muster |
| **6** | KW-30–KW-40 + V10 Golden-File-Matrix | Politur + Regressionsschutz |

> **Grundsatzentscheidungen (RA Schatz, 2026-07-17) — alle getroffen:**
> 1. **KW-03 Haftungsquote:** Zwei Fälle. Fall A (gegnerische Quote) = nur Darstellung in der RW, Beträge 100 %. Fall B (eigene Quote) = Klagebetrag quotiert: **erst quotieren, dann Zahlungen abziehen**; SG-Mindestbetrag NICHT auto-quotiert; Quote gilt auch für den vorgerichtlichen Streitwert (Nr.-2300-Basis). Schadentabelle immer 100 %. Step 7 bekommt die Fall-Auswahl.
> 2. **KW-08 Legacy-Button:** entfernen — der Wizard ist der einzige Weg.
> 3. **KW-13 Streitwerte:** keine gerichtliche Gebührenberechnung (Kostenfestsetzungs-Thema, nicht Klage). Gerichtlicher Streitwert (= offener Rest) nur als Gegenstandswert-Angabe in der Klageschrift; „RVG gerichtlich"-Anzeige-Duplikat entfernen.
