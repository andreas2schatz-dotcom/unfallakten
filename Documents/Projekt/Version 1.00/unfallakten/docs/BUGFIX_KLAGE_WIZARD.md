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

> **PRD-33 KOMPLETT (2026-07-19):** Sessions 1–6 abgeschlossen, alle 40 KW-Bugs behoben oder mit Begründung als entfallen dokumentiert (KW-36 teilweise). Die V10-Golden-File-Matrix (24 Kombinationen) + Render-Smoke-Test sind als dauerhafter Regressionsschutz in der Suite verankert. FF-Merge von Session 6 (`klage-wizard-fixes-s6`) nach `main` nach Freigabe ausstehend.

## Status-Übersicht

| ID | Prio | Datei | Kurztitel | Status |
|---|---|---|---|---|
| KW-01 | P0 | `backend/routers/klage_routes.py:1170` | Anträge-Override + Feststellungsanträge gehen komplett verloren | ✅ behoben `e668f50f` |
| KW-02 | P0 | `frontend/src/sections/KlageWizard.jsx:1954` | RVG-Faktor landet im Euro-Override → „weitere 1,50 €" | ✅ behoben `b1c1fbfb` |
| KW-03 | P0 | `backend/word/klage_service.py:1409` | Haftungsquote wird nie angewendet, Text behauptet Kürzung | ✅ behoben S2 (BE `ebbf7c1b`+`3947fc21`, FE `ff859255`+`db9dcfe7`+`ce18d869`) |
| KW-04 | P0 | `backend/word/klage_service.py:1338` | Antrag 1 ≠ Schadentabelle ≠ Differenz-Satz (3 Rechenwege) | ✅ behoben `974cecdd`+`f5a29ad7` |
| KW-05 | P0 | `backend/word/klage_service.py:1289` | Einleitung behauptet Eigentum trotz Leasing/Finanzierung | ✅ behoben `322fb9a1`+`633b6c95` |
| KW-06 | P1 | `backend/word/klage_service.py:1208` | Mehrere Beklagte: Singular-Anträge, kein Gesamtschuldner | ✅ behoben S3 (BE `caab700e`, FE `cab35cb9`) |
| KW-07 | P1 | `backend/routers/klage_routes.py:802` | Schmerzensgeld doppelt einklagbar (Position + mitSG) | ✅ behoben `5639c72e`+`bb64829b` |
| KW-08 | P1 | `frontend/src/sections/KlageSection.jsx:380` | Legacy-Button klagt vollen statt offenen Betrag ein | ✅ behoben S4 (FE `1dddf5ae`, BE `8da95f62`) |
| KW-09 | P1 | `backend/word/klage_service.py:972` | Zins-/Verzugsdatum erscheint im ISO-Format | ✅ behoben S4 (BE `36ca8ec6`, FE `69863dd3`+`44f26a81`) |
| KW-10 | P1 | `frontend/src/sections/KlageSection.jsx:581` | Verzugsdatum-State-Split (3 Stellen, 3 Werte) + Schreibdatum als Verzugseintritt | ✅ behoben S4 `0d867274` |
| KW-11 | P1 | `backend/word/forderungsschreiben_wv.py:807` | Unkostenpauschale nicht abwählbar (`or 30.0` + tote Weiche) | ✅ behoben `5cb2acc5`+`fb695b6b` |
| KW-12 | P1 | `backend/word/klage_service.py:478` | Anlagen-Kollision: zwei Dokumente heißen „K1" | ✅ behoben S4 `2076e83e` |
| KW-13 | P1 | `frontend/src/sections/KlageSection.jsx:317` | „RVG gerichtlich" ist außergerichtliche Gebühr; `rvg_override` wirkungslos | ✅ behoben S4 `9cef9655`+`3d0b22c3` |
| KW-14 | P1 | `backend/routers/klage_routes.py:1399` | `klage_generiert`-Ereignis immer ohne Positionen (geschluckter AttributeError) | ✅ behoben `d42f09eb` |
| KW-15 | P2 | `backend/word/klage_service.py:1138` | Rubrum-Rolle immer feminin („– Beklagte –") | ✅ behoben S3 `2c39550e` |
| KW-16 | P2 | `backend/word/klage_service.py:1121` | Vertreter-Grammatik („den Geschäftsführerin"), Anrede-Heuristik nur auf Funktion | ✅ behoben S3 `2c39550e` |
| KW-17 | P2 | `backend/word/klage_service.py:940` | Mehrere Kläger: Numerus-Fehler, Vorsteuer ignoriert | ✅ behoben S3 `9fec1983`+`b16321f0` |
| KW-18 | P2 | `backend/word/klage_service.py:1061` | Rubrum ohne Kläger möglich (kein Mandant-Fallback) | ✅ behoben S3 `0778af2e` |
| KW-19 | P2 | `frontend/src/sections/KlageWizard.jsx:1528` | Generieren mit 0 Beklagten möglich | ✅ behoben S3 `7e27f0c5` |
| KW-20 | P2 | `frontend/src/sections/KlageWizard.jsx:106` | Beklagten-Nummerierung Sachverhalt ≠ Rubrum; Nicht-Halter-Person fehlt | ✅ behoben S3 `8b23efbe`+`8e10749c` |
| KW-21 | P2 | `backend/word/klage_service.py:664` | Rechtsform-Heuristik matcht Substrings („UG" in „FAHRZEUGBAU") | ✅ behoben S3 `cbc41c13` |
| KW-22 | P3 | `frontend/src/sections/KlageWizard.jsx:1832` | Anträge-Text stale nach Positions-/SG-Änderung; Feststellungs-Checkboxen ohne Textwirkung | ✅ behoben S5 `4a4300e3` |
| KW-23 | P3 | `frontend/src/sections/KlageWizard.jsx:1744` | Platzhalter „[Außergerichtliche Anwaltsgebühren …]" kann im Antragstext verbleiben | ✅ behoben `a6711c2d` |
| KW-24 | P3 | `frontend/src/sections/KlageWizard.jsx:2010` | Step-9-Änderungen nach Erst-Ersetzung wirkungslos; `wizardGebuehrenText` nie gesendet | ✅ behoben S5 `0a2d3816`+`52d33252` |
| KW-25 | P3 | `frontend/src/sections/KlageWizard.jsx:489` | Step 3: manuelle Sachverhalt-Edits beim Remount überschrieben | ✅ behoben S5 `00d4c278` |
| KW-26 | P3 | `frontend/src/sections/KlageWizard.jsx:2271` | Fortschrittsbalken umgeht kannWeiter()-Sperren | ✅ behoben S5 `34c613ca` |
| KW-27 | P3 | `backend/routers/klage_routes.py:946` | Gericht-Persistenz: Rückweg tot (`rolle='gericht'` wird vorab weggefiltert) | ✅ behoben S5 `6752215e` |
| KW-28 | P3 | `frontend/src/sections/KlageSection.jsx:165` | Verzugsdokument-Auswahl ohne jede Wirkung (Placebo) | ✅ behoben S5 `a332bab4`+`2b9e1a45` |
| KW-29 | P3 | `frontend/src/sections/KlageSection.jsx:250` | Vertreter-Lookup-Modal öffnet wiederholt unaufgefordert | ✅ behoben S5 `e3c1ab68` |
| KW-30 | P4 | `backend/word/klage_service.py:1271` | Leere Felder erzeugen kaputte Sätze („…Unfall vom … in  geltend") | ✅ behoben S6 (BE `ebef927d`, FE `efc64588`) |
| KW-31 | P4 | `backend/word/klage_service.py:688` | `sachverhalt_override` zerstört Absatzstruktur des Nutzers | ✅ behoben S6 `449c5f0f`+`351e79e6` |
| KW-32 | P4 | `backend/word/klage_service.py:1440` | Verzug-Abschnitt ohne Nummer/Überschrift, Nummerierungssprung | ✅ behoben S6 `30d4fbc0` |
| KW-33 | P4 | `backend/word/klage_service.py:1421` | SG-Beweisantritt nicht als BEWEIS formatiert | ✅ behoben S6 `10febac9` |
| KW-34 | P4 | `backend/word/klage_service.py:989` | RVG-Antrag über „0,00 €" möglich | ✅ behoben S6 `1ad1a93f`+`b2e0ab16` |
| KW-35 | P4 | `backend/word/klage_service.py:963` | RVG-Fallback nutzt SQLite-Importdatum statt RA-MICRO-Anlagedatum | ✅ behoben S4 `8da95f62` (mit KW-08 vorgezogen) |
| KW-36 | P4 | `backend/word/klage_service.py:1394` | Haftungsquote int-Truncation: 66,67 % → „66 % + 33 % = 99" | ✅ S6 (Truncation/Guard entfällt, Rundungs-Parität `3e87ff86`) |
| KW-37 | P4 | `backend/word/klage_service.py:1478` | RVG-Faktor „(1.3)" mit Punkt statt Komma | ✅ behoben S6 `10febac9` |
| KW-38 | P4 | `frontend/src/sections/KlageSection.jsx:275` | Positions-Key-Vertrag ungesichert (`_KEY_MAP` nur Fahrzeugschaden) | ✅ behoben S6 `13d7eefc`+`c83e23d8` |
| KW-39 | P4 | `backend/routers/klage_routes.py:783` | Vorsteuer-Inkonsistenz Nebenkosten (Antrag brutto, Tabelle netto) | ✅ behoben `e19edc64` (S2 vorgezogen) |
| KW-40 | P4 | diverse | Sammelposten Kleinkram/toter Code (Details unten) | ✅ behoben S6 (BE `ba56cb1b`+`d7f81be0`, FE `efc64588`+`d0ceb920`) |

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

### - [x] KW-06 — Mehrere Beklagte: Anträge Singular, keine Gesamtschuldner-Formulierung — behoben BE `caab700e` + FE `cab35cb9`, Session 3 2026-07-18
> **Umsetzung:** Backend-Anträge (Zahlung/SG/Feststellung/RVG/Kosten) + VK-Abschnitt über neuen `bek_gram`-Helfer („Die Beklagten werden als Gesamtschuldner verurteilt…"); Einleitung jetzt EIN Satz je Beklagtem (Versicherung/Halter/Fahrer, genus-bewusst, Schadennummer nur bei erster Versicherung), Einzel-Versicherung byte-gleich zum Vorzustand. Bei 0 Beklagten entfällt der Einleitungssatz jetzt bewusst (statt eine nicht existente Partei zu behaupten) — der Zustand wird durch KW-19 im Wizard gesperrt. Frontend `baueAntraegeText`/`StepGebuehren.baueGebuehrenAntrag`/`EinwandePanel` auf `beklagtenGrammatik`/`versichererSuffix` umgestellt; hart kodiertes „(zu 1)" ersatzlos raus. Abschluss-Review-Fix `6774b443`: Insurer-Klassifikation `versicherung || (firma && !ist_halter)` — Firmen-Halter bekommt Halter-Satz, versichererSuffix/hq-100-Referenz überspringen ihn.
- **Datei:** `backend/word/klage_service.py:1208, 1216–1251` (Anträge), `:1279–1283` (Einleitung); nur Kostenantrag `:1254` und VK-Abschnitt `:1493` pluralisieren
- **Auswirkung:** Fahrer + Versicherung als 2 Beklagte (vom System via synthetischem GHPV-Eintrag aktiv angeboten, `klage_routes.py:948–980`) → Zahlungsantrag benennt nicht, wer verurteilt werden soll; „als Gesamtschuldner" fehlt vollständig.
- **Fix-Richtung:** Numerus-bewusste Antragsbausteine („Die Beklagten werden als Gesamtschuldner verurteilt, an …"); siehe Verbesserung V3 (Partei-Objekt). Frontend-Pendant: `baueAntraegeText()` in KlageWizard.jsx hat dasselbe Problem (`(zu 1)` hart, `EinwandePanel:981`, `StepGebuehren:1928`).

### - [x] KW-07 — Schmerzensgeld doppelt einklagbar — behoben `5639c72e` (BE) + `bb64829b` (FE), Session 2 2026-07-17
> **Umsetzung:** Backend schließt bei `mit_schmerzensgeld=true` die SG-Position vor der checked-Filterung aus (wirkt auf Antrag 1, Gegenstandswert, Tabelle, Differenz-Satz). Frontend StepSchaden: SG-Zeile bei aktivem Toggle enthakt (echter Setter) + disabled + Hinweis; Toggle aus → wieder bedienbar.
- **Datei:** `backend/routers/klage_routes.py:802–803` (SG als bezifferte, checked Position), `backend/word/klage_service.py:957–959, 1026, 1213 ff.` (kein Ausschluss zu `mit_schmerzensgeld`), `forderungsschreiben_wv.py:804` (SG-Zeile in Tabelle)
- **Auswirkung:** SG-Position 2.000 € angehakt + „Schmerzensgeld geltend machen" mit Mindestbetrag 2.000 € → Gegenstandswert 4.000 € zu hoch, SG beziffert in Antrag 1 UND unbeziffert als eigener Antrag.
- **Fix-Richtung:** Gegenseitiger Ausschluss: bei `mit_schmerzensgeld=true` die SG-Position aus Antrag 1/Tabelle/Streitwert nehmen (oder Checkbox in Step 5 deaktivieren mit Hinweis).

### - [x] KW-08 — Legacy-Button klagt vollen statt offenen Betrag ein — behoben FE `1dddf5ae` + BE `8da95f62`, Session 4 2026-07-18
> **Umsetzung:** `generieren()`-Funktion + beide grauen „(veraltet)"-Buttons ersatzlos entfernt (−70 Zeilen); der Wizard ist der einzige Weg, `apiKlage.generieren` wird nur noch von `wizardGenerieren()` gerufen. Backend-Legacy-Pfad bleibt als Toleranz für fehlende cfg-Teile bestehen, aber mit korrektem RVG-Anlagedatum (KW-35). Zusätzlich S3-Follow-up: `except ValueError`→422 im Generier-Endpoint loggt jetzt `logger.warning` (+ assertLogs-Test).
- **Datei:** `frontend/src/sections/KlageSection.jsx:380` (`generieren()` sendet volle Forderungsbeträge), UI-Kacheln zeigen offenen Betrag (`posOffen`, `:292–315`)
- **Auswirkung:** Akte mit 5.000 € Forderung, 3.000 € reguliert → Kachel zeigt 2.000 €, Klick auf den alten „Klage generieren"-Button erzeugt Klage über 5.000 €.
- **Fix-Richtung — ENTSCHIEDEN (RA Schatz, 2026-07-17): Legacy-Button entfernen. Der Klage-Wizard ist der einzige Weg.** Backend-seitig prüfen, ob der Legacy-Codepfad (`generieren()` ohne Wizard-cfg, RVG-Fallback KW-35) mit entfernt werden kann.

### - [x] KW-09 — Zins-/Verzugsdatum erscheint im ISO-Format — behoben BE `36ca8ec6` + FE `69863dd3`/`44f26a81`, Session 4 2026-07-18
> **Umsetzung (V5):** Transportformat bleibt ISO, Formatierung nur im Renderer: Backend leitet `verzugsdatum` an der cfg-Grenze durch `_fmt_datum` (eine Zeile — wirkt auf Antrag 1, Verzugs-Abschnitt, BEWEIS). Frontend: neuer Helfer `fmtDatumDe` in `config/utils.js` als **wörtlicher Port** des echten `_fmt_datum` (Zweig-für-Zweig reviewt, inkl. Randfälle: einstellige ISO-Teile ungepolstert, DD.MM.YY→20YY; Diskriminator-Tests); eingesetzt in `baueAntraegeText`/`StepAntraege`/`StepGebuehren` (zinsDat), `StepZusammenfassung`, `buildVerzugAutoText`, BEWEIS-Hinweis, `oeffneWizard`-Verzugstext.
- **Datei:** `backend/word/klage_service.py:972` (`f"dem {verzugsdatum}"` roh), `:1440–1444`; Quelle ISO: `forderung_positionen.datum` Default `date('now')` (`models/forderung.py:184`); `_fmt_datum` existiert (`:1581`), wird hier nicht genutzt. Auch Wizard-Auto-Verzugstext übernimmt ISO wörtlich (`KlageSection.jsx:512–513`).
- **Auswirkung:** „…nebst Zinsen … seit dem 2026-05-04" statt „04.05.2026" im Schriftsatz.
- **Fix-Richtung:** Jede Datumsausgabe durch `_fmt_datum` leiten (ein Wrapper an der cfg-Grenze); Transportformat ISO beibehalten, Formatierung nur im Renderer (Verbesserung V5).

### - [x] KW-10 — Verzugsdatum-State-Split + Schreibdatum als Verzugseintritt — behoben `0d867274`, Session 4 2026-07-18
> **Umsetzung:** Alt-State `verzug` restlos entfernt; SSOT = `wizardVerzugDatum` (**Verzugseintritt**) + `wizardVerzugDokDatum` (**Schreibdatum**). cfg-Vertrag NEU: `verzugsdatum` = Eintritt, `verzug_schreiben_datum` = Schreibdatum; Backend-BEWEIS nutzt das Schreibdatum (Fallback auf Eintritt nur wenn Schreibdatum fehlt). `buildVerzugAutoText` exportiert mit korrigierter Semantik: **ohne Eintritt → „Verzug ist mit Rechtshängigkeit eingetreten."** (kein Fallback aufs Schreibdatum mehr — das war der juristische Kernfehler), ohne Schreibdatum → kein BEWEIS-Satz. Eintritt-Vorbelegung = `verzugEintrittDefault` (Schreibdatum **+ 14 Tage**, Kanzlei-Standardfrist — Entscheidung dem Nutzer im Abschlussbericht vorgelegt), editierbar in Kachel 5 + Step 8. Step 6/9 speisen sich jetzt beide aus `wizardVerzugDatum`.
- **Datei:** `frontend/src/sections/KlageSection.jsx:581` (Wizard-Pfad sendet `verzug`, nicht `wizardVerzugDatum` — Legacy-Pfad `:383` wurde gefixt, Wizard-Pfad nicht), `KlageWizard.jsx:2394` (Step 6: `wizardVerzugDatum || verzug`) vs. `:2441` (Step 9: nur `verzug`), `:1345–1348` (Step 8 setzt nur `wizardVerzugDatum`); inhaltlich `:1313–1318` + `klage_service.py:1440–1444`: Schreibdatum des Forderungsschreibens wird als Verzugseintritt behauptet (Verzug tritt erst nach Fristablauf ein)
- **Auswirkung:** Verzugsdatum in Step 8 korrigiert → cfg und Step 9 nutzen weiter den alten Wert; Hauptantrag, Gebühren-Antrag und Verzugs-Abschnitt können drei verschiedene Daten nennen. Zudem juristisch schief: „Der Verzug ist am {Schreibdatum} eingetreten" + „BEWEIS: Schreiben vom {selbes Datum}".
- **Fix-Richtung:** Ein einziger Verzugsdatum-State; `wizardGenerieren` sendet `wizardVerzugDatum || verzug`; Schreibdatum und Verzugseintritt als getrennte Felder (Eintritt = Fristablauf, editierbar).

### - [x] KW-11 — Unkostenpauschale nicht abwählbar — behoben `5cb2acc5`+`fb695b6b`, Session 2 2026-07-17
> **Wichtige Erkenntnis:** Die DB kann „nie angefasst" nicht von „explizit 0" unterscheiden (`schadenpositionen.unkostenpauschale` ist `NOT NULL DEFAULT 0.0`). Deshalb: `_baue_tabelle` hat jetzt None-Semantik (Key fehlt/None → 30-€-Default; expliziter Wert, auch 0.0 → Wert); DB-seitig bleibt das Bestandsverhalten byte-gleich (falsy → None → 30 €) an beiden Aufbau-Stellen (Klage-Router + `word_service`/Forderungsschreiben); die Abwahl-Wirkung kommt aus den Wizard-cfg-Positionen (KW-04-Filter setzt nicht-checked → explizit 0.0).
- **Datei:** `backend/word/forderungsschreiben_wv.py:807` (`_f("unkostenpauschale") or 30.0` macht aus 0.0 → 30 €), `backend/routers/klage_routes.py:1221–1222` (Abwahl-Weiche tot: `s()` gibt nie `None`)
- **Auswirkung:** Im Wizard abgewählte/genullte Unkostenpauschale steht trotzdem mit 30 € in der Schadentabelle → verstärkt KW-04.
- **Fix-Richtung:** `None`-Semantik sauber trennen (nicht gesetzt vs. explizit 0); Default-30 nur bei „nicht gesetzt".

### - [x] KW-12 — Anlagen-Kollision „K1" — behoben `2076e83e`, Session 4 2026-07-18
> **Umsetzung (V4):** Neuer `AnlagenZaehler` vergibt fortlaufende K-Nummern in **Dokumentreihenfolge** (AktLeg → Schaden/Gutachten → SG; Vorlagen-Platzhalterreihenfolge per zipfile verifiziert = Code-Baureihenfolge). Startwert = `_max_anlagen_nr` über die vier Override-Texte (Regex matcht „K1" UND „K 1" — Nutzer-Edits und Alt-Vorschautexte kollidieren nicht mehr). Nummern werden nur verbraucht, wenn wirklich ein Anlagen-BEWEIS entsteht (eigentum/Override: keine). `get_aktivlegitimation_text`/`_build_aktivlegitimation_xml` mit optionalem `anlage_nr`-Param; `baue_sg_abschnitt(…, anlage_nr="K 2")` — Default hält den Forderungsschreiben-Pfad byte-gleich. Schreibweise einheitlich „K n" (auch FE-Vorschau `buildVorschauText`). Häufigster Fall (eigentum) bleibt byte-gleich: Gutachten K 1, Atteste K 2 (Pin-Test).
- **Datei:** `backend/word/klage_service.py:478/486` (Freigabeerklärung/Sicherungsbedingungen = „Anlage K1") vs. `:1360` (Gutachten = „Anlage K 1"); `sg_text_builder.py:53` („K 2"); Schreibweise „K1" vs. „K 1" inkonsistent
- **Auswirkung:** Bei finanziertem Fahrzeug mit Freigabeerklärung sind zwei verschiedene Dokumente beide als K1 bezeichnet.
- **Fix-Richtung:** Anlagen-Manager: fortlaufende K-Nummern zentral vergeben, Registrierung beim Erzeugen jedes BEWEIS-/Anlagen-Bausteins (Verbesserung V4).

### - [x] KW-13 — „RVG gerichtlich" ist die außergerichtliche Gebühr; `rvg_override` wirkungslos — behoben `9cef9655`+`3d0b22c3`, Session 4 2026-07-18
> **Umsetzung (V6, lt. Entscheidung):** Keine gerichtliche Gebührenberechnung. Step 10 zeigt statt „RVG gerichtlich" jetzt „Gerichtlicher Streitwert (Gegenstandswert)" als reine Zahl + kombinierte Zeile „Nr. 2300 VV RVG außergerichtlich (SW: …)"; Step 8 zeigt keine RVG-Zeile mehr. `rvgOverride`-State + Kachel-6-Override-Feld entfernt; cfg sendet `rvg`/`rvg_override` nicht mehr; Backend liest `rvg_override` nicht mehr (`cfg.get("rvg")` bleibt tolerant). `rvgData` bleibt nur für die korrekt beschriftete Nr.-2300-Anzeige in Kachel 6; SW-Hint „Gegenstandswert der Klage (Gebühren folgen im Kostenfestsetzungsverfahren)". Fix-Wave `3d0b22c3`: Regressionstest gegen rvg_override-Reintroduktion wirksam gemacht (rvg_ausserg ohne `gesamt` → Fallback-Zweig; Gegenbeweis geführt: reintroduzierte Zeilen machen den Test rot). `gesperrt`-Logik/Warnblöcke (KW-19/23) byte-gleich.
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

### - [x] KW-15 — Rubrum-Rolle immer feminin — behoben `2c39550e`, Session 3 2026-07-18
> **Umsetzung:** Rubrum-Rolle über neuen `_beklagten_rolle`-Helfer genus-korrekt („– Beklagter –" bei männlicher Privatperson, Firmen bleiben „Beklagte"), `zu N)`-Nummerierung unverändert.
- **Datei:** `backend/word/klage_service.py:1138` (`"– Beklagte{nr_suffix} –"`); Kläger-Seite unterscheidet korrekt (`:1073–1080`)
- **Auswirkung:** Männlicher Fahrer als Beklagter → „– Beklagte –" statt „– Beklagter –".
- **Fix-Richtung:** Genus aus `beteiligte.anrede` ableiten (sAnrede-Mapping existiert); Firmen bleiben „Beklagte".

### - [x] KW-16 — Vertreter-Grammatik im Rubrum — behoben `2c39550e`, Session 3 2026-07-18
> **Umsetzung:** Neuer `_vertreter_suffix`-Helfer leitet Artikel+Anrede aus dem Funktions-Genus ab (endet die Funktion auf „in"/„ende" → „die …"/„Frau"); bei leerer Funktion wird keine geratene Anrede mehr angehängt (nur Rechtsform-Label + Name).
- **Datei:** `backend/word/klage_service.py:1121–1126`
- **Auswirkung:** (a) Artikel hart „den": „vertreten durch **den Geschäftsführerin** Frau …". (b) Anrede-Heuristik prüft nur die Funktion, nicht den Namen — Vertreterin mit leerer Funktion wird „Herrn".
- **Fix-Richtung:** Artikel aus Funktions-Genus ableiten; Anrede aus dem Vertreter-Datensatz statt Heuristik.

### - [x] KW-17 — Mehrere Kläger: Numerus-Fehler, Vorsteuer ignoriert — behoben `9fec1983`+`b16321f0`, Session 3 2026-07-18
> **Umsetzung:** kl_macht/kl_ist/kl_laesst jetzt in allen Genus-Zweigen korrekt; Plural-`nicht_vst` korrigiert (Nominativ ohne -n) und vorsteuer-bewusst; „Halter und unmittelbare Besitzer"/„Eigentümer" pluralisiert; `baue_sg_abschnitt(…, verb_hat=)` neu parametrisiert (Forderungsschreiben-Pfad über Default unverändert); kl_dat3 war bereits plural-korrekt (Fund entfällt). Fix-Wave `b16321f0`: Vorsteuer-Klausel im Ohne-Unfalldatum-Satz nur im Plural-Zweig, Singular bleibt byte-gleich (Pin-Test). **Bewusst offen:** `get_aktivlegitimation_text`/`_build_aktivlegitimation_xml` (Forderungsschreiben-Pfad) NICHT plural-gehärtet — außerhalb S3-Scope, Rest-Lücke bei mehreren Klägern im AktLeg-Block.
- **Datei:** `backend/word/klage_service.py:940` (`kl_nom="Die Kläger"`), `:1272` („macht"), `:1291` („ist Eigentümer"), `:942` (falsche Flexion + Vorsteuer bei mehreren Klägern immer „nicht vorsteuerabzugsberechtigt"); `sg_text_builder.py:94/98` („hat … erlitten")
- **Auswirkung:** „Die Kläger macht … geltend", „Die Kläger ist Eigentümer" — Singular-Verben bei Plural-Subjekt; Vorsteuerabzug wird ignoriert.
- **Fix-Richtung:** Partei-Objekt mit Numerus (Verbesserung V3): Verbformen aus dem Objekt, nicht hart im Text.

### - [x] KW-18 — Rubrum ohne Kläger möglich — behoben `0778af2e`, Session 3 2026-07-18
> **Umsetzung:** Fallback-Kläger aus `akte_daten["mandant"]`, wenn kein Beteiligter mit `rolle_klage=="klaeger"` existiert; sind auch keine brauchbaren Mandantendaten vorhanden, wirft der Service jetzt `ValueError` → die Route antwortet 422 (`_err`, vor dem generischen 500-Handler). Neuer Route-Test `test_klage_kw18_route.py`. **Team-Awareness:** der `except ValueError → 422`-Fang greift für jeden `ValueError` aus `generiere_klageschrift`, ohne `logger.error`.
- **Datei:** `backend/word/klage_service.py:931–937, 1061–1088` (Klägerblock nur aus `cfg.beklagte` mit `rolle_klage=="klaeger"`; kein Fallback auf `akte_daten["mandant"]`, `mandant_name` `:917` ungenutzt)
- **Auswirkung:** Fehlt der Kläger-Beteiligten-Eintrag, bleibt das Rubrum bis auf „Prozessbevollmächtigte:" leer.
- **Fix-Richtung:** Fallback auf Mandant + harte Sperre/Fehlermeldung wenn kein Kläger ermittelbar.

### - [x] KW-19 — Generieren mit 0 Beklagten möglich — behoben `7e27f0c5`, Session 3 2026-07-18
> **Umsetzung:** `gesperrt`-Guard in Step 10 um `keineBeklagten` erweitert + roter Warnblock + „— keine —"-Zeile.
- **Datei:** `frontend/src/sections/KlageWizard.jsx:1528` (`gesperrt` prüft Beklagte nicht)
- **Auswirkung:** Alle Beklagten abgewählt → Step 2 warnt zwar, blockiert aber nichts; Generieren-Button aktiv, Anträge „Die Beklagte wird verurteilt…" ohne existierende Beklagte.
- **Fix-Richtung:** `beklagteG.length === 0` in die Sperr-Bedingungen von Step 10 aufnehmen.

### - [x] KW-20 — Beklagten-Nummerierung Sachverhalt ≠ Rubrum — behoben `8b23efbe`+`8e10749c`, Session 3 2026-07-18
> **Umsetzung:** Neue exportierte kanonische Liste `kanonischeBeklagte` (Array-Reihenfolge = Rubrum = Backend, `checked !== false`); `buildSachverhaltText` iteriert sie (Nicht-Halter-Privatperson fehlt nicht mehr, Versicherung-mit-`ist_halter` nicht mehr doppelt, Phantom-Fahrer aus `fahrGegnerName` vollständig entfernt — Prop-Kette ausgebaut); `StepRubrum` + `buildRwVorschau` angebunden; `anredeNorm` versteht jetzt auch RA-MICRO-numerische Anreden („1"/„2") im Frontend. Fix-Wave `8e10749c`: hq=100-RW-Satz nimmt Nummer UND Genus aus derselben Referenzpartei (erste Versicherung, sonst erster Eintrag). Abschluss-Review-Fix `6774b443`: Insurer-Klassifikation `versicherung || (firma && !ist_halter)` — Firmen-Halter bekommt Halter-Satz, versichererSuffix/hq-100-Referenz überspringen ihn.
- **Datei:** `frontend/src/sections/KlageWizard.jsx:106–141` (`buildSachverhaltText`: eigene Reihenfolge Versicherung→Fahrer→Halter mit eigener Zählung) vs. StepRubrum `:457–469` (Array-Reihenfolge). Zudem: `hatFahrer` aus `fahrGegnerName` unabhängig von Beklagten-Auswahl; angehakte Nicht-Halter-Privatperson fehlt im Sachverhalt; Versicherung mit `ist_halter=1` doppelt gezählt (Filter `:109/110` überschneiden sich)
- **Auswirkung:** „Beklagte zu 2)" im Rubrum, aber im Sachverhalt nicht erwähnt oder anders nummeriert.
- **Fix-Richtung:** Eine gemeinsame Funktion liefert die kanonische Beklagten-Liste (Reihenfolge + Nummern) für Rubrum UND Sachverhalt.

### - [x] KW-21 — Rechtsform-Heuristik matcht Substrings — behoben `cbc41c13`, Session 3 2026-07-18
> **Umsetzung:** Neuer `_rechtsform_klasse`-Helfer mit Token-/Wortgrenzen-Klassifikation statt Substring-Suche („UG" in „FAHRZEUGBAU" matcht nicht mehr; „Versicherungs-AG"/KGaA/e.V. korrekt erkannt); beide Konsumenten (`_funktion_aus_rechtsform_str`, `_vertretungs_hinweis`) umgestellt; ein latenter KGaA-„ KG"-Substring-Bug wurde dabei mitbehoben. Bildet die neue V3-Helfer-Basis: `_anrede_norm`, `_ist_maennliche_privatperson`, `_beklagten_grammatik`, `_beklagten_rolle`, `_vertreter_suffix` + neues `backend/tests/test_klage_partei_grammatik.py`.
- **Datei:** `backend/word/klage_service.py:664–686` (`"UG" in n` trifft „FAHRZEUGBAU"; `" AG"`/`"SE "` nur mit Leerzeichen → „…Versicherungs-AG" fällt durch)
- **Auswirkung:** Falsche Vertreter-Bezeichnung („gesetzlichen Vertreter" statt „Vorstand") bzw. falsche Rechtsform-Erkennung.
- **Fix-Richtung:** Wortgrenzen-Regex (`\b(GmbH|AG|SE|UG|KG|OHG|e\.K\.)\b` + Suffix-Varianten „-AG").

---

## P3 — Wizard-State / verlorene bzw. veraltete Texte

### - [x] KW-22 — Anträge-Text stale nach Positions-/SG-Änderung; Feststellungs-Checkboxen ohne Textwirkung — behoben `4a4300e3`, Session 5 2026-07-18
> **Umsetzung (V7-Kern):** Neue Exports `antraegeBasis(opts)` (JSON-Fingerprint der textrelevanten Eingaben: checked-Positionen+Beträge, mitSG/sgMind, Beklagte, weiblich, zinsenAb, verzug, unfalldatum, mitFestSg/mitFestSach, hq/hqTyp), `AntraegeSync` (immer gemountete Sync-Komponente im Wizard: regeneriert ab Step ≥ 6 bei Basis-Änderung automatisch, solange nicht manuell — wirkt auch bei Sprung Step 5 → 10 ohne Step-6-Besuch) und `TextVeraltetBadge`. Section-State neu: `wizardAntraegeManuell` + `wizardAntraegeBasis` (Reset in `oeffneWizard`). Manueller Edit in Step 6 setzt das Manuell-Flag; danach nie automatisches Überschreiben, stattdessen Badge „⚠ Text veraltet — Eingaben haben sich geändert" mit „↻ Neu generieren"/„Behalten" in Step 6 UND Step 10 (eine Handler-Quelle). Die Badge **sperrt das Generieren nicht** (bewusste Nutzerentscheidung möglich). Feststellungs-Checkboxen bleiben Toggle-only — die Regeneration kommt automatisch über die Basis. Alter „nur wenn leer"-Mount-Effect entfernt. Wirksamkeit der Tests per Mutations-Gegenbeweis belegt (Badge-Wiring aus → rot; mitFestSach aus Basis → rot).
- **Datei:** `frontend/src/sections/KlageWizard.jsx:1832–1834` (nur generieren wenn leer), `:1762–1765` (Klagebetrag als Fließtext im Antrag), `:1862–1865` (Checkbox-onChange ruft `regenerieren()` nicht)
- **Auswirkung:** Position in Step 5 abgewählt (5.000 → 3.000 €) → Zusammenfassung zeigt 3.000 €, `antraege_override` fordert 5.000 €. Feststellungsantrag anhaken ändert die Vorschau nicht. **Derzeit durch KW-01 maskiert — wird mit dessen Fix akut.**
- **Fix-Richtung:** Zentrales Dirty-Tracking (Verbesserung V7): Badge „Text veraltet — Eingaben haben sich geändert" mit Wahl Neu generieren/Behalten; Checkboxen triggern Regeneration (bzw. Backend-Flags als alleinige Quelle nutzen und die Anträge dort zusammensetzen).

### - [x] KW-23 — Platzhalter kann im finalen Antragstext verbleiben — behoben `a6711c2d` (Guard + Warnblock in Step 10), Session 1 2026-07-17
- **Datei:** `frontend/src/sections/KlageWizard.jsx:1744/1807` (Platzhalter immer eingefügt), `:2010–2015` (Ersetzung nur in Step 9), `:1528` (Generieren-Guard prüft Platzhalter nicht)
- **Auswirkung:** Step 6 neu generieren → direkt via Fortschrittsbalken zu Step 10 → Generieren: „[Außergerichtliche Anwaltsgebühren – wird in Schritt 9 ergänzt]" steht als nummerierter Klageantrag im Text. **Derzeit durch KW-01 maskiert.**
- **Fix-Richtung:** `gesperrt`-Guard in Step 10: `antraegeText.includes(PLACEHOLDER)` → roter Warnblock + Sperre. Quick Win, muss zeitgleich mit KW-01 kommen.

### - [x] KW-24 — Step-9-Änderungen nach Erst-Ersetzung wirkungslos — behoben `0a2d3816`+`52d33252`, Session 5 2026-07-18
> **Umsetzung:** Gebühren-Antrag ist jetzt ein eigenes Segment: der Einbrenn-Effect ist ersatzlos entfernt, der Platzhalter bleibt DAUERHAFT in `wizardAntraegeText`, und die neue exportierte Funktion `komponiereAntraege(antraegeText, gebuehrenText)` ersetzt ihn erst beim Senden (`wizardGenerieren` → `antraege_override`) bzw. für Anzeige/Guards. Step-9-Änderungen (Bereits-gezahlt, Override, manuelle Edits) landen damit immer im DOCX. Regenerations-Effects zusammengeführt mit Manuell-Schutz: neuer Section-State `wizardGebuehrenManuell` (Verzug-Muster inkl. Reset-Button); Remount überschreibt manuelle Gebühren-Edits nicht mehr. Step-10-Guard und Step-6-Statusbanner (Fix-Wave `52d33252`) prüfen den KOMPONIERTEN Text: Platzhalter + vorhandener Gebühren-Text sperrt/warnt nicht mehr, Platzhalter ohne Gebühren-Text sperrt weiterhin (KW-23-Schutz bleibt).
- **Datei:** `frontend/src/sections/KlageWizard.jsx:2010–2015` (Ersetzung nur solange Platzhalter vorhanden), `:2003–2007` (Remount-Effect überschreibt `wizardGebuehrenText` ohne Manuell-Schutz), `KlageSection.jsx:560–574` (`wizardGebuehrenText` wird nie gesendet)
- **Auswirkung:** Nach der ersten Ersetzung sind „Bereits gezahlt"-Änderungen und manuelle Edits am Gebühren-Antrag wirkungslos für den Anträge-Text; das DOCX fordert den alten Betrag.
- **Fix-Richtung:** Gebühren-Antrag nicht per String-Ersetzung „einbrennen", sondern als eigenes Segment führen, das beim Generieren zusammengesetzt wird; Dirty-Tracking wie KW-22.

### - [x] KW-25 — Step 3: manuelle Sachverhalt-Edits beim Remount überschrieben — behoben `00d4c278`, Session 5 2026-07-18
> **Umsetzung:** `prevAutoRef` ersatzlos entfernt; Manuell-Flag in den Section-State gehoben (`wizardSachverhaltManuell`, Reset in `oeffneWizard`) nach dem `wizardVerzugManuell`-Muster. Effect in `StepAktLeg` (jetzt named export) regeneriert nur bei nicht-manuellem Text (Deps unverändert); DokumentCard-Edit setzt das Flag; „↻ Neu generieren"-Reset-Button wie beim Verzug. Verhaltens-Rot per Gegenbeweis belegt (Guard deaktiviert → Remount-Kerntest rot).
- **Datei:** `frontend/src/sections/KlageWizard.jsx:489–503` (`prevAutoRef` lokal in `StepAktLeg`, beim Unmount weg → Remount überschreibt bedingungslos)
- **Auswirkung:** Manuell ergänztes Beweisangebot in Step 3 → zu Step 4 → zurück zu Step 3 → Ergänzung kommentarlos weg; betrifft genau den `sachverhalt_override`-Text der Klageschrift.
- **Fix-Richtung:** Manuell-Flag/prevAuto in den Section-State heben (wie beim gefixten `wizardVerzugManuell`), oder Dirty-Tracking V7.

### - [x] KW-26 — Fortschrittsbalken umgeht kannWeiter()-Sperren — behoben `34c613ca`, Session 5 2026-07-18
> **Umsetzung:** Neue Exports `schrittBlockiert(nr, ctx)` (eine Quelle für die Sperr-Regeln Step 1/5) und `kannSpringen(ziel, step, ctx)` (rückwärts immer, vorwärts nur wenn alle Steps bis Ziel-1 frei — kumulativ). `Fortschrittsbalken` (jetzt named export) erhält `springenErlaubt`-Prop; `kannWeiter()` nutzt dieselbe Quelle. maxStep-Begrenzung und Nicht-klickbar-Optik unverändert. Wirksamkeit per Gegenbeweis (Guard-Revert → Klick-durch-Test rot).
- **Datei:** `frontend/src/sections/KlageWizard.jsx:2271–2275` (kannWeiter nur Steps 1+5) vs. `:205` (Balken: alles ≤ maxStep klickbar)
- **Auswirkung:** Positionen in Step 5 abwählen → „Weiter" gesperrt, Klick auf Kreis „6" geht trotzdem; Auslöser für KW-23.
- **Fix-Richtung:** Balken-Klick durch dieselbe kannWeiter-Prüfung leiten (kumulativ bis Ziel-Step).

### - [x] KW-27 — Gericht-Persistenz: Rückweg tot — behoben `6752215e`, Session 5 2026-07-18
> **Umsetzung:** Gericht-Zeile wird jetzt VOR dem Rollen-Filter gelesen (`gericht_bet` via `next(...)`), Prio-1a nutzt sie direkt (Dict-Konstruktion inkl. `quelle="akte"` unverändert), toter Zweitfilter entfernt. KEIN V9/keine Migration. Frontend-Autobestätigung (`quelle==="akte"` → `wizardGerichtBest`) funktioniert damit ohne Änderung. **Nebenfund mitgefixt (Scope-Erweiterung, Controller-gebilligt):** die Frisch-DB-CHECK-Constraint `beteiligte.rolle` in `backend/db/schema.py` kannte `'gericht'` nicht → PUT scheiterte in jeder frisch erzeugten DB (inkl. Test-Suite) mit IntegrityError; additiv ergänzt. Route-Test `test_klage_kw27_gericht_persistenz.py` (PUT→GET-Roundtrip, Gericht nicht in Beteiligten-Liste).
> **⚠ Bestands-DB-Einordnung (Abschluss-Review-Fund C1, 2026-07-18):** `CREATE TABLE IF NOT EXISTS` ändert Bestands-Tabellen NICHT — eine Bestands-DB, deren `beteiligte`-Tabelle noch die alte CHECK-Liste trägt, lehnt `rolle='gericht'` weiter mit IntegrityError ab (SQLite kann CHECK nicht per ALTER erweitern; nötig wäre eine Rebuild-Migration create/copy/drop/rename). **Die aktiv laufende Docker-Volume-DB (`/app/data`) ist verifiziert NICHT betroffen** (Controller-Probe: DDL ohne rolle-CHECK, 7 gericht-Zeilen vorhanden, Probe-INSERT ok) — dort wirkt KW-27 vollständig. Betroffen wären alte DB-Kopien/Backups mit Original-DDL sowie ggf. die künftige Prod-DB → **beim Go-Live prüfen** (`SELECT sql FROM sqlite_master WHERE name='beteiligte'`; Hinweis im Rollout-Runbook ergänzt). **Offene Entscheidung RA Schatz:** Rebuild-Migration für solche Bestands-DBs ja/nein (Handover-Regel „bei struktureller KW-27-Lösung vorher fragen"). Als Defence-in-depth macht `4947a6ff` den Speicherfehler sichtbar: `gerichtSpeichernOderWarnen` zeigt bei fehlgeschlagener Persistenz einen Toast („gilt nur für diese Sitzung") statt des bisherigen stillen `.catch(() => {})`; Wizard-Fluss bleibt unblockiert.
- **Datei:** `backend/routers/klage_routes.py:1442–1451` (PUT speichert `beteiligte` mit `rolle='gericht'`) vs. `:946` (`alle_bet` vorab auf klaeger/beklagter gefiltert → Prio-1a-Loop `:998–1009` findet nie etwas; zweiter Filter `:1034` tot)
- **Auswirkung:** Manuell gewähltes Gericht wird gespeichert, aber beim nächsten Öffnen kommt wieder der RA-MICRO-/Unfallort-Vorschlag; die Auto-Bestätigung (`quelle === "akte"`) greift nie.
- **Fix-Richtung:** Gericht-Zeile vor dem Rollen-Filter lesen — oder strukturell: Gericht als eigenes Feld an `unfallakte` statt Missbrauch von `beteiligte` (Verbesserung V9).

### - [x] KW-28 — Verzugsdokument-Auswahl ohne Wirkung (Placebo) — behoben `a332bab4`+`2b9e1a45`, Session 5 2026-07-18
> **Umsetzung (Entscheidung: wirksam machen statt entfernen):** Zentraler Handler `waehleVerzugDok` in KlageSection, verdrahtet an BEIDEN Auswahl-Stellen (Kachel-5-Buttons + Step-8-Select, StepVerzug jetzt named export + Wiring-Test). Auswahl setzt `wizardVerzugDokDatum` (Schreibdatum) + `wizardVerzugDatum` via `verzugEintrittDefault` (+14 Tage) und baut bei nicht-manuellem Verzugstext `buildVerzugAutoText` neu. **Datumsquelle (Fix-Wave):** `verzug_dokumente` liefert jetzt `datum` = MAX(`forderung_positionen.datum`) je Dokument (korrelierte Subquery, echtes Schreibdatum; Backend-Test `test_klage_kw28_verzugdok_datum.py`); Frontend `verzugDatenAusDok` (KlageSection named export) bevorzugt `datum`, Fallback `hochgeladen_am` (Upload-Zeitstempel als Näherungs-Proxy für gescannte Fremdschreiben ohne forderung_position — Felder bleiben editierbar), Null-Guard bei unparsebarem Datum (kein Clobber). Dokument ohne Datum → nur ID-Wechsel. `verzugDokId` wird weiterhin NICHT gesendet (BEWEIS läuft über das Schreibdatum, S4-Vertrag); Initial-Load-Vorbelegung unverändert.
- **Datei:** `frontend/src/sections/KlageSection.jsx:165/223`, `KlageWizard.jsx:1388–1402` (`verzugDokId` wird nie gesendet, übernimmt auch nicht das Dokumentdatum)
- **Auswirkung:** Nutzer wählt das verzugsbegründende Schreiben aus — ohne jeden Effekt auf Datum, BEWEIS-Zeile oder Dokument.
- **Fix-Richtung:** Auswahl übernimmt das Dokumentdatum in „Datum des Schreibens" und sendet die Doc-ID als BEWEIS-/Anlagen-Referenz — oder das Feld entfernen.

### - [x] KW-29 — Vertreter-Lookup-Modal öffnet wiederholt unaufgefordert — behoben `e3c1ab68`, Session 5 2026-07-18
> **Umsetzung:** Auto-Lookup ist jetzt still: `lookupVertreter(id, name, {oeffneModal:false})` füllt nur den Cache; das Modal öffnet ausschließlich auf Klick der „🔍 Lookup"-Buttons (bei vorhandenem Cache-Ergebnis sofort aus dem Cache, ohne erneuten Fetch). Neuer Export `sollAutoLookup(b, lookupCache)` mit Existenz-Guard (`lookupCache[b.id]` gesetzt → kein erneuter Auto-Lookup — behebt die `?.laden`-Lücke; Mutations-Gegenbeweis geführt). **Entscheidungs-Notiz:** das im Handover erwähnte „dismissed-Set" entfällt — ohne Auto-Open gibt es nichts zu dismissen, der Cache ist der Einmal-Guard. **Bewusstes Design (RA Schatz ggf. bestätigen):** ein fehlgeschlagener Auto-Lookup blockiert automatische Wiederholungen für die Sitzung (Anti-Spam); der manuelle Klick fetcht in dem Fall neu — keine Sackgasse.
- **Datei:** `frontend/src/sections/KlageSection.jsx:250–263, 349–360` (Auto-Lookup öffnet Modal je Firma; Guard prüft nur `laden`, nicht „bereits nachgeschlagen"; jede `setBek`-Änderung triggert erneut)
- **Auswirkung:** Modal-Spam beim Tab-Aufruf; bewusst geschlossene Modals kommen nach jeder Beteiligten-Änderung wieder.
- **Fix-Richtung:** Auto-Lookup nur still cachen, Modal nur auf expliziten Klick; „dismissed"-Set je Sitzung.

---

## P4 — Textqualität / Kleinkram / toter Code

### - [x] KW-30 — Leere Felder erzeugen kaputte Sätze — behoben BE `ebef927d` + FE `efc64588`, Session 6 2026-07-19
> **Umsetzung:** Betroffene Bausteine (Unfallort-Satz, Feststellungsanträge) auf bedingte Segmente (`unfall_seg`/`ereignis_seg`) umgestellt — der Ortsteil bzw. Datumsteil entfällt ersatzlos, wenn das Feld leer ist, statt eine Lücke im Satz zu hinterlassen. Standardfall (alle Felder gesetzt) bleibt byte-gleich zum Vorzustand (Pin-Test). Frontend ergänzt Step-10-Warnblöcke bei fehlendem `unfallort`/`unfalldatum` — reine Warnung, keine Sperre (der Anwalt kann die Klage trotzdem ohne diese Felder generieren, wird aber gewarnt).
- **Datei:** `backend/word/klage_service.py:1271–1277` („…Verkehrsunfall vom 01.02.2026 in  geltend." bei leerem Unfallort), `:1233/1243` (Feststellungsanträge: „aus dem Unfallereignis vom  noch entstehen" bei leerem Unfalltag)
- **Fix-Richtung:** Bausteine mit bedingten Segmenten („ in {ort}" nur wenn gesetzt); Pflichtfeld-Warnung in Step 10.

### - [x] KW-31 — `sachverhalt_override` zerstört Absatzstruktur — behoben `449c5f0f`+`351e79e6`, Session 6 2026-07-19
> **Umsetzung:** Parser auf zeilenweise Auswertung umgestellt: jede Leerzeile beendet einen Absatz, BEWEIS-Erkennung greift jetzt auch nach einfachem `\n` (nicht mehr nur `\n\n`). Nebenfund im selben Zug mitbehoben: der Alt-Code flushte `\n\n`-getrennte Absätze in bestimmten Konstellationen gar nicht. Fix-Wave `351e79e6` deckt Randfälle ab (bare `BEWEIS`-Zeile ohne Doppelpunkt-Suffix, Tab-eingerückte Variante).
- **Datei:** `backend/word/klage_service.py:688–714` (Nicht-BEWEIS-Blöcke bis zum nächsten BEWEIS zu einem Absatz verkettet; BEWEIS-Zeile mit einfachem `\n` wird Fließtext — Split nur auf `\n\n`)
- **Fix-Richtung:** Jede Leerzeile = Absatz; BEWEIS-Erkennung zeilenweise.

### - [x] KW-32 — Verzug-Abschnitt ohne Nummer/Überschrift — behoben `30d4fbc0`, Session 6 2026-07-19
> **Umsetzung:** Neuer laufender Zähler-Helfer `_abschnitt_kopf` ersetzt die Arithmetik (`5 + int(mit_sg)` etc.) an allen 9 Kopfstellen. Verzug bekommt jetzt eine eigene Nummer + Überschrift („N.) Verzug") statt unnummeriert im Fließtext zwischen SG und VK zu hängen. Mit S4-M5-Vertrag verzahnt: der Verzug-BEWEIS erscheint weiterhin nur, wenn `verzug_schreiben_datum` gesetzt ist.
- **Datei:** Template-Reihenfolge `{{SCHMERZENSGELD}} {{VERZUG}} {{VORGERICHTLICHE_KOSTEN}}`; Nummerierung springt 4 → 5 (SG) → 5/6 (VK), Verzug hängt unnummeriert dazwischen (`klage_service.py`, Abschnittszähler `5 + int(mit_sg)`)
- **Fix-Richtung:** Laufender Abschnittszähler statt Arithmetik; Verzug bekommt eigene Nummer+Überschrift.

### - [x] KW-33 — SG-Beweisantritt nicht als BEWEIS formatiert — behoben `10febac9`, Session 6 2026-07-19
> **Umsetzung:** SG-Beweis läuft jetzt über den bestehenden `_beweis()`-Helfer (fett + Tabstopp) statt über `_p(sg_beweis, einzug=True)`; ein Präfix-Strip verhindert doppeltes „BEWEIS:" wenn der Text es bereits enthält.
- **Datei:** `backend/word/klage_service.py:1421` (`_p(sg_beweis, einzug=True)` statt `_beweis()`)
- **Fix-Richtung:** `_beweis()` verwenden (fett + Tabstopp, wie überall sonst).

### - [x] KW-34 — RVG-Antrag über „0,00 €" möglich — behoben `1ad1a93f`+`b2e0ab16`, Session 6 2026-07-19
> **Umsetzung:** Bei RVG-Betrag ≤ 0 entfallen sowohl der RVG-Antrag als auch der komplette VK-Abschnitt (auch im Override-Pfad, nicht nur im Auto-Pfad). Der Fall-B-Klemmsatz (Zahlungen übersteigen den quotierten Anspruch) nennt jetzt die real geleistete Zahlungssumme statt der arithmetisch abgeleiteten Differenz — Formulierung ist RA Schatz vorzulegen. Fix-Wave `b2e0ab16` hat den Klemm-Test mit einer realen `wertminderung`-Fixture wirksam gemacht (vorher griff der Test nicht).
- **Datei:** `backend/word/klage_service.py:989–991 + 1248` (`max(0.0, …)` → Antrag „…weitere 0,00 € … zu zahlen" samt VK-Abschnitt)
- **Fix-Richtung:** Bei 0 € Antrag + VK-Abschnitt weglassen.
- **Neu aus S2 (KW-03, hier mitzubehandeln):** Klammer-Randfall Fall B — wenn Zahlungen den quotierten Anspruch übersteigen (`klagebetrag` klemmt auf 0), nennt der Fall-B-Differenz-Satz eine geringere Zahlungssumme als real geleistet (`zahlungen_anzeige = ersatzfaehig − klagebetrag`, arithmetisch konsistent, aber juristisch schief). Zusammen mit der 0-€-Antrags-Frage lösen.

### - [x] KW-35 — RVG-Fallback nutzt SQLite-Importdatum — behoben `8da95f62`, Session 4 2026-07-18 (mit KW-08 vorgezogen)
> **Umsetzung:** Fix-Richtung „durchreichen": der Generier-Endpoint legt `akte_daten["akte"]["rvg_anlagedatum"] = _rvg_anlagedatum(az, akte.erstellt_am)` an; der `berechne_rvg`-Fallback im Service nutzt `rvg_anlagedatum or erstellt_am`. Trennscharfer DOCX-Test (Tarif 2021 vs. 2025: 159,94 € vs. 167,67 € bei SW 700 €).
- **Datei:** `backend/word/klage_service.py:963–965` (`erstellt_am` statt `_rvg_anlagedatum` aus `klage_routes.py:48–85`)
- **Auswirkung:** Alt-Akte, 2025 importiert → fälschlich 2025er-Gebührentabelle. Nur relevant wenn `cfg.rvg` fehlt (Legacy-Pfad).
- **Fix-Richtung:** `_rvg_anlagedatum` durchreichen oder Fallback entfernen (zusammen mit KW-08).

### - [x] KW-36 — Haftungsquote int-Truncation — ✅ S6, teilweise entfällt (Rundungs-Parität `3e87ff86`), Session 6 2026-07-19
> **Umsetzung:** Verifiziert per Grep, dass die ursprüngliche int-Truncation nicht mehr existiert — `_pct_str`/`pctStr` sind seit S2/S3 überall im Einsatz, betreffen also **entfällt** (kein Fund mehr im Code). Der optionale `hq=0`-Guard **entfällt ebenfalls**: `parseFloat(...) || 100` schluckt `0` bereits korrekt (führt zu 100 %, nicht zu einem sinnfreien 0-%-Text); ein Regressions-Pin-Test wurde committet, um das dauerhaft zu belegen. Der einzige real behobene Teil: eine Rundungs-Divergenz zwischen Frontend (JS `Math.round` = half-up) und Backend (Python `round` = banker's rounding) wurde nachgewiesen — konkretes Beispiel 50,50 € × 33 % → FE 16,67 vs. BE 16,66, beide Werte tauchen im selben DOCX auf. Fix: neuer Helfer `_round2_half_up`, an exakt den 4 Rundungsstellen im Fall-B-Pfad eingesetzt (Backend jetzt half-up wie das Frontend).
- **Datei:** `backend/word/klage_service.py:1394/1410` (`int(hq)`/`int(100-hq)`: 66,67 % → „66 %" + „33 %" = 99)
- **Fix-Richtung:** Runden statt truncaten; Summe = 100 sicherstellen.
- **Stand nach S2:** In allen von S2 berührten/neuen Texten bereits via `_pct_str`/`pctStr` gelöst; Rest-Scope = verbliebene Alt-Stellen. **Empfehlung Abschluss-Review S2:** gemeinsamen Rundungs-Helper BE/FE einführen (JS `Math.round` = half-up vs. Python `round` = banker's — theoretische 1-Cent-Divergenz Antragstext↔Backend-Werte im selben Dokument) und in Session 6 zusammen mit KW-34 lösen. Optional: Ein-Zeilen-Guard gegen `hq=0` + `typ=eigen` (RW-Text behauptet dann „100 % anrechnen", Betrag bleibt voll — sinnfreie Eingabe, Slider erlaubt 0).

### - [x] KW-37 — RVG-Faktor „(1.3)" mit Punkt statt Komma — behoben `10febac9`, Session 6 2026-07-19
> **Umsetzung:** Komma-Format an der aktiven Tabellen-Stelle über einen `.replace(".", ",")` auf den Faktor-String korrigiert (dieselbe Fix-Session wie KW-33/KW-37, gemeinsamer Commit).
- **Datei:** `backend/word/klage_service.py:1478` (die tote Alt-Funktion `:386` machte den Komma-Replace korrekt)
- **Fix-Richtung:** Komma-Format wie überall.

### - [x] KW-38 — Positions-Key-Vertrag ungesichert — behoben `13d7eefc`+`c83e23d8`, Session 6 2026-07-19
> **Umsetzung:** Neue zentrale Registry `frontend/src/config/klagePositionKeys.js` (`KLAGE_KEY_MAP` + `KEYS_OHNE_POSITION`) löst drei bisher separat gepflegte Map-Kopien ab; 8 Aliase byte-gleich übernommen. Neu wirksam durch die Konsolidierung: `kostenpauschale`→`unkostenpauschale`, `wbw*`→`fahrzeugschaden` (vorher unmapped, senkten `_unassigned` statt einer echten Position). `sonstiges_wdm_*` bewusst **nicht** gemappt — der reale Wizard-Key für diese Position ist label-basiert (`extra_<Label>`, siehe `klage_routes.py:~844`), das ist keine Lücke sondern eine dokumentierte Grenze (in `KEYS_OHNE_POSITION` vermerkt). Contract-Tests in beide Richtungen: Frontend-Spiegel prüft alle 38 Keys, Backend-Wächter `test_klage_kw38_position_keys.py` verhindert stille Drift zwischen Wizard-Keys und `regulierung_positionen.position_key`.
- **Datei:** `frontend/src/sections/KlageSection.jsx:275–284, 407–416` (`_KEY_MAP` nur Fahrzeugschaden-Parser-Keys; Zahlungen auf nicht-mappende Keys senken `_unassigned`, reduzieren aber keine Position)
- **Auswirkung:** Offener Betrag/Klagebetrag zu hoch. Verwandter Bug-Typ war schon einmal da (`sonstiges_wdm_X ≠ extra_wdm_ssX`, siehe [[unfallakten-key-mismatch-bug]]).
- **Fix-Richtung:** Vollständiges Key-Mapping + Test, der alle `regulierung_positionen.position_key`-Werte gegen die Wizard-Keys prüft; langfristig V2 (offen-je-Position im Backend).

### - [x] KW-39 — Vorsteuer-Inkonsistenz Nebenkosten — behoben `e19edc64`, Session 2 2026-07-17 (vorgezogen aus S6, weil das KW-04-Review die Divergenz als aktiven Widerspruch Tabelle↔Antrag nachwies)
> **Umsetzung:** `pos_definitionen` berechnet die fünf Nebenkosten-Keys (Mietwagen/SV/Abschlepp/Stand/An-Abmeldung) jetzt via importierter `_netto_oder_brutto`-Logik (echte Wiederverwendung, keine Kopie); `kostennb` behielt seine äquivalente eigene Weiche.
- **Datei:** `backend/routers/klage_routes.py:783–794` (SV-Kosten/Mietwagen/Abschlepp/Stand/An-Abmeldung immer brutto, nur `fahrzeugschaden`/`kostennb` vorsteuer-bewusst) vs. `forderungsschreiben_wv.py:715–737, 798–803` (Tabelle rechnet netto)
- **Auswirkung:** Beim Vorsteuer-Mandanten: Antrag brutto, Tabelle netto → Widerspruch.
- **Fix-Richtung:** `pos_definitionen` vorsteuer-bewusst machen (dieselbe `_netto_oder_brutto`-Logik).

### - [x] KW-40 — Sammelposten Kleinkram / toter Code — behoben BE `ba56cb1b`+`d7f81be0`, FE `efc64588`+`d0ceb920`, Session 6 2026-07-19
> **Umsetzung:** Backend: 10 tote Symbole entfernt (`_xml_absatz`, `_xml_leerzeile`, `_xml_tabelle_schaden`, `_xml_tabelle_rvg`, `_xml_antrag`, `_tab_rechts`, `_VORLAGE_FS`, `kanzlei_str`, `mandant_anschr`, Top-Level `import zipfile`); `antrag()` nutzt jetzt `<w:tab/>`-Runs statt rohem Tab-Zeichen; GHPV-Filter zieht wie `beklagte_gef` `checked` + Rollen nach; nicht gemappte `extra_wdm_`-Positionen werden jetzt sauber als „Sonstige Schäden" beschriftet statt roh als „Extra Wdm Ss1"; `_merge_split_placeholders` läuft jetzt über alle 16 Platzhalter statt nur `{{GEGENSTANDSWERT}}` (Absicherung durch V10-Render-Smoke-Test). Die RVG-Antragsnummer-Raterei bei `antraege_override` bleibt bewusst unangetastet (kein sauberer 1-Zeilen-Fix, Risiko/Aufwand nicht gerechtfertigt). Frontend: „Text übernehmen" im Einwände-Panel ersetzt jetzt statt anzuhängen; die Kürzungs-Summe klemmt negative Werte (reguliert > gefordert reduziert die Summe nicht mehr unter 0); `ersetzeMandantDurchKlaeger` als einziger Export dedupliziert die vorher zweifach geführte Mandant→Kläger-Ersetzung inkl. Artikel-Fix (Der/Dem/Den); der „ungeklärt"-Warntext in Step 3 ist jetzt ehrlich (Anzeige entspricht wieder dem tatsächlichen Payload); NaN-Guard `parseBetragOderNull` + expliziter Versand-Guard `baueRvgAussergOverride` verhindern `fmtEuro(NaN)`-Anzeigen; toter Fixture-Rest entfernt. S4-M6 im selben Zug mitgenommen: `StepVerzug`-Vorbelegung nutzt jetzt `fmtDatumDe`. Tote-Fracht-Punkte aus dem letzten Aufzählungsblock (gesendet-nie-gelesen/GET-nie-genutzt) bewusst **nicht** angefasst — reine Vertrags-Doku ohne funktionalen Fehler, kein TDD-Ansatzpunkt.
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
| **3** ✅ | KW-06, KW-15–KW-21 (Rubrum/Grammatik-Cluster) — erledigt 2026-07-18, Branch `klage-wizard-fixes-s3` | Als V3-Refactoring (Partei-Objekt) in einem Zug: neue Helfer `_anrede_norm`, `_ist_maennliche_privatperson`, `_beklagten_grammatik`, `_beklagten_rolle`, `_vertreter_suffix`, `_rechtsform_klasse` (Backend) + `kanonischeBeklagte`/`beklagtenGrammatik`/`versichererSuffix` (Frontend). Baseline: Backend 204f/1044p (Alt-Cluster, null neue, +44 Passes), Frontend 141 Vitest (122→141) + Build. FF-Merge nach Freigabe ausstehend. |
| **4** ✅ | KW-09, KW-10, KW-12, KW-13, KW-08 + KW-35 (vorgezogen) — erledigt 2026-07-18, Branch `klage-wizard-fixes-s4` | Datum/RVG/Anlagen als V5 (Datumsvertrag: ISO im Transport, `_fmt_datum`/`fmtDatumDe` nur im Renderer, BE↔FE wortgleicher Port) + V6 (nur noch Nr. 2300 außergerichtlich, gerichtl. SW als Zahl) + V4 (`AnlagenZaehler` mit Override-Scan). Legacy-Button weg (V8-Teil). Neue cfg-Keys: `verzug_schreiben_datum`; entfallene: `rvg`, `rvg_override`. Eintritt-Default Schreibdatum+14 Tage. Baseline: Frontend 159 Vitest (143→159) + Build; Backend-Voll-Lauf siehe TODO. FF-Merge nach Freigabe ausstehend. |
| **5** ✅ | KW-22, KW-24–KW-29 (Wizard-State/UX) — erledigt 2026-07-18, Branch `klage-wizard-fixes-s5` | V7 umgesetzt: Manuell-Flags im Section-State (`wizardSachverhaltManuell`/`wizardGebuehrenManuell`/`wizardAntraegeManuell`) + `antraegeBasis`-Fingerprint + `AntraegeSync` (immer gemountet) + `TextVeraltetBadge` (Step 6+10); Gebühren-Antrag als Segment mit `komponiereAntraege` beim Senden (Platzhalter bleibt im State); `kannSpringen` kumulativ für den Fortschrittsbalken; KW-27 ohne V9/Migration (Gericht-Zeile vor Rollen-Filter + Frisch-DB-CHECK um `'gericht'`); KW-28 mit echtem Schreibdatum aus `forderung_positionen` (neues `datum`-Feld in `verzug_dokumente`); KW-29 stiller Lookup-Cache statt dismissed-Set. Plan: `docs/superpowers/plans/2026-07-18-prd33-s5-wizard-state-ux.md`. Baseline: Backend 204f/1059p (Alt-Cluster, null neue, +5 Passes), Frontend 198 Vitest (159→198) + Build. FF-Merge nach Freigabe ausstehend. |
| **6** ✅ | KW-30–34, KW-36–38, KW-40 + V10 Golden-File-Matrix — erledigt 2026-07-19, Branch `klage-wizard-fixes-s6` | Politur (Textqualität/toter Code) + dauerhafter Regressionsschutz. KW-35/KW-39 bereits in S4/S2 erledigt; KW-36 teilweise entfällt (Truncation/hq=0-Guard nicht mehr vorhanden), Rest = Rundungs-Parität BE/FE (`_round2_half_up`). V10: `TestV10RenderSmoke` (kein `{{`/`}}` im Ergebnis-XML, Wächter-Wirksamkeit per Mutation belegt) + `TestV10Matrix` (24 Kombinationen mit_sg × 1/2 Beklagte × eigentum/finanziert/geleast × Overrides an/aus, No-Platzhalter-Check + Struktur-Invarianten in allen 24). Baseline: Backend voller Lauf **204f/1086p/18s + 24 Subtests** (204f = Alt-Cluster, null neue Failures, +27 Passes ggü. S5), Frontend **223** Vitest (200→223) + Build grün. 15 Code/Test-Commits `c003e962`..`81706b67`. FF-Merge nach Freigabe ausstehend. **PRD-33 damit komplett (alle 40 KW-Bugs behoben oder begründet entfallen).** |

> **Grundsatzentscheidungen (RA Schatz, 2026-07-17) — alle getroffen:**
> 1. **KW-03 Haftungsquote:** Zwei Fälle. Fall A (gegnerische Quote) = nur Darstellung in der RW, Beträge 100 %. Fall B (eigene Quote) = Klagebetrag quotiert: **erst quotieren, dann Zahlungen abziehen**; SG-Mindestbetrag NICHT auto-quotiert; Quote gilt auch für den vorgerichtlichen Streitwert (Nr.-2300-Basis). Schadentabelle immer 100 %. Step 7 bekommt die Fall-Auswahl.
> 2. **KW-08 Legacy-Button:** entfernen — der Wizard ist der einzige Weg.
> 3. **KW-13 Streitwerte:** keine gerichtliche Gebührenberechnung (Kostenfestsetzungs-Thema, nicht Klage). Gerichtlicher Streitwert (= offener Rest) nur als Gegenstandswert-Angabe in der Klageschrift; „RVG gerichtlich"-Anzeige-Duplikat entfernen.
