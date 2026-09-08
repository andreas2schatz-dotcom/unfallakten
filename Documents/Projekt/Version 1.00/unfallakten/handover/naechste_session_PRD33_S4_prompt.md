# Prompt für die nächste Session — PRD-33 Session 4 (Datum/RVG/Anlagen-Cluster)

> Zum Einfügen als Start-Prompt. Stand: 2026-07-18 nach Abschluss Session 3.

---

Wir setzen PRD-33 (Klage-Wizard) fort. docs/BUGFIX_KLAGE_WIZARD.md ist das maßgebliche
Tracking-Dokument — zuerst vollständig lesen, ebenso docs/TODO.md und
handover/klage_wizard_map.md. Sessions 1–3 sind erledigt und in main (FF-Merges
578c93e0, d19b9640, d856a8d4 — nicht gepusht, main ist ~68 Commits vor origin/main).
Session 3 hat das V3-Partei-Grammatik-Modell eingeführt (Details unten).

Heutige Session = Session 4 aus dem Tracking-Dokument: Datum/RVG/Anlagen — V5
(Datumsvertrag) + V6 (RVG-Objekte) als Leitideen. Genau diese fünf Bugs:

1. KW-09 (P1) — Zins-/Verzugsdatum erscheint im ISO-Format („seit dem 2026-05-04").
   `_fmt_datum` existiert in klage_service.py, wird an den Zins-Stellen nicht genutzt;
   auch der Wizard-Auto-Verzugstext übernimmt ISO wörtlich (KlageSection).
   V5-Leitidee: Transportformat ISO beibehalten, Formatierung NUR im Renderer
   (ein Wrapper an der cfg-Grenze).
2. KW-10 (P1) — Verzugsdatum-State-Split: Wizard-Pfad sendet `verzug` statt
   `wizardVerzugDatum` (KlageSection, `verzugsdatum:`-Zeile im wizardGenerieren-cfg);
   Step 6 nutzt `wizardVerzugDatum || verzug`, Step 9 nur `verzug` → drei Stellen,
   drei mögliche Werte. Inhaltlich zudem juristisch schief: das Schreibdatum des
   Forderungsschreibens wird als Verzugseintritt behauptet (Verzug tritt erst nach
   Fristablauf ein) — Schreibdatum und Verzugseintritt als getrennte Felder führen
   (Eintritt = Fristablauf, editierbar).
3. KW-12 (P2) — Anlagen-Kollision: Freigabeerklärung/Sicherungsbedingungen heißen
   „Anlage K1", das Gutachten „Anlage K 1"; sg_text_builder vergibt „K 2" hart;
   Schreibweise inkonsistent. V4-Leitidee: Anlagen-Manager — fortlaufende K-Nummern
   zentral vergeben, Registrierung beim Erzeugen jedes BEWEIS-/Anlagen-Bausteins.
4. KW-13 (P1) — „RVG gerichtlich" ist in Wahrheit die außergerichtliche Gebühr;
   `rvg_override` (Kachel 6) wirkungslos sobald Step 9 betreten.
   **ENTSCHIEDEN (RA Schatz, 2026-07-17): KEINE gerichtliche Gebührenberechnung
   bauen** (Kostenfestsetzungs-Thema). Konzept: vorgerichtlicher Streitwert = Basis
   Nr. 2300 (bei eigener Quote quotiert, seit S2 via berechneSwAussergEffektiv);
   gerichtlicher Streitwert (= offener Rest + SG-Mindestbetrag) nur als
   Gegenstandswert-Angabe ({{GEGENSTANDSWERT}} passt schon). Konkret: das
   „RVG gerichtlich"-Anzeige-Duplikat (`rvgData`) in Step 8/10 samt irreführendem
   Label ENTFERNEN; nur `rvg_ausserg` bleibt; `rvg_override` entfernen oder auf
   `rvg_ausserg` umleiten; Step 8/10 zeigen künftig gerichtlichen Streitwert (Zahl,
   ohne Gebühren) + Nr. 2300 auf vorgerichtlichem SW.
5. KW-08 (P1) — Legacy-Button klagt vollen statt offenen Betrag ein.
   **ENTSCHIEDEN: Legacy-Button entfernen — der Wizard ist der einzige Weg.**
   Backend-seitig prüfen, ob der Legacy-Codepfad (`generieren()` ohne Wizard-cfg)
   mit entfernt werden kann. Dabei KW-35 mitprüfen (RVG-Fallback nutzt
   SQLite-Importdatum statt RA-MICRO-Anlagedatum — nur im Legacy-Pfad relevant;
   Fix-Richtung laut Tracking-Doc: „Fallback entfernen, zusammen mit KW-08" —
   ggf. wie KW-39 in S2 vorziehen, wenn er durch den Ausbau trivial wird).

Arbeitsregeln: TDD strikt (fehlschlagender Test = Verifikation; falscher Fund →
`entfällt` mit Begründung). Zeilennummern im Tracking-Doc sind Stand VOR Session 1 —
durch S1–S3 stark verschoben, immer frisch prüfen (Ist-Erhebung per Explore-Agent zu
Beginn hat sich erneut bewährt). RA-MICRO read-only, keine Migration erwartet.
Baseline: Backend 204f/1044p (204f = bekannte Alt-Cluster test_modul2/3/4/7,
test_sv_portal, test_prd27), null neue Failures; Frontend 143 Vitest + Build grün.
Arbeitsbranch von main (z. B. klage-wizard-fixes-s4), am Ende FF-Merge nach Freigabe.
Beim Abhaken: [x] + Commit-Hash im Tracking-Doc, Status-Tabelle mitpflegen, TODO.md
aktualisieren. Docker-Dev: HMR unter Windows kaputt → Frontend-Container ggf. neu
starten (für Vitest/Build irrelevant, die laufen direkt im frontend/-Ordner).

Nützliches aus S3 (unbedingt nutzen):
- **V3-Partei-Grammatik ist die neue SSOT** und BE↔FE wortgleich — bei Textänderungen
  IMMER beide Seiten pflegen: Backend `klage_service.py` (`_anrede_norm`,
  `_ist_maennliche_privatperson`, `_rechtsform_klasse`, `_beklagten_grammatik`,
  `_beklagten_rolle`, `_vertreter_suffix`, lokal `bek_gram`), Frontend
  `KlageWizard.jsx`-Exporte (`anredeNorm`, `kanonischeBeklagte`, `beklagtenGrammatik`,
  `versichererSuffix`). Insurer-Klassifikation überall
  `versicherung || (firma && !ist_halter)` (Abschluss-Review-Fix 6774b443).
- **DOCX-Direkttest-Muster**: backend/tests/test_klage_service_docx.py (~50 Tests,
  echtes Rendering via zipfile→document.xml) — für KW-09/12 ideal (Datums-/
  Anlagen-Strings im XML asserten). Reine Helfer-Tests: test_klage_partei_grammatik.py.
- **Route-Test-Harness**: backend/tests/test_klage_kw18_route.py (Flask-Client, Login,
  Temp-SQLite, generiere_klageschrift gepatcht) — Vorlage für Router-Verhalten;
  Achtung: `_err()` liefert JSON-Key `"fehler"`, nicht `"error"`.
- Benannte Frontend-Exporte (KlageWizard.jsx): StepZusammenfassung, StepGebuehren,
  StepSchaden, StepRw, ANTRAEGE_PLACEHOLDER, baueAntraegeText, buildSachverhaltText,
  buildRwVorschau, berechneKlagebetrag, berechneSwAussergEffektiv + die V3-Helfer oben.
- Subagent-Falle: Test-Anweisung von Anfang an „NIEMALS run_in_background, immer
  blockierend im Vordergrund, Timeout bis 600000 ms, volle Suite notfalls splitten".

Wechselwirkungen mit S3-Änderungen:
- Die Antrags-Subjekte kommen jetzt aus `bek_gram['verurteilt']` etc. — KW-09/10
  ändern in denselben Antragssätzen NUR die Zins-Datums-Teile (`seit {…}`), die
  Parteibenennung nicht anfassen. Byte-Regressionstests aus S3 pinnen die Sätze.
- StepZusammenfassung wurde in S3 um den 0-Beklagte-Guard erweitert (KW-19) — beim
  KW-13-Umbau der RVG-Zeilen in Step 10 die `gesperrt`-Logik und Warnblöcke nicht
  beschädigen (KlageWizard.zusammenfassung.test.jsx deckt sie ab).
- KW-18 (S3): generiere_klageschrift wirft ValueError → Route 422. Beim
  KW-08-Legacy-Ausbau beachten; S3-Review-Follow-up (note only): den breiten
  `except ValueError` verengen bzw. `logger.warning` ergänzen — kann in S4 als
  Mini-Task mitgehen, wenn ohnehin am Router gearbeitet wird.
- `wizardVerzugManuell`-Muster (PRD-35) existiert bereits für Manual-Edit-Schutz in
  Step 8 — KW-10-State-Konsolidierung darauf aufsetzen.
- sg_text_builder hat seit S3 den Param `verb_hat` (Forderungsschreiben-Pfad nutzt
  den Default) — bei KW-12 (dort ist „Anlage K 2" hart kodiert) Signatur-Erweiterungen
  wieder rückwärtskompatibel mit Default-Werten bauen.
- Vertagte Minors bleiben S6 (KW-34/36, Rundungs-Helper BE/FE, hq=0-Guard) und stehen
  im Tracking-Doc + .superpowers/sdd/progress.md — nicht mitfixen, nur nicht
  verschlimmern. Rest-Lücke (dokumentiert, nicht S4): AktLeg-Block/Forderungsschreiben
  nicht plural-gehärtet.

Abschluss: Tracking-Doc + TODO.md aktualisieren, Abschluss-Review (Opus,
Whole-Branch), Commits auf dem Branch, FF-Merge nach main nach Freigabe.
