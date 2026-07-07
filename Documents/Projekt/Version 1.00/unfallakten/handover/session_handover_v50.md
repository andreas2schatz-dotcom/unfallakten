# Session-Übergabe – Kanzlei Koch, Schatz & Kollegen
# Unfallakten-Verwaltungssystem
> Stand: Session v50 – 14. April 2026

---

## Aktueller Systemstand

| Komponente | Details |
|---|---|
| DB-Schema-Version | **36** |
| Frontend | React + Vite, aufgeteilt in Section-Dateien |
| Backend | Flask/Python 3.9, SQLite PK az TEXT |
| RA-Micro | Optional (RAMICRO_AKTIV=true) |
| E-Akte | EAKTE_BASE_PATH konfiguriert → Auto-Import aktiv |
| LLM | Qwen via LM Studio lokal (Shadow-Mode für Regulierungsschreiben + Gutachten aktiv) |

---

## Erledigte Arbeiten v50

### PRD-31 – KI-Parsing für Gutachten (Shadow-Mode)

Analoges LLM Shadow-Mode wie beim Regulierungsschreiben, jetzt auch für Gutachten.

#### Backend (4 Dateien)

| Datei | Änderung |
|---|---|
| `backend/services/llm_service.py` | `_SYSTEM_PROMPT_GUTACHTEN` + `parse_gutachten_raw(text)` ergänzt |
| `backend/parsers/gutachten_parser.py` | 9 LLM-Felder in `GutachtenParseResult`, `_llm_shadow_gutachten()`, `parse_gutachten(llm_aktiv=False)` |
| `backend/routers/pdf_parse_routes.py` | Gutachten-Zweig: LLM-Aktivierungscheck + 10 LLM-Felder im Ergebnis-Dict |
| `backend/workflow/dispatcher.py` | Gutachten-Zweig: LLM-Aktivierungscheck, `nutzungsausfall_tagessatz/tage` top-level + 10 LLM-Felder |

**LLM-Felder in `GutachtenParseResult`:**
- `llm_verwendet`, `llm_konflikt`
- `llm_wbw`, `llm_restwert`, `llm_reparaturkosten_netto`
- `llm_wertminderung`, `llm_nutzungsausfall_tagessatz`, `llm_nutzungsausfall_tage`
- `llm_sv_kosten_netto`, `llm_schadenart`

**Konflikt-Erkennung:** Betragsabweichung > 1 € je Position; Sentinel 1_000_000 (WBW "ausreichend") wird nie als Konflikt gewertet.

**System-Prompt:** 2 Few-Shot-Beispiele (Reparaturschaden + Totalschaden), `/no_think`-Präfix für Qwen, max_tokens=512.

#### Frontend (2 Dateien)

| Datei | Änderung |
|---|---|
| `frontend/src/api.js` | `dokumente.parse(aId, id)` + `dokumente.korrektur(aId, id, body)` ergänzt |
| `frontend/src/sections/DokumenteSection.jsx` | "🔬 KI"-Button + `GutachtenKiDialog`-Komponente |

**"🔬 KI"-Button:** Erscheint in der Dokumentenliste bei jedem PDF mit `dokumentenklasse === "gutachten"`.

**`GutachtenKiDialog`:**
- Lädt `GET /akten/<id>/dokumente/<did>/parse` (Lazy Load)
- Metadaten-Zeile: SV-Büro, Schadenart, Konfidenz
- `✦ Qwen ✓`-Badge (Übereinstimmung) oder `⚠ KI-Konflikt`-Badge (Abweichung)
- Vergleichstabelle: 7 numerische Felder (Regex-Wert vs. KI-Wert)
- Conflicting rows: `[Regex]`/`[KI]`-Toggle-Buttons für jede abweichende Position
- Footer: „KI-Werte übernehmen" (wenn KI-Felder gewählt) oder „Regex-Werte bestätigen"
- Speichern via `POST /korrektur` mit gemergetem parse_json (löst `llm_konflikt=false`)
- Nach Speichern: `ladeBelegeKandidaten()` aktualisiert Schadenbelege

**Sentinel-Schutz:** WBW-Wert ≥ 999.000 (Sentinel = "ausreichend") wird im Dialog nie als Konflikt angezeigt.

---

## Nächste Session: PRD-33 – Feintuning Klage-Wizard

Details werden direkt in der Umsetzungssession erfasst (kein separates PRD-Dokument nötig).

---

## Offene PRDs (Gesamt-Übersicht)

| PRD | Titel | Status |
|---|---|---|
| PRD-33 | Feintuning Klage-Wizard | Planung offen |
| PRD-27 | ReguWizard – Stellungnahme | Planung offen |
