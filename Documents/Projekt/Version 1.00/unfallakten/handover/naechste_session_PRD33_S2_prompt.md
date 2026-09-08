# Prompt für nächste Session: PRD-33 Bugfix-Session 2 (Klage-Wizard)

---

Wir setzen PRD-33 (Klage-Wizard) fort. **`docs/BUGFIX_KLAGE_WIZARD.md`** ist das maßgebliche Tracking-Dokument — **zuerst vollständig lesen**, ebenso `docs/TODO.md` (Pflichtlektüre) und `handover/klage_wizard_map.md` (Architektur-Überblick Wizard). Session 1 (KW-01/02/14/23) ist erledigt und in `main` (FF-Merge `578c93e0`): Overrides kommen jetzt im Backend an, Platzhalter-Guard in Step 10 aktiv, Faktor/Euro getrennt, `klage_generiert`-Ereignis trägt Positionen.

**Heutige Session = Session 2 aus dem Tracking-Dokument: konsistente Beträge & Tatsachenbehauptungen im DOCX — genau diese fünf Fixes:**

1. **KW-03 (P0)** — Haftungsquote wird nie angewendet, der Auto-Text behauptet aber „Die Klageforderung wurde entsprechend gekürzt" (`klage_service.py:1409–1411`; hq fließt weder in cfg noch in Beträge ein). **Umsetzung exakt nach der bereits getroffenen Grundsatzentscheidung (im Tracking-Doc unter KW-03, NICHT neu diskutieren):**
   - **Fall A — gegnerische Quote** (HPV hat nur nach ihrer Quote reguliert): Schadentabelle UND Klagebetrag bleiben 100 %; Quote nur in der rechtlichen Würdigung erwähnen und bestreiten; der „entsprechend gekürzt"-Satz fliegt raus.
   - **Fall B — eigene Quote** (wir akzeptieren Mithaftung): Schadentabelle bleibt 100 %, Klagebetrag wird quotiert — **erst quotieren, dann Zahlungen abziehen** (Anspruch = Gesamtschaden × Quote; davon reguliert abziehen). Schmerzensgeld NICHT auto-quotieren. Die eigene Quote gilt auch für den **vorgerichtlichen Streitwert** (Basis Nr. 2300 VV RVG).
   - **UI:** Step 7 bekommt die Fall-Auswahl („gegnerisch angenommen — nur Darstellung" vs. „von uns akzeptiert — kürzt Forderung + Gebührenbasis"); je Fall eigener RW-Textbaustein.
