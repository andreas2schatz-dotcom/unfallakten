# Projektübergabe: Unfallakten-Verwaltung
## Kanzlei Koch, Schatz & Kollegen, Offenbach

---

## 1. Projektbeschreibung

Webbasiertes Aktenverwaltungssystem für Verkehrsunfallakten. RA-Micro (bestehendes Kanzleisystem) bleibt die Hauptdatenbank — dieses System ergänzt sie um Schadenserfassung, Regulierungsverlauf, PDF-Gutachtenimport und Word-Generierung.

**Kernprinzip:** RA-Micro ist Quelle der Wahrheit. Lokale SQLite-Datenbank entsteht nur "on demand" wenn eine Akte tatsächlich bearbeitet wird.

---

## 2. Tech-Stack

| Komponente | Technologie |
|---|---|
| Backend | Flask 3.1.2, Python 3.12 |
| Datenbank lokal | SQLite (WAL-Modus), Schema v7 |
| RA-Micro | pymssql 2.3.1 → SQL Server 2014 (192.168.10.100:1433, DB: RAMICRO) |
| PDF-Parsing | pdfplumber |
| Word-Generierung | python-docx |
| Frontend | React 18 + Vite 5 (App.jsx ~5366 Zeilen) |
| Charts | Recharts |
| Deployment | Docker Compose (Backend + Frontend/nginx) |

---

## 3. Dateipfade

```
unfallakten/
├── backend/
│   ├── app.py                          ← Flask-App, _ensure_admin_exists()
│   ├── auth/
│   │   ├── jwt_handler.py
│   │   ├── middleware.py
│   │   └── service.py                  ← Login, Token, logge_aktivitaet
│   ├── db/
│   │   ├── database.py                 ← get_connection(), WAL-Modus
│   │   ├── schema.py                   ← DDL, Schema v7
│   │   └── schema_manager.py           ← Migrationen 1-7
│   ├── models/
│   │   ├── akte.py                     ← PK: az (TEXT), erstelle_oder_hole_akte()
│   │   ├── benutzer.py
│   │   ├── dokument.py                 ← logge_aktivitaet(), hole_aktivitaeten()
│   │   ├── schaden.py
│   │   ├── abrechnungsschreiben.py
│   │   └── kuerzungsart.py
│   ├── ramicro/
│   │   ├── connector.py                ← get_ramicro_connection(), RaMicroNichtAktiv
│   │   ├── sachbearbeiter.py           ← SACHBEARBEITER-Dict, HV_KENNZEICHEN
│   │   └── wiedervorlage_service.py    ← Wiedervorlage-Logik
│   ├── routers/
│   │   ├── akten_routes.py             ← CRUD, PATCH loggt Aktivitäten
│   │   ├── aktensuche_routes.py        ← GET /aktensuche (az/name/kz/tag)
│   │   ├── auth_routes.py              ← Login, /auth/ping mit DB-Status
│   │   ├── beteiligte_routes.py
│   │   ├── dokumente_routes.py
│   │   ├── email_routes.py
│   │   ├── kuerzungsarten_routes.py
│   │   ├── pdf_parse_routes.py
│   │   ├── ramicro_akte_routes.py      ← RA-Micro Hauptdatei (652 Zeilen)
│   │   ├── schaden_routes.py
│   │   ├── wiedervorlage_routes.py
│   │   └── word_routes.py
│   ├── parsers/
│   │   └── gutachten_parser.py
│   ├── pdf/
│   │   ├── parser.py
│   │   └── upload_service.py
│   └── word/
│       ├── word_service.py
│       ├── forderungsschreiben.py
│       ├── abrechnungsuebersicht.py
│       └── sachstandsanfrage.py
├── frontend/
│   ├── src/
│   │   ├── App.jsx                     ← Gesamt-Frontend (~5366 Zeilen)
│   │   ├── api.js                      ← API-Client inkl. ramicroListe, ramicroWdm
│   │   ├── globals.css                 ← Globale Styles (Animationen etc.)
│   │   └── main.jsx                    ← Einstiegspunkt, importiert globals.css
│   ├── public/
│   │   └── favicon.ico
│   ├── Dockerfile                      ← Multi-Stage: node builder + nginx runtime
│   ├── docker/
│   │   └── nginx-spa.conf
│   └── vite.config.js                  ← Proxy für /ramicro, /akten etc.
├── docker-compose.prod.yml             ← Produktions-Stack
├── docker-compose.yml                  ← Dev-Stack
├── Dockerfile                          ← Backend
├── Makefile
├── .env.example
└── scripts/
    └── deploy.sh
```

