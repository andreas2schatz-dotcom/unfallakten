# Prompt für die nächste Session — PRD-33 Session 6 (Politur + Regressionsschutz)

> Zum Einfügen als Start-Prompt. Stand: 2026-07-18 nach Abschluss Session 5.

---

Wir setzen PRD-33 (Klage-Wizard) fort — letzte Session der Reihe. docs/BUGFIX_KLAGE_WIZARD.md
ist das maßgebliche Tracking-Dokument — zuerst vollständig lesen, ebenso docs/TODO.md und
handover/klage_wizard_map.md. Sessions 1–5 sind erledigt (S1–S4 per FF in main; Session 5
auf Branch `klage-wizard-fixes-s5`, FF-Merge-Status siehe TODO.md/Tracking-Doc).

Heutige Session = Session 6 aus dem Tracking-Dokument: **KW-30–KW-40 (offene) + V10
Golden-File-Matrix**. Konkret offen:

1. KW-30 (P4) — Leere Felder erzeugen kaputte Sätze („…Unfall vom … in  geltend");
   bedingte Segmente + Pflichtfeld-Warnung in Step 10.
2. KW-31 (P4) — `sachverhalt_override` zerstört Absatzstruktur (Split nur auf `\n\n`,
   BEWEIS-Zeilen mit einfachem `\n` werden Fließtext).
3. KW-32 (P4) — Verzug-Abschnitt ohne Nummer/Überschrift; laufender Abschnittszähler
   statt Arithmetik `5 + int(mit_sg)`.
4. KW-33 (P4) — SG-Beweisantritt via `_beweis()` formatieren statt `_p(einzug=True)`.
5. KW-34 (P4) — RVG-Antrag über „0,00 €" möglich; zusammen mit dem S2-Klammer-Randfall
   (Fall B: Zahlungen > quotierter Anspruch → `zahlungen_anzeige` juristisch schief) lösen.
6. KW-36 (P4) — Haftungsquote int-Truncation an den verbliebenen Alt-Stellen; dabei die
   S2-Empfehlung umsetzen: gemeinsamer Rundungs-Helper BE/FE (JS `Math.round` half-up vs.
   Python banker's — 1-Cent-Divergenz-Risiko) + optional hq=0-Guard bei `typ=eigen`.
7. KW-37 (P4) — RVG-Faktor „(1.3)" mit Punkt statt Komma.
8. KW-38 (P4) — Positions-Key-Vertrag: vollständiges `_KEY_MAP` + Test gegen alle
   `regulierung_positionen.position_key`-Werte (Vorgeschichte: [[unfallakten-key-mismatch-bug]]).
9. KW-40 (P4) — Sammelposten toter Code/Kleinkram (Liste im Tracking-Doc; inkl.
   `_merge_split_placeholders` nur auf GEGENSTANDSWERT — Absicherung via V10).
10. V10 — Render-Smoke-Test (kein `{{` im Ergebnis-XML) + Golden-File-Matrix
    (mit/ohne SG × 1/2 Beklagte × eigentum/finanziert/geleast × Overrides an/aus);
    Muster: backend/tests/test_klage_service_docx.py (~60 Tests, echtes DOCX + zipfile).

Arbeitsregeln: TDD strikt (Verhaltens-Rot, Import-Fehler zählt nicht; falscher Fund →
`entfällt` mit Begründung). Zeilennummern im Tracking-Doc sind Stand VOR Session 1 —
durch S1–S5 stark verschoben, Ist-Erhebung per Explore-Agent zu Beginn (bewährt).
RA-MICRO read-only, keine Migration erwartet. Baseline: Backend 204f/1059p/18s
(204f = bekannte Alt-Cluster test_modul1–7, test_dashboard_uebersicht, test_sv_portal,
test_prd27, test_modul6, test_migration_46; Achtung: ±2 Test-Order-Rauschen im
Auth-Cluster möglich — bei Abweichung Datei-Ebene vergleichen), null neue Failures;
Frontend 200 Vitest + Build grün. Arbeitsbranch von main (z. B. klage-wizard-fixes-s6),
am Ende FF-Merge nach Freigabe. Beim Abhaken: [x] + Commit-Hash im Tracking-Doc,
Status-Tabelle mitpflegen, TODO.md aktualisieren.

Nützliches aus S5 (unbedingt nutzen/nicht brechen):
- **V7-Muster**: Manuell-Flags `wizardSachverhaltManuell`/`wizardGebuehrenManuell`/
  `wizardAntraegeManuell` im Section-State; `antraegeBasis`/`AntraegeSync`/
  `TextVeraltetBadge` (KlageWizard named exports). Neue textrelevante Eingaben für den
  Anträge-Text MÜSSEN in `antraegeBasis` aufgenommen werden, sonst erkennt das
  Dirty-Tracking sie nicht.
- **KW-24-Vertrag**: Platzhalter `ANTRAEGE_PLACEHOLDER` bleibt DAUERHAFT in
  `wizardAntraegeText`; `komponiereAntraege(antraegeText, gebuehrenText)` ersetzt erst
  beim Senden (`wizardGenerieren`) und in Anzeigen/Guards (Step 6 + 10). NIE wieder
  einbrennen.
- **Named Exports seit S5**: `schrittBlockiert`, `kannSpringen`, `Fortschrittsbalken`,
  `StepAktLeg`, `StepAntraege`, `StepVerzug`, `komponiereAntraege`, `antraegeBasis`,
  `AntraegeSync`, `TextVeraltetBadge` (KlageWizard.jsx); `verzugDatenAusDok`,
  `sollAutoLookup` (KlageSection.jsx — erste named exports der Datei).
- **KW-28-Backend**: `verzug_dokumente` liefert `datum` (MAX `forderung_positionen.datum`
  je Dokument, korrelierte Subquery) — Schreibdatum-Quelle, `hochgeladen_am` nur Fallback.
- **KW-27**: Frisch-DB-CHECK `beteiligte.rolle` enthält jetzt `'gericht'`
  (backend/db/schema.py); Bestands-DBs unberührt.
- **Subagent-Regeln** (haben sich erneut bewährt): Tests NIE run_in_background, immer
  Vordergrund, Timeout bis 600000 ms; TDD-Rot muss VERHALTENS-Rot sein (Export-only-
  Zwischenschritt), sonst Controller-Gegenbeweis per Mutation.

Vertagte Minors aus S4+S5 (nicht mitfixen, nur nicht verschlimmern; Kleinkram davon darf
als Mini-Task mitgehen, wenn ohnehin an der Datei gearbeitet wird):
- S4-M5: BE-BEWEIS-Fallback aufs Eintrittsdatum divergiert von FE (UI-unerreichbar) — angleichen.
- S4-M6: StepVerzug-Textfeld zeigt ISO-Rohwert bei Vorbelegung (vorbestehend).
- Toter Fixture-Rest `rvgData/rvgOverride` in KlageWizard.haftungsquote.test.jsx (~Z.205).
- try/catch in fmtDatumDe ist totes Gerüst (bewusster BE-Spiegel).
- Rest-Lücke S3: AktLeg-Block/Forderungsschreiben nicht plural-gehärtet.
- S5: tote Props `antraegeText`/`onAntraegeText` in StepGebuehren-Signatur; Kachel-5-
  Wiring von `waehleVerzugDok` ohne dedizierten Test (review-verifiziert); `antraegeBasis`-
  `bek`-Fingerprint erfasst anrede/versicherung/firma nicht (nur relevant, falls
  Beklagten-Stammdaten im Wizard editierbar werden); Fixture-Boilerplate-Duplikat
  test_klage_kw18↔kw27.
- Offene Nutzer-Bestätigungen: Verzugseintritt-Default +14 Tage (S4); KW-29-Design
  „fehlgeschlagener Auto-Lookup blockiert Auto-Retries für die Sitzung" (S5);
  KW-28 `hochgeladen_am`-Fallback als Schreibdatum-Vorschlag für gescannte
  Fremdschreiben ohne forderung_position (S5-Abschluss-Review I1 — editierbar, aber
  Upload≠Schreibdatum möglich; Alternative: kein Vorschlag/null); KW-27 Rebuild-
  Migration für Bestands-DBs mit altem beteiligte-CHECK (Live-Dev-DB nicht betroffen,
  Go-Live-Check 6b im Rollout-Runbook; nur nötig falls eine betroffene DB in Betrieb geht).
- KW-27-Kontext: `gerichtSpeichernOderWarnen` (KlageSection named export) zeigt
  Persistenz-Fehlschläge als Toast — nicht wieder still schlucken.

Abschluss: Tracking-Doc + TODO.md aktualisieren (PRD-33 damit KOMPLETT — Abschluss-Vermerk),
Abschluss-Review (Opus, Whole-Branch), Commits auf dem Branch, FF-Merge nach Freigabe.
