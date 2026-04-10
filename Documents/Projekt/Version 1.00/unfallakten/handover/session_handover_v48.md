# Session-Übergabe – Kanzlei Koch, Schatz & Kollegen
# Unfallakten-Verwaltungssystem
> Stand: Session v48 – 10. April 2026

---

## Aktueller Systemstand

| Komponente | Details |
|---|---|
| DB-Schema-Version | **36** |
| Frontend | React + Vite, aufgeteilt in Section-Dateien |
| Backend | Flask/Python 3.9, SQLite PK az TEXT |
| RA-Micro | Optional (RAMICRO_AKTIV=true) |
| E-Akte | EAKTE_BASE_PATH konfiguriert → Auto-Import aktiv |
| anthropic SDK | **0.49.0** (web_search_20250305 unterstützt) |

---

## Erledigte Arbeiten v48

### 1. Klage-Wizard Bug-Fixes (Fix A + B)

| Was | Datei | Details |
|---|---|---|
| **Fix A**: Gericht erschien in Kachel 2 (Parteien) | `klage_routes.py` | `alle_bet = [b for b in alle_bet if b.get("rolle","").lower() != "gericht"]` nach gericht_vorschlag-Extraktion |
| **Fix B**: Weibliche Klägerin als "Kläger" | `word_service.py` `_beteiligter_dict()` | RA-MICRO speichert `sAnrede` numerisch ("1"=Herr, "2"=Frau) → `_ANREDE_NORM = {"1":"Herr","2":"Frau"}` Mapping hinzugefügt |

---

### 2. PRD-29: Schmerzensgeld-Ermittlungstool – vollständig implementiert

**Phase 1 – DB-Migration 36** (`backend/db/schema_manager.py`)
- 5 neue Spalten in `personenschaden`: `sg_mindest REAL`, `sg_text TEXT`, `sg_urteil_gericht TEXT`, `sg_urteil_az TEXT`, `sg_urteil_betrag REAL`

**Phase 2 – Backend-Endpunkte** (`backend/routers/klage_routes.py`)
- `GET /akten/<az>/klage/sg-analyse` – Verletzungsprofil aus personenschaden (inkl. Tage-Berechnung)
- `POST /akten/<az>/klage/sg-recherche` – Claude Sonnet + web_search → bis zu 5 Vergleichsurteile
- `POST /akten/<az>/klage/sg-text` – Claude Sonnet generiert juristischen Klageschrift-Abschnitt
- `personenschaden_routes.py` allowed_fields erweitert um sg_*-Felder

**Phase 3 – Gemeinsamer Textbaustein** (`backend/word/sg_text_builder.py` NEU)
- `baue_sg_abschnitt(ps_data, kl_nom, sg_mind)` → `(absaetze, beweis, vgl)`
- `_fmt_datum()` – konvertiert ISO ↔ DD.MM.YYYY
- `_parse_datum()` – parst beide Formate zu datetime.date
- Wird von `klage_service.py` UND `forderungsschreiben_wv.py` verwendet

**Phase 4 – Frontend** (`frontend/src/components/SchmerzensgelDialog.jsx` NEU)
- Modal mit 3 Bereichen: Verletzungsprofil (readonly), Vergleichsurteile, Mindestbetrag + Text
- **Textvorschlag erstellen** (sofort, kein KI) – repliziert `baue_sg_abschnitt` in JS
- **KI-Text (optional)** – Claude Sonnet, ~6 Cent/Aufruf
- Übernehmen: speichert sg_* in personenschaden + setzt mitSG=true + sgMind im Wizard/Section

**Phase 5 – Integration** (`KlageSection.jsx`, `KlageWizard.jsx`)
- Button "Schmerzensgeld-Assistent" in Kachel 4 (KlageSection) + StepSchaden (Wizard Step 5)
- Beide öffnen SchmerzensgelDialog, nach Übernehmen werden mitSG + sgMind gesetzt

**Phase 6 – API** (`frontend/src/api.js`)
- `apiKlage.sgAnalyse`, `.sgRecherche`, `.sgText` hinzugefügt
- `export const apiPersonenschaden` hinzugefügt (laden + speichern)

---

### 3. QA-Review PRD-29 – Bugs gefunden und behoben

