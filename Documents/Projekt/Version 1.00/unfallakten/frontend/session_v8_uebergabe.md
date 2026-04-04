# Übergabe-Dokumentation – Kanzlei Koch, Schatz & Kollegen
# Unfallakten-Verwaltungssystem – Session v8

## Stack & Umgebung

| Komponente | Details |
|---|---|
| Backend | Flask 3.1.2 / Python 3.12, SQLite Schema **v16** |
| Frontend | React 18 + Vite 5 |
| RA-Micro | pymssql → `192.168.10.100:1433`, DB: `RAMICRO` |
| Docker | `unfallakten-backend-dev` / `unfallakten-frontend-dev` |
| Projektpfad (Host) | `C:\users\HAL9000\Documents\Projekt\Version 1.00\unfallakten` |

## Neue Dateipfade (Session v8)

```
backend/
  routers/
    abrechnungen_routes.py    ← PUT + DELETE + wdm-check + wdm-import NEU
  word/
    abrechnungsuebersicht_service.py  ← NEU
    abrechnungsuebersicht_vorlage.docx ← NEU (nur auf Server)
  db/
    schema_manager.py         ← Migration 16 einbauen
  ramicro/
    wdm_regulierung_service.py  ← NEU
frontend/src/
  App.jsx                     ← ~7624 Zeilen
```

## SQLite Schema – Migration 16 (NEU)

```sql
ALTER TABLE abrechnungen ADD COLUMN quelle TEXT NOT NULL DEFAULT 'pdf'
-- 'pdf' | 'manuell' | 'wdm'

ALTER TABLE abrechnungen ADD COLUMN wdm_importiert INTEGER NOT NULL DEFAULT 0

ALTER TABLE abrechnungen_positionen ADD COLUMN position_label TEXT
```

**In schema_manager.py einbauen** – Funktion `migration_16()` aus `migration_16_patch.py` kopieren,
in `migrate()`-Funktion nach Migration 15 aufrufen.

## WDM Regulierungsvariablen (verifiziert mit SQL-Test Akte 31/21)

### Tabellenstruktur `_tbl0WDMDaten`
```
lPoolId (int) | AktenNr varchar(15) | sName nvarchar(53) | Value ntext
```
AktenNr = Aktenzeichen OHNE Kürzel (`31/21`), nicht `31/21 PK`

### Werteformat
- Zahlen: `2.616,71 EUR` oder `650,00` – EUR-Suffix inkonsistent, immer strippen
- Datum `varRGGDAT`: `23.03.2021` (TT.MM.JJJJ, Länge 10)
- Nullwerte: `0,00` oder `0,00 EUR` → ignorieren (nur > 0 importieren)

### WDM → position_key Mapping
```
varREPKOSTENSVG → rep_gutachten_netto    varREPKOSTENG   → rep_rechnung_netto
varKOSTENSVG    → sv_kosten              varKOSTENNBG    → kostennb
varABSCHLEPPG   → abschleppkosten       varSTANDKOSTENG → standkosten
varMIETWAGENG   → mietwagenkosten       varVERDIENSTG   → verdienstausfall
varANABKOSTENG  → anabmeldekosten       varHAUSHALTG    → haushalt
varUNKOSTENG    → unkostenpauschale     varWERTMINDG    → wertminderung
varNUTZUNGSAG   → nutzungsausfall       varSGVORSCHUSS  → schmerzensgeld
varVORSCHUSSG   → vorschuss             varSSCHADEN1G–6G → sonstiges_wdm_1–6
varRGGDAT       → (Datum)               varQUOTEG       → (Haftungsquote)
```

## In Session v8 implementiert

### Frontend (App.jsx, 24/24 Patches, Klammer-Balance 0)

**`ManuelleAbrechnungFormular`** – neues Subcomponent (Zeile ~4439):
- Toggle Schnelleingabe ↔ Vollständig
- Schnelleingabe: Datum*, Versicherung (auto), Positionen (Dropdown + Freitext)
- Edit-Modus via `initialData`-Prop
- Speichert mit `quelle: "manuell"`

**`RegulierungSection`** erweitert:
- Prop `beteiligte` neu → Versicherungsname auto aus GHPV/Gegner
- WDM-Auto-Hinweis-Banner (gelb) beim ersten Laden wenn WDM-Daten vorhanden
- Badges: `[Manuell]` grau / `[RA-Micro WDM]` blau / `[PDF geparst]` grün
- ✏️ / 🗑 Icons bei manuellen Einträgen
- Handler: `onUpdate`, `onDelete`, `onWdmImport`