---

## 4. Datenbank-Schema (SQLite, aktuell v7)

### Primärschlüssel-Konzept
`unfallakte.az TEXT PRIMARY KEY` — das Aktenzeichen aus RA-Micro (z.B. `"211/26"`) ist der PK. Alle FK-Spalten sind `akte_id TEXT`.

### Tabellen
| Tabelle | Beschreibung |
|---|---|
| `unfallakte` | Kern-Akte: az, status, notizen, haftungsquote, kurzbezeichnung, sachbearbeiter |
| `schadenpositionen` | rep_gutachten_netto, rep_rechnung_brutto, wiederbeschaffung, restwert, wertminderung, nutzungsausfall, mietwagenkosten, sv_kosten, abschleppkosten, standkosten, anabmeldekosten, schmerzensgeld, verdienstausfall, haushalt, unkostenpauschale, sonstiges + wdm_extras_json |
| `regulierung` | Regulierungsvorgänge mit Positionen |
| `beteiligte` | Lokale Beteiligte (aus SQLite, nicht RA-Micro) |
| `dokumente` | PDFs + Word-Dokumente |
| `aktivitaeten` | Audit-Log: zeitstempel, aktion, beschreibung, akte_id, benutzer_id |
| `abrechnungsschreiben` | Generierte Word-Dokumente |
| `pruefberichte` | SV-Prüfberichte |
| `kuerzungsarten` | Globaler Kürzungskatalog |
| `benutzer` | Kanzleimitarbeiter |
| `email_import_log` | E-Mail-Import-Protokoll |

### Views
- `v_schadensummen` — berechnete Summen aus schadenpositionen
- `v_regulierungsstatus` — GROUP BY a.az (nicht a.id!)

### Migrationen
- Migration 5: AZ als PK
- Migration 6: Neue Schadenfelder (verdienstausfall, haushalt, wdm_extras_json etc.)
- Migration 7: v_regulierungsstatus GROUP BY az korrigiert

---

## 5. RA-Micro Anbindung

### Verbindung
```
Host: 192.168.10.100
Port: 1433
DB:   RAMICRO
```
Umgebungsvariable `RAMICRO_AKTIV=true` in `.env` nötig.

### Wichtige Tabellen
| Tabelle | Beschreibung |
|---|---|
| `tblAkten` | `sAktenNummer` (ohne SB-Kürzel!), `sAktenSachbearbeiter`, `GUIDAkte`, `dtAblage` |
| `tblAktenBeteiligte` | Join via `GUIDAkte` (NICHT AktenNr!), `iBeteiligtenArt`, `sBeteiligtenKennzeichen` |
| `tblAdressen` | `sNachname`, `sVorname`, `sTelefon`, `sTelefon2`, `sMobiltelefon`, `sTelefax`, `sEMail` |
| `_tbl0WDMDaten` | `AktenNr`, `sName`, `Value` — Variablen für Schaden, KFZ, Datum |
| `tblAktenWiedervorlagen` | Wiedervorlagen |

### AZ-Format
RA-Micro speichert `sAktenNummer = "1213/25"` (ohne SB-Kürzel). Das vollständige AZ `"1213/25AS"` wird aus `sAktenNummer + sAktenSachbearbeiter` zusammengesetzt.

**_az_basis()-Funktion** in `ramicro_akte_routes.py` schneidet das SB-Kürzel ab: `"1213/25AS" → "1213/25"`.

### Aktiv-Filter
```sql
dtAblage IS NULL OR CAST(dtAblage AS DATE) = '1899-12-30'
```

### Beteiligten-Klassifizierung
| Art | Kennzeichen | Gruppe |
|---|---|---|
| 1 | beliebig (außer SB/SO/G) | mandant |
| 2 | HP, HPV, KASK | eigene_versicherung |
| 2 | sonstige | gegner |
| 3 | — | rechtsschutz |
| 4 | GHPV, GBEV | gegner |
| 4 | AA | behoerde |
| 6 | — | behoerde |
| 9 | — | gegner |

