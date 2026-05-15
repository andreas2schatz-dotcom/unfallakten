# TODO – Unfallakten-Verwaltungssystem
> Generiert: 2026-05-02 aus allen Session-Handovers (v18–v56), PRD-Dateien, backlog.md
> Quellen: session_handover_v38–v56.md, handover/backlog.md, handover/PRD-*.md

---

## ✅ Erledigt

| PRD / Feature | Beschreibung | Quelle |
|---|---|---|
| PRD-01 (Basis) | To-Do-System + Header-Widget | (aus: session_handover_v38.md, v20/v21) |
| PRD-02 | Textbaustein-Feld Kürzungsarten | (aus: session_handover_v55.md, 2e1e0fb) |
| PRD-03 K-01–K-15 | Klageschrift-Formatierung vollständig | (aus: session_handover_v38.md, v35–v36) |
| PRD-04 | Dokumentenklassen + Dispatcher + Registry | (aus: session_handover_v38.md, v23) |
| PRD-04b | Feedback-Loop: Korrektur + Trainingsdata | (aus: session_handover_v38.md, v24) |
| PRD-14 | Single Source of Truth: Abrechnungsart (Backend + Frontend) | (aus: session_handover_v55.md, 0caaa4a) |
| PRD-15 | WDM Auto-Load | (aus: session_handover_v38.md, v26) |
| PRD-16 | Tab-Reihenfolge als Workflow-Ablauf | (aus: session_handover_v55.md, d2748df) |
| PRD-18 | Phasen-Strip (UebersichtSection) | (aus: session_handover_v55.md, 3f34ed5) |
| PRD-20 | App.jsx Refactoring (26 Dateien) | (aus: session_handover_v38.md, v25) |
| PRD-21 Phase 1+2+3a | E-Akte Auto-Import vollständig | (aus: session_handover_v38.md, v28–v29) |
| PRD-22a | Gutachten im Schaden-Reiter | (aus: session_handover_v38.md, v30) |
| PRD-22b | Regulierung: Abrechnungen + Löschfunktion | (aus: session_handover_v38.md, v31) |
| PRD-22d | E-Mail-Import UI (3 Tabs + Smart-Inbox) | (aus: handover/backlog.md) |
| PRD-23a | Schadenposition-Belege + Schadenbelege-Card | (aus: session_handover_v38.md, v32) |
| PRD-23b | Rechnungs-Parser (Registry + Kandidaten + Frontend + 59 Tests) | (aus: handover/backlog.md) |
| PRD-24 | Aktivlegitimation + Klage-Wizard Sessions A–D | (aus: session_handover_v38.md, post-v38 deployed) |
| PRD-25a | Automatische Fristen | (aus: handover/backlog.md) |
| PRD-25b | Action-Dashboard (UebersichtSection) | (aus: handover/backlog.md) |
| PRD-26 | Klage-Wizard 10-Step (Umbau) | (aus: handover/backlog.md) |
| PRD-27 | ReguWizard – Stellungnahme-Wizard | (aus: session_handover_v55.md, 2e1e0fb) |
| PRD-28 | Gebührenassistent Nr. 2300 VV RVG + Kostennote DOCX | (aus: handover/backlog.md) |
| PRD-29b | E-Akte Auto-Parser: E-Brief-Filter via Schlagwort | (aus: handover/backlog.md, PRD-29_EAkte_Filter_DKz.md) |
| PRD-30 | OCR + SSE-Streaming für Bild-PDFs (pytesseract, pdf2image) | (aus: handover/backlog.md) |
| PRD-31 (KI) | KI-Parsing Gutachten: Shadow-Mode, Konflikt-Dialog, Korrektur-Endpoint | (aus: handover/backlog.md) |
| PRD-32 Phase 1 | Rechnungstypen-Subklassen (Standkosten/Abschlepprechnung) im Classifier | (aus: handover/backlog.md) |
| PRD-34 | Inbox-Pattern Dokumente-Kachel (KLASSE_TO_POS, Inline-Zuordnung) | (aus: handover/backlog.md) |
| Regulierungs-Workflow Option B | 5 Phasen, Legacy-regulierung deprecated, Delete-Bug v14c gefixt | (aus: handover/backlog.md) |
| KI-Parsing Regulierungsschreiben | Qwen Shadow-Mode, Modell-Switcher UI, Few-Shot, Datum-Fix | (aus: handover/backlog.md) |
| Action Board Global + OnboardingHub | ActionBoardView (3 Spalten), OnboardingHub (7 Kacheln) | (aus: session_handover_v56.md) |
| PRD-22c | Mandanten-Fragebogen: E-Mail-Parser, fragebogen_parser.py, DB-Tabelle fragebogen_erstkontakt, Verarbeitungslogik, Frontend (FragebogenErstkontaktKarte.jsx). Ausstehend: Website-Formular + PRD-22d (Akte-Anlage). | (Code-Prüfung 2026-05-03) |
| PRD-35 | Klage-Wizard Bug-Fixes (5 Bugs): vorsteuer in b_dict, wizardVerzugDatum in Step 6, EinwändePanel-Preview, StepVerzug Manual-Edit-Schutz (wizardVerzugManuell), StepSchaden Gefordert-Spalte (betragOriginal). + klage_service: RVG außergerichtl. Gegenstandswert, rvg_bereits_gezahlt Abzug. | (Session 2026-05-10) |
| B-08 | Netto/Brutto bei Vorsteuer-Mandant | (aus: session_handover_v38.md, v33) |
| B-09 | Gegenstandswert + fehlende Schadenspositionen | (aus: session_handover_v38.md, v34) |

