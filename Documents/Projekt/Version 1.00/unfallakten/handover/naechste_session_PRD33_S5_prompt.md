# Prompt für die nächste Session — PRD-33 Session 5 (Wizard-State/UX-Cluster)

> Zum Einfügen als Start-Prompt. Stand: 2026-07-18 nach Abschluss Session 4.

---

Wir setzen PRD-33 (Klage-Wizard) fort. docs/BUGFIX_KLAGE_WIZARD.md ist das maßgebliche
Tracking-Dokument — zuerst vollständig lesen, ebenso docs/TODO.md und
handover/klage_wizard_map.md. Sessions 1–4 sind erledigt (FF-Merges 578c93e0, d19b9640,
d856a8d4; Session 4 auf Branch `klage-wizard-fixes-s4`, FF-Merge-Status siehe TODO.md).
Session 4 hat V5 (Datumsvertrag), V6 (RVG-Bereinigung), V4 (AnlagenZaehler) eingeführt
und den Legacy-Generieren-Pfad entfernt (Details unten).

Heutige Session = Session 5 aus dem Tracking-Dokument: Wizard-State/UX — V7
(zentrales Dirty-Tracking) als gemeinsames Muster. Genau diese sieben Bugs:

1. KW-22 (P3) — Anträge-Text stale nach Positions-/SG-Änderung; Feststellungs-Checkboxen
   ohne Textwirkung (KlageWizard.jsx: nur generieren wenn leer; Checkbox-onChange ruft
   regenerieren() nicht). Seit dem KW-01-Fix (S1) ist das AKUT — der stale Text landet
   als antraege_override im DOCX. V7-Leitidee: Dirty-Tracking {text, istManuell,
   basisHash} im Section-State, Badge „Text veraltet" mit Neu-generieren/Behalten.
2. KW-24 (P3) — Step-9-Änderungen nach Erst-Ersetzung wirkungslos; `wizardGebuehrenText`
   wird nie gesendet. Gebühren-Antrag nicht per String-Ersetzung „einbrennen", sondern
   als eigenes Segment führen; Dirty-Tracking wie KW-22.
3. KW-25 (P3) — Step 3: manuelle Sachverhalt-Edits beim Remount überschrieben
   (`prevAutoRef` lokal in StepAktLeg). Manuell-Flag in den Section-State heben —
   das `wizardVerzugManuell`-Muster (PRD-35/S4) ist die Vorlage.
4. KW-26 (P3) — Fortschrittsbalken umgeht kannWeiter()-Sperren (Balken: alles ≤ maxStep
   klickbar). Balken-Klick durch dieselbe kumulative kannWeiter-Prüfung leiten.
5. KW-27 (P3) — Gericht-Persistenz: Rückweg tot (`rolle='gericht'` wird vorab
   weggefiltert; Prio-1a-Loop findet nie etwas). Gericht-Zeile vor dem Rollen-Filter
   lesen — oder strukturell V9 (eigenes Feld an unfallakte; nur wenn ohnehin nötig).
6. KW-28 (P3) — Verzugsdokument-Auswahl ohne Wirkung (Placebo): `verzugDokId` wird nie
   gesendet, Auswahl übernimmt nicht das Dokumentdatum. Fix-Richtung: Auswahl setzt
   `wizardVerzugDokDatum` (= Schreibdatum, seit S4 eigener cfg-Key
   `verzug_schreiben_datum`) und via `verzugEintrittDefault` (+14 Tage) den
   Eintritt-Vorschlag — oder Feld entfernen.
7. KW-29 (P3) — Vertreter-Lookup-Modal öffnet wiederholt unaufgefordert (Auto-Lookup je
   Firma, Guard prüft nur `laden`). Auto-Lookup still cachen, Modal nur auf Klick;
   „dismissed"-Set je Sitzung.

