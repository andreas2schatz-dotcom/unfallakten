# Projekt-Architektur – Unfallakten-Verwaltungssystem
# Kanzlei Koch, Schatz & Kollegen
> Stand: 2026-04-29 | Schema-Version 37 | Session v55

---

## Stack & Deployment

```
Browser (localhost:5173)
  └─ React + Vite (node:20-alpine)
       └─ fetch() → JWT Bearer → Flask (localhost:5000)
            └─ SQLite /app/data/unfallakten.db   ← SCHREIBEN
            └─ SQL Server //192.168.10.100 (RA-MICRO, read-only via WSL-Mount)
            └─ LM Studio (Qwen lokal) – Shadow-Mode Parsing
```

**Zwei Container:** `unfallakten-frontend-dev` (Vite) · `unfallakten-backend-dev` (Flask --debug)
**Config-Dateien:** `frontend/src/config/constants.js` · `theme.js` · `icons.jsx` · `utils.js`

---

## Frontend – Views & Sections

### AkteDetailView.jsx – Tab-Container
Lädt beim Öffnen automatisch: Schaden, Beteiligte, Dokumente, Status, WDM (PRD-15 ✅).

**Tab-Reihenfolge** (PRD-16 ✅ seit v55):
| Pos | Tab-ID | Datei | Inhalt |
|---|---|---|---|
| 1 | `uebersicht` | `UebersichtSection.jsx` | Action Board + Phasen-Strip (PRD-18 ✅) |
| 2 | `beteiligte` | `BeteiligteSection.jsx` | Mandant, Gegner, Zeugen – CRUD |
| 3 | `unfalldetails` | `UnfalldetailsSection.jsx` | Unfalldetails (WDM + manuelle Eingabe) |
| 4 | `schaden` | `SchadenSection.jsx` | Schadenpositionen, Belege-Kandidaten |
| 5 | `dokumente` | `DokumenteSection.jsx` | Upload, Klassifizierung, E-Akte-Viewer |
| 6 | `regulierung` | `RegulierungSection.jsx` | Abrechnungsschreiben + Kürzungsanalyse (Option B) |
| 7 | `klage` | `KlageSection.jsx` | Klage-Wizard 10 Steps (PRD-26) |
| 8 | `word` | `WordSection.jsx` | Forderungsschreiben, WVB, sonstige Word-Dokumente |
| 9 | `gebuehren` | `GebuehrenSection.jsx` | Gebührenassistent Nr. 2300 VV RVG (PRD-28) |

To-Dos-Tab entfernt (v55) – Todos nur noch im Action Board (Übersicht).

**Header** (navy, immer sichtbar):
- AZ + Kurzbezeichnung/Langbezeichnung (aus RA-Micro)
- KPI-Box rechts: Gefordert / Reguliert / Offen
- Action-Buttons: 💬 Nachricht → Mandant · 📤 STA senden · + Todo · 📝 Word · ⚖ Klage
- Portal-Toggle Checkbox

### Standalone Views

| Datei | Zweck |
|---|---|
| `AktensucheView.jsx` | Suche (AZ/KFZ/Schadentag) + Autocomplete + **Neue-Akte-Stub** (v54) |
| `DashboardView.jsx` | Kennzahlen-Dashboard (Fristen, offene Akten, Eingänge) |
| `WiedervorlageView.jsx` | Sachstandsanfragen-Workflow (PRD-25b) |
| `email_import/UnfallEmailView.jsx` | E-Mail-Import unfall@/termin@/bussgeld@ (PRD-22d) |
| `KuerzungskatalogView.jsx` | 19 Kürzungsarten-Verwaltung |
| `StatistikenView.jsx` | Statistiken |
| `EinstellungenView.jsx` | App-Einstellungen |

### Wichtige Shared Components

| Datei | Zweck |
|---|---|
| `common.jsx` | Card, Btn, Toast, SlidePanel, Input, BackendBadge, Skeleton |
| `StaDialog.jsx` | Sachstandsanfragen-Dialog (PRD-25d) |
| `layout.jsx` | App-Shell mit Navigation |
| `AkteDetailView.jsx` | Tab-Container (438 Z.), WDM-Autoload, PRD-14-Brutto |

---

## Backend – Blueprint-Übersicht

Alle Blueprints in `backend/app.py → erstelle_app()` registriert.

### Akten-Domain (`/akten/<az>/...`)