| # | Bug | Fix |
|---|---|---|
| QA-1 | `fromisoformat()` schlägt bei DD.MM.YYYY fehl → Tage immer 0 | `_parse_datum()` in sg_text_builder, importiert in klage_routes |
| QA-2 | ISO-Datum (`2024-03-15`) im deutschen Rechtstext | `_fmt_datum()` auf alle Datumsfelder in sg_text_builder |
| QA-3 | `antwort_text = block.text` überschreibt statt akkumuliert | `getattr(block,"text",None)` + append + join |
| QA-4 | `kl_nom \|\| "Der Mandant"` – falsch | → `"Der Kläger"` |
| QA-5 | forderungsschreiben_wv.py: `gram.get("kl_nom","Der Mandant")` | → `gram.get("kl_nom") or "Der Kläger"` |
| QA-6 | Profil-Anzeige zeigt rohe ISO-Daten | `fmtD()` helper in SchmerzensgelDialog |
| QA-7 | schmerzensgeld.online-Link erst nach Recherche-Klick | Link immer angezeigt nach Analyse-Load |

---

### 4. sg-recherche Optimierungen (Token / Rate Limit)

| Problem | Fix |
|---|---|
| 30k-TPM-Rate-Limit bei web_search | `max_uses: 2` → reduziert interne Suchanfragen |
| Haiku ignoriert JSON-Format-Vorgabe | Zurück zu Sonnet (Haiku für diese Aufgabe unzuverlässig) |
| `'NoneType' has no attribute 'strip'` | `getattr(block,"text",None)` Null-Safe |
| max_tokens=1500 zu niedrig → JSON abgeschnitten | → 2500 |
| Prompt zu strikt (exakte Übereinstimmung) → kein Ergebnis | "ähnliche Verletzungsbilder ausdrücklich erwünscht" |
| Tool wurde nicht aufgerufen | `tool_choice={"type":"any"}` + System-Prompt für JSON-only |
| ~6 Cent/Aufruf mit optimierten Einstellungen | Akzeptabel, dokumentiert |

---

### 5. Impeccable Skill-Paket installiert

- 17 Design-Skills via `npx skills add pbakaus/impeccable`
- Installiert in: `.agents/skills/<name>/SKILL.md`
- **Windows-Fix**: SKILL.md Dateien manuell nach `~/.claude/commands/<name>.md` kopiert (Installer-Symlinks funktionieren auf Windows nicht)
- Verfügbare Befehle: `/audit`, `/polish`, `/critique`, `/typeset`, `/bolder`, `/quieter`, `/colorize`, `/layout`, `/animate`, `/overdrive`, `/distill`, `/shape`, `/delight`, `/optimize`, `/adapt`, `/clarify`, `/impeccable`

---

## Offene Bugs / Bekannte Probleme

| # | Problem | Priorität |
|---|---|---|
| B-01 | Klagegenerator – 13 Blöcke noch nicht vollständig getestet | 🔴 |
| – | PRD-22c Session 4–5 (Fragebogen-Backend-Tests) ausstehend | 🟡 |
| – | PRD-25c Mandantenkommunikation nicht implementiert | 🟡 |
| – | PRD-25d STA End-to-End-Test ausstehend | 🟡 |
| – | Bußgeld-Deployment ausstehend | 🟡 |

---

## To-Do – Nächste Session

### 🔴 Priorität 1: Klagegenerator – Abschlusstest (je Block)

| Block | Was prüfen | Status |
|---|---|---|
| **Rubrum** | Kläger (Name, Anrede, Anschrift), alle Beklagten, Vertreter, Gericht | ⬜ |
| **Einleitung** | AZ, Unfalldatum, Unfallort, Kennzeichen Gegner, Schadennummer | ⬜ |
| **Tatbestand** | Unfallschilderung, Zeugen + Adressen, Fahrer, KFZ-Daten | ⬜ |
| **Ermittlungsakte** | AZ Ermittlungsakte, Behörde, Ort | ⬜ |
| **Schadentabelle** | Positionen, Beträge, Unkostenpauschale-Default 30€ | ⬜ |
| **Haftungsquote** | Block bei HQ < 100%, korrekte Berechnung | ⬜ |
| **Haftungsbegründung** | varANSP1 oder SQLite `haftungsbegruendung` | ⬜ |
| **Schmerzensgeld** | Block erscheint wenn angehakt, Mindestbetrag optional, sg_text aus Dialog | ⬜ |
| **Zinsen** | Verzugsdatum, Zinsbeginn-Wahl, korrekter Zinssatz 5PP | ⬜ |
| **Klageanträge** | Hauptantrag korrekt je Abrechnungsart, Versäumnisurteil-Antrag | ⬜ |
| **Rechtliche Würdigung** | Platzhalter-Text, Kürzungsargumente auto | ⬜ |
| **RVG** | Streitwert, §13-Tabelle, Mehrwertsteuer, Override | ⬜ |
| **Verweisbetrieb** | Textbaustein erscheint wenn verweisFlag gesetzt | ⬜ |