Arbeitsregeln: TDD strikt (fehlschlagender Test = Verifikation; falscher Fund →
`entfällt` mit Begründung). Zeilennummern im Tracking-Doc sind Stand VOR Session 1 —
durch S1–S4 stark verschoben, immer frisch prüfen (Ist-Erhebung per Explore-Agent zu
Beginn hat sich erneut bewährt). RA-MICRO read-only, keine Migration erwartet (außer
ggf. V9-Entscheidung bei KW-27 — dann vorher fragen). Baseline: Backend 204f/1056p/18s
(204f = bekannte Alt-Cluster test_modul2/3/4/7, test_sv_portal, test_prd27), null
neue Failures; Frontend 159 Vitest + Build grün. Arbeitsbranch von main (z. B.
klage-wizard-fixes-s5), am Ende FF-Merge nach Freigabe. Beim Abhaken: [x] +
Commit-Hash im Tracking-Doc, Status-Tabelle mitpflegen, TODO.md aktualisieren.
Docker-Dev: HMR unter Windows kaputt → Frontend-Container ggf. neu starten (für
Vitest/Build irrelevant, die laufen direkt im frontend/-Ordner).

Nützliches aus S4 (unbedingt nutzen):
- **Datums-Helfer**: `fmtDatumDe` + `verzugEintrittDefault` in
  `frontend/src/config/utils.js` (wortgleicher Port von `_fmt_datum`; Tests
  utils.fmtDatumDe.test.js). Neue Datumsanzeigen IMMER durch fmtDatumDe leiten.
- **Verzug-Vertrag seit S4**: cfg `verzugsdatum` = Verzugseintritt,
  `verzug_schreiben_datum` = Schreibdatum; FE-SSOT `wizardVerzugDatum` +
  `wizardVerzugDokDatum`; der Alt-State `verzug` existiert NICHT mehr.
  `buildVerzugAutoText(dokDatum, eintrittDatum)` ist exportiert: ohne Eintritt →
  Rechtshängigkeit, ohne Schreibdatum → kein BEWEIS-Satz (KlageWizard.verzug.test.jsx).
- **RVG seit S4**: nur noch Nr. 2300 außergerichtlich (`wizardRvgAussergData`/-`Ov`);
  `rvgOverride`/cfg-`rvg`/`rvg_override` existieren nicht mehr; StepVerzug und
  StepZusammenfassung haben KEINE rvgData/rvgOverride-Props mehr. Step 10 zeigt
  „Gerichtlicher Streitwert (Gegenstandswert)" als Zahl.
- **AnlagenZaehler (KW-12)**: K-Nummern werden zentral in klage_service vergeben;
  `_max_anlagen_nr` scannt die vier Override-Texte („K1" und „K 1"). Bei KW-22/24
  (Antrags-/Gebührentext-Umbau) KEINE Anlagen-Verweise in neue Auto-Texte einbauen,
  ohne den Zaehler zu nutzen.
- **Legacy weg (KW-08)**: `wizardGenerieren()` ist die EINZIGE cfg-Versandstelle —
  KW-24 (wizardGebuehrenText senden) dort anbinden.
- **DOCX-Direkttest-Muster**: backend/tests/test_klage_service_docx.py (~57 Tests);
  Route-Harness test_klage_kw18_route.py (inkl. assertLogs-Beispiel).
- Subagent-Falle: Test-Anweisung von Anfang an „NIEMALS run_in_background, immer
  blockierend im Vordergrund, Timeout bis 600000 ms, volle Suite notfalls splitten".

Vertagte Minors aus S4 (Tracking-Doc/Ledger, nicht mitfixen, nur nicht verschlimmern;
Kleinkram davon kann als Mini-Task mitgehen, wenn ohnehin an der Datei gearbeitet wird):
- Stale Docstring `rvg_override` im /generieren-Endpoint (klage_routes.py ~Z.1169).
- Toter Fixture-Rest `rvgData: null, rvgOverride: null` in
  KlageWizard.haftungsquote.test.jsx (~Z.205).
- try/catch in fmtDatumDe ist totes Gerüst (strukturelle Parität zum Python-Original).
- Rest-Lücke aus S3: AktLeg-Block/Forderungsschreiben nicht plural-gehärtet.
- S6 bleibt: KW-30–40 + V10 Golden-File-Matrix, Rundungs-Helper BE/FE, hq=0-Guard.

Abschluss: Tracking-Doc + TODO.md aktualisieren, Abschluss-Review (Opus,
Whole-Branch), Commits auf dem Branch, FF-Merge nach main nach Freigabe.
