# Projekt-Architektur – Unfallakten-Verwaltungssystem
# Kanzlei Koch, Schatz & Kollegen
> Stand: 2026-04-10 | Schema-Version 36

---

## Stack & Deployment

```
Browser (localhost:5173)
  └─ React + Vite (node:20-alpine)
       └─ fetch() → JWT Bearer → Flask (localhost:5000)
            └─ SQLite /app/data/unfallakten.db   ← SCHREIBEN
            └─ SQL Server //192.168.10.100 (RA-MICRO, read-only via WSL-Mount)
```

**Zwei Container:** `unfallakten-frontend-dev` (Vite) · `unfallakten-backend-dev` (Flask --debug)
**Config-Dateien:** `frontend/src/config/constants.js` (alle Domain-Konstanten) · `theme.js` · `icons.jsx`

---

## Frontend – Sections & Views

### AkteDetailView.jsx – Tab-Container
Jeder Tab entspricht einer Section. Reihenfolge = Tab-Reihenfolge.

| Tab / Datei | Inhalt |
|---|---|
| `BeteiligteSection.jsx` | Mandant, Gegner, Zeugen – CRUD |
| `UnfalldetailsSection.jsx` | Unfalldetails aus WDM/DB lesen + bearbeiten |
| `SchadenSection.jsx` | Schadenpositionen (Reparatur, Mietwagen, GA-Kosten …) |
| `DokumenteSection.jsx` | Datei-Upload, Klassifizierung, E-Akte-Viewer |
| `GebuehrenSection.jsx` | Gebührenassistent Nr. 2300 VV RVG (PRD-28) |
| `RegulierungSection.jsx` | Abrechnungsschreiben erfassen + Kürzungsanalyse |
| `KlageSection.jsx` | Klage-Übersicht + Wizard-Einstieg (deprecated: Ein-Klick) |
| `WordSection.jsx` | Forderungsschreiben, WVB, sonstige Word-Dokumente |
| `UebersichtSection.jsx` | Chronik, Regulierungsstand, Todos, Beteiligten-Übersicht |

### Standalone Views

| Datei | Zweck |
|---|---|
| `AktensucheView.jsx` | Suche + Filter über alle Akten |
| `DashboardView.jsx` | Kennzahlen-Dashboard |
| `WiedervorlageView.jsx` | Sachstandsanfragen (PRD-25b) |
| `email_import/UnfallEmailView.jsx` | E-Mail-Import unfall@/termin@/bussgeld@ (PRD-22d) |
| `KuerzungskatalogView.jsx` | 19 Kürzungsarten-Verwaltung |
| `StatistikenView.jsx` | Statistiken |
| `EinstellungenView.jsx` | App-Einstellungen |

### Wichtige Shared Components

| Datei | Zweck |
|---|---|
| `common.jsx` | Card, Btn, Toast, SlidePanel, Input, Modal |
| `StaDialog.jsx` | Sachstandsanfragen-Dialog (PRD-25d) |
| `layout.jsx` | App-Shell mit Navigation |

---

## Backend – Blueprint-Übersicht

Alle Blueprints in `backend/app.py → erstelle_app()` registriert.

### Akten-Domain (`/akten/<az>/...`)

| Blueprint-Datei | Prefix-Suffix | Zweck |
|---|---|---|
| `akten_routes.py` | `/akten` | CRUD Akte, Status, Aktivitäten |
| `beteiligte_routes.py` | `/beteiligte` | Parteien CRUD |
| `schaden_routes.py` | `/schaden` | Schadenpositionen |
| `regulierung (in schaden_routes)` | `/regulierungen` | Regulierungsstand |
| `abrechnungsschreiben_routes.py` | `/abrechnungen` | Abrechnungsschreiben + Prüfberichte |
| `pruefberichte_routes.py` | `/pruefberichte` | Prüfberichte detail |
| `dokumente_routes.py` | `/dokumente` | Upload, Klassifizierung, Download |
| `klage_routes.py` | `/klage` | Klage-Daten, RVG-Berechnung, Gericht-Suche |
| `word_routes.py` | `/dokumente/word` | Word-Generierung |
| `belege_routes.py` | `/belege` | Belege |
| `forderung_routes.py` | `/forderungen` | Forderungspositionen |
| `personenschaden_routes.py` | `/personenschaden` | Personenschaden |
| `todos_routes.py` | `/todos` | Aufgaben |
| `stellungnahme_routes.py` | `/stellungnahmen` | Stellungnahmen |
| `sta_routes.py` | `/sta` | Sachstandsanfragen |
| `eakte_routes.py` | `/eakte` | E-Akte-Integration |
| `gebuehren_routes.py` | `/gebuehren` | Gebührenassistent Nr. 2300 (PRD-28) |
| `pdf_parse_routes.py` | `/parse` | PDF-Parser (GA, Abrechnung) |
| `ramicro_akte_routes.py` | `/ramicro/akte` | RA-MICRO Sync |

