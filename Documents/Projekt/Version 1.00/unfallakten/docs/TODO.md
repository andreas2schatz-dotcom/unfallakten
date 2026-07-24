# TODO – Unfallakten-Verwaltungssystem

> Schlanke Arbeitsliste — nur Zukunftsgerichtetes. Zuletzt gestrafft: 2026-07-20.
> Erledigtes mit Protokoll → `docs/CHANGELOG.md` · Entscheidungen mit Begründung → `docs/DECISIONS.md` · Deploy/Betrieb → `docs/STATE.md`.

---

## 🔄 In Arbeit

### Klage-Wizard-Verbesserungsrunde (4 Pakete, Designs freigegeben 2026-07-19)
Empfohlene Reihenfolge 1→2→3→4 (3+4 teilen sich den Textaufbau-Umbau/V11 — bei der Planung abstimmen). Je Paket vor Umsetzung `superpowers:writing-plans` auf die Spec.

1. **Entwurf speichern** — ✅ umgesetzt + in `main` (2026-07-19). Detail → CHANGELOG.
2. **UI-Führung** — ✅ KOMPLETT (Browser-Nachtest bestanden 2026-07-23: Status-Symbole, Schließen-Dialog, Vertreter-Lookup im Wizard). In `main`, gepusht. Detail → CHANGELOG.
3. **Gesamtvorschau** — ✅ KOMPLETT (Browser-E2E bestanden 2026-07-23: Vorschau → Sachverhalt-Edit → Übernehmen → DOCX mit geändertem Text). In `main`, gepusht. Spec: `docs/superpowers/specs/2026-07-19-klage-wizard-gesamtvorschau-design.md`.
4. **Standardtexte pflegbar (V11)** — ✅ Stufe 1 umgesetzt (Branch `standardtexte-v11`). Detail → CHANGELOG.

### Kürzungstaxonomie — Phase 0 ✅ · Phase 1 ✅ · **in `main` gemergt + gepusht (2026-07-24, `febe6f06`)**
Alle 12 Tasks + Genus-Platzhalter-Nachtrag (Weg 2). Abnahme: Bausteine von RA Schatz gegengelesen ✅; Katalog-Editor, Wizard-Zitat, Genus-Formen, Speichern-Sperre per Playwright-E2E bestanden ✅ (2026-07-24). Protokoll → `docs/CHANGELOG.md`.
**Offen:**
- **Messung Zielwerte (~2026-08-20, nach ~4 Wochen Betrieb):** `docker exec unfallakten-backend-dev python /app/tools/kuerzungsmatching_report.py` — Zielwerte: Abdeckung ≥ 90 %, Trefferquote ≥ 75 %, Positionszuordnung ≥ 90 % (DECISIONS 2026-07-23). Baseline siehe CHANGELOG.
- **Fehlablage-Entscheidung RA Schatz (aus Phase 0):** Dok 41478 + 43429 aus Akten 971/25 / 980/25 löschen? (FEHLABLAGE-Vermerk gesetzt; 852/25 nur in RA-MICRO, 418/28 existiert nirgends.)
- **Runden-Kachel im echten Betrieb** sichten, sobald die erste Akte 2 Abrechnungsrunden hat (Test-Abdeckung vorhanden, echter Fall noch nicht).
Phase 2 (vorgemerkt): Trigger-Umkehr Stellungnahme (PRD-39), Zahlungs-Kaskade, Vorgangsautomat — Konzept `handover/KONZEPT-Kuerzungstaxonomie-Vorgangsautomat.md` Abschnitt 12.

---

## 📋 Backlog (nach Priorität)

### Kritisch / Bald
- **PRD-NEW – Onboarding-Wizard (Neue-Akte-Anlage):** Stub `NeueAkteModal` existiert (AZ, Unfalldatum, -ort, Notizen), echte Anlage-Logik fehlt. Braucht eigenes Brainstorming.
- **PRD-25c – Automatische Mandantenkommunikation:** `MandantenEmailDialog` nach Generierung von Forderungs-/Regulierungsschreiben; 3 Textbausteine je Trigger, neue Tabelle `mandanten_emails`. PRD: `handover/PRD-25c_Mandantenkommunikation.md`.