2. **KW-04 (P0)** — Antrag 1 ≠ Schadentabelle ≠ Differenz-Satz (drei parallele Rechenwege: Antrag aus checked cfg-Positionen `klage_service.py:957–959`, Tabelle aus vollen DB-Werten `:1334–1374`, Zahlungen nur positionsgebunden `klage_routes.py:1249–1260`). Fix-Richtung: EINE Rechenquelle — Tabelle und Differenz-Satz aus denselben genetteten, checked cfg-Positionen speisen wie Antrag 1 (oder „offen je Position" ins Backend, Verbesserung V2, falls beim Umsetzen sinnvoller).
3. **KW-05 (P0)** — Einleitung behauptet bedingungslos Eigentum („{kl_nom} ist Eigentümer des … Fahrzeugs", `klage_service.py:1289–1296`) — bei Leasing/Finanzierung direkter Widerspruch zum AktLeg-Block, bei Eigentum Dublette. Fix: Eigentumssatz vom `aktivlegitimation_typ` abhängig machen (finanziert/geleast → „Halter und unmittelbarer Besitzer" o.ä.), Dublette entfernen.
4. **KW-07 (P1)** — Schmerzensgeld doppelt einklagbar: SG als bezifferte checked Position UND `mit_schmerzensgeld` mit Mindestbetrag (`klage_routes.py:802–803`, `klage_service.py:957–959, 1026, 1213 ff.`, `forderungsschreiben_wv.py:804`) → Gegenstandswert zu hoch, SG in Antrag 1 UND als eigener Antrag. Fix: gegenseitiger Ausschluss (bei `mit_schmerzensgeld=true` SG-Position aus Antrag 1/Tabelle/Streitwert nehmen, oder Checkbox in Step 5 mit Hinweis deaktivieren).
5. **KW-11 (P1)** — Unkostenpauschale nicht abwählbar: `forderungsschreiben_wv.py:807` macht per `or 30.0` aus explizit 0,00 € wieder 30 €; die Abwahl-Weiche `klage_routes.py:1221–1222` ist tot (`s()` gibt nie None). Fix: None-Semantik sauber trennen (nicht gesetzt vs. explizit 0); Default-30 nur bei „nicht gesetzt". Verstärkt KW-04 — sinnvoll nach/mit KW-04 fixen.

**Arbeitsregeln (aus dem Tracking-Doc):**
- TDD strikt: erst fehlschlagender Test (= Verifikation des Funds), dann Fix. Kein Refactoring über den Fix hinaus. Stellt sich ein Fund als falsch heraus: mit Begründung als `entfällt` abhaken.
- Zeilennummern im Doc sind Stand 2026-07-17 (vor Session 1) — durch Session 1 leicht verschoben, vor jedem Fix frisch verifizieren.
- RA-MICRO read-only. Voraussichtlich keine Migration (reine Code-Fixes; falls doch eine nötig wird: Reloader-Trap beachten, Migration atomar in EINEM Edit).
- Baseline: Backend voller Lauf 204f-Alt-Cluster (Stand nach S1: 204f/965p), **null neue Failures**; Frontend 97 Tests + Build grün.
- Arbeitsbranch von `main` abzweigen (z.B. `klage-wizard-fixes-s2`), am Ende Fast-Forward nach `main` nach Freigabe (Projekt-Muster).
- Beim Abhaken in `docs/BUGFIX_KLAGE_WIZARD.md`: `[x]` + Commit-Hash hinter den Titel; Status-Tabelle mitpflegen. `docs/TODO.md`-PRD-33-Eintrag aktualisieren.
- Docker-Dev: HMR unter Windows kaputt → Frontend-Container ggf. neu starten.
- Nützlich aus Session 1: `KlageWizard.jsx` exportiert `StepZusammenfassung`, `StepGebuehren`, `ANTRAEGE_PLACEHOLDER` als benannte Exporte (Testmuster `KlageWizard.*.test.jsx`); Backend-Route-Test-Muster in `test_klage_overrides_merge.py` / `test_klage_ereignis_positionen.py` (Temp-DB, Auth, gemockter `generiere_klageschrift`).

**Wichtige Wechselwirkungen:**
- KW-03 Fall B ändert die Nr.-2300-Basis (vorgerichtlicher Streitwert) → Zusammenspiel mit Step 9 (`swAusserg`, `rvg_ausserg`) beachten; KW-13 (Streitwert-Aufräumen) kommt erst in Session 4 — hier nur so viel anfassen wie für Fall B nötig.
- KW-04 und KW-11 hängen zusammen (Unkostenpauschale-Zwangs-30 € verfälscht die Tabelle) — Reihenfolge/Zusammenlegung im Plan selbst entscheiden.
- Seit Session 1 kommt `antraege_override` real im Backend an: Der im Frontend gebaute Antragstext (Step 6) nennt Beträge als Fließtext. Wenn KW-03/04/07 die Rechenwege ändern, muss auch `baueAntraegeText()`/die Klagebetrag-Berechnung im Wizard konsistent mitziehen — sonst entsteht neuer Widerspruch Antragstext ↔ Tabelle (das volle Stale-Text-Problem KW-22 bleibt aber Session 5).

Abschluss: Abhaken im Tracking-Doc, `docs/TODO.md` aktualisieren, Abschluss-Review, Commits auf dem Branch, FF-Merge nach `main` nach Freigabe.