### Globale Routen

| Blueprint-Datei | Prefix | Zweck |
|---|---|---|
| `auth_routes.py` | `/auth` | Login, JWT, User-CRUD |
| `email_routes.py` | `/email` | E-Mail-Import (EML-Parsing) |
| `wiedervorlage_routes.py` | `/wiedervorlage` | Sachstandsanfragen-Workflow |
| `kuerzungsarten_routes.py` | `/kuerzungsarten` | Kürzungskatalog (read-mostly) |
| `dashboard_routes.py` | `/dashboard` | Kennzahlen |
| `firmen_routes.py` | `/firmen` | Firmensuche (Vertreter-Lookup) |
| `einstellungen_routes.py` | `/einstellungen` | Konfiguration |
| `distanz_routes.py` | `/distanz` | Entfernungsberechnung |
| `aktensuche_routes.py` | `/aktensuche` | Volltext-Aktensuche |

### Word-Generierung (`backend/word/`)

| Datei | Zweck |
|---|---|
| `klage_service.py` | Klageschrift (DOCX) – Platzhalter-System + `berechne_rvg()` |
| `forderungsschreiben_wv.py` | Forderungsschreiben / Wiedervorlage-Brief – `_render_docx()`, `_unterschrift_bytes()`, `_mandant_anrede_nominativ()` |
| `sachstandsanfrage.py` | Sachstandsanfragen-Dokument |
| `gebuehren_word.py` | Kostennote Nr. 2300 VV RVG – nutzt `forderungsschreiben_vorlage.docx` + `_render_docx` aus `forderungsschreiben_wv.py` |
| `abrechnungsuebersicht.py` | Abrechnungsübersicht DOCX |
| `abrechnungsuebersicht_service.py` | Service für Abrechnungsübersicht |

---

## Datenbank – SQLite-Tabellen

> Alle Schreiboperationen → SQLite. RA-MICRO nur SELECT.

### Kern (Schema 1–10)
| Tabelle | Inhalt |
|---|---|
| `unfallakte` | Hauptakte (az, status, hq, unfalldatum …) |
| `beteiligte` | Alle Parteien (mandant/gegner/zeuge/sonstiger) + Klage-Rollen |
| `schadenpositionen` | Einzelpositionen (reparatur, mietwagen, nutzungsausfall …) |
| `regulierung` | Regulierungsschreiben (gefordert vs. reguliert) |
| `regulierung_positionen` | Positions-genaue Regulierung + Kürzungen |
| `dokumente` | Uploads + generierte Dateien |
| `aktivitaeten` | Audit-Log aller Änderungen |
| `benutzer` | User-Konten + Rollen |
| `schema_version` | Migrationsversionierung |

### Erweiterungen (Schema 11–34)
| Tabelle | Inhalt |
|---|---|
| `abrechnungsschreiben` | Abrechnungs-Schreiben (mit Kürzungsanalyse) |
| `pruefberichte` | Kfz-Gutachter-Prüfberichte |
| `kuerzungsarten` | 19 Kürzungsarten (Katalog) |
| `todos` | Aufgaben je Akte |
| `personenschaden` | Personenschaden-Positionen (+ sg_mindest/sg_text/sg_urteil_* seit Schema 36) |
| `forderung_positionen` | Extrahierte Forderungspositionen aus PDF |
| `eakte_klassifikation` | Dokumentklassifizierung (E-Akte) |
| `email_import_log` | E-Mail-Import-Protokoll |
| `fragebogen_erstkontakt` | Mandanten-Fragebogen (PRD-22c) |
| `rechnung_parse_cache` | PDF-Parser-Cache (nur manueller Parse-Endpunkt schreibt hier) |
| `konfiguration` | App-Einstellungen (Key-Value) |
| `gebuehren_berechnung` | Gebührenassistent-Ergebnis je Akte (VU-Regel, Faktor, Begründung) |