---

## 🔄 In Arbeit

### Action Board – Fristen-Spalte unvollständig
Zeigt aktuell nur RA-MICRO Wiedervorlagen (`tblAktenWiedervorlagen`), keine „harten" Rechtsmittelfristen. Falls RA-MICRO eine separate Fristen-Tabelle führt, wäre Schritt 1 aus Task 2 des Plans zu wiederholen.
(aus: session_handover_v56.md)

### Action Board – Nachrichten-Spalte Placeholder
Spalte zeigt nur E-Mails aus `email_import_log`. Mandantenportal- und SV-Portal-Nachrichten sind als Placeholder angelegt; echte Integration hängt an PRD-25c.
(aus: session_handover_v56.md)

### Pre-existing Testfehler (kein Blocker)
`test_prd23b.py` (7 Failures) und `test_modul8.py` (16 Errors) schlagen seit vor PRD-31 fehl — nicht durch aktuelle Sessions verursacht, noch nicht behoben.
(aus: session_handover_v55.md, session_handover_v54.md)

---

## 📋 Offen

> Absteigend nach Priorität gemäß letztem Handover (v55/v56).

### Priorität: Kritisch / Bald (nächste 1–3 Sessions)

**PRD-33 – Klage-Wizard Feintuning (klage_service.py)**
Qualitäts-Pass am generierten DOCX. Bereits gefixt (Session 2026-05-10): RVG-Tabelle zeigt jetzt außergerichtl. Gegenstandswert; `rvg_bereits_gezahlt`-Abzug mit bedingten Tabellenzeilen.
Noch offen: weitere Layout-/Inhaltsfehler im generierten DOCX (Absätze, Textbausteine, Rubrum bei mehreren Beklagten, Platzhalter-Kontrolle).
Debugging-Vorbereitung: `handover/session_handover_v52.md` → Abschnitt „Nächste Session".
(aus: handover/backlog.md, session_handover_v55.md, Session 2026-05-10)

**PRD-NEW – Onboarding-Wizard (Neue-Akte-Anlage)**
Stub `NeueAkteModal` existiert seit v54 in `AktensucheView.jsx` (AZ, Unfalldatum, Unfallort, Notizen). Echte Akte-Anlage-Logik fehlt vollständig. Hängt an PRD-22d-Konzept (neuer Mandant → Akte anlegen).
(aus: session_handover_v54.md, session_handover_v55.md)

**PRD-25c – Automatische Mandantenkommunikation**
`MandantenEmailDialog.jsx` nach Generierung von Forderungsschreiben / Regulierungsschreiben / Abrechnungsübersicht öffnen. 3 Textbausteine je Trigger, SMTP via `unfall@anwalt-offenbach.de`, neue DB-Tabelle `mandanten_emails`. 4 Sessions geplant.
PRD vorhanden: `handover/PRD-25c_Mandantenkommunikation.md`
(aus: session_handover_v55.md, session_handover_v56.md)

---

### Priorität: Mittel

**PRD-32 Phase 2 – Rechnungstypen-Parser: Beleg-Mapping**
Phase 1 (Subklassen im Classifier) ist fertig. Phase 2: erkannte Rechnungstypen automatisch der richtigen Schadenposition zuordnen (Standkosten → Standgeld-Position, Abschlepprechnung → Abschleppkosten-Position).
Plan: `handover/PRD-32_Rechnungstypen_Parser.md`
(aus: handover/backlog.md, session_handover_v55.md)

**PRD-05 – Betrag-Abgleich nach Upload**
Nach Hochladen einer Rechnung automatisch Betrag gegen Schadenposition abgleichen.
(aus: session_handover_v55.md)

**PRD-03 – Klagegenerator Abschlusstest**
Code wurde in v35–v36 implementiert und deployed. Ob ein formaler Abnahmetest je erfolgte, ist unklar. v55 listet ihn noch als offene MITTEL-Aufgabe.
(aus: session_handover_v55.md)

