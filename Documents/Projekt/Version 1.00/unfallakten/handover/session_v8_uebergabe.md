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
| DB-Pfad (Container) | `/app/data/unfallakten.db` |

## Dateipfade

```
backend/
  routers/
    abrechnungsschreiben_routes.py   ← v8: PUT/DELETE/WDM-Routen
  db/
    schema_manager.py                ← v8: Migration 16
  ramicro/
    connector.py                     ← get_ramicro_connection(), TDS 7.0
    wdm_regulierung_service.py       ← v8: NEU
  word/
    abrechnungsuebersicht_service.py ← v7: 4-spaltige Tabelle
frontend/src/
  App.jsx                            ← v8: ~7660 Zeilen
  api.js                             ← NICHT geändert
data/
  unfallakten.db                     ← Schema v16, id = INTEGER PRIMARY KEY
```

## Kritischer DB-Fix v8

**Problem:** `abrechnungsschreiben.id` hatte Typ `INT` ohne `PRIMARY KEY` (Schaden aus Migration 5).
Alle Inserts erzeugten `id=NULL` → DELETE per `WHERE id=?` traf nie etwas → Phantom-Einträge.

**Fix:** Tabelle neu gebaut via `fix_db.py` im Container:
```powershell
docker cp fix_db.py unfallakten-backend-dev:/app/fix_db.py
docker exec unfallakten-backend-dev python3 /app/fix_db.py
docker restart unfallakten-backend-dev
```

## SQLite Schema v16 – neue Felder

**`abrechnungsschreiben`:**
- `quelle TEXT NOT NULL DEFAULT 'pdf'` → `'pdf' | 'manuell' | 'wdm'`
- `gesamt_kuerzung REAL NOT NULL DEFAULT 0.0`
- `wdm_importiert INTEGER NOT NULL DEFAULT 0`

**`regulierung_positionen`:**
- `position_label TEXT`
- CHECK-Constraint auf `position_key` entfernt

## WDM-Regulierung

### Verbindung
`wdm_regulierung_service.py` nutzt `connector.py` → `get_ramicro_connection()`.
- `tds_version="7.0"` Pflicht
- `RAMICRO_AKTIV=true` in `.env` erforderlich

### WDM → position_key Mapping
```
varREPKOSTENSVG → rep_gutachten_netto    varREPKOSTENG   → rep_rechnung_netto
varKOSTENSVG    → sv_kosten             varKOSTENNBG    → kostennb
varABSCHLEPPG   → abschleppkosten      varSTANDKOSTENG → standkosten
varMIETWAGENG   → mietwagenkosten      varVERDIENSTG   → verdienstausfall
varANABKOSTENG  → anabmeldekosten      varHAUSHALTG    → haushalt
varUNKOSTENG    → unkostenpauschale    varWERTMINDG    → wertminderung
varNUTZUNGSAG   → nutzungsausfall      varSGVORSCHUSS  → schmerzensgeld
varVORSCHUSSG   → vorschuss            varSSCHADEN1-6G → sonstiges_wdm_1-6
varRGGDAT       → datum                varQUOTEG       → haftungsquote
```

## Neue Backend-Routen

```
PUT    /akten/<id>/abrechnungen/<ab_id>      Bearbeiten (manuell)
DELETE /akten/<id>/abrechnungen/<ab_id>      Löschen (direktes sqlite3 + commit)
GET    /akten/<id>/abrechnungen/wdm-check    WDM-Vorschau
POST   /akten/<id>/abrechnungen/wdm-import   WDM importieren
```

**DELETE** nutzt direkt `sqlite3.connect()` mit explizitem `conn.commit()`.

## Frontend-Änderungen (App.jsx)

### Regulierung-Tab
- `ManuelleAbrechnungFormular`: Schnelleingabe + Vollständig, Dropdown + Freitext
- Buttons: `[📄 PDF] [📋 WDM] [+ Manuell]`
- 🗑 bei allen Einträgen, ✏️ nur bei manuellen
- Badges: Manuell (grau), RA-Micro WDM (blau), PDF geparst (grün)
- posMap: Manuell kumulativ, PDF/WDM letzter Eintrag gewinnt
- Tooltip mit Herkunft (Datum · Versicherung · Betrag · Quelle)

### Allgemein
- Anmeldeseite: § links neben Kanzleinamen
- Akte-Header: Status-Buttons direkt im Header (alle Tabs)
- Übersicht-Tab: Status-Kachel weg, Notizen volle Breite
- `POSITION_LABELS_FE` erweitert um `rep_gutachten_netto`, `rep_rechnung_netto/brutto`,
  `verdienstausfall`, `haushalt`, `unkostenpauschale`, `kostennb`, `vorschuss`, `sonstiges_wdm_1-6`
- Kein Demo-Fallback in Formularen → Fehler als Alert
- State immer frisch aus DB nach Save/Delete/Import

### Wichtig: request() statt apiAbrechnungen.liste()
`api.js` wurde nicht angepasst. Alle neuen Calls nutzen `request()` direkt:
```javascript
request(`/akten/${akteId}/abrechnungen`)
request(`/akten/${akteId}/abrechnungen/wdm-check`)
request(`/akten/${akteId}/abrechnungen/${abId}`, { method: "DELETE" })
```

## Funktionsstand

| Feature | Status |
|---|---|
| Login / Aktenübersicht / Suche | ✅ |
| Schaden (manuell / WDM / PDF) | ✅ |
| Forderungsschreiben / Vollmacht | ✅ |
| Personenschaden | ✅ |
| E-Mail-Import | ✅ (IMAP-Test ausstehend) |
| Regulierung PDF-Import | ✅ |
| Regulierung manuell / WDM / Edit / Delete | ✅ v8 |
| Abrechnungsübersicht Word | ✅ v7 |
| Statistiken | ⚠️ Mock-Daten |
| Klageschreiben | ⚠️ Stub (501) |

## Offene Punkte nächste Session

1. **api.js** – `abrechnungen.update()` + `.delete()` ergänzen
2. **Abrechnungsübersicht-Route** – Word-Generator verdrahten
3. **IMAP E-Mail-Import** – echter Server-Test
4. **Statistiken** – echte DB-Abfragen
5. **Klageschreiben-Generator** – Vorlage fehlt
