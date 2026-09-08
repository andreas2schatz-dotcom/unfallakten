# Prompt für die nächste Session — PRD-33 Session 3 (Rubrum/Grammatik-Cluster)

> Zum Einfügen als Start-Prompt. Stand: 2026-07-17 nach Abschluss Session 2.

---

Wir setzen PRD-33 (Klage-Wizard) fort. docs/BUGFIX_KLAGE_WIZARD.md ist das maßgebliche
Tracking-Dokument — zuerst vollständig lesen, ebenso docs/TODO.md und
handover/klage_wizard_map.md. Session 1 (KW-01/02/14/23) und Session 2
(KW-03/04/05/07/11 + KW-39 vorgezogen) sind erledigt und in main (FF-Merges 578c93e0
bzw. d19b9640, nicht gepusht — main ist ~55 Commits vor origin/main).

Heutige Session = Session 3 aus dem Tracking-Dokument: Rubrum & Grammatik — am besten
als V3-Refactoring (Partei-Objekt mit Genus/Numerus) in einem Zug statt acht
Einzel-Pflaster. Genau diese acht Bugs:

1. KW-06 (P1) — Mehrere Beklagte: Anträge im Singular, „als Gesamtschuldner" fehlt
   komplett (klage_service.py, Anträge + Einleitung; nur Kostenantrag und VK-Abschnitt
   pluralisieren). Frontend-Pendant: baueAntraegeText() hat „(zu 1)" hart kodiert,
   ebenso EinwandePanel und StepGebuehren.
2. KW-15 (P2) — Rubrum-Rolle immer feminin („– Beklagte –" auch bei männlichem
   Fahrer). Genus aus beteiligte.anrede ableiten (sAnrede-Mapping existiert,
   „1"=Herr/„2"=Frau); Firmen bleiben „Beklagte".
3. KW-16 (P2) — Vertreter-Grammatik: Artikel hart „den" („vertreten durch den
   Geschäftsführerin"); Anrede-Heuristik prüft nur die Funktion, nicht den Namen.
4. KW-17 (P2) — Mehrere Kläger: Singular-Verben bei Plural-Subjekt („Die Kläger
   macht … geltend"), Vorsteuer bei mehreren Klägern ignoriert; auch
   sg_text_builder.py betroffen.
5. KW-18 (P2) — Rubrum ohne Kläger möglich (kein Fallback auf akte_daten["mandant"];
   mandant_name wird gelesen, aber nie genutzt). Fallback + harte Sperre/Fehlermeldung.
6. KW-19 (P2) — Generieren mit 0 Beklagten möglich (gesperrt-Guard in Step 10 prüft
   Beklagte nicht). beklagteG.length === 0 in die Sperr-Bedingungen aufnehmen.
7. KW-20 (P2) — Beklagten-Nummerierung Sachverhalt ≠ Rubrum (buildSachverhaltText hat
   eigene Reihenfolge/Zählung; Nicht-Halter-Privatperson fehlt; Versicherung mit
   ist_halter=1 doppelt gezählt). EINE gemeinsame Funktion liefert die kanonische
   Beklagten-Liste (Reihenfolge + Nummern) für Rubrum UND Sachverhalt.
8. KW-21 (P2) — Rechtsform-Heuristik matcht Substrings („UG" in „FAHRZEUGBAU";
   „…Versicherungs-AG" fällt durch). Wortgrenzen-Regex inkl. Suffix-Varianten.

V3-Leitidee (Tracking-Doc): Partei-Objekt mit Genus/Numerus (bez, Artikel-Formen,
Verbform Sg/Pl) + Gesamtschuldner-Baustein statt verstreuter Ternaries — behebt
KW-06 + KW-15–17 strukturell. KW-18/19/21 sind davon unabhängige kleine Fixes,
KW-20 ist das Frontend-Gegenstück (kanonische Liste ggf. mit demselben Objekt).

Arbeitsregeln: TDD strikt (fehlschlagender Test = Verifikation; falscher Fund →
`entfällt` mit Begründung). Zeilennummern im Tracking-Doc sind Stand VOR Session 1 —
durch S1+S2 deutlich verschoben, immer frisch prüfen (Ist-Erhebung per Explore-Agent
zu Beginn hat sich bewährt). RA-MICRO read-only, keine Migration erwartet.
Baseline: Backend 204f/1000p/18s (204f = bekannte Alt-Cluster test_modul2/3/4/7,
test_sv_portal, test_prd27), null neue Failures; Frontend 122 Vitest + Build grün.
Arbeitsbranch von main (z. B. klage-wizard-fixes-s3), am Ende FF-Merge nach Freigabe.
Beim Abhaken: [x] + Commit-Hash im Tracking-Doc, Status-Tabelle mitpflegen, TODO.md
aktualisieren. Docker-Dev: HMR unter Windows kaputt → Frontend-Container ggf. neu
starten (für Vitest/Build irrelevant, die laufen direkt im frontend/-Ordner).

Nützliches aus S2 (unbedingt nutzen):
- **DOCX-Direkttest-Muster**: backend/tests/test_klage_service_docx.py rendert echte
  DOCX via generiere_klageschrift + zipfile→document.xml. Ideal für Rubrum-/
  Grammatik-Assertions (Vorkommen zählen, XML-Escaping beachten). 25 Tests als Vorlage.
- Benannte Frontend-Exporte: StepZusammenfassung, StepGebuehren, StepSchaden,
  ANTRAEGE_PLACEHOLDER, buildRwVorschau, berechneKlagebetrag,
  berechneSwAussergEffektiv, pctStr (KlageWizard.jsx).
- Subagent-Falle aus S2: Test-Anweisung von Anfang an „NIEMALS run_in_background,
  immer blockierend im Vordergrund, Timeout bis 600000 ms, volle Suite notfalls in
  zwei Hälften splitten" — sonst hängen Agents in Hintergrund-Warteschleifen.

Wechselwirkungen mit S2-Änderungen:
- buildRwVorschau hat seit S2 einen Parameter `beklagte` und enthält den genus-/
  anzahlbewussten „alleinige Haftung"-Satz (hq=100) — diese Logik überschneidet sich
  mit KW-20/V3: bei Einführung einer kanonischen Beklagten-Liste dort mit anbinden,
  nicht duplizieren.
- KW-05 (S2) hat die Einleitung typabhängig gemacht (Eigentümer/Halter-Sätze mit
  anrede_m-Flexion) — KW-17-Numerus-Arbeit an denselben Sätzen darauf aufsetzen.
- KW-07 (S2): SG-Position wird bei mit_sg vor der checked-Filterung ausgeschlossen;
  KW-04 (S2): Tabelle/Differenz-Satz hängen an den checked Positionen — bei
  KW-06-Antragsumbau (Gesamtschuldner-Baustein) darf sich am Klagebetrag nichts
  ändern, nur an der Parteibenennung.
- Der Legacy-generieren()-Button existiert noch (quotierungsblind) — sein Ausbau ist
  KW-08 und kommt in Session 4, in S3 NICHT anfassen.
- Vertagte Minors aus S2 stehen im Tracking-Doc (KW-34/KW-36-Abschnitte) und in
  .superpowers/sdd/progress.md — nicht in S3 mitfixen, nur nicht verschlimmern.

Abschluss: Tracking-Doc + TODO.md aktualisieren, Abschluss-Review (Opus,
Whole-Branch), Commits auf dem Branch, FF-Merge nach main nach Freigabe.