**PRD-29 – Schmerzensgeld-Ermittlungstool**
Modal im Klage-Wizard: KI recherchiert Vergleichsurteile (dejure.org, lexetius.com), Anwalt legt Mindestbetrag fest, KI generiert Klagetext → Übernahme in Klageschrift + Forderungsschreiben. Schema-Migration 36 + 3 neue Endpoints. Noch nicht begonnen.
Plan: `handover/PRD-29_Schmerzensgeld_Tool.md`
(aus: handover/PRD-29_Schmerzensgeld_Tool.md — fälschlicherweise als erledigt markiert, 2026-05-04 korrigiert)

---

### Priorität: Später

**PRD-01 – To-Do-System Vollausbau**
Basis (Header-Widget) vorhanden. Action Board deckt ca. 70 % des ursprünglichen Konzepts ab. Vollausbau (Aufgabenzuweisung, Fälligkeiten, Filterung) noch nicht begonnen.
(aus: session_handover_v55.md)

**PRD-06 – Parser Reparaturrechnung via LLM**
LLM-basierte Extraktion von Reparaturrechnungen, die nicht per Regex geparst werden können.
(aus: session_handover_v38.md, session_handover_v55.md)

**PRD-07 – Workflow-Regeln + automatische To-Dos**
Regelmaschine: bei bestimmten Ereignissen (z.B. Regulierungsschreiben eingegangen) automatisch To-Do anlegen.
(aus: session_handover_v55.md)

**PRD-17 – Tagesstart-Dashboard** `[refining]`
ActionBoardView (v56) erfüllt die Funktion vollständig. Wird als erledigt betrachtet; läuft in der Verfeinerungsphase (Fristen-Spalte, Nachrichten-Spalte).
(aus: session_handover_v38.md, session_handover_v55.md, session_handover_v56.md)

**~~PRD-19 – RA-Micro DMS Integration (Read-Only)~~** ✅
Vollständig implementiert in `DokumenteSection.jsx`: E-Akte-Card mit Lazy Load, Filter, Sort, Pagination, PDF-Vorschau, Einzel- und Bulk-Import.
(aus: session_handover_v55.md — als offen gelistet, Code aber fertig)

**PRD-21 Phase 3b – Batch-Klassifikation**
Mehrere E-Akte-Dokumente auf einmal klassifizieren.
(aus: session_handover_v38.md)

**PRD-21 Phase 3c – Filter nach Dokumentenklasse**
E-Akte-Ansicht nach Dokumentenklasse filtern.
(aus: session_handover_v38.md)

**PRD-04c – TF-IDF Classifier**
Statistischer Classifier als Ergänzung zum Regex-Dispatcher.
(aus: session_handover_v38.md)

**PRD-24b – Vollständiger 5-Step-Wizard**
Erweiterung des Klage-Wizards um Unfallhergang und Haftungsbegründung als eigene Wizard-Steps.
(aus: session_handover_v38.md)

**PRD-25d – Intelligente Sachstandsanfrage (STA)**
Automatisierter Versand von Sachstandsanfragen an den Versicherer nach konfigurierbaren Fristen.
PRD vorhanden: `handover/PRD-25d_Intelligente_Sachstandsanfrage.md`
(aus: session_handover_v38.md, backlog)

**Stakeholder-Portal (separates Projekt)**
Vier Phasen geplant. Kein Implementierungsstand im Unfallakten-Repo.
- PORTAL-A1: Unfallakten-Sync (`handover/PORTAL-A1_Unfallakten_Sync.md`)
- PORTAL-B1: Foundation (`handover/PORTAL-B1_Foundation.md`)
- PORTAL-B2: SV-Cockpit (`handover/PORTAL-B2_SV_Cockpit.md`)
- PORTAL-B3: Privatmandant (`handover/PORTAL-B3_Privatmandant.md`)
(aus: handover/PORTAL-*.md)

---

## ❓ Unklar

**PRD-29 DKz-Filter: erledigt oder offen?**
`session_handover_v56.md` nennt „PRD-29 DKz-Filter: noch nicht gestartet". `handover/PRD-29_EAkte_Filter_DKz.md` sagt `✅ Implementiert` — das DKz-Feld existiert in der DB nicht, daher Lösung via Schlagwort `E-Brief`. Ist damit das ursprüngliche Ziel als vollständig erfüllt zu betrachten?
(aus: session_handover_v56.md vs. handover/PRD-29_EAkte_Filter_DKz.md)

**PRD-03 Abschlusstest**
`session_handover_v55.md` listet „PRD-03 Klagegenerator Abschlusstest" als offene MITTEL-Aufgabe. Code wurde in v35–v36 implementiert. Ob ein Integrationstest jemals formal durchgeführt wurde, geht aus den Handovers nicht hervor.
(aus: session_handover_v55.md, session_handover_v38.md)

