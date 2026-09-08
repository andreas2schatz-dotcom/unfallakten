# Prompt für nächste Session: PRD-33 Bugfix-Session 1 (Klage-Wizard)

---

Wir setzen PRD-33 (Klage-Wizard) um. Die Ist-Analyse ist abgeschlossen: **`docs/BUGFIX_KLAGE_WIZARD.md`** ist das maßgebliche Tracking-Dokument (40 Bugs KW-01–KW-40, Prioritäten, Fix-Richtungen, Session-Aufteilung) — **zuerst vollständig lesen**, ebenso `docs/TODO.md` (Pflichtlektüre) und `handover/klage_wizard_map.md` (Architektur-Überblick Wizard).

**Heutige Session = Session 1 aus dem Tracking-Dokument, genau diese vier Fixes:**

1. **KW-01 + KW-23 ZWINGEND ZUSAMMEN** — Anträge-Override-Merge-Lücke (`klage_routes.py:1170`: nur die 3 rvg_*-Keys werden aus `overrides` gemergt; `antraege_override`, `mit_feststellung_sg`, `mit_feststellung_sach` gehen verloren — dieser Fund ist bereits im Code verifiziert) **plus** Platzhalter-Guard in Step 10 (`KlageWizard.jsx`: `antraegeText` enthält „[Außergerichtliche Anwaltsgebühren – wird in Schritt 9 ergänzt]" → Warnblock + Generieren sperren). ⚠️ KW-01 maskiert derzeit KW-23: Fixt man nur den Merge, kann der Platzhalter-Text als Klageantrag im DOCX landen. Reihenfolge im TDD: erst Guard-Test (Frontend), dann Merge-Fix (Backend).
2. **KW-02** — RVG-Faktor landet im Euro-Override: `KlageWizard.jsx:1954` schreibt `String(neuerFaktor)` in `rvgAussergOv`, das überall als Euro gelesen wird (→ DOCX „weitere 1,50 €"). Fix-Richtung: Faktor und Euro-Betrag als getrennte Felder/States; die Gebühren-Analyse setzt nur den Faktor und rechnet neu. Auch das tote Prefill `KlageSection.jsx:236–238` bereinigen.
3. **KW-14** — `klage_routes.py:1399`: `.items()` auf der `Schadenposition`-Dataclass wirft AttributeError, Best-Effort schluckt ihn → das `klage_generiert`-Ereignis wird immer OHNE Positionen gebucht (betrifft P1.4-Positionsmodell). Fix: korrekt serialisieren, Test dass das Ereignis Positionen trägt, Fehler mindestens `logger.error`.

**Arbeitsregeln (aus dem Tracking-Doc):**
- TDD strikt: erst fehlschlagender Test (= Verifikation des Funds), dann Fix. Kein Refactoring über den Fix hinaus. Stellt sich ein Fund als falsch heraus: mit Begründung als `entfällt` abhaken.
- Zeilennummern im Doc sind Stand 2026-07-17 — vor jedem Fix die Stelle frisch verifizieren.
- RA-MICRO read-only. Keine Migration nötig (reine Code-Fixes).
- Baseline: Backend 204f-Alt-Cluster-Baseline, **null neue Failures**; Frontend 91 Tests + Build grün.
- Arbeitsbranch von `main` abzweigen (z.B. `klage-wizard-fixes`), am Ende Fast-Forward nach `main` (Projekt-Muster).
- Beim Abhaken in `docs/BUGFIX_KLAGE_WIZARD.md`: `[x]` + Commit-Hash; Status-Tabelle mitpflegen.
- Docker-Dev: HMR unter Windows kaputt → Frontend-Container ggf. neu starten.

**Wichtig — bereits getroffene Grundsatzentscheidungen (RA Schatz, 2026-07-17, im Tracking-Doc dokumentiert, NICHT neu diskutieren):** Haftungsquote = zwei Fälle (gegnerisch=Darstellung / eigene=quotiert, erst quotieren dann Zahlungen abziehen); Legacy-Button wird entfernt; keine gerichtliche Gebührenberechnung (gerichtl. Streitwert nur als Gegenstandswert-Angabe). Diese betreffen erst Session 2+4 — heute nur die vier Fixes oben.

Abschluss: Abhaken im Tracking-Doc, `docs/TODO.md`-PRD-33-Eintrag aktualisieren, Abschluss-Review, Commit(s) auf dem Branch, FF-Merge nach `main` nach Freigabe.
