# Session-Übergabe – Kanzlei Koch, Schatz & Kollegen
# Unfallakten-Verwaltungssystem
> Stand: Session v52 – 18. April 2026

---

## Aktueller Systemstand

| Komponente | Details |
|---|---|
| DB-Schema-Version | **37** |
| Frontend | React + Vite, aufgeteilt in Section-Dateien |
| Backend | Flask/Python 3.9, SQLite PK az TEXT |
| RA-Micro | Optional (RAMICRO_AKTIV=true) |
| E-Akte | EAKTE_BASE_PATH konfiguriert → Auto-Import aktiv |
| LLM | Qwen via LM Studio lokal (Shadow-Mode für Regulierungsschreiben + Gutachten aktiv) |

---

## Erledigte Arbeiten v52

### Regulierungs-Workflow Redesign – Option B (5 Phasen)

**Kernprinzip:** Jedes Abrechnungsschreiben speichert nur seine eigene Zahlung (Inkrement).
Das System summiert automatisch bei Read-Time. Legacy `regulierung`-Tabelle soft-deprecated.

#### Phase 1 – Aggregationsbug + Semantik

| Datei | Änderung |
|---|---|
| `backend/word/abrechnungsuebersicht_service.py` | `_baue_pos_map()`: summiert alle Inkremente statt "neueste gewinnt"; `_KEY_NORMALISE` + `_normalise_key()` für Parser-Art-Werte (wbw→wiederbeschaffung, kostenpauschale→unkostenpauschale etc.) |
| `frontend/src/config/constants.js` | `positionenVorlage(schaden, { isFollowUp = false })` – bei Folge-Abrechnung startet `betrag_reguliert` bei 0; Kommentar vor `_mapPdfPos()` |
| `backend/tests/test_modul5.py` | 11 neue Tests in `TestBauePosMap`: Summierung, 6 Key-Normalisierungen, art-Fallback |

#### Phase 2 – v_regulierungsstatus View migrieren

| Datei | Änderung |
|---|---|
| `backend/db/schema_manager.py` | Migration 37: `DROP VIEW + CREATE VIEW v_regulierungsstatus` → Daten aus `abrechnungsschreiben + regulierung_positionen` statt `regulierung`-Tabelle |
| `backend/db/schema.py` | Kanonische DDL für `v_regulierungsstatus` aktualisiert |
| `backend/services/gebuehren_service.py` | `SELECT MAX(datum) FROM abrechnungsschreiben` statt `regulierung` |

#### Phase 3 – Legacy `regulierung`-Tabelle ablösen

| Datei | Änderung |
|---|---|
| `backend/routers/dashboard_routes.py` | `_lade_regulierung_offen()`: `FROM v_regulierungsstatus + abrechnungsschreiben`; Status abgeleitet; Ablehnung ausgeblendet |
| `backend/routers/akten_routes.py` | `regulierungen`-Key aus `_akte_komplett()` entfernt; Import `hole_regulierungen_by_akte` entfernt |
| `frontend/src/sections/WordSection.jsx:85` | `st.abrechnungen[].gesamt_reguliert` statt `st.regulierungen` |
| `frontend/src/state/reducer.js` | `SET_REGULIERUNGEN`, `ADD_REGULIERUNG` entfernt; dead `regulierungen`-Zeile aus `ADD_ABRECHNUNG` entfernt |
| `backend/routers/schaden_routes.py` | Legacy-Endpunkte `/regulierungen` mit DEPRECATED-Kommentar; Tabelle nicht gelöscht (historische Daten) |

#### Phase 4 – Klage-Pipeline mit Provenance

| Datei | Änderung |
|---|---|
| `backend/routers/klage_routes.py` | `reg_agg`-Dict in `hole_klage_daten()` Response: `position_key → { gesamt_reguliert, quellen[] }` |
| `frontend/src/sections/KlageWizard.jsx / StepSchaden` | `provenanceMap` statt `regMap`; Einzelzahlungen bei >1 AB sichtbar (Datum · Versicherung · Betrag) |

#### Phase 5 – Frontend-Klarheit

| Datei | Änderung |
|---|---|
| `frontend/src/sections/RegulierungSection.jsx` | Toast: "Neue Abrechnung angelegt" + Hinweis "Betrag = Zahlung dieses Schreibens" bei Folge-AB |
| `frontend/src/sections/RegulierungSection.jsx` | Expand-Button ab 1 Zahlung (statt >1); `2×`-Badge unter ▶ bei Mehrfachzahlungen |

#### Bug-Fixes (aus Code-Review nach Phase 4)

