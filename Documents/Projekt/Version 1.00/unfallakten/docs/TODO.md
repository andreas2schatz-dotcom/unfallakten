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
4. **Standardtexte pflegbar (V11)** — **wartet bewusst** (Entscheidung 2026-07-23, DECISIONS.md): Phase 1 der Kürzungstaxonomie kommt zuerst und baut die gemeinsame Editor-Komponente; V11 erbt sie. Spec bleibt gültig: `docs/superpowers/specs/2026-07-19-klage-wizard-standardtexte-design.md`.

### Kürzungstaxonomie — Phase 0 ✅ · Phase 1 GEPLANT (Plan wartet auf Freigabe)
**Phase-1-Plan (2026-07-23):** `docs/superpowers/plans/2026-07-23-kuerzungstaxonomie-phase1.md` — 12 Tasks in 4 Sessions (Migration 64 → YAML-Registry 32 A–F-Typen → Baustein-Import → Matching+LLM-Fallback → Verkettung → Typ-UI mit Pflicht-Begründung → Runden-Vergleich → TextbausteinEditor → Konsistenz → Messanker). **Vor Umsetzung: RA Schatz bestätigt die 3 Detail-Entscheidungen im Plan-Kopf** (A05a–c für Fehlerspeicher/Batterie/Tankrest, Varianten-Suffix-Modell, A09 für Technische Kürzungen).
Konzept + Verifikation: `handover/KONZEPT-Kuerzungstaxonomie-Vorgangsautomat.md` (Abschnitt 12 = verbindlicher Prozess-Stand 2026-07-23).
**Befunde 2026-07-23 (aktive DB `/app/data/unfallakten.db` im Container `unfallakten-backend-dev`, Schema 63):**
- **Der geplante Freitext-Bestand existiert nicht:** `pruefberichte` 0 Zeilen; alle 44 `regulierung_positionen.kuerzung_freitext` leer; nur 4 manuelle `kuerzungsart_id`. Handtest lief deshalb gegen die **PDF-Volltexte** (11 einzigartige Prüfberichte + 59 einzigartige Abrechnungsschreiben mit Positionen — die 672/6.243 DB-Zeilen sind Re-Import-Duplikate mit identischem `pdf_hash`).
- **Abdeckung 94 %** (30 von 32 Dokumenten mit Kürzungs-Indiz haben ≥1 Typ-Treffer); die 2 Lücken sind Zahlungsavise („Schadenzahlung…" → Fall für die Zahlungs-Kaskade, DECISIONS 2026-07-23). 5 Dokumente ohne Textschicht (Image-PDF → OCR-Pfad PRD-30). **Trefferquote** ist mangels Ground Truth nur per Stichproben-Review messbar → `handover/phase0-handtest-stichproben.md` (30 Stück, **wartet auf RA Schatz**).
- **Unkostenpauschale (15) geklärt + behoben:** `ghpfup.DOC` wird vom Import übersprungen (nur .docx/.rtf); der 2. Lauf nach der .doc→.rtf-Konvertierung schrieb in `backend/data/` (Default-Pfad) statt ins Docker-Volume. Baustein (1.882 Z., identisch mit Konvertat) am 2026-07-23 in die aktive DB übertragen → **15/19 befüllt**.
- **30-Stichproben-Review ✅ (2026-07-23, RA Schatz):** Ergebnis + Kernerkenntnisse → `handover/phase0-handtest-stichproben.md` (Abschnitt „Ergebnis"). Wichtigste: Kürzungs-Erkennung = Differenz Forderung/Zahlung, NIE aus dem Abrechnungsschreiben (nur Typ-Begründung, nur auf Begründungsdokumenten); Trefferquote Typ auf Prüfberichten 61 % roh / ~71 % nach trivialen Stichwort-Fixes; Begründung↔Zahlung oft in getrennten Dokumenten → Verkettung nötig; Typ „Neu-für-alt" (A07) + Baustein fehlen.
- **Datenqualitäts-Funde ✅ behoben (2026-07-23):** Dok 2562 per `korrigiere_klassifikation` → `gutachten` umklassifiziert (neu geparst). Dok 41478 + 43429: FEHLABLAGE-Vermerk in `dokumente.notizen` gesetzt — Umhängen unmöglich: 852/25 existiert nur in RA-MICRO (Matic/Weil, SB PK, keine Unfallakte), 418/28 existiert nirgends (fremdes Zeichen). **Offen für RA Schatz: entscheiden, ob die 2 Fehlablage-Dokumente aus den Akten 971/25 / 980/25 gelöscht werden.**
- **Entscheidungs-Tor ✅ + A–F-Zuordnung ✅ + Zielwerte ✅ (RA Schatz 2026-07-23):** 2 neue DECISIONS-Einträge (Option (b) Ereignis-Attribut + getrennte Faltungen; Zielwerte/Matching-Architektur/A–F-Zuordnung inkl. neuer Typen A07, A11, C01b). **Phase 0 damit abgeschlossen.** `ghpfstverort.DOC` gesichtet (2026-07-23): Datei ist LEER (0 Wörter, leer gespeichert 2012) → entfällt ersatzlos; A04 speist sich allein aus `ghpfansprort.doc` (Inhalt bestätigt: Stundenverrechnungssätze; braucht .doc→.rtf-Konvertierung vor Import). (`mockups/` war bereits mit 80e2f044 versioniert.) → Nächstes: Phase 1 planen — Prompt: `handover/naechste_session_kuerzungstaxonomie_phase1_prompt.md`.

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