**Wichtige `dokumente`-Spalten:**
- `pdf_hash TEXT` (seit Migration 24): SHA-256 hex – vor `registriere_dokument` auf Duplikat prüfen
- `dateigroesse INTEGER`: Byte-Größe der Datei

### RA-MICRO (read-only, //192.168.10.100)
| Quelle | Zugriff | Inhalt |
|---|---|---|
| SQL Server `ra` | SELECT only via sqlalchemy | Aktenzeichen, Beteiligte, Termine |
| WDM-Variablen | SELECT only | Unfalldetails (varU-TAG, varU-ORT …) |
| E-Akte (CIFS-Mount) | Dateisystem read-only | PDF/Dokumente je Akte |

---

## PRD → Dateien (Kurzreferenz)

| PRD | Feature | Hauptdateien |
|---|---|---|
| PRD-22c | Mandanten-Fragebogen | `fragebogen_routes.py`, `fragebogen_erstkontakt` (DB) |
| PRD-22d | E-Mail-Import | `email_routes.py`, `UnfallEmailView.jsx` |
| PRD-23b | Rechnungs-Parser | `pdf_parse_routes.py`, `rechnung_parse_cache` (DB) |
| PRD-24b | Klage-Wizard (7→10 Steps) | `KlageWizard.jsx`, `KlageSection.jsx`, `klage_service.py` |
| PRD-25a | Fristen-Tracking | `todos_routes.py`, `UebersichtSection.jsx` |
| PRD-25b | Action-Dashboard / WVL | `wiedervorlage_routes.py`, `WiedervorlageView.jsx` |
| PRD-25c | Mandantenkommunikation | offen |
| PRD-25d | Intelligente STA | `sta_routes.py`, `StaDialog.jsx` |
| PRD-26 | Klage-Wizard Umbau | `KlageWizard.jsx`, `KlageSection.jsx`, `klage_service.py` |
| PRD-28 | Gebührenassistent Nr. 2300 | `gebuehren_routes.py`, `gebuehren_service.py`, `GebuehrenSection.jsx` |
| PRD-29 | Schmerzensgeld-Ermittlungstool | `klage_routes.py` (sg-*), `sg_text_builder.py`, `SchmerzensgelDialog.jsx` |
| Bußgeld | Bußgeld-Feature | separates Projekt (bussgeld@ Strato) |

---

## Schlüssel-Konventionen

```
API-Routen:     /akten/<az>/ressource  (az = Aktenzeichen als TEXT, nicht ID)
Auth:           JWT Bearer in jedem fetch(), kein credentials:'include'
Python:         3.9 – keine Union-Types (X | Y), kein Walrus (:=)
Reducer:        Neue Actions immer in reducer.js eintragen
JSX:            Toast/Modal neben Root-div → Fragment <> </> erforderlich
WDM-Keys:       sonstiges_wdm_X ≠ extra_wdm_ssX → Remap bei posMap prüfen
E-Akte-Cache:   rechnung_parse_cache (DB) = nur manueller Parse. Auto-Import → eakte_cache dict (in-memory)
Auto-Import:    Konfidenz >= 0.85 für E-Akte Auto-Import. Darunter: nur anzeigen, nicht importieren.
Hash-Dedup:     Vor registriere_dokument immer pdf_hash prüfen (SHA-256, WHERE akte_id+pdf_hash)
Datumsformat:   personenschaden speichert Daten GEMISCHT (ISO oder DD.MM.YYYY je nach Quelle)
                → immer _fmt_datum()/_parse_datum() aus sg_text_builder.py verwenden
sAnrede RM:     RA-MICRO sAnrede ist numerisch: "1"=Herr, "2"=Frau → Mapping _ANREDE_NORM in word_service.py
sg_text:        sg_text in personenschaden hat Vorrang vor Template-Aufbau in baue_sg_abschnitt()
Gebühren-NULL:  verletzungsgrad = NULL → "noch nicht beantwortet" (in fehlende_felder). auslandsbezug = 0 (DEFAULT) → "Nein, beantwortet".
Gebühren-UPSERT: gebuehren_berechnung hat UNIQUE(akte_id) → immer ON CONFLICT(akte_id) DO UPDATE
Kostennote:     OOXML-Template (forderungsschreiben_vorlage.docx als ZIP), _render_docx aus forderungsschreiben_wv.py, gespeichert als typ='sonstiges' in dokumente
Gebühren-Anrede: beteiligte.anrede (nicht geschlecht) → _mandant_anrede_nominativ() aus forderungsschreiben_wv.py
```