| Datei | Bug | Fix |
|---|---|---|
| `frontend/src/components/AkteDetailView.jsx` | Legacy `GET /regulierungen` + `SET_REGULIERUNGEN` Dispatch (no-op) | Block entfernt |
| `frontend/src/components/AkteDetailView.jsx` | `st.regulierungen` in `regulierungOk` + useMemo-Deps | Bereinigt |
| `frontend/src/components/AkteDetailView.jsx` | Dead Prop `regulierungen={st.regulierungen\|\|[]}` an `RegulierungSection` | Entfernt |
| `frontend/src/sections/RegulierungSection.jsx` | Dead Prop in Funktionssignatur | Entfernt |
| `backend/routers/abrechnungsschreiben_routes.py` | **v14c-Bug DELETE**: `WHERE akte_id=?` mit rohem URL-Param → Löschen schlug bei PDF-importierten ABs fehl | `az = akte_obj.aktenzeichen` |
| `backend/routers/abrechnungsschreiben_routes.py` | **v14c-Bug GET-Single**: `ab.akte_id != akte_id` mit rohem URL-Param | Normalisiert |

---

## Nächste Session: PRD-33 – Feintuning Klage-Wizard

### Kontext

Der 10-Step-Wizard ist funktional vollständig (PRD-26, Session v45). PRD-33 ist ein
**Qualitäts-/Debugging-Pass** am generierten Word-Dokument: Formatierung, Zeilenumbrüche,
Absätze, Textqualität einzelner Abschnitte.

### Ziel der nächsten Session

1. **Ist-Analyse:** Klage für eine Testakte generieren, das DOCX öffnen, alle Abschnitte
   systematisch durchgehen und Mängel dokumentieren
2. **Bugfixing** an `backend/word/klage_service.py` (Hauptdatei für Word-Generierung)
3. Optional: Textbausteine in `KlageWizard.jsx` (Step 3/6/7/8/9) überarbeiten

### Relevante Dateien

| Datei | Rolle |
|---|---|
| `backend/word/klage_service.py` | Word-Generierung: python-docx, alle Abschnitte, Formatierung |
| `frontend/src/sections/KlageWizard.jsx` | Wizard-UI (10 Steps), Textbausteine in `buildSachverhaltText()`, `baueAntraegeText()`, `baueGebuehrenAntrag()` |
| `frontend/src/sections/KlageSection.jsx` | Wizard-Orchestrierung, `wizardGenerieren()` baut `cfg`-Objekt |
| `handover/klage_wizard_map.md` | Vollständige Step-Map, State-Übersicht, bekannte Mängel |

### Bekannte Qualitätsmängel (aus klage_wizard_map.md)

| Step | Problem |
|---|---|
| Step 4 | Kein Diff-View, kein Zurücksetzen-Button |
| Step 5 | Kein Regulierungsstand neben Position |
| Step 8 | Zeigt gerichtl. RVG – könnte Nutzer verwirren |
| Step 10 | Zeigt nur gerichtl. RVG, nicht außergerichtl. |
| Backend | Formatierung (Absätze, Leerzeilen, Zeilenumbrüche) lt. Nutzer-Feedback |

### Debugging-Vorbereitung

Für die nächste Session: Klage für eine reale Testakte generieren, DOCX öffnen und prüfen:

1. **Absätze und Leerzeilen** zwischen Abschnitten (Sachverhalt / Rechtliche Würdigung / Anträge)
2. **Schriftbild** – Überschriften, Fließtext, Einrückungen in python-docx
3. **Platzhalter** – sind alle `{{...}}` korrekt ersetzt?
4. **Antragstexte** – RVG-Betrag korrekt eingesetzt? Außergerichtl. vs. gerichtl. Trennung?
5. **Rubrum** – Beklagte korrekt formatiert (mehrere Beklagte)?

---

## Offene PRDs (Gesamt-Übersicht)

| PRD | Titel | Status |
|---|---|---|
| PRD-33 | Feintuning Klage-Wizard | Debugging-Pass nächste Session |
| PRD-32 Phase 2 | Rechnungstypen-Beleg-Mapping | Phase 1 ✅, Phase 2 offen |
| PRD-27 | ReguWizard – Stellungnahme | Planung offen |
| PRD-25c | Mandantenkommunikation | Planung offen |

---

## Wichtige Architektur-Hinweise für nächste Session

### Option B – Regulierungslogik

- `regulierung`-Tabelle ist **deprecated** (Endpunkte erhalten, aber kein neuer Code schreibt dort)
- **Neue Datenquelle:** `abrechnungsschreiben` + `regulierung_positionen` + `v_regulierungsstatus`
- **Summierung:** Immer über alle `regulierung_positionen` je `akte_id` aggregieren
- **Key-Normalisierung:** `_normalise_key()` in `abrechnungsuebersicht_service.py` für Parser-Art-Werte

### v14c-Muster (kritisch!)

In jedem Router mit `_pruefe_akte()` oder `hole_akte_by_id()` IMMER:
```python
akte_obj = _pruefe_akte(akte_id)
if not akte_obj:
    return _err(...)
az = akte_obj.aktenzeichen if hasattr(akte_obj, "aktenzeichen") else akte_id
# Alle DB-Queries mit az, nie mit akte_id
```