### UI-Kleinkram / Bugs (gemeldet RA Schatz 2026-07-23)
1. **Systemstatus-Kachel defekt:** Im Systemstatus-Reiter der Einstellungen-Section ist die Kachel nicht mehr ausklappbar — es wird nichts mehr angezeigt.
2. **Navigationsleiste links:** Alle Symbole gerade linksbündig ausrichten.
3. **Navigationsleiste links:** Hover-Effekt stärker ausprägen.
4. **E-Mail-Identifier zusammenführen:** In der Einstellungen-Section existieren „Versicherer" und „Gutachter" getrennt für E-Mail-Identifier → zu EINEM Reiter zusammenfassen mit Subreitern Versicherer/Gutachter (Muster: Personenschaden/Sachschaden).
5. **Dabei prüfen:** Welche Gutachter werden bereits als E-Mail-Identifier vom System verwendet? (Bestandsaufnahme vor dem Umbau von Punkt 4.)
6. **Reiter KI-Assistent:** Das LLM für OCR (GLM-OCR) muss dort ebenfalls einstellbar UND testbar sein (analog zum bestehenden Modell-Switcher).

### Mittel
- **V11 Stufe 2 — Kategorie C über vorflektierte Platzhalter (eigener Plan):** Stufe 1 (44 Bausteine A+B) ist umgesetzt; Stufe 2 baut auf derselben Registry/Editor-Infrastruktur auf, braucht aber eigenes Brainstorming (vorflektierte statt regelbasierte Platzhalter).
- **PRD-39 – Stellungnahme zum Abrechnungsschreiben (DOCX): bereits durch PRD-27 abgedeckt** (verifiziert 2026-07-23: 4 aktive Routen in `stellungnahme_routes.py`, voller DOCX-Generator, Tabelle `stellungnahme_texte`/Mig 40). Offen ist NUR die Trigger-Umkehr (Queue liefert fertigen Entwurf statt manuellem Wizard-Aufruf) — Teil von Phase 2 der Kürzungstaxonomie, kein eigenes Vorhaben.
- **Dokumentenklasse „Klagedrohung" mit `frist_datum` → Verzugs-Automatik im Klage-Wizard:** Fristsetzungs-Schreiben bekommen eigene Klasse + strukturiertes Fristdatum; Verzugseintritt-Vorbelegung = Tag nach Fristablauf. Zwei Befüllungswege (selbst erzeugte Schreiben stempeln die Frist exakt; importierte via Parser). `verzug_dokumente` um `frist_datum` erweitern; optional Kopplung an Fristen-System (PRD-25a). Berührt Intake + Generator — eigenes Vorhaben.
- **PRD-32 Phase 2 – Rechnungstypen Beleg-Mapping:** erkannte Typen automatisch der Schadenposition zuordnen (Standkosten→Standgeld usw.). Plan: `handover/PRD-32_Rechnungstypen_Parser.md`.
- **PRD-05 – Betrag-Abgleich nach Upload:** hochgeladene Rechnung gegen Schadenposition abgleichen.
- **PRD-03 – Klagegenerator Abschlusstest:** formaler Abnahmetest unklar (siehe „Unklar").
- **PRD-29 – Schmerzensgeld-Ermittlungstool:** Modal im Klage-Wizard, KI recherchiert Vergleichsurteile. Plan: `handover/PRD-29_Schmerzensgeld_Tool.md`.

### Später
- **PRD-01 – To-Do-System Vollausbau** (Aufgabenzuweisung, Fälligkeiten, Filterung).
- **PRD-06 – Parser Reparaturrechnung via LLM** (für nicht-Regex-parsbare Rechnungen).
- **PRD-07 – Workflow-Regeln + automatische To-Dos** (Regelmaschine bei Ereignissen).
- **PRD-21 Phase 3b/3c** – Batch-Klassifikation + Filter nach Dokumentenklasse (E-Akte).
- **PRD-04c – TF-IDF Classifier** (Ergänzung zum Regex-Dispatcher).
- **PRD-24b – Vollständiger 5-Step-Wizard** (Unfallhergang + Haftungsbegründung als eigene Steps).
- **PRD-25d – Intelligente Sachstandsanfrage.** Plan: `handover/PRD-25d_Intelligente_Sachstandsanfrage.md`.
- **Stakeholder-Portal (separates Projekt):** PORTAL-A1/B1/B2/B3 — je Plan in `handover/PORTAL-*.md`.

### UserStories (externes Review, offen)
- **PRD-US03 – SV-Portal Upload-Empfang (Kanzlei-Seite):** `POST /sv-portal/upload`, Audit-Tabelle `sv_portal_uploads`. **Braucht US04** (Gegenstelle).
- **PRD-US04 – SV-Portal-Server (Gegenstelle):** eigenständige Web-App, **nicht** im Unfallakten-Repo umsetzbar. Entspricht `handover/PORTAL-B2_SV_Cockpit.md`.

### Action-Board-Restposten (Verfeinerung)
- Fristen-Spalte zeigt nur RA-MICRO-Wiedervorlagen, keine „harten" Rechtsmittelfristen (falls RA-MICRO eine Fristen-Tabelle führt, Schritt 1 wiederholen).
- Nachrichten-Spalte: Mandantenportal-/SV-Portal-Nachrichten sind Placeholder; echte Integration hängt an PRD-25c.

---

## ⏸️ Zurückgestellt (bewusst, kein Handlungsbedarf)
- **Prod-Rollout intake-stufe1** (Nutzer 2026-07-15) → Runbook + Deploy-Reihenfolge in `docs/STATE.md`.
- **N-05** (Yielding/Teilergebnisse) und **P1.8** (Backfill, forward-only) → Begründung in `docs/DECISIONS.md`.
- **PRD-38** (Dokumentenbezeichnung per LLM) → Begründung in `docs/DECISIONS.md`.

---

## ❓ Unklar / zu klären
- **PRD-29 DKz-Filter — erledigt oder offen?** Handover sagt „implementiert" (via Schlagwort `E-Brief`, da DKz-Feld in DB fehlt), v56 sagt „nicht gestartet". Ist das ursprüngliche Ziel als erfüllt zu betrachten?
- **PRD-03 Abschlusstest** — Code in v35–v36 implementiert; ob je ein formaler Integrationstest lief, ist aus den Handovers nicht ersichtlich.

---

## ✅ Erledigt
> Kompakter Index. Vollständige Umsetzungs-Protokolle mit Commits/Tests: **`docs/CHANGELOG.md`**.

| Datum | Feature |
|---|---|
| 2026-07-23 | Kürzungstaxonomie **Phase 1 komplett** (12 Tasks: Mig 64, YAML-Registry A–F, Matching+LLM, Verkettung, Typ-UI, Runden-Vergleich, TextbausteinEditor, ZITAT, Messanker) — Branch `kuerzungstaxonomie-phase1` |
| 2026-07-23 | Kürzungstaxonomie-Konzept verifiziert + Prozess revidiert (Papier Abschnitt 12, 3 DECISIONS-Einträge); Klage-Wizard-Fix [FEHLT]-Marker; Browser-Nachtests Paket 2+3 bestanden; main gepusht (58 Commits) |
| 2026-07-21 | Klage-Wizard Paket 3: Gesamtvorschau (Server-Text-Vorschau + Inline-Edit, Single-Source; lokal main, Browser-E2E offen) |
| 2026-07-21 | Globaler Firmen-Vertreter-Speicher (Tabelle `firmen_vertreter`, aktenübergreifende Vertreter-Zuordnung) |
| 2026-07-20 | Klage-Wizard Paket 2: UI-Führung (umgesetzt, noch nicht gemergt) |
| 2026-07-19 | Klage-Wizard Paket 1: Entwurf speichern (in main) |
| 2026-07-19 | PRD-33 Klage-Wizard Feintuning KOMPLETT (40 Bugs KW-01–40, S1–6) |
| 2026-07-16 | Rausch-Absender auto-aussortieren + Papierkorb |
| 2026-07-16 | Bugfix AZ-Normalisierung + Personenschaden-Schema-Drift (Mig 60) |
| 2026-07-15 | PRD-37 Dokumentenbezeichnung (Mig 59); PDF-Splitting Review (Mig 58); Prod-Rollout Git-Teil |
| 2026-07-14 | Fragebogen-Feld-Übernahme; N-03 Retry-Differenzierung (Mig 57); N-04 Seiten-Triage |
| 2026-07-13 | Bugfix-Reihe BUG-01–30 (Intake v7); N-01/N-02 (Mig 56)/N-06; N-09/N-10; Druckbutton |
| 2026-07-12 | P1.5e Review-Freigabe schreibt Ereignisse für alle Klassen |
| 2026-07-10 | P1.7 UI-Positionsmodell; Text-Pfad Intake (Mig 54); N-08 (Mig 55)/N-07 |
| 2026-07-09 | Intake-Refactoring S1.9 + Positionsmodell P1.1–P1.6 (Mig 49/51/52) |
| 2026-07-08 | Bugfixing-Session (Testsuite-Sanierung, Mig 50 unfalldetails) |
| bis 2026-07 | Ältere PRDs (PRD-01…PRD-36, US01/02/05/06, B-08/09 …) — Index in CHANGELOG.md |