### 🟡 Priorität 2: PRD-27 ReguWizard
Geführter Wizard: Stellungnahme auf Abrechnungsschreiben. PRD: `handover/PRD-27_ReguWizard.md`.

### 🟡 Priorität 3: PRD-25c Mandantenkommunikation
### 🟡 Priorität 4: Bußgeld-Deployment

---

## Kritische Architektur-Notizen

- `unfallakte` PK = `az TEXT` → `WHERE az=?` überall
- `beteiligte.anrede` (nicht `geschlecht`) → `_mandant_anrede_nominativ()` aus `forderungsschreiben_wv.py`
- `beteiligte.sAnrede` aus RA-MICRO ist **numerisch** ("1"=Herr, "2"=Frau) → Mapping `_ANREDE_NORM` in `word_service.py`
- `personenschaden.krankenhaus_von/bis` (nicht `krankenhaus_aufenthalt`)
- `personenschaden` Datumsfelder: **gemischtes Format** (ISO oder DD.MM.YYYY je nach Erfassungsweg) → immer `_fmt_datum()` / `_parse_datum()` aus `sg_text_builder.py` verwenden
- `dokumente.typ` (nicht `klasse`)
- `sg_text` in personenschaden hat Vorrang vor generiertem Template in `baue_sg_abschnitt()`
- sg-recherche: Sonnet + `tool_choice=any` + `max_uses=2` + `max_tokens=2500` – Haiku ignoriert JSON-Format
- Impeccable Skills: Symlinks auf Windows defekt → manuell nach `~/.claude/commands/` kopieren
- RA-MICRO: NIEMALS schreiben. Nur SELECT.

---

## Geänderte Dateien v48

| Datei | Änderung |
|---|---|
| `backend/db/schema_manager.py` | Migration 36: 5 neue sg_*-Spalten in personenschaden |
| `backend/routers/klage_routes.py` | Fix A (gericht aus alle_bet), 3 neue sg-Endpunkte, sg-recherche Optimierungen |
| `backend/routers/personenschaden_routes.py` | allowed_fields um sg_*-Felder erweitert |
| `backend/word/sg_text_builder.py` | **NEU**: baue_sg_abschnitt, _fmt_datum, _parse_datum |
| `backend/word/klage_service.py` | sg_text_builder importiert, personenschaden-Daten in generiere_klageschrift |
| `backend/word/forderungsschreiben_wv.py` | sg_text_builder importiert, _baue_verletzungsblock ersetzt, kl_nom-Fallback fix |
| `backend/word/word_service.py` | Fix B: sAnrede Mapping "1"→Herr/"2"→Frau in _beteiligter_dict |
| `frontend/src/api.js` | apiKlage.sgAnalyse/sgRecherche/sgText + export apiPersonenschaden |
| `frontend/src/components/SchmerzensgelDialog.jsx` | **NEU**: vollständiges Modal mit Textvorschlag + KI-Text |
| `frontend/src/sections/KlageSection.jsx` | SchmerzensgelDialog importiert + Button in Kachel 4 |
| `frontend/src/sections/KlageWizard.jsx` | SchmerzensgelDialog importiert + Button in StepSchaden |
| `~/.claude/commands/*.md` | 17 Impeccable-Skills als Claude Code Slash-Commands |

---

## Docker-Befehle

```bash
docker restart unfallakten-backend-dev
docker logs unfallakten-backend-dev --tail 50
docker exec unfallakten-backend-dev sqlite3 /app/data/unfallakten.db "SELECT schema_version FROM schema_version;"
# Schema 36 prüfen:
docker exec unfallakten-backend-dev sqlite3 /app/data/unfallakten.db ".schema personenschaden" | grep sg_
```