### WDM-Variablen (Schadenpositionen)
RA-Micro schreibt Beträge mit `" EUR"` Suffix (z.B. `"6.495,48 EUR"`). Die `_zahl()`-Funktion in `ramicro_akte_routes.py` entfernt diesen Suffix vor dem Parsen.

**Kanzlei-spezifisches Mapping (hartkodiert):**
```
varREPKOSTENSV      → rep_gutachten_netto (fiktiv, lt. Gutachten)
varUST-REPKOSTENSV  → rep_gutachten_mwst
varREPKOSTEN        → rep_rechnung_netto (konkret, lt. Rechnung)
varUST-REPKOSTEN    → → rep_rechnung_brutto (zusammen)
varWIEDERBESCHAFF   → wiederbeschaffung
varRESTWERT         → restwert
varWERTMIND         → wertminderung
varNUTZUNGSA        → nutzungsausfall
varMIETWAGEN        → mietwagenkosten (+ varUST-MIETWAGEN)
varKOSTENSV         → sv_kosten (+ varUST-KOSTENSV + varKOSTENNB + varUST-KOSTENNB)
varABSCHLEPP        → abschleppkosten (+ varUST-ABSCHLEPP)
varSTANDKOSTEN      → standkosten (+ varUST-STANDKOSTEN)
varANABKOSTEN       → anabmeldekosten (+ varUST-ANABKOSTEN)
varSCHMGELD         → schmerzensgeld
varVERDIENST        → verdienstausfall
varHAUSHALT         → haushalt
varUNKOSTEN         → unkostenpauschale (immer 30 €)
varSSCHADEN1-6      → extras[].label
varSSBETRAG1-6      → extras[].netto (varSSBETRAG5A für Schaden 5!)
varUST-SS1-6        → extras[].mwst
varFKLASSE          → info.fahrzeugklasse_na
varNABETRAG         → info.na_tagessatz
varREPDAUER         → info.reparaturdauer
```

---

## 6. API-Endpunkte (Übersicht)

### Lokal (SQLite)
```
POST   /auth/login
GET    /auth/ping                       ← DB-Status + Benutzer-Liste
GET    /akten/<az>/aktivitaeten
PATCH  /akten/<az>                      ← loggt status/notizen/hq
GET/POST /akten/<az>/schaden
GET/POST /akten/<az>/regulierungen
GET/POST /akten/<az>/dokumente
```

### RA-Micro
```
GET  /ramicro/akte/liste?seite=1        ← Dashboard-Aktenliste (50/Seite)
GET  /ramicro/akte?az=211/26            ← Stammdaten + Beteiligte + WDM
GET  /ramicro/akte/wdm-schaden?az=211/26 ← Schadenpositionen aus WDM
POST /ramicro/akte/on-demand            ← Akte on-demand in SQLite anlegen
GET  /aktensuche?az=211/26             ← Suche nach AZ / Name / kz / tag
GET  /wiedervorlage                     ← Wiedervorlagen aus RA-Micro
```

---

## 7. Frontend-Struktur (App.jsx)

Das gesamte Frontend ist in einer Datei `App.jsx` (~5366 Zeilen). Wichtige Komponenten:

| Funktion | Beschreibung |
|---|---|
| `AppShell` | Hauptlayout: Menü + Tabs + Content |
| `openAkte(baseAkte)` | Öffnet Akte als Tab, ruft on-demand, schneidet SB-Kürzel ab |
| `DashboardView` | Lädt Aktenliste aus RA-Micro, paginiert |
| `AkteDetailView` | Tabs: Übersicht / Schaden / Regulierung / Dokumente / Word |
| `UebersichtSection` | Stammdaten + RA-Micro Kacheln + Positionen-Tabelle |
| `RaMicroAkteUebersicht` | RA-Micro Live-Daten (Beteiligten-Kacheln) |
| `BeteiligterKachel` | Kachel mit Name, Adresse, Tel, Mobil, E-Mail |
| `SchadenSection` | Schadenpositionen + WDM-Auto-Load + Extras-Tabelle |
| `AktenTimeline` | Chronik mit Datum + Uhrzeit |
| `WiedervorlageView` | Wiedervorlagen aus RA-Micro |
| `AktensucheView` | Suche nach AZ / Name / KFZ |
| `KuerzungskatalogSection` | Globaler Kürzungskatalog (im Menü) |