**posMap-Aggregation** (Übersicht-Tab):
- Manuell = kumulativ (Teilzahlungen addieren sich)
- PDF/WDM = letzter Eintrag gewinnt
- `eintraege[]` für Tooltip-Daten

**Tooltip** in Übersicht-Positionstabelle:
- `ℹ`-Icon bei regulierten Positionen
- Hover: `TT.MM.JJJJ · Versicherungsname · €-Betrag · (manuell/WDM/PDF)`

**Reducer** (neu):
- `UPDATE_ABRECHNUNG` – aktualisiert Abrechnung in Liste
- `DELETE_ABRECHNUNG` – entfernt Abrechnung aus Liste

**POSITION_LABELS_FE** ergänzt:
`verdienstausfall`, `haushalt`, `unkostenpauschale`, `kostennb`,
`vorschuss`, `sonstiges_wdm_1`–`6`

### Backend (als Patch-Dateien, noch einzubauen)

**`migration_16_patch.py`** → in `schema_manager.py` einbauen

**`abrechnungen_routes_patch.py`** → neue Routen:
- `PUT  /<akte_id>/abrechnungen/<ab_id>` – nur quelle='manuell'
- `DELETE /<akte_id>/abrechnungen/<ab_id>` – nur quelle='manuell'
- `GET  /<akte_id>/abrechnungen/wdm-check` – WDM-Vorschau
- `POST /<akte_id>/abrechnungen/wdm-import` – WDM importieren

**`wdm_regulierung_service.py`** → nach `backend/ramicro/`:
- `lade_wdm_regulierung(akte_id, conn)` – SQL-Abfrage
- `wdm_zu_abrechnung(wdm_dict)` – Konvertierung
- `hat_wdm_regulierung(wdm_dict)` – Schnell-Check
- `parse_wdm_betrag('2.616,71 EUR')` → `2616.71`
- `parse_wdm_datum('23.03.2021')` → `'2021-03-23'`

**`abrechnungsuebersicht_service.py`** → nach `backend/word/`:
- 4-spaltige Tabelle: Position | Gefordert | Gezahlt | Offen
- Briefkopf identisch zur Sachstandsanfrage

## Aktueller Funktionsstand

| Feature | Status |
|---|---|
| Login / Auth | ✅ |
| Aktenübersicht / Suche | ✅ |
| Beteiligte-Tab | ✅ |
| Schaden-Tab (alle Modi) | ✅ |
| Personenschaden-Tab | ✅ |
| Forderungsschreiben-Generator | ✅ |
| Vollmacht-Generator (PDF) | ✅ |
| IBAN-Check | ✅ |
| Vollmacht-Check (WDM) | ✅ |
| Wiedervorlage (RA-Micro) | ✅ |
| E-Mail-Import | ✅ (IMAP-Test ausstehend) |
| Regulierung – PDF-Import | ✅ |
| Regulierung – Manuell | ✅ Frontend / ⚠️ Backend-Patch einbauen |
| Regulierung – WDM-Auto-Import | ✅ Frontend / ⚠️ Backend-Patch einbauen |
| Abrechnungsübersicht (Word) | ✅ Generator / ⚠️ Route verdrahten |
| Statistiken | ⚠️ Mock-Daten |
| Klageschreiben | ⚠️ Stub (501) |

## Offene Punkte / nächste Session

1. **Backend-Patches einbauen** – Migration 16 + neue Routen + wdm_regulierung_service
2. **Abrechnungsübersicht-Route** – `GET /akten/<id>/word/abrechnungsuebersicht`
3. **Word-Tab** – Button „Abrechnungsübersicht" ergänzen
4. **IMAP E-Mail-Import** – echter Server-Test
5. **Statistiken** – echte DB-Abfragen
6. **Klageschreiben** – Vorlage fehlt, Route gibt 501
7. **KANZLEI_IBAN/BIC** – Platzhalter in `.env`

## API-Konventionen

```javascript
tokenStore.getAccess()          // Token sessionStorage 'uas_access'
request('/akten/1/16/schaden')  // kein /api-Prefix
// AZ im URL-Pfad NICHT encodeURIComponent (Flask nutzt <path:akte_id>)
```