| Blueprint-Datei | Prefix-Suffix | Zweck |
|---|---|---|
| `akten_routes.py` | `/akten` | CRUD Akte, Status, Aktivitäten, PWA-Nachricht |
| `beteiligte_routes.py` | `/beteiligte` | Parteien CRUD |
| `schaden_routes.py` | `/schaden` | Schadenpositionen + Regulierungen |
| `abrechnungsschreiben_routes.py` | `/abrechnungen` | Abrechnungsschreiben + Option-B-Workflow |
| `pruefberichte_routes.py` | `/pruefberichte` | Prüfberichte |
| `dokumente_routes.py` | `/dokumente` | Upload, Klassifizierung, Download, SHA-256-Dedup |
| `klage_routes.py` | `/klage` | Klage-Daten, RVG-Berechnung, Gericht-Suche, SG-Tool |
| `word_routes.py` | `/dokumente/word` | Word-Generierung |
| `belege_routes.py` | `/belege` | Belege + Kandidaten |
| `forderung_routes.py` | `/forderungen` | Forderungspositionen |
| `personenschaden_routes.py` | `/personenschaden` | Personenschaden |
| `todos_routes.py` | `/todos` | Aufgaben (PRD-25a) |
| `stellungnahme_routes.py` | `/stellungnahmen` | Stellungnahmen |
| `sta_routes.py` | `/sta` | Sachstandsanfragen (PRD-25d) |
| `eakte_routes.py` | `/eakte` | E-Akte-Integration (Auto-Import) |
| `gebuehren_routes.py` | `/gebuehren` | Gebührenassistent Nr. 2300 VV RVG (PRD-28) |
| `pdf_parse_routes.py` | `/parse` | PDF-Parser (GA, Abrechnung, OCR/SSE) |
| `ramicro_akte_routes.py` | `/ramicro/akte` | RA-MICRO Sync + mandant-checks |
| `fragebogen_routes.py` | `/fragebogen` | Mandanten-Fragebogen (PRD-22c) |

### Globale Routen

| Blueprint-Datei | Prefix | Zweck |
|---|---|---|
| `auth_routes.py` | `/auth` | Login, JWT, User-CRUD |
| `email_routes.py` | `/email` | E-Mail-Import (EML-Parsing, PRD-22d) |
| `wiedervorlage_routes.py` | `/wiedervorlage` | Sachstandsanfragen-Workflow (PRD-25b) |
| `kuerzungsarten_routes.py` | `/kuerzungsarten` | Kürzungskatalog (read-mostly) |
| `dashboard_routes.py` | `/dashboard` | Kennzahlen |
| `firmen_routes.py` | `/firmen` | Firmensuche (Vertreter-Lookup) |
| `einstellungen_routes.py` | `/einstellungen` | Konfiguration |
| `distanz_routes.py` | `/distanz` | Entfernungsberechnung |
| `aktensuche_routes.py` | `/aktensuche` | Volltext-Aktensuche |

### Word-Generierung (`backend/word/`)

| Datei | Zweck |
|---|---|
| `klage_service.py` | Klageschrift (DOCX) – 10-Step-Wizard, `berechne_rvg()` |
| `forderungsschreiben_wv.py` | Forderungsschreiben / WVB – `_render_docx()`, `_unterschrift_bytes()`, `_mandant_anrede_nominativ()` |
| `sachstandsanfrage.py` | Sachstandsanfragen-Dokument |
| `gebuehren_word.py` | Kostennote Nr. 2300 VV RVG (OOXML-Template) |
| `abrechnungsuebersicht.py` | Abrechnungsübersicht DOCX |
| `abrechnungsuebersicht_service.py` | Service + `_normalise_key()` für kanonische Keys |
| `sg_text_builder.py` | Schmerzensgeld-Text, `_fmt_datum()`, `_parse_datum()` |

### PDF-Parser (`backend/workflow/` und `backend/parsers/`)

| Datei | Zweck |
|---|---|
| `document_classifier.py` | Dokumenttyp-Erkennung (inkl. Subklassen PRD-32) |
| `parser_gutachten.py` | Gutachten-Parser (Regex + Qwen Shadow-Mode) |
| `parser_abrechnung.py` | Abrechnungsschreiben-Parser |
| `llm_parser.py` | Qwen-Integration (LM Studio lokal) |
| `ocr_service.py` | pytesseract + pdf2image (PRD-30) |

---

## Datenbank – SQLite-Tabellen

> Alle Schreiboperationen → SQLite. RA-MICRO nur SELECT.