### State-Management
Redux-ähnlicher `useReducer` mit `aktenState`. Key = `akte.az` (String). Wichtige Actions:
- `SET_SCHADEN`, `SAVE_SCHADEN`
- `SET_AKTIVITAETEN`, `PREPEND_AKTIVITAET`
- `SET_STATUS`

### API-Client (api.js)
```javascript
ramicroListe.laden(seite, limit)   // Dashboard
ramicroListe.onDemand(az)          // on-demand SQLite
ramicroWdm.schaden(az)             // WDM Schadenpositionen
apiRaMicroAkte.laden(az)           // Beteiligten-Kacheln
```

---

## 8. Deployment

### Docker-Compose (Produktion)
```powershell
# Build mit Cache-Bust (immer nötig bei Änderungen!)
$env:CACHEBUST = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
docker compose -f docker-compose.prod.yml build --no-cache backend frontend
docker compose -f docker-compose.prod.yml up -d
```

### Initiale Benutzer (automatisch beim ersten Start)
- `koch@anwalt-offenbach.de` / `Kanzlei2024!` (Admin)
- `schatz@anwalt-offenbach.de` / `As155255` (Admin)

### Wichtige .env-Variablen
```env
RAMICRO_AKTIV=true
RAMICRO_HOST=192.168.10.100
RAMICRO_PORT=1433
RAMICRO_DB=RAMICRO
RAMICRO_USER=...
RAMICRO_PASS=...
JWT_SECRET_KEY=...
DB_PATH=/app/data/unfallakten.db
```

### Vite-Proxy (lokale Entwicklung)
Alle Backend-Routen in `vite.config.js` eingetragen: `/auth`, `/akten`, `/email`, `/wiedervorlage`, `/word`, `/health`, `/aktensuche`, `/ramicro`.

---

## 9. Sachbearbeiter-Kürzel

```python
"AS": "Andreas Schatz"      # Rechtsanwalt
"CO": "Claudia Ostarek"     # Rechtsanwältin
"EI": "Elsa Ihl"
"SK": "Sophie Koch"
"SN": "Susanne Neumann"
"TB": "Tanja Brunner"
"PK": "Peter Koch"          # Rechtsanwalt
"CS": "Carina Salvagnin"    # Rechtsanwältin
"MM": "Monika Mieth"        # Rechtsanwältin
"AH": "Alexander Herbert"   # Rechtsanwalt
```

---

## 10. Bekannte offene Punkte / Nächste Schritte

1. **Forderungsschreiben-Textgenerator** — nimmt den höheren Nettowert zwischen `rep_gutachten_netto` und `rep_rechnung_netto`. Logik in `word/forderungsschreiben.py` noch nicht auf neue Felder angepasst.

2. **E-Mail-Import** — Funktioniert (IMAP), UI für Konfiguration vorhanden. Zuordnung zu Akten über Kennzeichen/AZ.

3. **Kürzungskatalog** — globale SQLite-Tabelle `kuerzungsarten`, Endpunkt vorhanden, UI im Menü.

4. **Regulierungsreiter** — vorhanden und funktionsfähig, aber noch nicht mit WDM-Daten verknüpft.

5. **Mock-Daten** — `BASE_AKTEN` und `buildMockState` sind noch im Code (Zeilen 52-114) aber nicht mehr aktiv genutzt (`INITIAL_STATE = {}`). Können bei Gelegenheit entfernt werden.

6. **Backup-Container** — im docker-compose.prod.yml konfiguriert, sichert das SQLite-Volume.

---

## 11. Häufige Probleme & Lösungen

| Problem | Ursache | Lösung |
|---|---|---|
| Vite Build `eof-in-element-that-can-contain-only-text` | SVG/CSS in index.html | CSS in globals.css, Favicon als ICO |
| Backend unhealthy | Route-Parameter `<int:akte_id>` | Alle Routen auf `<path:akte_id>` |
| WDM-Werte = 0 | RA-Micro schreibt `"6.495,48 EUR"` | `_zahl()` entfernt EUR-Suffix |
| Akte nicht gefunden | AZ mit SB-Kürzel übergeben | `_az_basis()` schneidet Kürzel ab |
| Login 500 | v_regulierungsstatus GROUP BY a.id | Migration 7 korrigiert auf a.az |
| Container nicht healthy | wget fehlt in nginx:alpine | curl installiert, HEALTHCHECK auf curl |
