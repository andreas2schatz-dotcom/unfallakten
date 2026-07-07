# Session-Übergabe – Kanzlei Koch, Schatz & Kollegen
# Unfallakten-Verwaltungssystem
> Stand: Session v49 – 14. April 2026

---

## Aktueller Systemstand

| Komponente | Details |
|---|---|
| DB-Schema-Version | **36** |
| Frontend | React + Vite, aufgeteilt in Section-Dateien |
| Backend | Flask/Python 3.9, SQLite PK az TEXT |
| RA-Micro | Optional (RAMICRO_AKTIV=true) |
| E-Akte | EAKTE_BASE_PATH konfiguriert → Auto-Import aktiv |
| LLM | Qwen via LM Studio lokal (Shadow-Mode für Regulierungsschreiben aktiv) |

---

## Erledigte Arbeiten v49

### 1. PRD-32 Phase 1 – Rechnungstypen-Parser

| Was | Datei | Details |
|---|---|---|
| Subtyp-Erkennung | `document_classifier.py` | Nach `rg_score >= 2`: Signallisten für `abschlepprechnung` (LFBK, Bergung, Pannendienst …) und `standkostenrechnung` (Standgeld, Tage à, €/Tag …) |
| Beleg-Mapping | `belege_routes.py` | `_KLASSE_POSITION_MAP`: `standkostenrechnung → standkosten` ergänzt; beide SQL-Queries um `standkostenrechnung` erweitert |
| Registry | `registry.json` | `asd-offenbach.de` → `abschlepprechnung` (Abschleppdienst Offenbach GmbH, AdNr 1135) |

**Verhalten:** Kombinierte Abschlepp+Standkosten-Rechnung bleibt `abschlepprechnung` → `abschleppkosten` (Gesamtbetrag). Reine Standkostenrechnung → `standkostenrechnung` → `standkosten`.

### 2. QuickAkteSearch – Schnellaufruf in Seitenleiste

| Was | Datei | Details |
|---|---|---|
| Neue Komponente | `App.jsx` | `QuickAkteSearch` ganz oben in der linken Seitenleiste (vor Dashboard, wie in RA-MICRO) |
| API | `api.js` | Nutzt `emailImport.aktensuche(q)` (min 2 Zeichen, Debounce 180ms) |
| Verhalten | — | Enter → erster Treffer öffnet als Tab; ESC leert Feld; Feld leert sich nach Auswahl |

### 3. PRD-33 – in Backlog aufgenommen

Feintuning Klage-Wizard (Formatierungen, Absätze, Leerzeilen, Texte). Anforderungen werden direkt in der Umsetzungssession erfasst.

### 4. Bugfix WiedervorlageView

`fill=T.green` → `fill={T.green}` (JSX-Syntaxfehler, blockierte den Build).

---

## Nächste Session: PRD-31 – KI-Parsing für Gutachten

### Ziel

Analoger LLM Shadow-Mode für Gutachten wie bereits für Regulierungsschreiben implementiert.
Regex-Parser läuft zuerst, LLM läuft parallel im Hintergrund, Ergebnisse werden verglichen.
Bei Konflikt wählt der Benutzer per Klick welchen Wert er importieren möchte.

### Referenz-Implementierung

Die vollständige Vorlage liegt in:
- `backend/parsers/abrechnungsschreiben_parser.py` – LLM Shadow-Mode Logik
- `backend/routers/pdf_parse_routes.py` – `/parse-stream` Endpoint mit SSE
- `frontend/src/sections/RegulierungSection.jsx` – Konflikt-UI (Regex/KI-Buttons)

### Bestehender Gutachten-Parser

**Datei:** `backend/parsers/gutachten_parser.py`

**Extrahierte Felder (Regex):**

| Feld | Typ | Beschreibung |
|---|---|---|
| `reparaturkosten_netto` | float | Netto-Reparaturkosten |
| `reparaturkosten_brutto` | float | Brutto-Reparaturkosten |
| `wiederbeschaffungswert` | float | WBW netto |
| `restwert` | float | Restwert |
| `wertminderung` | float | Merkantile Wertminderung |
| `nutzungsausfall_tagessatz` | float | Tagessatz Nutzungsausfall |
| `nutzungsausfall_tage` | int | Ausfalltage |
| `nutzungsausfall_gesamt` | float | Gesamt Nutzungsausfall |
| `sv_kosten_netto` | float | SV-Honorar netto |
| `sv_kosten_brutto` | float | SV-Honorar brutto |
| `schadenart` | str | `reparaturschaden` / `totalschaden` / `grenzfall` |

### Implementierungsplan PRD-31

#### Schritt 1: LLM-Prompt für Gutachten
- System-Prompt + Few-Shot-Beispiel für Gutachten-Format
- Felder: wbw, restwert, reparaturkosten_netto, wertminderung, nutzungsausfall_tagessatz, nutzungsausfall_tage, sv_kosten_netto
- Analoges JSON-Schema wie beim Abrechnungsschreiben-Prompt

#### Schritt 2: `gutachten_parser.py` – LLM Shadow-Mode ergänzen
- `llm_shadow_parse_gutachten(text, regex_result)` analog zu `_llm_shadow_parse()`
- `GutachtenParseResult` um Felder erweitern:
  - `llm_wbw`, `llm_restwert`, `llm_reparaturkosten_netto` etc.
  - `llm_verwendet: bool`, `llm_konflikt: bool`
- Konflikt-Erkennung: Betragsabweichung > 1 € pro Position

#### Schritt 3: `/parse-stream` Endpoint
- `pdf_parse_routes.py`: Gutachten-Zweig analog zu Abrechnungsschreiben erweitern
- LLM-Ergebnis in SSE-Response mitliefern

#### Schritt 4: Frontend – Konflikt-UI
- `DokumenteSection.jsx` oder neuer Gutachten-Preview-Block
- Pro Position: Regex-Wert / KI-Wert wählbar (wie in RegulierungSection)

### Kritische Dateien

| Datei | Rolle |
|---|---|
| `backend/parsers/gutachten_parser.py` | Hauptparser – LLM-Logik ergänzen |
| `backend/routers/pdf_parse_routes.py` | SSE-Endpoint – Gutachten-Zweig |
| `frontend/src/sections/DokumenteSection.jsx` | Gutachten-Preview-UI |
| `backend/parsers/abrechnungsschreiben_parser.py` | Referenz für LLM Shadow-Mode |

---

## Offene PRDs (Gesamt-Übersicht)

| PRD | Titel | Status |
|---|---|---|
| PRD-31 | KI-Parsing für Gutachten | Planung offen → **nächste Session** |
| PRD-33 | Feintuning Klage-Wizard | Planung offen |
| PRD-27 | ReguWizard – Stellungnahme | Planung offen |