### Kern (Schema 1–10)
| Tabelle | Inhalt |
|---|---|
| `unfallakte` | Hauptakte (az, status, hq, unfalldatum, portal_aktiv …) |
| `beteiligte` | Alle Parteien (mandant/gegner/zeuge/sonstiger) + Klage-Rollen |
| `schadenpositionen` | Einzelpositionen (reparatur, mietwagen, nutzungsausfall …) |
| `regulierung` | **DEPRECATED seit Schema 37** – kein neuer Code schreibt hier |
| `regulierung_positionen` | Positions-genaue Regulierung + Kürzungen (aktiv) |
| `dokumente` | Uploads + generierte Dateien (pdf_hash, dateigroesse) |
| `aktivitaeten` | Audit-Log aller Änderungen |
| `benutzer` | User-Konten + Rollen |
| `schema_version` | Migrationsversionierung |

### Erweiterungen (Schema 11–37)
| Tabelle | Inhalt |
|---|---|
| `abrechnungsschreiben` | Abrechnungsschreiben (Kürzungsanalyse, Option-B-Workflow) |
| `pruefberichte` | Kfz-Gutachter-Prüfberichte |
| `kuerzungsarten` | 19 Kürzungsarten (Katalog) |
| `todos` | Aufgaben je Akte (PRD-25a) |
| `personenschaden` | Personenschaden + sg_mindest/sg_text/sg_urteil_* |
| `forderung_positionen` | Extrahierte Forderungspositionen aus PDF |
| `eakte_klassifikation` | Dokumentklassifizierung (E-Akte) |
| `email_import_log` | E-Mail-Import-Protokoll |
| `fragebogen_erstkontakt` | Mandanten-Fragebogen (PRD-22c) |
| `rechnung_parse_cache` | PDF-Parser-Cache (manueller Parse-Endpunkt) |
| `konfiguration` | App-Einstellungen (Key-Value) |
| `gebuehren_berechnung` | Gebührenassistent-Ergebnis je Akte (VU-Regel, Faktor, Begründung) |

**Wichtige `dokumente`-Spalten:**
- `pdf_hash TEXT` (SHA-256 hex) – vor `registriere_dokument` auf Duplikat prüfen
- `dateigroesse INTEGER` – Byte-Größe
- `dokumentenklasse TEXT` – geplant PRD-04

**`unfallakte`-Spalten (neu seit Schema 36–37):**
- `portal_aktiv INTEGER` – Mandanten-Portal aktiviert
- `portal_last_sync TEXT` – letzter Portal-Sync

### RA-MICRO (read-only, //192.168.10.100)
| Quelle | Zugriff | Inhalt |
|---|---|---|
| SQL Server `ra` | SELECT only via sqlalchemy | Aktenzeichen, Beteiligte, Termine, mandant-checks |
| WDM-Variablen | SELECT only | Unfalldetails (varU-TAG, varU-ORT, varM-KZ …) |
| E-Akte (CIFS-Mount) | Dateisystem read-only | PDF/Dokumente je Akte |
| `tblElo_AktenArchiv` | SELECT only via pyodbc | DMS-Dokumente (PRD-19 geplant) |

---

## PRD → Dateien (Kurzreferenz)

| PRD | Feature | Hauptdateien |
|---|---|---|
| PRD-14 | Single Source of Truth Abrechnungsart | `AkteDetailView.jsx:172`, `UebersichtSection.jsx:~1789`, `RegulierungSection.jsx:~1776` |
| PRD-15 ✅ | WDM automatisch laden | `AkteDetailView.jsx:106–158` |
| PRD-16 | Tab-Reihenfolge | `AkteDetailView.jsx:222–233` |
| PRD-18 | Statusmodell | `akten_routes.py` (Migration), `UebersichtSection.jsx` |
| PRD-22c | Mandanten-Fragebogen | `fragebogen_routes.py`, `fragebogen_erstkontakt` (DB) |
| PRD-22d | E-Mail-Import | `email_routes.py`, `UnfallEmailView.jsx` |
| PRD-23b | Rechnungs-Parser | `pdf_parse_routes.py`, `rechnung_parse_cache` (DB) |
| PRD-24b | Klage-Wizard (10 Steps) | `KlageWizard.jsx`, `KlageSection.jsx`, `klage_service.py` |
| PRD-25a | Fristen-Tracking | `todos_routes.py`, `UebersichtSection.jsx` |
| PRD-25b | Action-Dashboard / WVL | `wiedervorlage_routes.py`, `WiedervorlageView.jsx` |
| PRD-25d | Intelligente STA | `sta_routes.py`, `StaDialog.jsx` |
| PRD-26 | Klage-Wizard Umbau | `KlageWizard.jsx`, `klage_wizard_map.md` |
| PRD-27 | ReguWizard Stellungnahme | `RegulierungSection.jsx` (geplant) |
| PRD-28 | Gebührenassistent Nr. 2300 | `gebuehren_routes.py`, `gebuehren_service.py`, `GebuehrenSection.jsx` |
| PRD-29 | Schmerzensgeld-Ermittlungstool | `klage_routes.py` (sg-*), `sg_text_builder.py`, `SchmerzensgelDialog.jsx` |
| PRD-30 | OCR + SSE-Streaming | `pdf_parse_routes.py` (SSE), `ocr_service.py`, `DokumenteSection.jsx` |
| PRD-31 | Action Board Übersicht-Tab | `UebersichtSection.jsx`, `AkteDetailView.jsx` |
| PRD-32 | Rechnungstypen-Subklassen | `document_classifier.py` |
| PRD-NEW | Neue Akte Stub | `AktensucheView.jsx`, `akten_routes.py` POST /akten |
| PRD-NEW | Onboarding-Wizard | geplant: `OnboardingWizard.jsx` |

---

## Schlüssel-Konventionen

```
API-Routen:        /akten/<az>/ressource  (az = Aktenzeichen als TEXT, nicht ID)
Auth:              JWT Bearer in jedem fetch(), kein credentials:'include'
Python:            3.9 – keine Union-Types (X | Y), kein Walrus (:=)
Reducer:           Neue Actions immer in reducer.js eintragen
JSX:               Toast/Modal neben Root-div → Fragment <> </> erforderlich
WDM-Keys:          sonstiges_wdm_X ≠ extra_wdm_ssX → Remap bei posMap prüfen
E-Akte-Cache:      rechnung_parse_cache (DB) = nur manueller Parse. Auto-Import → eakte_cache (in-memory)
Auto-Import:       Konfidenz >= 0.85 für E-Akte Auto-Import. Darunter: nur anzeigen.
Hash-Dedup:        Vor registriere_dokument immer pdf_hash prüfen (SHA-256, WHERE akte_id+pdf_hash)
Datumsformat:      personenschaden speichert GEMISCHT (ISO oder DD.MM.YYYY) → immer _fmt_datum()/_parse_datum()
sAnrede RM:        RA-MICRO sAnrede ist numerisch: "1"=Herr, "2"=Frau → Mapping in word_service.py
sg_text:           sg_text in personenschaden hat Vorrang vor Template-Aufbau in baue_sg_abschnitt()
Gebühren-NULL:     verletzungsgrad = NULL → "noch nicht beantwortet"; auslandsbezug = 0 → "Nein, beantwortet"
Gebühren-UPSERT:   gebuehren_berechnung hat UNIQUE(akte_id) → ON CONFLICT(akte_id) DO UPDATE
Kostennote:        OOXML-Template (forderungsschreiben_vorlage.docx als ZIP), _render_docx aus forderungsschreiben_wv.py
Regulierung-OptionB: jedes AB speichert nur eigene Zahlung (Inkrement). Summierung via v_regulierungsstatus.
                   regulierung-Tabelle deprecated.
Key-Normalisierung: Parser-Art-Werte (wbw, kostenpauschale) → _normalise_key() in abrechnungsuebersicht_service.py
_pruefe_akte-Muster: Rückgabewert IMMER nutzen → az = akte_obj.aktenzeichen if hasattr(...) else akte_id (v14c)
Gebühren-Anrede:   beteiligte.anrede (nicht geschlecht) → _mandant_anrede_nominativ()
RSV-Check:         IMMER RA-MICRO abfragen (tblAktenBeteiligte iBeteiligtenArt=3 bDeaktiviert=0)
                   SQLite beteiligte hat kein 'rechtsschutz'-Rolle (CHECK constraint verletzt)
LLM Shadow-Mode:   Qwen läuft parallel zu Regex-Parser. Konflikte → UI-Auswahl. Kein Auto-Override.
```

---

## Bekannte Pre-existing Testfehler

`test_prd23b.py` (7 Failures) und `test_modul8.py` (16 Errors) schlagen seit vor PRD-31 fehl.
Keine Blocker – nicht durch aktuelle Änderungen verursacht.
